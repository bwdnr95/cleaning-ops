from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.constants import OrderStatus
from app.models.order import Order
from app.models.order_group import OrderGroup
from app.repositories.orders import OrderRepository


ORDER_EXPORT_HEADERS: tuple[str, ...] = (
    "order_id",
    "group_id",
    "status",
    "received_date",
    "scheduled_date",
    "requested_time",
    "customer_name",
    "customer_phone",
    "customer_address",
    "customer_address_detail",
    "source_channel",
    "service_name",
    "size_or_quantity",
    "service_detail",
    "special_request",
    "total_amount",
    "discount_amount",
    "deposit_amount",
    "balance_amount",
    "onsite_extra_amount",
    "vat_type",
    "payment_status",
    "payment_memo",
    "evidence_memo",
    "partner_id",
    "team_name",
    "partner_payment_amount",
    "partner_payment_status",
    "partner_settled_at",
    "profit_amount",
    "customer_visible_payment",
    "group_notes",
    "created_at",
    "updated_at",
    "is_cancelled",
)

ExportCell = str | int | float | bool | Decimal | date | datetime | None


@dataclass(frozen=True)
class OrderExportTable:
    headers: tuple[str, ...]
    rows: list[list[ExportCell]]


class MissingExportOrdersError(Exception):
    def __init__(self, order_ids: list[str]) -> None:
        super().__init__("orders_not_found")
        self.order_ids = order_ids


class OrderExportService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def build_admin_orders_export(self, order_ids: Sequence[str]) -> OrderExportTable:
        requested_ids = list(order_ids)
        orders = OrderRepository(self.db).list_by_ids_preserving_order(requested_ids)
        found_ids = {order.id for order in orders}
        missing_ids = [order_id for order_id in requested_ids if order_id not in found_ids]
        if missing_ids:
            raise MissingExportOrdersError(missing_ids)

        groups_by_id = self._groups_by_id(orders)
        return OrderExportTable(
            headers=ORDER_EXPORT_HEADERS,
            rows=[self._order_row(order, groups_by_id.get(order.group_id)) for order in orders],
        )

    def _groups_by_id(self, orders: Sequence[Order]) -> dict[str, OrderGroup]:
        group_ids = sorted({order.group_id for order in orders if order.group_id})
        if not group_ids:
            return {}
        stmt = select(OrderGroup).where(
            OrderGroup.deleted_at.is_(None),
            OrderGroup.id.in_(group_ids),
        )
        return {group.id: group for group in self.db.scalars(stmt)}

    def _order_row(self, order: Order, group: OrderGroup | None) -> list[ExportCell]:
        customer_name = group.customer_name if group else order.customer_name
        customer_phone = group.customer_phone if group else order.customer_phone
        customer_address = group.customer_address if group else order.customer_address
        customer_address_detail = group.customer_address_detail if group else None
        source_channel = group.source_channel if group else order.source_channel
        customer_visible_payment = group.customer_visible_payment if group else bool(order.customer_visible_payment)
        group_notes = group.notes if group else None

        return [
            order.id,
            order.group_id,
            order.status,
            order.received_date,
            order.scheduled_date,
            order.requested_time,
            customer_name or "",
            customer_phone or "",
            customer_address or "",
            customer_address_detail or "",
            source_channel or "",
            order.service_name,
            format_quantity(order.size_or_quantity),
            order.service_detail or "",
            order.special_request or "",
            order.total_amount,
            order.discount_amount,
            order.deposit_amount,
            order.balance_amount,
            order.onsite_extra_amount,
            order.vat_type,
            order.payment_status,
            order.payment_memo or "",
            order.evidence_memo or "",
            order.partner_id,
            order.team_name,
            order.partner_payment_amount,
            order.partner_payment_status,
            order.partner_settled_at,
            _profit_amount(order),
            customer_visible_payment,
            group_notes or "",
            order.created_at,
            order.updated_at,
            order.status == OrderStatus.CANCELLED,
        ]


_DECIMAL_ONLY_RE = re.compile(r"^(\s*)(\d+)\.(\d+)(\s*)$")
_DECIMAL_WITH_UNIT_RE = re.compile(r"^(\s*)(\d+)\.(\d+)(\s*[^\d.\s].*)$")


def format_quantity(value: str | None) -> str:
    if value is None:
        return ""
    if value.strip() == "":
        return value

    decimal_only = _DECIMAL_ONLY_RE.match(value)
    if decimal_only:
        return (
            f"{decimal_only.group(1)}"
            f"{_format_decimal_quantity(decimal_only.group(2), decimal_only.group(3))}"
            f"{decimal_only.group(4)}"
        )

    decimal_with_unit = _DECIMAL_WITH_UNIT_RE.match(value)
    if decimal_with_unit:
        return (
            f"{decimal_with_unit.group(1)}"
            f"{_format_decimal_quantity(decimal_with_unit.group(2), decimal_with_unit.group(3))}"
            f"{decimal_with_unit.group(4)}"
        )

    return value


def _format_decimal_quantity(integer_part: str, decimal_part: str) -> str:
    normalized_integer = re.sub(r"^0+(?=\d)", "", integer_part)
    trimmed_decimal = re.sub(r"0+$", "", decimal_part)
    if not trimmed_decimal:
        return normalized_integer or "0"
    return f"{normalized_integer or '0'}.{trimmed_decimal}"


def _profit_amount(order: Order) -> Decimal:
    total_amount = order.total_amount or Decimal("0")
    partner_amount = order.partner_payment_amount or Decimal("0")
    return total_amount - partner_amount
