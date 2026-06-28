from decimal import Decimal
from types import SimpleNamespace

from app.domain.constants import OrderStatus
from app.domain.payment_status import PartnerPaymentStatus, PaymentStatus
from app.domain.recurring_billing import aggregate_orders


def _o(**kw):
    base = dict(
        status=OrderStatus.COMPLETED, total_amount=Decimal("100000"), onsite_extra_amount=None,
        payment_status=PaymentStatus.PAID, partner_id="p1", partner_payment_amount=Decimal("60000"),
        partner_payment_status=PartnerPaymentStatus.PAID, deleted_at=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_aggregate_customer_and_partner_sides():
    orders = [
        _o(status=OrderStatus.COMPLETED, payment_status=PaymentStatus.PAID,
           partner_payment_status=PartnerPaymentStatus.PAID),
        _o(status=OrderStatus.CUSTOMER_DELIVERY_DONE, payment_status=PaymentStatus.UNPAID,
           partner_payment_status=PartnerPaymentStatus.UNPAID),
        _o(status=OrderStatus.IN_PROGRESS, payment_status=PaymentStatus.PENDING,
           partner_payment_status=None),  # 미완 → 확정매출 X, 정산 가능 X
    ]
    agg = aggregate_orders(orders)
    assert agg.visit_count == 3
    assert agg.billed_total == Decimal("300000")
    # 확정 매출 = 전달완료/완료 2건
    assert agg.confirmed_revenue == Decimal("200000")
    # 미입금 고객 = UNPAID/PENDING 2건
    assert agg.unpaid_customer_count == 2
    assert agg.partner_total == Decimal("180000")
    # 미정산(정산 가능 = COMPLETED+미정산): 2번째는 전달완료라 settleable 아님, 3번째는 미완.
    # → 정산 가능 0, 미정산 합계 0
    assert agg.unpaid_partner_count == 0
    assert agg.unpaid_partner_total == Decimal("0")


def test_partner_subtotals_group_by_partner():
    orders = [
        _o(partner_id="p1", partner_payment_amount=Decimal("60000"),
           status=OrderStatus.COMPLETED, partner_payment_status=PartnerPaymentStatus.UNPAID),
        _o(partner_id="p2", partner_payment_amount=Decimal("50000"),
           status=OrderStatus.COMPLETED, partner_payment_status=PartnerPaymentStatus.PAID),
    ]
    agg = aggregate_orders(orders)
    subs = {s.partner_id: s for s in agg.partner_subtotals}
    assert subs["p1"].partner_total == Decimal("60000")
    assert subs["p1"].settleable_count == 1  # COMPLETED + UNPAID
    assert subs["p1"].unpaid_partner_total == Decimal("60000")
    assert subs["p2"].settleable_count == 0  # 이미 PAID
