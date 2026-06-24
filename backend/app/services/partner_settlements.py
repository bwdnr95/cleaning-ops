from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.domain.constants import OrderStatus, TimelineEventType
from app.domain.order_metrics import SETTLEABLE_ORDER_STATUSES
from app.domain.order_pricing import order_consumer_total
from app.domain.payment_status import PARTNER_SETTLEMENT_PENDING_STATUSES, PartnerPaymentStatus
from app.models.order import Order
from app.models.order_group import OrderGroup
from app.repositories.order_groups import OrderGroupRepository
from app.repositories.partners import PartnerRepository
from app.schemas.partner import (
    PartnerSettlementActionResult,
    PartnerSettlementItemRead,
    PartnerSettlementListRead,
)
from app.services.timeline import TimelineService

# SETTLEABLE_ORDER_STATUSES 는 domain/order_metrics(단일 출처)에서 import 한다.


def unpaid_partner_condition():
    """미정산 SQL 조건(전 화면 공통).

    정책: '서비스완료'된 작업 중 아직 지급완료가 아닌 건만 미정산으로 본다.
    (완료 전 건은 미정산으로 세지 않는다 → 미정산 목록/합계와 '정산 실행 가능' 집합을 일치시켜
     "미정산인데 정산 버튼 비활성/총액이 안 줄어듦" 문제를 없앤다. 취소건은 COMPLETED 가 아니라 자연 제외.)
    """
    return (Order.status == OrderStatus.COMPLETED) & (
        Order.partner_payment_status.is_(None)
        | Order.partner_payment_status.in_(PARTNER_SETTLEMENT_PENDING_STATUSES)
    )


