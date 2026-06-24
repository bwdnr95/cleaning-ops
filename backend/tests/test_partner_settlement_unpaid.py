"""미정산 정의 테스트.

정책: '서비스완료'된 작업 중 아직 지급완료가 아닌 건만 미정산으로 본다(완료 전 건은 제외).
미정산 목록/합계와 '정산 실행 가능' 집합을 일치시켜, 미정산으로 보이는데 정산이 안 되는 모순을 없앤다.
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


# ---- is_unpaid_partner_order: 정산 '실행' 가드(서비스완료만 허용) ----

def _order(**over) -> Order:
    base = dict(id="o", status=OrderStatus.COMPLETED, partner_payment_status=None, deleted_at=None)
    base.update(over)
    return Order(**base)


def test_settle_guard_allows_completed_unpaid() -> None:
    assert is_unpaid_partner_order(_order(status=OrderStatus.COMPLETED, partner_payment_status="unpaid"))
    assert is_unpaid_partner_order(_order(status=OrderStatus.COMPLETED, partner_payment_status=None))


def test_settle_guard_rejects_incomplete_even_if_explicit_unpaid() -> None:
    # 가시성은 넓지만, 미완료 작업을 지급완료로 찍는 건 막는다.
    assert not is_unpaid_partner_order(_order(status=OrderStatus.PARTNER_CONFIRMING, partner_payment_status="unpaid"))
    assert not is_unpaid_partner_order(_order(status=OrderStatus.IN_PROGRESS, partner_payment_status=None))


def test_settle_guard_rejects_paid_and_deleted() -> None:
    from datetime import UTC, datetime

    assert not is_unpaid_partner_order(_order(status=OrderStatus.COMPLETED, partner_payment_status="paid"))
    assert not is_unpaid_partner_order(
        _order(status=OrderStatus.COMPLETED, partner_payment_status="unpaid", deleted_at=datetime.now(UTC))
    )


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


def test_unpaid_only_includes_completed_unpaid(db_session: Session) -> None:
    pid = _make_partner(db_session)
    confirming_unpaid = _add_line(db_session, pid, status=OrderStatus.PARTNER_CONFIRMING, pps="unpaid", amount=100000)
    completed_null = _add_line(db_session, pid, status=OrderStatus.COMPLETED, pps=None, amount=200000)
    completed_paid = _add_line(db_session, pid, status=OrderStatus.COMPLETED, pps="paid", amount=300000)
    inprogress_null = _add_line(db_session, pid, status=OrderStatus.IN_PROGRESS, pps=None, amount=400000)

    result = PartnerSettlementService(db_session).list_settlements(partner_id=pid, status="unpaid")
    ids = {item.order_id for item in result.items}

    assert completed_null in ids          # 서비스완료 + 미지급(NULL) 포함
    assert confirming_unpaid not in ids   # 완료 전은 명시적 미지급이어도 제외(정책: 완료건만)
    assert inprogress_null not in ids     # 완료 전 제외
    assert completed_paid not in ids      # 지급완료 제외


def test_unpaid_summary_amount_and_count(db_session: Session) -> None:
    pid = _make_partner(db_session)
    _add_line(db_session, pid, status=OrderStatus.PARTNER_CONFIRMING, pps="unpaid", amount=100000)  # 완료 전 → 제외
    _add_line(db_session, pid, status=OrderStatus.COMPLETED, pps=None, amount=200000)
    _add_line(db_session, pid, status=OrderStatus.COMPLETED, pps="paid", amount=300000)  # 지급완료 → 제외

    detail = PartnerService(db_session).get_detail(pid)
    assert detail.unpaid_partner_order_count == 1  # 완료건만(서비스완료 + 미지급)
    assert detail.unpaid_partner_amount_total == 200000


def test_settle_rejected_before_completion(db_session: Session) -> None:
    # 완료 전 주문은 정산 대상이 아니며 지급완료 처리도 거부한다.
    import pytest

    pid = _make_partner(db_session)
    order_id = _add_line(db_session, pid, status=OrderStatus.PARTNER_CONFIRMING, pps="unpaid", amount=100000)

    with pytest.raises(ValueError, match="invalid_settlement_order"):
        PartnerSettlementService(db_session).settle(
            partner_id=pid, order_ids=[order_id], actor_user_id=None
        )
