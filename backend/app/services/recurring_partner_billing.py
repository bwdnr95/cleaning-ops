from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import business_today
from app.domain.constants import RecurringBillingMode, RecurringContractStatus
from app.models.order import Order
from app.models.recurring_contract import RecurringContract
from app.models.recurring_monthly_status import RecurringMonthlyStatus
from app.models.recurring_partner_billing_period import RecurringPartnerBillingPeriod

BASELINE_EFFECTIVE_MONTH = "0001-01"


@dataclass(frozen=True, slots=True)
class RecurringPartnerBillingTerms:
    partner_id: str | None
    billing_mode: RecurringBillingMode
    partner_payment_amount: Decimal | None


def billing_month(value: date) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def money_decimal(value: Decimal | float | int | None) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


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


class RecurringPartnerBillingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def resolve(
        self,
        contract: RecurringContract,
        month: str,
        *,
        refresh: bool = False,
    ) -> RecurringPartnerBillingTerms:
        stmt = (
            select(RecurringPartnerBillingPeriod)
            .where(
                RecurringPartnerBillingPeriod.contract_id == contract.id,
                RecurringPartnerBillingPeriod.effective_month <= month,
            )
            .order_by(RecurringPartnerBillingPeriod.effective_month.desc())
            .limit(1)
        )
        if refresh:
            stmt = stmt.execution_options(populate_existing=True)
        period = self.db.scalar(stmt)
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

    def allows_order_settlement(self, order: Order) -> bool:
        if order.recurring_contract_id is None:
            return True
        # 조건 변경 전에 확정된 회당 정산 이력은 해당 월의 계약 조건이 월정산으로
        # 바뀌어도 주문 자체의 금액/상태를 기준으로 계속 조회·되돌리기 할 수 있어야 한다.
        if (
            order.recurring_partner_settlement_retained
            and order.partner_payment_amount is not None
            and money_decimal(order.partner_payment_amount) > 0
        ):
            return True
        settlement_date = order.recurring_planned_date or order.scheduled_date
        if settlement_date is None:
            return False
        contract = self.db.get(RecurringContract, order.recurring_contract_id)
        if contract is None:
            return False
        terms = self.resolve(contract, billing_month(settlement_date))
        return terms.billing_mode == RecurringBillingMode.PER_VISIT

    def ensure_baseline(self, contract: RecurringContract) -> RecurringPartnerBillingPeriod:
        baseline = self.db.get(
            RecurringPartnerBillingPeriod,
            (contract.id, BASELINE_EFFECTIVE_MONTH),
        )
        if baseline is None:
            baseline = RecurringPartnerBillingPeriod(
                contract_id=contract.id,
                effective_month=BASELINE_EFFECTIVE_MONTH,
                partner_id=contract.default_partner_id,
                billing_mode=contract.partner_billing_mode or RecurringBillingMode.PER_VISIT,
                partner_payment_amount=money_decimal(contract.partner_payment_amount),
            )
            self.db.add(baseline)
        return baseline

    def set_effective(
        self,
        contract: RecurringContract,
        *,
        month: str,
        partner_id: str | None,
        billing_mode: RecurringBillingMode,
        partner_payment_amount: Decimal | None,
    ) -> RecurringPartnerBillingPeriod:
        self.ensure_baseline(contract)
        period = self.db.get(RecurringPartnerBillingPeriod, (contract.id, month))
        if period is None:
            period = RecurringPartnerBillingPeriod(
                contract_id=contract.id,
                effective_month=month,
                partner_id=partner_id,
                billing_mode=billing_mode,
                partner_payment_amount=partner_payment_amount,
            )
            self.db.add(period)
        else:
            period.partner_id = partner_id
            period.billing_mode = billing_mode
            period.partner_payment_amount = partner_payment_amount
        return period

    def materialize_incurred_statuses(
        self,
        contract: RecurringContract,
        *,
        through_date: date | None = None,
    ) -> list[RecurringMonthlyStatus]:
        months = incurred_billing_months(contract, through_date=through_date)
        if not months:
            return []
        existing = {
            status.billing_month: status
            for status in self.db.scalars(
                select(RecurringMonthlyStatus).where(
                    RecurringMonthlyStatus.contract_id == contract.id,
                    RecurringMonthlyStatus.billing_month.in_(months),
                )
            )
        }
        for month in months:
            if month in existing:
                continue
            status = RecurringMonthlyStatus(
                id=str(uuid4()),
                contract_id=contract.id,
                billing_month=month,
                tax_invoice_issued=False,
                balance_paid=False,
                partner_payment_paid=False,
                retained_partner_id=None,
                retained_partner_payment_amount=None,
            )
            self.db.add(status)
            existing[month] = status
        return [existing[month] for month in months]