class PartnerSettlementService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.partners = PartnerRepository(db)
        self.groups = OrderGroupRepository(db)
        self.timeline = TimelineService(db)

    def list_settlements(
        self,
        *,
        partner_id: str,
        status: str = "unpaid",
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> PartnerSettlementListRead:
        self._require_partner(partner_id)
        orders = self._list_orders(
            partner_id=partner_id,
            status=status,
            from_date=from_date,
            to_date=to_date,
        )
        groups_by_id = self.groups.list_by_ids(order.group_id for order in orders)
        # 취소건은 목록(items)에는 남겨 기록을 보존하되, 건수/금액 집계에선 제외한다.
        countable = [order for order in orders if order.status != OrderStatus.CANCELLED]
        total_partner_price = sum(
            (money_decimal(order.partner_payment_amount) for order in countable),
            Decimal("0"),
        )
        total_consumer_price = sum(
            (order_consumer_total(order) for order in countable),
            Decimal("0"),
        )
        items = [
            to_settlement_item(order, group=groups_by_id.get(order.group_id))
            for order in orders
        ]
        return PartnerSettlementListRead(
            items=items,
            total_partner_price=float(total_partner_price),
            total_consumer_price=float(total_consumer_price),
            count=len(countable),
        )

    def settle(
        self,
        *,
        partner_id: str,
        order_ids: list[str],
        actor_user_id: str,
        memo: str | None = None,
    ) -> PartnerSettlementActionResult:
        self._require_partner(partner_id)
        orders = self._lock_orders(
            partner_id=partner_id,
            order_ids=order_ids,
            action="settle",
        )
        now = utc_now()
        for order in orders:
            order.partner_payment_status = PartnerPaymentStatus.PAID
            order.partner_settled_at = now
            self.timeline.record(
                order_id=order.id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.PARTNER_SETTLED,
                title="협력사 정산 완료",
                description=memo,
                metadata={"partner_id": partner_id, "settled_at": now.isoformat()},
            )
        return PartnerSettlementActionResult(
            updated_order_ids=[order.id for order in orders],
            skipped_order_ids=[],
        )

    def revert(
        self,
        *,
        partner_id: str,
        order_ids: list[str],
        actor_user_id: str,
    ) -> PartnerSettlementActionResult:
        self._require_partner(partner_id)
        orders = self._lock_orders(
            partner_id=partner_id,
            order_ids=order_ids,
            action="revert",
        )
        for order in orders:
            order.partner_payment_status = PartnerPaymentStatus.UNPAID
            order.partner_settled_at = None
            self.timeline.record(
                order_id=order.id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.PARTNER_SETTLEMENT_REVERTED,
                title="협력사 정산 되돌리기",
                metadata={"partner_id": partner_id},
            )
        return PartnerSettlementActionResult(
            updated_order_ids=[order.id for order in orders],
            skipped_order_ids=[],
        )

    def _require_partner(self, partner_id: str) -> None:
        partner = self.partners.get(partner_id)
        if partner is None:
            raise ValueError("partner_not_found")
        if not partner.is_active:
            raise ValueError("partner_inactive")

    def _list_orders(
        self,
        *,
        partner_id: str,
        status: str,
        from_date: date | None,
        to_date: date | None,
    ) -> list[Order]:
        stmt = (
            select(Order)
            .where(
                Order.partner_id == partner_id,
                Order.deleted_at.is_(None),
            )
            .order_by(Order.scheduled_date.desc().nulls_last(), Order.id.desc())
        )
        if from_date is not None:
            stmt = stmt.where(Order.scheduled_date >= from_date)
        if to_date is not None:
            stmt = stmt.where(Order.scheduled_date <= to_date)
        if status == "unpaid":
            stmt = stmt.where(unpaid_partner_condition())
        elif status == "paid":
            # 정산완료 이력은 기존대로 서비스완료 주문만 본다.
            stmt = stmt.where(
                Order.status.in_(SETTLEABLE_ORDER_STATUSES),
                Order.partner_payment_status == PartnerPaymentStatus.PAID,
            )
        elif status == "all":
            # '전체'는 이 협력사에 배정된 모든 작업(상태 무관, 취소 포함)을 보여준다.
            # 운영자가 "배정 작업이 있는데 안 뜬다"고 한 문제(완료-미지급만 보이던 것) 해결.
            pass
        else:
            raise ValueError("invalid_settlement_status")
        return list(self.db.scalars(stmt))

    def _lock_orders(self, *, partner_id: str, order_ids: list[str], action: str) -> list[Order]:
        if not order_ids:
            return []
        requested_ids = list(dict.fromkeys(order_ids))
        stmt = (
            select(Order)
            .where(
                Order.id.in_(requested_ids),
                Order.deleted_at.is_(None),
            )
            .with_for_update()
        )
        orders = list(self.db.scalars(stmt))
        by_id = {order.id: order for order in orders}
        if any(order_id not in by_id for order_id in requested_ids):
            raise ValueError("settlement_order_not_found")
        if any(order.partner_id != partner_id for order in orders):
            raise ValueError("settlement_order_partner_mismatch")
        if action == "settle" and any(not is_unpaid_partner_order(order) for order in orders):
            raise ValueError("invalid_settlement_order")
        if action == "revert" and any(not is_revertible_partner_order(order) for order in orders):
            raise ValueError("invalid_settlement_order")
        if action not in {"settle", "revert"}:
            raise ValueError("invalid_settlement_action")
        return [by_id[order_id] for order_id in requested_ids]


def to_settlement_item(
    order: Order, *, group: OrderGroup | None = None
) -> PartnerSettlementItemRead:
    # 정산 확인을 쉽게 하려고 기본주소 + 상세주소까지 모두 노출한다.
    base_address = (group.customer_address if group else None) or order.customer_address or ""
    address_detail = group.customer_address_detail if group else None
    return PartnerSettlementItemRead(
        order_id=order.id,
        status=order.status,
        scheduled_date=order.scheduled_date,
        service_name=order.service_name,
        customer_name=order.customer_name or "",
        address_short=base_address,
        address_detail=address_detail,
        consumer_price=float(order_consumer_total(order)),
        partner_price=float(order.partner_payment_amount or 0),
        partner_payment_status=order.partner_payment_status,
        settled_at=order.partner_settled_at,
    )


def is_unpaid_partner_order(order: Order) -> bool:
    # 정산 '실행(지급완료 처리)' 가드. 가시성(unpaid_partner_condition)과 달리,
    # 미완료 작업을 지급완료로 찍지 못하도록 서비스완료 주문만 허용한다.
    return (
        order.deleted_at is None
        and order.status in SETTLEABLE_ORDER_STATUSES
        and (
            order.partner_payment_status is None
            or order.partner_payment_status in PARTNER_SETTLEMENT_PENDING_STATUSES
        )
    )


def is_revertible_partner_order(order: Order) -> bool:
    return (
        order.deleted_at is None
        and order.status in SETTLEABLE_ORDER_STATUSES
        and order.partner_payment_status == PartnerPaymentStatus.PAID
    )


def money_decimal(value: object) -> Decimal:
    return Decimal(str(value or 0))
