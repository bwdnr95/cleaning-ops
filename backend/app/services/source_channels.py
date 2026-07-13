from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.domain.constants import OrderStatus
from app.domain.order_metrics import REVENUE_STATUSES
from app.domain.order_pricing import order_consumer_total
from app.models.order import Order
from app.models.order_group import OrderGroup
from app.schemas.report import SourceChannelReport, SourceChannelRow

_REVENUE_STATUSES = REVENUE_STATUSES


class SourceChannelReportService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def source_channels(self, *, start_date: date, end_date: date) -> SourceChannelReport:
        if start_date > end_date:
            raise ValueError("invalid_range")

        by_source: dict[str, list[Order]] = {}
        for order, group in self.db.execute(_source_channel_orders(start_date, end_date)).all():
            source_channel = _source_channel_label(group.source_channel or order.source_channel)
            by_source.setdefault(source_channel, []).append(order)

        total_revenue = Decimal("0")
        partials: list[tuple[str, list[Order], int, Decimal]] = []
        for source_channel, orders in by_source.items():
            completed_orders = [order for order in orders if order.status in _REVENUE_STATUSES]
            revenue = sum((order_consumer_total(order) for order in completed_orders), Decimal("0"))
            total_revenue += revenue
            partials.append((source_channel, orders, len(completed_orders), revenue))

        denominator = total_revenue if total_revenue > 0 else Decimal("1")
        rows = [
            SourceChannelRow(
                source_channel=source_channel,
                order_count=len(orders),
                completed_count=completed_count,
                revenue=revenue,
                revenue_share_pct=float(revenue / denominator * Decimal("100")),
            )
            for source_channel, orders, completed_count, revenue in partials
        ]
        rows.sort(key=lambda row: (-row.revenue, -row.order_count, row.source_channel))
        return SourceChannelReport(
            start_date=start_date,
            end_date=end_date,
            rows=rows,
            total_orders=sum(row.order_count for row in rows),
            total_completed=sum(row.completed_count for row in rows),
            total_revenue=total_revenue,
        )


def _source_channel_orders(start_date: date, end_date: date) -> Select[tuple[Order, OrderGroup]]:
    return (
        select(Order, OrderGroup)
        .join(OrderGroup, Order.group_id == OrderGroup.id)
        .where(
            Order.deleted_at.is_(None),
            OrderGroup.deleted_at.is_(None),
            Order.status != OrderStatus.CANCELLED,
            Order.scheduled_date >= start_date,
            Order.scheduled_date <= end_date,
        )
    )


def _source_channel_label(value: str | None) -> str:
    source_channel = (value or "").strip()
    if source_channel == "네이버":
        return "네이버톡톡"
    return source_channel or "미지정"
