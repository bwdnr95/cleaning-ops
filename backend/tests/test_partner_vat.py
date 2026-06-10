from datetime import UTC, date, datetime
from decimal import Decimal

from app.domain.partner_vat import (
    gross_up_partner_vat_amount,
    should_gross_up_partner_vat_amount,
)


def test_gross_up_partner_vat_amount_adds_ten_percent() -> None:
    assert gross_up_partner_vat_amount(Decimal("196000")) == Decimal("215600")
    assert gross_up_partner_vat_amount(Decimal("100001")) == Decimal("110001")
    assert gross_up_partner_vat_amount(None) is None


def test_partner_vat_gross_up_scope_starts_from_june_and_excludes_settled() -> None:
    assert should_gross_up_partner_vat_amount(
        scheduled_date=date(2026, 6, 1),
        partner_payment_status="unpaid",
    )
    assert not should_gross_up_partner_vat_amount(
        scheduled_date=date(2026, 5, 31),
        partner_payment_status="unpaid",
    )
    assert not should_gross_up_partner_vat_amount(
        scheduled_date=date(2026, 6, 1),
        partner_payment_status="paid",
    )
    assert not should_gross_up_partner_vat_amount(
        scheduled_date=date(2026, 6, 1),
        partner_payment_status="unpaid",
        partner_settled_at=datetime(2026, 6, 5, tzinfo=UTC),
    )
