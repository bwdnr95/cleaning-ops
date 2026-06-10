from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from app.domain.payment_status import PartnerPaymentStatus

PARTNER_VAT_INCLUDED_EFFECTIVE_DATE = date(2026, 6, 1)
PARTNER_VAT_MULTIPLIER = Decimal("1.10")


def gross_up_partner_vat_amount(amount: Decimal | int | float | str | None) -> Decimal | None:
    if amount is None:
        return None
    value = Decimal(str(amount))
    return (value * PARTNER_VAT_MULTIPLIER).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def is_partner_settlement_completed(
    partner_payment_status: str | None,
    partner_settled_at: datetime | None = None,
) -> bool:
    return partner_payment_status == PartnerPaymentStatus.PAID.value or partner_settled_at is not None


def should_gross_up_partner_vat_amount(
    *,
    scheduled_date: date | None,
    partner_payment_status: str | None,
    partner_settled_at: datetime | None = None,
) -> bool:
    return (
        scheduled_date is not None
        and scheduled_date >= PARTNER_VAT_INCLUDED_EFFECTIVE_DATE
        and not is_partner_settlement_completed(partner_payment_status, partner_settled_at)
    )
