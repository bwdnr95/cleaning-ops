from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.domain.constants import OrderStatus, TimelineEventType
from app.domain.payment_status import PARTNER_SETTLEMENT_PENDING_STATUSES, PartnerPaymentStatus
from app.models.order import Order
from app.repositories.partners import PartnerRepository
from app.schemas.partner import (
    PartnerSettlementActionResult,
    PartnerSettlementItemRead,
    PartnerSettlementListRead,
)
from app.services.timeline import TimelineService

SETTLEABLE_ORDER_STATUSES = (OrderStatus.COMPLETED,)


class PartnerSettlementService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.partners = PartnerRepository(db)
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
        total_partner_price = sum(
            (money_decimal(order.partner_payment_amount) for order in orders),
            Decimal("0"),
        )
        total_consumer_price = sum(
            (money_decimal(order.total_amount) for order in orders),
            Decimal("0"),
        )
        items = [to_settlement_item(order) for order in orders]
        return PartnerSettlementListRead(
            items=items,
            total_partner_price=float(total_partner_price),
            total_consumer_price=float(total_consumer_price),
            count=len(items),
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
                Order.status.in_(SETTLEABLE_ORDER_STATUSES),
            )
            .order_by(Order.scheduled_date.desc().nulls_last(), Order.id.desc())
        )
        if from_date is not None:
            stmt = stmt.where(Order.scheduled_date >= from_date)
        if to_date is not None:
            stmt = stmt.where(Order.scheduled_date <= to_date)
        if status == "unpaid":
            unpaid_condition = Order.partner_payment_status.is_(None) | Order.partner_payment_status.in_(
                PARTNER_SETTLEMENT_PENDING_STATUSES
            )
            stmt = stmt.where(unpaid_condition)
        elif status == "paid":
            stmt = stmt.where(Order.partner_payment_status == PartnerPaymentStatus.PAID)
        elif status != "all":
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


def to_settlement_item(order: Order) -> PartnerSettlementItemRead:
    return PartnerSettlementItemRead(
        order_id=order.id,
        status=order.status,
        scheduled_date=order.scheduled_date,
        service_name=order.service_name,
        customer_name=order.customer_name or "",
        address_short=order.customer_address or "",
        consumer_price=float(order.total_amount or 0),
        partner_price=float(order.partner_payment_amount or 0),
        partner_payment_status=order.partner_payment_status,
        settled_at=order.partner_settled_at,
    )


def is_unpaid_partner_order(order: Order) -> bool:
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
