from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import business_today
from app.domain.constants import OrderStatus, RecurringBillingMode, RecurringContractStatus
from app.domain.order_metrics import REVENUE_STATUSES
from app.domain.order_pricing import order_consumer_total
from app.domain.payment_status import PARTNER_SETTLEMENT_PENDING_STATUSES
from app.models.order import Order
from app.models.partner import Partner
from app.models.recurring_contract import RecurringContract
from app.models.recurring_monthly_status import RecurringMonthlyStatus
from app.models.service_item import ServiceItem
from app.services.partner_settlements import unpaid_partner_condition
from app.services.recurring_monthly import RecurringMonthlyService
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
# 매출 대상 상태는 단일 출처(domain/order_metrics)를 사용한다.
_REVENUE_STATUSES = REVENUE_STATUSES


@dataclass(frozen=True)
class PendingRecurringMonthlySettlement:
    contract: RecurringContract
    month: str
    month_start: date
    amount: Decimal


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
            # 매출 = 기본가 + 현장추가비
            buckets.setdefault(key, []).append(order_consumer_total(order))

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
        monthly_by_partner: dict[str, list[PendingRecurringMonthlySettlement]] = {}
        for monthly in self._pending_recurring_monthly_settlements(
            start_date=start_date,
            end_date=end_date,
        ):
            partner_id = monthly.contract.default_partner_id
            if partner_id is None:
                continue
            monthly_by_partner.setdefault(partner_id, []).append(monthly)

        rows: list[PartnerPerformanceRow] = []
        for partner_id in sorted(set(by_partner) | set(monthly_by_partner)):
            orders = by_partner.get(partner_id, [])
            monthly_settlements = monthly_by_partner.get(partner_id, [])
            partner = partners.get(partner_id)
            if partner is None:
                continue
            total_amounts = [Decimal(str(order.total_amount or 0)) for order in orders]
            pending_orders = [
                order
                for order in orders
                if _is_unpaid_partner_order(order)
            ]
            expected_settlement = sum(
                (Decimal(str(order.partner_payment_amount or 0)) for order in pending_orders),
                Decimal("0"),
            ) + sum((monthly.amount for monthly in monthly_settlements), Decimal("0"))
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
                    pending_settlement_count=len(pending_orders) + len(monthly_settlements),
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
            revenue = sum((order_consumer_total(order) for order in orders), Decimal("0"))
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
                    source="order",
                )
            )
        rows.extend(self._recurring_monthly_settlement_rows(partners))
        return SettlementBacklogReport(rows=rows)

    def _recurring_monthly_settlement_rows(
        self,
        partners: dict[str, Partner],
    ) -> list[SettlementBacklogRow]:
        rows: list[SettlementBacklogRow] = []
        for pending in self._pending_recurring_monthly_settlements():
            contract = pending.contract
            partner = partners.get(contract.default_partner_id or "")
            rows.append(
                SettlementBacklogRow(
                    order_id=f"recurring-monthly:{contract.id}:{pending.month}",
                    scheduled_date=pending.month_start,
                    service_name=f"{contract.label} 월정산 도급가",
                    partner_id=contract.default_partner_id,
                    partner_name=partner.name if partner else None,
                    total_amount=Decimal(str(contract.total_amount or 0)),
                    expected_settlement_amount=pending.amount,
                    status="월정산대기",
                    source="recurring_monthly",
                )
            )
        return rows

    def _pending_recurring_monthly_settlements(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[PendingRecurringMonthlySettlement]:
        monthly_service = RecurringMonthlyService(self.db)
        pending: dict[tuple[str, str], PendingRecurringMonthlySettlement] = {}
        status_stmt = (
            select(RecurringContract, RecurringMonthlyStatus)
            .join(
                RecurringMonthlyStatus,
                RecurringMonthlyStatus.contract_id == RecurringContract.id,
            )
            .where(
                RecurringContract.deleted_at.is_(None),
                RecurringContract.partner_billing_mode == RecurringBillingMode.MONTHLY,
                RecurringContract.partner_payment_amount > 0,
                RecurringMonthlyStatus.partner_payment_paid.is_(False),
            )
        )
        if start_date is not None:
            status_stmt = status_stmt.where(
                RecurringMonthlyStatus.billing_month >= _month_key(start_date)
            )
        if end_date is not None:
            status_stmt = status_stmt.where(
                RecurringMonthlyStatus.billing_month <= _month_key(end_date)
            )
        for contract, monthly_status in self.db.execute(status_stmt).all():
            month = monthly_status.billing_month
            month_start = _month_start(month)
            amount = monthly_service._partner_month_amount(contract, month)
            if amount is None or Decimal(str(amount)) <= 0:
                continue
            pending[(contract.id, month)] = PendingRecurringMonthlySettlement(
                contract=contract,
                month=month,
                month_start=month_start,
                amount=Decimal(str(amount)),
            )

        today = business_today()
        current_month = _month_key(today)
        current_month_start = today.replace(day=1)
        current_month_end = _month_end(current_month_start)
        if (
            (start_date is None or current_month_start >= start_date.replace(day=1))
            and (end_date is None or current_month_start <= end_date.replace(day=1))
        ):
            current_stmt = (
                select(RecurringContract)
                .where(
                    RecurringContract.deleted_at.is_(None),
                    RecurringContract.status == RecurringContractStatus.ACTIVE,
                    RecurringContract.partner_billing_mode == RecurringBillingMode.MONTHLY,
                    RecurringContract.partner_payment_amount > 0,
                    RecurringContract.start_date <= current_month_end,
                    (
                        RecurringContract.end_date.is_(None)
                        | (RecurringContract.end_date >= current_month_start)
                    ),
                )
                .order_by(RecurringContract.label.asc(), RecurringContract.id.asc())
            )
            for contract in self.db.scalars(current_stmt):
                key = (contract.id, current_month)
                if key in pending:
                    continue
                monthly_status = self.db.scalar(
                    select(RecurringMonthlyStatus).where(
                        RecurringMonthlyStatus.contract_id == contract.id,
                        RecurringMonthlyStatus.billing_month == current_month,
                    )
                )
                if monthly_status is not None and monthly_status.partner_payment_paid:
                    continue
                amount = monthly_service._partner_month_amount(contract, current_month)
                if amount is None or Decimal(str(amount)) <= 0:
                    continue
                pending[key] = PendingRecurringMonthlySettlement(
                    contract=contract,
                    month=current_month,
                    month_start=current_month_start,
                    amount=Decimal(str(amount)),
                )

        return sorted(pending.values(), key=lambda item: (item.month_start, item.contract.label, item.contract.id))


def _period_key(value: date, granularity: str) -> date:
    if granularity == "day":
        return value
    if granularity == "week":
        return value - timedelta(days=value.weekday())
    if granularity == "month":
        return value.replace(day=1)
    raise ValueError(f"unsupported_granularity:{granularity}")


def _month_key(value: date) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def _month_start(month: str) -> date:
    return date(int(month[:4]), int(month[5:7]), 1)


def _month_end(month_start: date) -> date:
    return month_start.replace(day=monthrange(month_start.year, month_start.month)[1])


def _is_unpaid_partner_order(order: Order) -> bool:
    return (
        order.status != OrderStatus.CANCELLED
        and Decimal(str(order.partner_payment_amount or 0)) > 0
        and (
            order.partner_payment_status is None
            or order.partner_payment_status in PARTNER_SETTLEMENT_PENDING_STATUSES
        )
    )


def _contract_active_in_month(
    contract: RecurringContract,
    month_start: date,
    month_end: date,
) -> bool:
    if contract.start_date > month_end:
        return False
    return contract.end_date is None or contract.end_date >= month_start
