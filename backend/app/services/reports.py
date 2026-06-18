from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.constants import OrderStatus
from app.domain.payment_status import PARTNER_SETTLEMENT_PENDING_STATUSES
from app.models.order import Order
from app.models.partner import Partner
from app.models.service_item import ServiceItem
from app.services.partner_settlements import unpaid_partner_condition
from app.schemas.report import (
    PartnerPerformanceReport,
    PartnerPerformanceRow,
    RevenueBucket,
    RevenueReport,
    ServicePopularityReport,
    ServicePopularityRow,
    SettlementBacklogReport,
    SettlementBacklogRow,
)

_GRANULARITIES = {"day", "week", "month"}
_REVENUE_STATUSES = (OrderStatus.CUSTOMER_DELIVERY_DONE, OrderStatus.COMPLETED)


class ReportService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def revenue(
        self,
        *,
        granularity: str,
        start_date: date,
        end_date: date,
        partner_id: str | None = None,
        service_item_id: str | None = None,
    ) -> RevenueReport:
        if granularity not in _GRANULARITIES:
            raise ValueError(f"unsupported_granularity:{granularity}")
        if start_date > end_date:
            raise ValueError("invalid_range")

        stmt = select(Order).where(
            Order.deleted_at.is_(None),
            Order.status.in_(_REVENUE_STATUSES),
            Order.scheduled_date >= start_date,
            Order.scheduled_date <= end_date,
        )
        if partner_id:
            stmt = stmt.where(Order.partner_id == partner_id)
        if service_item_id:
            stmt = stmt.where(Order.service_item_id == service_item_id)

        buckets: dict[date, list[Decimal]] = {}
        for order in self.db.scalars(stmt):
            if order.scheduled_date is None:
                continue
            key = _period_key(order.scheduled_date, granularity)
            buckets.setdefault(key, []).append(Decimal(str(order.total_amount or 0)))

        bucket_rows = [
            RevenueBucket(
                period=period,
                completed_count=len(amounts),
                revenue=sum(amounts, Decimal("0")),
            )
            for period, amounts in sorted(buckets.items())
        ]
        return RevenueReport(
            granularity=granularity,
            start_date=start_date,
            end_date=end_date,
            partner_id=partner_id,
            service_item_id=service_item_id,
            buckets=bucket_rows,
            total_revenue=sum((bucket.revenue for bucket in bucket_rows), Decimal("0")),
            total_completed=sum(bucket.completed_count for bucket in bucket_rows),
        )

    def partners(self, *, start_date: date, end_date: date) -> PartnerPerformanceReport:
        partners = {partner.id: partner for partner in self.db.scalars(select(Partner))}
        order_stmt = select(Order).where(
            Order.deleted_at.is_(None),
            Order.partner_id.is_not(None),
            Order.status != OrderStatus.CANCELLED,
            Order.scheduled_date >= start_date,
            Order.scheduled_date <= end_date,
        )

        by_partner: dict[str, list[Order]] = {}
        for order in self.db.scalars(order_stmt):
            if order.partner_id is None:
                continue
            by_partner.setdefault(order.partner_id, []).append(order)

        rows: list[PartnerPerformanceRow] = []
        for partner_id, orders in by_partner.items():
            partner = partners.get(partner_id)
            if partner is None:
                continue
            total_amounts = [Decimal(str(order.total_amount or 0)) for order in orders]
            pending_orders = [
                order
                for order in orders
                if order.status == OrderStatus.COMPLETED
                and (
                    order.partner_payment_status is None
                    or order.partner_payment_status in PARTNER_SETTLEMENT_PENDING_STATUSES
                )
            ]
            expected_settlement = sum(
                (Decimal(str(order.partner_payment_amount or 0)) for order in pending_orders),
                Decimal("0"),
            )
            rows.append(
                PartnerPerformanceRow(
                    partner_id=partner_id,
                    partner_name=partner.name,
                    job_count=len(orders),
                    avg_unit_price=(
                        sum(total_amounts, Decimal("0")) / len(total_amounts)
                        if total_amounts
                        else Decimal("0")
                    ),
                    pending_settlement_count=len(pending_orders),
                    expected_settlement_amount=expected_settlement,
                )
            )

        rows.sort(key=lambda row: row.job_count, reverse=True)
        return PartnerPerformanceReport(start_date=start_date, end_date=end_date, rows=rows)

    def services(self, *, start_date: date, end_date: date) -> ServicePopularityReport:
        services = {service.id: service for service in self.db.scalars(select(ServiceItem))}
        order_stmt = select(Order).where(
            Order.deleted_at.is_(None),
            Order.status.in_(_REVENUE_STATUSES),
            Order.scheduled_date >= start_date,
            Order.scheduled_date <= end_date,
        )

        by_key: dict[tuple[str | None, str], list[Order]] = {}
        for order in self.db.scalars(order_stmt):
            service = services.get(order.service_item_id or "")
            if service is not None:
                key = (service.id, service.name)
            else:
                key = (None, order.service_name or "(unknown)")
            by_key.setdefault(key, []).append(order)

        total_revenue = Decimal("0")
        partials: list[tuple[tuple[str | None, str], list[Order], Decimal]] = []
        for key, orders in by_key.items():
            revenue = sum((Decimal(str(order.total_amount or 0)) for order in orders), Decimal("0"))
            total_revenue += revenue
            partials.append((key, orders, revenue))

        denominator = total_revenue if total_revenue > 0 else Decimal("1")
        rows = [
            ServicePopularityRow(
                service_item_id=service_item_id,
                service_name=service_name,
                job_count=len(orders),
                revenue=revenue,
                revenue_share_pct=float(revenue / denominator * Decimal("100")),
            )
            for (service_item_id, service_name), orders, revenue in partials
        ]
        rows.sort(key=lambda row: row.revenue, reverse=True)
        return ServicePopularityReport(start_date=start_date, end_date=end_date, rows=rows)

    def settlements(self) -> SettlementBacklogReport:
        partners = {partner.id: partner for partner in self.db.scalars(select(Partner))}
        order_stmt = (
            select(Order)
            .where(
                Order.deleted_at.is_(None),
                unpaid_partner_condition(),
            )
            .order_by(Order.scheduled_date.asc().nulls_last(), Order.id.asc())
        )

        rows: list[SettlementBacklogRow] = []
        for order in self.db.scalars(order_stmt):
            partner = partners.get(order.partner_id or "")
            rows.append(
                SettlementBacklogRow(
                    order_id=order.id,
                    scheduled_date=order.scheduled_date,
                    service_name=order.service_name,
                    partner_id=order.partner_id,
                    partner_name=partner.name if partner else None,
                    total_amount=Decimal(str(order.total_amount or 0)),
                    expected_settlement_amount=Decimal(str(order.partner_payment_amount or 0)),
                    status=order.status,
                )
            )
        return SettlementBacklogReport(rows=rows)


def _period_key(value: date, granularity: str) -> date:
    if granularity == "day":
        return value
    if granularity == "week":
        return value - timedelta(days=value.weekday())
    if granularity == "month":
        return value.replace(day=1)
    raise ValueError(f"unsupported_granularity:{granularity}")
