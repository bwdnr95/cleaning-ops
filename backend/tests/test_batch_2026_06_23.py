"""2026-06-23 도급사 2차 피드백 회귀 테스트.

검증 대상:
- 대시보드 KPI 카운트 == 클릭 시 진입하는 주문목록 드릴다운 행 수(원본 상태 기준).
- 협력사 정산: '전체'는 배정된 모든 작업 노출, 취소건은 목록엔 남되 건수/금액에서 제외.
- 정산 항목에 상세주소(address_detail) 노출.
- 증빙자료 유형에 card_payment(카드결제) 추가.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.seed import DEV_PARTNER_ID, DEV_PARTNER_USER_ID
from app.core.config import settings
from app.core.time import business_today
from app.domain.constants import (
    MessageChannel,
    MessageStatus,
    MessageType,
    OrderStatus,
    PhotoType,
    ReceiptType,
    RecipientType,
    TimelineEventType,
)
from app.domain.payment_status import PaymentStatus
from app.models.message import MessageLog
from app.models.order import Order
from app.models.order_group import OrderGroup
from app.models.photo import OrderPhoto
from app.repositories.timeline import TimelineRepository
from app.schemas.message import MessageSendRequest
from app.schemas.partner import PartnerCreate
from app.services.dashboard import DashboardService
from app.services.messages import MessageService, customer_balance_due_amount
from app.services.order_page import OrderPageService
from app.services.orders import OrderService
from app.services.partner_settlements import PartnerSettlementService
from app.services.partners import PartnerService
from app.services.photos import PhotoService
from app.services.timeline import TimelineService


def _confirm_order(db: Session, order_id: str) -> None:
    order = db.get(Order, order_id)
    assert order is not None
    order.partner_id = DEV_PARTNER_ID
    TimelineService(db).record(
        order_id=order.id,
        event_type=TimelineEventType.PARTNER_CONFIRMED,
        title="테스트 협력사 확인",
        metadata={"partner_id": DEV_PARTNER_ID},
    )
    db.flush()


def _clean_universe(db: Session) -> None:
    """시드 주문을 soft-delete 해 결정적 카운트 유니버스를 만든다."""
    now = datetime.now(UTC)
    for order in db.scalars(select(Order)):
        order.deleted_at = now
    db.flush()


def _add(
    db: Session,
    *,
    status: str,
    scheduled_date: date | None = None,
    received_date: date | None = None,
    payment_status: str | None = None,
    partner_id: str | None = None,
    partner_payment_status: str | None = None,
    partner_payment_amount: float | None = None,
    total_amount: float | None = None,
    deposit_amount: float | None = None,
    balance_amount: float | None = None,
    address: str = "서울특별시 강남구 테스트로 1",
    address_detail: str | None = None,
) -> str:
    oid = f"o-{uuid4()}"
    gid = f"g-{oid}"
    db.add(
        OrderGroup(
            id=gid,
            customer_token=f"t-{oid}",
            customer_name="홍길동",
            customer_phone="01055556666",
            customer_address=address,
            customer_address_detail=address_detail,
            customer_visible_payment=False,
        )
    )
    db.flush()
    db.add(
        Order(
            id=oid,
            group_id=gid,
            status=status,
            received_date=received_date or date(2026, 6, 1),
            scheduled_date=scheduled_date,
            partner_id=partner_id,
            team_name="검증팀" if partner_id else None,
            service_name="입주청소",
            customer_token=f"t-{oid}",
            customer_name="홍길동",
            customer_phone="01055556666",
            customer_address=address,
            payment_status=payment_status,
            total_amount=total_amount,
            deposit_amount=deposit_amount,
            balance_amount=balance_amount,
            partner_payment_amount=partner_payment_amount,
            partner_payment_status=partner_payment_status,
        )
    )
    db.flush()
    return oid


def _partner(db: Session) -> str:
    return PartnerService(db).create(PartnerCreate(name="청소왕", phone="01011112222")).id


def _message_log(
    db: Session,
    *,
    order_id: str,
    message_type: MessageType,
    status: MessageStatus,
    sent_at: datetime | None = None,
) -> None:
    db.add(
        MessageLog(
            id=str(uuid4()),
            order_id=order_id,
            recipient_type=RecipientType.CUSTOMER,
            recipient_name="홍길동",
            recipient_phone="01055556666",
            message_type=message_type,
            channel=MessageChannel.ALIMTALK,
            content="test",
            status=status,
            requested_at=datetime.now(UTC),
            sent_at=sent_at,
        )
    )
    db.flush()


# --------------------------------------------------------------------------
# 대시보드 KPI == 드릴다운 목록 (원본 상태 기준 일치)
# --------------------------------------------------------------------------


def test_delivery_kpi_matches_drilldown(db_session: Session) -> None:
    _clean_universe(db_session)
    _add(db_session, status=OrderStatus.CUSTOMER_DELIVERY_NEEDED)
    _add(db_session, status=OrderStatus.CUSTOMER_DELIVERY_NEEDED)
    _add(db_session, status=OrderStatus.PHOTO_REVIEW_PENDING)
    _add(db_session, status=OrderStatus.CUSTOMER_DELIVERY_DONE)  # 전달 끝남 → '고객 전달 필요' 아님
    db_session.flush()

    summary = DashboardService(db_session).summary()
    deliver = OrderPageService(db_session).list_page(status="deliver", visit_preset="all", page_size=200)
    photo = OrderPageService(db_session).list_page(status="photo_review", visit_preset="all", page_size=200)

    assert summary.customer_delivery_needed == 2
    assert deliver.total == summary.customer_delivery_needed  # KPI == 목록 행 수
    assert summary.photo_review_pending == 1
    assert photo.total == summary.photo_review_pending
    # 사진검수대기와 고객전달필요 드릴다운은 더 이상 동일 목록이 아니다.
    assert deliver.total != photo.total


def test_tomorrow_notice_kpi_matches_drilldown(db_session: Session) -> None:
    _clean_universe(db_session)
    tomorrow = business_today() + timedelta(days=1)
    _add(db_session, status=OrderStatus.SCHEDULE_CONFIRMED, scheduled_date=tomorrow)
    _add(db_session, status=OrderStatus.DAY_BEFORE_NOTICE_NEEDED, scheduled_date=tomorrow)
    _add(db_session, status=OrderStatus.DAY_BEFORE_NOTICE_DONE, scheduled_date=tomorrow)  # 작업예정 워크플로 → 포함
    _add(db_session, status=OrderStatus.SCHEDULE_CONFIRMED, scheduled_date=business_today())  # 오늘 → 제외
    db_session.flush()

    summary = DashboardService(db_session).summary()
    page = OrderPageService(db_session).list_page(
        status="tomorrow_notice", visit_preset="tomorrow", page_size=200
    )

    # 내일 안내 대상 = 내일 '일정 및 작업 확정'(작업예정 워크플로) 전체 → 3건. KPI == 드릴다운.
    assert summary.tomorrow_notice_targets == 3
    assert page.total == summary.tomorrow_notice_targets


def test_payment_check_excludes_cancelled(db_session: Session) -> None:
    _clean_universe(db_session)
    _add(db_session, status=OrderStatus.IN_PROGRESS, payment_status="unpaid")
    _add(db_session, status=OrderStatus.CANCELLED, payment_status="unpaid")  # 취소 → 제외
    db_session.flush()

    summary = DashboardService(db_session).summary()
    assert summary.payment_check_needed == 1


# --------------------------------------------------------------------------
# 협력사 정산: '전체'=배정 작업 전부, 취소는 목록 유지·집계 제외
# --------------------------------------------------------------------------


def test_cancelled_excluded_from_unpaid_summary(db_session: Session) -> None:
    pid = _partner(db_session)
    _add(
        db_session,
        status=OrderStatus.COMPLETED,
        scheduled_date=business_today(),
        partner_id=pid,
        partner_payment_amount=200000,
    )
    _add(
        db_session,
        status=OrderStatus.CANCELLED,
        scheduled_date=business_today(),
        partner_id=pid,
        partner_payment_status="unpaid",
        partner_payment_amount=500000,
    )
    db_session.flush()

    detail = PartnerService(db_session).get_detail(pid)
    assert detail.unpaid_partner_order_count == 1
    assert detail.unpaid_partner_amount_total == 200000


def test_all_filter_shows_every_assigned_job(db_session: Session) -> None:
    pid = _partner(db_session)
    _add(db_session, status=OrderStatus.IN_PROGRESS, partner_id=pid, partner_payment_amount=100000)
    _add(
        db_session,
        status=OrderStatus.COMPLETED,
        partner_id=pid,
        partner_payment_status="paid",
        partner_payment_amount=200000,
    )
    cancelled = _add(
        db_session,
        status=OrderStatus.CANCELLED,
        partner_id=pid,
        partner_payment_status="unpaid",
        partner_payment_amount=999000,
    )
    db_session.flush()

    result = PartnerSettlementService(db_session).list_settlements(partner_id=pid, status="all")
    ids = {item.order_id for item in result.items}

    # 배정된 모든 작업이 보인다(진행중 포함) — '배정 작업이 안 뜬다' 문제 해결.
    assert len(result.items) == 3
    assert cancelled in ids  # 취소건도 목록엔 남는다(기록 보존)
    # 집계(건수/금액)에선 취소 제외.
    assert result.count == 2
    assert result.total_partner_price == 300000  # 100000 + 200000 (취소 999000 제외)


def test_settlement_item_exposes_full_detail_address(db_session: Session) -> None:
    pid = _partner(db_session)
    _add(
        db_session,
        status=OrderStatus.COMPLETED,
        partner_id=pid,
        partner_payment_amount=100000,
        address="서울특별시 강남구 테스트로 1",
        address_detail="3층 301호",
    )
    db_session.flush()

    result = PartnerSettlementService(db_session).list_settlements(partner_id=pid, status="all")
    item = result.items[0]
    assert item.address_short == "서울특별시 강남구 테스트로 1"
    assert item.address_detail == "3층 301호"


# --------------------------------------------------------------------------
# 미배정(방문일 미정) 주문에 방문일 지정 시 자동 일정확정
# --------------------------------------------------------------------------


def test_assigning_date_auto_confirms_unscheduled_order(db_session: Session) -> None:
    from datetime import date

    from app.schemas.order import OrderUpdate
    from app.services.orders import OrderService

    oid = _add(db_session, status=OrderStatus.CONSULTING, scheduled_date=None)
    db_session.flush()

    OrderService(db_session).update(oid, OrderUpdate(scheduled_date=date(2026, 7, 1)))

    order = db_session.get(Order, oid)
    assert order.status == OrderStatus.SCHEDULE_CONFIRMED  # 방문일 지정 → 자동 일정확정


def test_changing_existing_date_keeps_status(db_session: Session) -> None:
    from datetime import date

    from app.schemas.order import OrderUpdate
    from app.services.orders import OrderService

    # 이미 방문일이 있는(진행 중) 주문은 날짜를 바꿔도 상태가 자동으로 바뀌지 않는다.
    oid = _add(db_session, status=OrderStatus.IN_PROGRESS, scheduled_date=date(2026, 7, 1))
    db_session.flush()

    OrderService(db_session).update(oid, OrderUpdate(scheduled_date=date(2026, 7, 2)))

    order = db_session.get(Order, oid)
    assert order.status == OrderStatus.IN_PROGRESS


def test_explicit_status_overrides_auto_confirm(db_session: Session) -> None:
    from datetime import date

    from app.schemas.order import OrderUpdate
    from app.services.orders import OrderService

    # 같은 요청에서 상태를 직접 지정하면 자동 일정확정이 끼어들지 않는다.
    oid = _add(db_session, status=OrderStatus.CONSULTING, scheduled_date=None)
    db_session.flush()

    OrderService(db_session).update(
        oid, OrderUpdate(scheduled_date=date(2026, 7, 1), status=OrderStatus.PARTNER_CONFIRMING)
    )

    order = db_session.get(Order, oid)
    assert order.status == OrderStatus.PARTNER_CONFIRMING


def test_partner_assignment_auto_message_is_disabled_by_default(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.schemas.order import OrderUpdate

    monkeypatch.setattr(settings, "automation_send_partner_assignment", False)
    pid = _partner(db_session)
    oid = _add(db_session, status=OrderStatus.CONSULTING, scheduled_date=date(2026, 7, 1))
    db_session.flush()

    OrderService(db_session).update(oid, OrderUpdate(partner_id=pid))

    logs = db_session.scalars(select(MessageLog).where(MessageLog.order_id == oid)).all()
    assert logs == []


def test_partner_assignment_auto_message_runs_when_enabled(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.schemas.order import OrderUpdate

    monkeypatch.setattr(settings, "automation_send_partner_assignment", True)
    pid = _partner(db_session)
    oid = _add(db_session, status=OrderStatus.CONSULTING, scheduled_date=date(2026, 7, 1))
    db_session.flush()

    OrderService(db_session).update(oid, OrderUpdate(partner_id=pid))

    logs = db_session.scalars(select(MessageLog).where(MessageLog.order_id == oid)).all()
    assert len(logs) == 1
    assert logs[0].message_type == MessageType.PARTNER_ASSIGNMENT
    assert logs[0].recipient_type == "partner"
    order = db_session.get(Order, oid)
    assert order.status == OrderStatus.PARTNER_CONFIRMING


def test_partner_assignment_auto_message_runs_on_create_when_enabled(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.schemas.order import OrderGroupCreate, OrderLineCreate

    monkeypatch.setattr(settings, "automation_send_partner_assignment", True)
    pid = _partner(db_session)

    group = OrderService(db_session).create_group(
        OrderGroupCreate(
            customer_name="신규고객",
            customer_phone="01044445555",
            customer_address="서울특별시 중구 신규로 1",
            lines=[
                OrderLineCreate(
                    status=OrderStatus.PARTNER_CONFIRMING,
                    received_date=date(2026, 7, 1),
                    scheduled_date=date(2026, 7, 2),
                    partner_id=pid,
                    service_name="입주청소",
                )
            ],
        )
    )

    order = db_session.scalars(select(Order).where(Order.group_id == group.id)).one()
    logs = db_session.scalars(select(MessageLog).where(MessageLog.order_id == order.id)).all()
    assert len(logs) == 1
    assert logs[0].message_type == MessageType.PARTNER_ASSIGNMENT


def test_schedule_confirmed_auto_message_runs_when_enabled(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.schemas.order import OrderUpdate

    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", True)
    oid = _add(db_session, status=OrderStatus.CONSULTING, scheduled_date=None)
    _confirm_order(db_session, oid)
    db_session.flush()

    OrderService(db_session).update(oid, OrderUpdate(scheduled_date=date(2026, 7, 1)))

    logs = db_session.scalars(select(MessageLog).where(MessageLog.order_id == oid)).all()
    assert len(logs) == 1
    assert logs[0].message_type == MessageType.CUSTOMER_SCHEDULE_CONFIRMED


def test_schedule_confirmed_auto_message_runs_on_create_when_enabled(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.schemas.order import OrderGroupCreate, OrderLineCreate

    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", True)

    group = OrderService(db_session).create_group(
        OrderGroupCreate(
            customer_name="일정확정고객",
            customer_phone="01055557777",
            customer_address="서울특별시 중구 일정로 1",
            lines=[
                OrderLineCreate(
                    status=OrderStatus.SCHEDULE_CONFIRMED,
                    received_date=date(2026, 7, 1),
                    scheduled_date=date(2026, 7, 2),
                    service_name="입주청소",
                )
            ],
        )
    )

    order = db_session.scalars(select(Order).where(Order.group_id == group.id)).one()
    logs = db_session.scalars(select(MessageLog).where(MessageLog.order_id == order.id)).all()
    assert logs == []


def test_schedule_confirmed_auto_message_respects_disabled_setting(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.schemas.order import OrderGroupCreate, OrderLineCreate

    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", False)

    group = OrderService(db_session).create_group(
        OrderGroupCreate(
            customer_name="일정확정고객",
            customer_phone="01055557777",
            customer_address="서울특별시 중구 일정로 1",
            lines=[
                OrderLineCreate(
                    status=OrderStatus.SCHEDULE_CONFIRMED,
                    received_date=date(2026, 7, 1),
                    scheduled_date=date(2026, 7, 2),
                    service_name="입주청소",
                )
            ],
        )
    )

    order = db_session.scalars(select(Order).where(Order.group_id == group.id)).one()
    logs = db_session.scalars(select(MessageLog).where(MessageLog.order_id == order.id)).all()
    assert logs == []


def test_schedule_confirmed_auto_message_requires_scheduled_date(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.schemas.order import OrderGroupCreate, OrderLineCreate

    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", True)

    group = OrderService(db_session).create_group(
        OrderGroupCreate(
            customer_name="일정확정고객",
            customer_phone="01055557777",
            customer_address="서울특별시 중구 일정로 1",
            lines=[
                OrderLineCreate(
                    status=OrderStatus.SCHEDULE_CONFIRMED,
                    received_date=date(2026, 7, 1),
                    scheduled_date=None,
                    service_name="입주청소",
                )
            ],
        )
    )

    order = db_session.scalars(select(Order).where(Order.group_id == group.id)).one()
    logs = db_session.scalars(select(MessageLog).where(MessageLog.order_id == order.id)).all()
    assert logs == []


def test_schedule_confirmed_auto_message_requires_schedule_confirmed_status(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.schemas.order import OrderGroupCreate, OrderLineCreate

    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", True)

    group = OrderService(db_session).create_group(
        OrderGroupCreate(
            customer_name="상담고객",
            customer_phone="01055557777",
            customer_address="서울특별시 중구 일정로 1",
            lines=[
                OrderLineCreate(
                    status=OrderStatus.CONSULTING,
                    received_date=date(2026, 7, 1),
                    scheduled_date=date(2026, 7, 2),
                    service_name="입주청소",
                )
            ],
        )
    )

    order = db_session.scalars(select(Order).where(Order.group_id == group.id)).one()
    logs = db_session.scalars(select(MessageLog).where(MessageLog.order_id == order.id)).all()
    assert logs == []


def test_schedule_confirmed_auto_message_runs_on_explicit_status_update_when_enabled(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.schemas.order import OrderUpdate

    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", True)
    oid = _add(db_session, status=OrderStatus.CONSULTING, scheduled_date=None)
    _confirm_order(db_session, oid)
    db_session.flush()

    OrderService(db_session).update(
        oid,
        OrderUpdate(status=OrderStatus.SCHEDULE_CONFIRMED, scheduled_date=date(2026, 7, 1)),
    )

    logs = db_session.scalars(select(MessageLog).where(MessageLog.order_id == oid)).all()
    assert len(logs) == 1
    assert logs[0].message_type == MessageType.CUSTOMER_SCHEDULE_CONFIRMED


def test_schedule_confirmed_auto_message_skips_pending_attempt(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.schemas.order import OrderUpdate

    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", True)
    oid = _add(
        db_session,
        status=OrderStatus.SCHEDULE_CONFIRMED,
        scheduled_date=date(2026, 7, 1),
    )
    _message_log(
        db_session,
        order_id=oid,
        message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
        status=MessageStatus.PENDING,
    )

    OrderService(db_session).update(oid, OrderUpdate(scheduled_date=date(2026, 7, 2)))

    logs = db_session.scalars(
        select(MessageLog).where(
            MessageLog.order_id == oid,
            MessageLog.message_type == MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
        )
    ).all()
    assert len(logs) == 1
    assert logs[0].status == MessageStatus.PENDING


def test_schedule_confirmed_auto_message_skips_success_without_sent_at(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.schemas.order import OrderUpdate

    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", True)
    oid = _add(
        db_session,
        status=OrderStatus.SCHEDULE_CONFIRMED,
        scheduled_date=date(2026, 7, 1),
    )
    _message_log(
        db_session,
        order_id=oid,
        message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
        status=MessageStatus.SENT,
        sent_at=None,
    )

    OrderService(db_session).update(oid, OrderUpdate(scheduled_date=date(2026, 7, 2)))

    logs = db_session.scalars(
        select(MessageLog).where(
            MessageLog.order_id == oid,
            MessageLog.message_type == MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
        )
    ).all()
    assert len(logs) == 1
    assert logs[0].status == MessageStatus.SENT
    assert logs[0].sent_at is None


def test_schedule_confirmed_auto_message_does_not_send_twice(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.schemas.order import OrderUpdate

    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", True)
    oid = _add(db_session, status=OrderStatus.CONSULTING, scheduled_date=None)
    _confirm_order(db_session, oid)
    db_session.flush()

    service = OrderService(db_session)
    service.update(
        oid,
        OrderUpdate(status=OrderStatus.SCHEDULE_CONFIRMED, scheduled_date=date(2026, 7, 1)),
    )
    service.update(oid, OrderUpdate(scheduled_date=date(2026, 7, 2)))

    logs = db_session.scalars(select(MessageLog).where(MessageLog.order_id == oid)).all()
    assert len(logs) == 1
    assert logs[0].message_type == MessageType.CUSTOMER_SCHEDULE_CONFIRMED


def test_day_before_notice_batch_sends_once_for_default_target(db_session: Session) -> None:
    from app.services.messages import MessageService

    _clean_universe(db_session)
    tomorrow = business_today() + timedelta(days=1)
    target_id = _add(
        db_session,
        status=OrderStatus.SCHEDULE_CONFIRMED,
        scheduled_date=tomorrow,
    )
    _confirm_order(db_session, target_id)
    already_sent_id = _add(
        db_session,
        status=OrderStatus.DAY_BEFORE_NOTICE_NEEDED,
        scheduled_date=tomorrow,
    )
    _confirm_order(db_session, already_sent_id)
    _add(
        db_session,
        status=OrderStatus.DAY_BEFORE_NOTICE_DONE,
        scheduled_date=tomorrow,
    )
    _add(
        db_session,
        status=OrderStatus.SCHEDULE_CONFIRMED,
        scheduled_date=tomorrow + timedelta(days=1),
    )
    db_session.add(
        MessageLog(
            id=str(uuid4()),
            order_id=already_sent_id,
            recipient_type=RecipientType.CUSTOMER,
            recipient_name="홍길동",
            recipient_phone="01055556666",
            message_type=MessageType.CUSTOMER_DAY_BEFORE,
            channel=MessageChannel.SMS,
            content="already sent",
            status=MessageStatus.SENT,
            provider="mock",
            requested_at=datetime.now(UTC),
            sent_at=datetime.now(UTC),
        )
    )
    db_session.flush()

    result = MessageService(db_session).send_day_before_notices(target_date=tomorrow)

    assert result.scanned == 2
    assert result.sent == 1
    assert result.skipped_already_sent == 1
    assert result.failed == 0
    assert result.sent_order_ids == [target_id]
    sent_logs = db_session.scalars(
        select(MessageLog).where(
            MessageLog.order_id == target_id,
            MessageLog.message_type == MessageType.CUSTOMER_DAY_BEFORE,
        )
    ).all()
    assert len(sent_logs) == 1
    assert db_session.get(Order, target_id).status == OrderStatus.DAY_BEFORE_NOTICE_DONE
    assert db_session.get(Order, already_sent_id).status == OrderStatus.DAY_BEFORE_NOTICE_DONE


SIGNATURE_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def test_customer_balance_due_auto_message_runs_after_partner_completion(
    db_session: Session,
) -> None:
    pid = _partner(db_session)
    oid = _add(
        db_session,
        status=OrderStatus.IN_PROGRESS,
        scheduled_date=date(2026, 7, 1),
        partner_id=pid,
        payment_status=PaymentStatus.BALANCE_PENDING,
        balance_amount=50000,
    )
    db_session.add(
        OrderPhoto(
            id=f"p-before-{oid}",
            order_id=oid,
            uploaded_by_user_id=DEV_PARTNER_USER_ID,
            photo_type=PhotoType.BEFORE,
            file_url="https://cdn.example.com/before.jpg",
            file_name="before.jpg",
            is_customer_visible=True,
        )
    )
    db_session.add(
        OrderPhoto(
            id=f"p-after-{oid}",
            order_id=oid,
            uploaded_by_user_id=DEV_PARTNER_USER_ID,
            photo_type=PhotoType.AFTER,
            file_url="https://cdn.example.com/after.jpg",
            file_name="after.jpg",
            is_customer_visible=True,
        )
    )
    db_session.flush()

    OrderService(db_session).complete_partner_job(
        oid,
        actor_user_id=DEV_PARTNER_USER_ID,
        partner_id=pid,
        customer_signature_data_url=SIGNATURE_DATA_URL,
    )

    logs = db_session.scalars(select(MessageLog).where(MessageLog.order_id == oid)).all()
    assert len(logs) == 1
    assert logs[0].message_type == MessageType.CUSTOMER_BALANCE_DUE
    order = db_session.get(Order, oid)
    assert order.status == OrderStatus.CUSTOMER_DELIVERY_NEEDED
    assert order.work_completed_at is not None
    assert order.customer_signature_file_url is not None


def test_customer_balance_due_auto_message_skips_paid_partner_completion(
    db_session: Session,
) -> None:
    pid = _partner(db_session)
    oid = _add(
        db_session,
        status=OrderStatus.IN_PROGRESS,
        scheduled_date=date(2026, 7, 1),
        partner_id=pid,
        payment_status=PaymentStatus.PAID,
        balance_amount=0,
        total_amount=100000,
    )
    for photo_type in (PhotoType.BEFORE, PhotoType.AFTER):
        db_session.add(
            OrderPhoto(
                id=f"p-{photo_type}-{oid}",
                order_id=oid,
                uploaded_by_user_id=DEV_PARTNER_USER_ID,
                photo_type=photo_type,
                file_url=f"https://cdn.example.com/{photo_type}.jpg",
                file_name=f"{photo_type}.jpg",
                is_customer_visible=True,
            )
        )
    db_session.flush()

    OrderService(db_session).complete_partner_job(
        oid,
        actor_user_id=DEV_PARTNER_USER_ID,
        partner_id=pid,
        customer_signature_data_url=SIGNATURE_DATA_URL,
    )

    logs = db_session.scalars(select(MessageLog).where(MessageLog.order_id == oid)).all()
    assert all(log.message_type != MessageType.CUSTOMER_BALANCE_DUE for log in logs)
    assert db_session.get(Order, oid).status == OrderStatus.CUSTOMER_DELIVERY_NEEDED


def test_customer_balance_due_auto_message_skips_zero_balance_partner_completion(
    db_session: Session,
) -> None:
    pid = _partner(db_session)
    oid = _add(
        db_session,
        status=OrderStatus.IN_PROGRESS,
        scheduled_date=date(2026, 7, 1),
        partner_id=pid,
        payment_status=PaymentStatus.DEPOSIT_PAID,
        balance_amount=0,
        total_amount=100000,
    )
    for photo_type in (PhotoType.BEFORE, PhotoType.AFTER):
        db_session.add(
            OrderPhoto(
                id=f"p-zero-{photo_type}-{oid}",
                order_id=oid,
                uploaded_by_user_id=DEV_PARTNER_USER_ID,
                photo_type=photo_type,
                file_url=f"https://cdn.example.com/zero-{photo_type}.jpg",
                file_name=f"zero-{photo_type}.jpg",
                is_customer_visible=True,
            )
        )
    db_session.flush()

    OrderService(db_session).complete_partner_job(
        oid,
        actor_user_id=DEV_PARTNER_USER_ID,
        partner_id=pid,
        customer_signature_data_url=SIGNATURE_DATA_URL,
    )

    logs = db_session.scalars(select(MessageLog).where(MessageLog.order_id == oid)).all()
    assert all(log.message_type != MessageType.CUSTOMER_BALANCE_DUE for log in logs)


def test_customer_balance_due_manual_send_requires_positive_due(db_session: Session) -> None:
    oid = _add(
        db_session,
        status=OrderStatus.CUSTOMER_DELIVERY_NEEDED,
        scheduled_date=date(2026, 7, 1),
        payment_status=PaymentStatus.DEPOSIT_PAID,
        total_amount=100000,
        deposit_amount=100000,
        balance_amount=None,
    )
    order = db_session.get(Order, oid)
    assert customer_balance_due_amount(order) == 0

    payload = MessageSendRequest(
        order_id=oid,
        message_type=MessageType.CUSTOMER_BALANCE_DUE,
        recipient_type=RecipientType.CUSTOMER,
    )
    with pytest.raises(ValueError, match="customer_balance_not_due"):
        MessageService(db_session).preview(payload)
    with pytest.raises(ValueError, match="customer_balance_not_due"):
        MessageService(db_session).send(payload, actor_user_id=DEV_PARTNER_USER_ID)


def test_customer_balance_due_manual_preview_uses_total_minus_deposit(db_session: Session) -> None:
    oid = _add(
        db_session,
        status=OrderStatus.CUSTOMER_DELIVERY_NEEDED,
        scheduled_date=date(2026, 7, 1),
        payment_status=PaymentStatus.DEPOSIT_PAID,
        total_amount=100000,
        deposit_amount=30000,
        balance_amount=None,
    )
    order = db_session.get(Order, oid)
    assert order is not None
    order.work_completed_at = datetime.now(UTC)
    db_session.flush()

    preview = MessageService(db_session).preview(
        MessageSendRequest(
            order_id=oid,
            message_type=MessageType.CUSTOMER_BALANCE_DUE,
            recipient_type=RecipientType.CUSTOMER,
        )
    )

    assert "잔금: 70,000원" in preview.content


def test_customer_balance_due_preview_does_not_duplicate_honorific(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "solapi_kakao_template_customer_balance_due", "KA_BALANCE")
    oid = _add(
        db_session,
        status=OrderStatus.CUSTOMER_DELIVERY_NEEDED,
        scheduled_date=date(2026, 7, 1),
        payment_status=PaymentStatus.DEPOSIT_PAID,
        total_amount=100000,
        deposit_amount=30000,
    )
    order = db_session.get(Order, oid)
    assert order is not None
    order.work_completed_at = datetime.now(UTC)
    order.customer_name = "우리인테리어 현순철 대표님"
    db_session.flush()

    preview = MessageService(db_session).preview(
        MessageSendRequest(
            order_id=oid,
            message_type=MessageType.CUSTOMER_BALANCE_DUE,
            recipient_type=RecipientType.CUSTOMER,
            channel=MessageChannel.ALIMTALK,
        )
    )

    assert "대표님님" not in preview.content
    assert "[클린잡] 우리인테리어 현순철 대표님," in preview.content
    assert preview.kakao_variables is not None
    assert preview.kakao_variables["#{고객명}"] == "우리인테리어 현순철 대표"


def test_partner_assignment_message_link_opens_assigned_job(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "frontend_url", "https://ops.example.com")
    pid = _partner(db_session)
    oid = _add(
        db_session,
        status=OrderStatus.PARTNER_CONFIRMING,
        scheduled_date=date(2026, 7, 1),
        partner_id=pid,
    )

    preview = MessageService(db_session).preview(
        MessageSendRequest(
            order_id=oid,
            message_type=MessageType.PARTNER_ASSIGNMENT,
            recipient_type=RecipientType.PARTNER,
            channel=MessageChannel.ALIMTALK,
        )
    )

    assert f"https://ops.example.com/partner?job={oid}" in preview.content
    assert preview.kakao_variables["#{협력사링크}"] == f"ops.example.com/partner?job={oid}"


def test_as_messages_require_stateful_as_request(db_session: Session) -> None:
    pid = _partner(db_session)
    oid = _add(
        db_session,
        status=OrderStatus.COMPLETED,
        scheduled_date=date(2026, 7, 1),
        partner_id=pid,
        payment_status=PaymentStatus.PAID,
    )
    payload = MessageSendRequest(
        order_id=oid,
        message_type=MessageType.PARTNER_AS_REQUEST,
        recipient_type=RecipientType.PARTNER,
    )
    with pytest.raises(ValueError, match="as_request_required"):
        MessageService(db_session).preview(payload)
    with pytest.raises(ValueError, match="as_request_required"):
        MessageService(db_session).send(payload, actor_user_id=DEV_PARTNER_USER_ID)

    OrderService(db_session).request_as(
        oid,
        memo="욕실 코너 AS 요청",
        actor_user_id=DEV_PARTNER_USER_ID,
    )

    preview = MessageService(db_session).preview(payload)
    assert "AS(재작업) 요청" in preview.content


def test_as_job_can_restart_and_complete_to_final_when_paid(db_session: Session) -> None:
    pid = _partner(db_session)
    oid = _add(
        db_session,
        status=OrderStatus.COMPLETED,
        scheduled_date=date(2026, 7, 1),
        partner_id=pid,
        payment_status=PaymentStatus.PAID,
        balance_amount=0,
    )
    old_photo_time = datetime(2026, 6, 30, 9, 0, tzinfo=UTC)
    for photo_type in (PhotoType.BEFORE, PhotoType.AFTER):
        db_session.add(
            OrderPhoto(
                id=f"p-old-{photo_type}-{oid}",
                order_id=oid,
                uploaded_by_user_id=DEV_PARTNER_USER_ID,
                photo_type=photo_type,
                file_url=f"https://cdn.example.com/old-{photo_type}.jpg",
                file_name=f"old-{photo_type}.jpg",
                is_customer_visible=True,
                created_at=old_photo_time,
            )
        )
    db_session.flush()

    OrderService(db_session).request_as(
        oid,
        memo="AS 재방문 필요",
        actor_user_id=DEV_PARTNER_USER_ID,
    )
    as_requested_at = TimelineRepository(db_session).latest_created_at(
        order_id=oid,
        event_type=TimelineEventType.AS_REQUESTED,
    )
    assert as_requested_at is not None
    assert db_session.get(Order, oid).status == OrderStatus.CUSTOMER_CHECK_NEEDED

    with pytest.raises(ValueError, match="before_photo_required_for_start"):
        OrderService(db_session).start_partner_job(
            oid,
            actor_user_id=DEV_PARTNER_USER_ID,
            partner_id=pid,
        )

    new_photo_time = as_requested_at + timedelta(seconds=1)
    db_session.add(
        OrderPhoto(
            id=f"p-as-before-{oid}",
            order_id=oid,
            uploaded_by_user_id=DEV_PARTNER_USER_ID,
            photo_type=PhotoType.BEFORE,
            file_url="https://cdn.example.com/as-before.jpg",
            file_name="as-before.jpg",
            is_customer_visible=True,
            created_at=new_photo_time,
        )
    )
    db_session.flush()

    started = OrderService(db_session).start_partner_job(
        oid,
        actor_user_id=DEV_PARTNER_USER_ID,
        partner_id=pid,
    )
    assert started.status == OrderStatus.IN_PROGRESS
    assert started.work_started_at is not None

    with pytest.raises(ValueError, match="completion_evidence_required"):
        OrderService(db_session).complete_partner_job(
            oid,
            actor_user_id=DEV_PARTNER_USER_ID,
            partner_id=pid,
            customer_signature_data_url=SIGNATURE_DATA_URL,
        )

    db_session.add(
        OrderPhoto(
            id=f"p-as-after-{oid}",
            order_id=oid,
            uploaded_by_user_id=DEV_PARTNER_USER_ID,
            photo_type=PhotoType.AFTER,
            file_url="https://cdn.example.com/as-after.jpg",
            file_name="as-after.jpg",
            is_customer_visible=True,
            created_at=new_photo_time,
        )
    )
    db_session.flush()

    completed = OrderService(db_session).complete_partner_job(
        oid,
        actor_user_id=DEV_PARTNER_USER_ID,
        partner_id=pid,
        customer_signature_data_url=SIGNATURE_DATA_URL,
    )

    assert completed.status == OrderStatus.COMPLETED
    assert completed.as_requested is False
    logs = db_session.scalars(select(MessageLog).where(MessageLog.order_id == oid)).all()
    assert all(log.message_type != MessageType.CUSTOMER_BALANCE_DUE for log in logs)


def test_as_photo_ready_evidence_ignores_old_photos_after_revoke(db_session: Session) -> None:
    pid = _partner(db_session)
    oid = _add(
        db_session,
        status=OrderStatus.COMPLETED,
        scheduled_date=date(2026, 7, 1),
        partner_id=pid,
        payment_status=PaymentStatus.DEPOSIT_PAID,
        balance_amount=50000,
    )
    old_photo_time = datetime(2026, 6, 30, 9, 0, tzinfo=UTC)
    for photo_type in (PhotoType.BEFORE, PhotoType.AFTER):
        db_session.add(
            OrderPhoto(
                id=f"p-old-as-gate-{photo_type}-{oid}",
                order_id=oid,
                uploaded_by_user_id=DEV_PARTNER_USER_ID,
                photo_type=photo_type,
                file_url=f"https://cdn.example.com/old-as-gate-{photo_type}.jpg",
                file_name=f"old-as-gate-{photo_type}.jpg",
                is_customer_visible=True,
                created_at=old_photo_time,
            )
        )
    db_session.flush()

    OrderService(db_session).request_as(
        oid,
        memo="AS 재방문 필요",
        actor_user_id=DEV_PARTNER_USER_ID,
    )
    as_requested_at = TimelineRepository(db_session).latest_created_at(
        order_id=oid,
        event_type=TimelineEventType.AS_REQUESTED,
    )
    assert as_requested_at is not None
    new_photo_time = as_requested_at + timedelta(seconds=1)
    for photo_type in (PhotoType.BEFORE, PhotoType.AFTER):
        db_session.add(
            OrderPhoto(
                id=f"p-new-as-gate-{photo_type}-{oid}",
                order_id=oid,
                uploaded_by_user_id=DEV_PARTNER_USER_ID,
                photo_type=photo_type,
                file_url=f"https://cdn.example.com/new-as-gate-{photo_type}.jpg",
                file_name=f"new-as-gate-{photo_type}.jpg",
                is_customer_visible=True,
                created_at=new_photo_time,
            )
        )
    db_session.flush()

    OrderService(db_session).start_partner_job(
        oid,
        actor_user_id=DEV_PARTNER_USER_ID,
        partner_id=pid,
    )
    completed = OrderService(db_session).complete_partner_job(
        oid,
        actor_user_id=DEV_PARTNER_USER_ID,
        partner_id=pid,
        customer_signature_data_url=SIGNATURE_DATA_URL,
    )
    assert completed.status == OrderStatus.CUSTOMER_DELIVERY_NEEDED

    PhotoService(db_session).revoke_visibility(
        f"p-new-as-gate-{PhotoType.AFTER}-{oid}",
        actor_user_id=DEV_PARTNER_USER_ID,
    )
    order = db_session.get(Order, oid)
    assert order is not None
    assert order.status == OrderStatus.IN_PROGRESS

    with pytest.raises(ValueError, match="customer_photo_ready_not_allowed"):
        MessageService(db_session).send(
            MessageSendRequest(
                order_id=oid,
                message_type=MessageType.CUSTOMER_PHOTO_READY,
                recipient_type=RecipientType.CUSTOMER,
            ),
            actor_user_id=DEV_PARTNER_USER_ID,
        )


# --------------------------------------------------------------------------
# 증빙자료: 카드결제 추가
# --------------------------------------------------------------------------


def test_receipt_type_card_payment_added() -> None:
    assert ReceiptType.CARD_PAYMENT.value == "card_payment"
    assert "card_payment" in {member.value for member in ReceiptType}
