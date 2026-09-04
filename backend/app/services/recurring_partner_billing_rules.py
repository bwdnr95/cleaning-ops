from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.core.time import business_today
from app.domain.constants import RecurringBillingMode, RecurringContractStatus
from app.models.recurring_contract import RecurringContract
from app.models.recurring_monthly_status import RecurringMonthlyStatus
from app.models.recurring_partner_billing_period import RecurringPartnerBillingPeriod


@dataclass(frozen=True, slots=True)
class RecurringPartnerBillingTerms:
    partner_id: str | None
    billing_mode: RecurringBillingMode
    partner_payment_amount: Decimal | None


def billing_month(value: date) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def money_decimal(value: Decimal | float | int | None) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


def has_recurring_monthly_partner_history(
    status: RecurringMonthlyStatus | None,
) -> bool:
    return status is not None and (
        bool(status.partner_payment_paid)
        or status.retained_partner_id is not None
        or status.retained_partner_payment_amount is not None
    )


def recurring_monthly_settlement_amount(
    status: RecurringMonthlyStatus | None,
    terms: RecurringPartnerBillingTerms,
) -> Decimal | None:
    if status is not None and status.retained_partner_payment_amount is not None:
        return status.retained_partner_payment_amount
    return terms.partner_payment_amount


def terms_from_billing_period(
    contract: RecurringContract,
    period: RecurringPartnerBillingPeriod | None,
) -> RecurringPartnerBillingTerms:
    if period is None:
        return RecurringPartnerBillingTerms(
            partner_id=contract.default_partner_id,
            billing_mode=RecurringBillingMode(
                contract.partner_billing_mode or RecurringBillingMode.PER_VISIT
            ),
            partner_payment_amount=money_decimal(contract.partner_payment_amount),
        )
    return RecurringPartnerBillingTerms(
        partner_id=period.partner_id,
        billing_mode=RecurringBillingMode(period.billing_mode),
        partner_payment_amount=money_decimal(period.partner_payment_amount),
    )


def resolve_terms_from_periods(
    contract: RecurringContract,
    month: str,
    periods: list[RecurringPartnerBillingPeriod],
) -> RecurringPartnerBillingTerms:
    period = next(
        (
            candidate
            for candidate in reversed(periods)
            if candidate.effective_month <= month
        ),
        None,
    )
    return terms_from_billing_period(contract, period)


def incurred_billing_months(
    contract: RecurringContract,
    *,
    through_date: date | None = None,
) -> tuple[str, ...]:
    through = through_date or business_today()
    if (
        contract.deleted_at is not None
        or contract.status != RecurringContractStatus.ACTIVE
    ):
        return ()
    first_day = max(
        contract.start_date,
        contract.active_segment_start_date or contract.start_date,
    )
    last_day = min(through, contract.end_date or through)
    if first_day > last_day:
        return ()

    cursor = first_day.replace(day=1)
    last_month = last_day.replace(day=1)
    months: list[str] = []
    while cursor <= last_month:
        months.append(billing_month(cursor))
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
    return tuple(months)
