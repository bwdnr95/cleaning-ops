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

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import business_today
from app.domain.constants import OrderStatus, ReceiptType
from app.models.order import Order
from app.models.order_group import OrderGroup
from app.schemas.partner import PartnerCreate
from app.services.dashboard import DashboardService
from app.services.order_page import OrderPageService
from app.services.partner_settlements import PartnerSettlementService
from app.services.partners import PartnerService


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
            partner_payment_amount=partner_payment_amount,
            partner_payment_status=partner_payment_status,
        )
    )
    db.flush()
    return oid


def _partner(db: Session) -> str:
    return PartnerService(db).create(PartnerCreate(name="청소왕", phone="01011112222")).id


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
    _add(db_session, status=OrderStatus.COMPLETED, partner_id=pid, partner_payment_amount=200000)
    _add(
        db_session,
        status=OrderStatus.CANCELLED,
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


# --------------------------------------------------------------------------
# 증빙자료: 카드결제 추가
# --------------------------------------------------------------------------


def test_receipt_type_card_payment_added() -> None:
    assert ReceiptType.CARD_PAYMENT.value == "card_payment"
    assert "card_payment" in {member.value for member in ReceiptType}
