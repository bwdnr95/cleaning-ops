"""미정산 정의 테스트.

1-1 정책: '서비스완료' 요건 없이, 취소가 아니고 도급가(partner_payment_amount)가 0보다 크며
아직 지급완료가 아닌 주문을 미정산으로 본다. 미정산 목록/합계/정산 실행 가능 집합 + 프론트
canSettle(>0)까지 일치시킨다. 도급가 미입력(NULL·0)은 정산할 게 없어 제외한다.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.domain.constants import OrderStatus
from app.models.order import Order
from app.repositories.order_groups import OrderGroupRepository
from app.schemas.order import OrderGroupCreate, OrderLineCreate
from app.schemas.partner import PartnerCreate
from app.services.partner_settlements import (
    PartnerSettlementService,
    is_unpaid_partner_order,
)
from app.services.orders import OrderService
from app.services.partners import PartnerService


# ---- is_unpaid_partner_order: 정산 '실행' 가드(도급가>0 + 미지급 + 취소 아님) ----

def _order(**over) -> Order:
    # 기본값에 도급가 > 0 을 둔다(1-1: 금액 없는 건은 미정산이 아니다).
    base = dict(
        id="o",
        status=OrderStatus.COMPLETED,
        partner_payment_status=None,
        partner_payment_amount=100000,
        deleted_at=None,
    )
    base.update(over)
    return Order(**base)


def test_settle_guard_allows_any_noncancelled_with_amount() -> None:
    # 완료 여부와 무관하게 도급가>0 + 미지급이면 정산 가능.
    assert is_unpaid_partner_order(_order(status=OrderStatus.COMPLETED, partner_payment_status="unpaid"))
    assert is_unpaid_partner_order(_order(status=OrderStatus.COMPLETED, partner_payment_status=None))
    assert is_unpaid_partner_order(_order(status=OrderStatus.PARTNER_CONFIRMING, partner_payment_status="unpaid"))
    assert is_unpaid_partner_order(_order(status=OrderStatus.IN_PROGRESS, partner_payment_status=None))


def test_settle_guard_requires_positive_amount() -> None:
    # 도급가 미입력(NULL·0)은 정산할 게 없어 제외.
    assert not is_unpaid_partner_order(_order(partner_payment_amount=None))
    assert not is_unpaid_partner_order(_order(partner_payment_amount=0))


def test_settle_guard_rejects_paid_deleted_cancelled() -> None:
    from datetime import UTC, datetime

    assert not is_unpaid_partner_order(_order(partner_payment_status="paid"))
    assert not is_unpaid_partner_order(_order(deleted_at=datetime.now(UTC)))
    assert not is_unpaid_partner_order(_order(status=OrderStatus.CANCELLED))


# ---- 통합: 협력사 정산 목록 + 미정산 합계 ----

def _make_partner(db: Session) -> str:
    return PartnerService(db).create(PartnerCreate(name="청소왕", phone="01011112222")).id


def _add_line(db: Session, partner_id: str, *, status, pps, amount) -> str:
    osvc = OrderService(db)
    group = osvc.create_group(
        OrderGroupCreate(
            customer_name="홍길동",
            customer_phone="01055556666",
            customer_address="서울특별시 강남구 테스트로 1",
            lines=[
                OrderLineCreate(
                    status=status,
                    received_date=date(2026, 6, 1),
                    service_name="입주청소",
                    partner_id=partner_id,
                    partner_payment_amount=amount,
                    partner_payment_status=pps,
                )
            ],
        )
    )
    return OrderGroupRepository(db).list_lines(group.id)[0].id


def test_unpaid_includes_any_noncancelled_with_amount(db_session: Session) -> None:
    pid = _make_partner(db_session)
    confirming_unpaid = _add_line(db_session, pid, status=OrderStatus.PARTNER_CONFIRMING, pps="unpaid", amount=100000)
    completed_null = _add_line(db_session, pid, status=OrderStatus.COMPLETED, pps=None, amount=200000)
    completed_paid = _add_line(db_session, pid, status=OrderStatus.COMPLETED, pps="paid", amount=300000)
    inprogress_null = _add_line(db_session, pid, status=OrderStatus.IN_PROGRESS, pps=None, amount=400000)
    completed_no_amount = _add_line(db_session, pid, status=OrderStatus.COMPLETED, pps=None, amount=None)

    result = PartnerSettlementService(db_session).list_settlements(partner_id=pid, status="unpaid")
    ids = {item.order_id for item in result.items}

    assert confirming_unpaid in ids       # 완료 전이어도 도급가>0 + 미지급이면 포함(1-1)
    assert completed_null in ids
    assert inprogress_null in ids
    assert completed_paid not in ids      # 지급완료 제외
    assert completed_no_amount not in ids  # 도급가 없음 제외


def test_unpaid_summary_amount_and_count(db_session: Session) -> None:
    pid = _make_partner(db_session)
    _add_line(db_session, pid, status=OrderStatus.PARTNER_CONFIRMING, pps="unpaid", amount=100000)  # 포함(1-1)
    _add_line(db_session, pid, status=OrderStatus.COMPLETED, pps=None, amount=200000)               # 포함
    _add_line(db_session, pid, status=OrderStatus.COMPLETED, pps="paid", amount=300000)             # 지급완료 → 제외

    detail = PartnerService(db_session).get_detail(pid)
    assert detail.unpaid_partner_order_count == 2  # 도급가>0 + 미지급(완료 여부 무관)
    assert detail.unpaid_partner_amount_total == 300000  # 100000 + 200000


def test_unpaid_list_with_date_range_keeps_undated(db_session: Session) -> None:
    """A: 방문일 미정(scheduled_date NULL) 미정산 건은 날짜 범위 조회에서도 목록에 남아야 한다.

    기존엔 `scheduled_date >= from AND <= to` 가 NULL 을 무조건 탈락시켜, 날짜와 무관한
    미정산 합계/배지(전체)와 날짜로 거르는 목록이 어긋났다(전체 5건 vs 목록 4건).
    """
    from app.models.order import Order as OrderModel

    pid = _make_partner(db_session)
    undated = _add_line(db_session, pid, status=OrderStatus.CONSULTING, pps=None, amount=330000)
    in_range = _add_line(db_session, pid, status=OrderStatus.COMPLETED, pps=None, amount=100000)
    out_range = _add_line(db_session, pid, status=OrderStatus.COMPLETED, pps=None, amount=200000)
    db_session.get(OrderModel, undated).scheduled_date = None
    db_session.get(OrderModel, in_range).scheduled_date = date(2026, 6, 15)
    db_session.get(OrderModel, out_range).scheduled_date = date(2020, 1, 1)
    db_session.flush()

    result = PartnerSettlementService(db_session).list_settlements(
        partner_id=pid,
        status="unpaid",
        from_date=date(2026, 6, 1),
        to_date=date(2026, 6, 30),
    )
    ids = {item.order_id for item in result.items}
    assert undated in ids       # A: 방문일 미정도 목록에 남는다
    assert in_range in ids       # 범위 안은 포함
    assert out_range not in ids  # 범위 밖(실제 날짜)은 여전히 제외
    assert result.count == 2
    assert result.total_partner_price == 430000  # 330000 + 100000


def test_settle_allowed_before_completion(db_session: Session) -> None:
    # 1-1: 완료 전 주문도 도급가>0면 정산 실행이 가능하다.
    pid = _make_partner(db_session)
    order_id = _add_line(db_session, pid, status=OrderStatus.PARTNER_CONFIRMING, pps="unpaid", amount=100000)

    result = PartnerSettlementService(db_session).settle(
        partner_id=pid, order_ids=[order_id], actor_user_id=None
    )
    assert order_id in result.updated_order_ids


def test_settle_rejected_without_amount(db_session: Session) -> None:
    # 도급가 미입력 건은 정산 대상이 아니라 거부한다.
    import pytest

    pid = _make_partner(db_session)
    order_id = _add_line(db_session, pid, status=OrderStatus.COMPLETED, pps=None, amount=None)

    with pytest.raises(ValueError, match="invalid_settlement_order"):
        PartnerSettlementService(db_session).settle(
            partner_id=pid, order_ids=[order_id], actor_user_id=None
        )
