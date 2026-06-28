from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.order_metrics import REVENUE_STATUSES, SETTLEABLE_ORDER_STATUSES
from app.domain.order_pricing import order_consumer_total
from app.domain.payment_status import PARTNER_SETTLEMENT_PENDING_STATUSES, PAYMENT_CHECK_STATUSES


def _is_settleable(order) -> bool:
    # is_unpaid_partner_order와 동일 정의(서비스완료 + 미정산). 순수 함수라 model import 없이 status 비교.
    return order.status in SETTLEABLE_ORDER_STATUSES and (
        order.partner_payment_status is None
        or order.partner_payment_status in PARTNER_SETTLEMENT_PENDING_STATUSES
    )


def _sum_partner_amount(orders: Iterable) -> Decimal:
    return sum((Decimal(str(o.partner_payment_amount or 0)) for o in orders), Decimal("0"))


@dataclass(frozen=True)
class PartnerSubtotal:
    partner_id: str | None
    partner_total: Decimal
    unpaid_partner_total: Decimal
    settleable_count: int


@dataclass(frozen=True)
class BillingAggregate:
    visit_count: int
    billed_total: Decimal
    confirmed_revenue: Decimal
    unpaid_customer_count: int
    payment_breakdown: dict[str, int]
    partner_total: Decimal
    unpaid_partner_total: Decimal
    unpaid_partner_count: int
    partner_subtotals: list[PartnerSubtotal] = field(default_factory=list)


def aggregate_orders(orders: Iterable) -> BillingAggregate:
    orders = list(orders)
    billed_total = sum((order_consumer_total(o) for o in orders), Decimal("0"))
    confirmed_revenue = sum(
        (order_consumer_total(o) for o in orders if o.status in REVENUE_STATUSES), Decimal("0")
    )
    unpaid_customer_count = sum(1 for o in orders if o.payment_status in PAYMENT_CHECK_STATUSES)
    payment_breakdown: dict[str, int] = {}
    for o in orders:
        key = str(o.payment_status) if o.payment_status is not None else "none"
        payment_breakdown[key] = payment_breakdown.get(key, 0) + 1

    partner_total = _sum_partner_amount(orders)
    settleable = [o for o in orders if _is_settleable(o)]
    unpaid_partner_total = _sum_partner_amount(settleable)

    # 협력사별 소계
    by_partner: dict[str | None, list] = {}
    for o in orders:
        by_partner.setdefault(o.partner_id, []).append(o)
    subtotals = []
    for partner_id, group in by_partner.items():
        g_settleable = [o for o in group if _is_settleable(o)]
        subtotals.append(
            PartnerSubtotal(
                partner_id=partner_id,
                partner_total=_sum_partner_amount(group),
                unpaid_partner_total=_sum_partner_amount(g_settleable),
                settleable_count=len(g_settleable),
            )
        )

    return BillingAggregate(
        visit_count=len(orders),
        billed_total=billed_total,
        confirmed_revenue=confirmed_revenue,
        unpaid_customer_count=unpaid_customer_count,
        payment_breakdown=payment_breakdown,
        partner_total=partner_total,
        unpaid_partner_total=unpaid_partner_total,
        unpaid_partner_count=len(settleable),
        partner_subtotals=subtotals,
    )
