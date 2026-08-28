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


@dataclass(frozen=True, slots=True)
class RecurringMonthlySettlementRow:
    """월정산(계약×월) 도급 지급 단위. 협력사관리 배지·정산 목록 공용 표현."""

    contract_id: str
    contract_label: str
    month: str  # "YYYY-MM"
    month_start: date
    partner_id: str
    amount: Decimal
    paid: bool


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

    def list_monthly_settlement_rows(
        self,
        *,
        partner_ids: set[str] | None = None,
        today: date | None = None,
    ) -> list[RecurringMonthlySettlementRow]:
        """월정산 지급 대상 행(계약×월)을 지급/미지급 포함해 나열한다.

        협력사관리의 미정산 배지와 정산 목록이 **모두 이 헬퍼에서 파생**되어야 한다.
        따로 계산하면 "배지에는 미정산이 보이는데 목록에는 정산할 행이 없는" 모순이
        생긴다(2026-08 김해푸르지오하이엔드1차/치움 사례).

        포함 기준(기존 미정산 배지와 동일):
        - 대상 월 = 발생 월(incurred, 활성 계약 시작~오늘) ∪ 이미 status 행이 있는
          현재 월 이하의 월(계약 종료/삭제 후에도 남은 미지급 이력 보존).
        - 그 월의 조건이 월정산(monthly)이거나, 조건 변경 시점에 남긴 지급 스냅샷
          (retained_*)이 있는 경우만.
        - 지급 금액 > 0, 지급 대상 협력사 존재.
        """
        today = today or business_today()
        current_month = billing_month(today)
        statuses_by_contract: dict[str, dict[str, RecurringMonthlyStatus]] = {}
        for status in self.db.scalars(select(RecurringMonthlyStatus)):
            statuses_by_contract.setdefault(status.contract_id, {})[
                status.billing_month
            ] = status

        rows: list[RecurringMonthlySettlementRow] = []
        for contract in self.db.scalars(select(RecurringContract)):
            statuses = statuses_by_contract.get(contract.id, {})
            months = {month for month in statuses if month <= current_month}
            months.update(incurred_billing_months(contract, through_date=today))
            for month in sorted(months):
                status = statuses.get(month)
                retained_amount = (
                    status.retained_partner_payment_amount
                    if status is not None
                    else None
                )
                has_retained = retained_amount is not None
                terms = self.resolve(contract, month)
                if not has_retained and terms.billing_mode != RecurringBillingMode.MONTHLY:
                    continue
                payable_partner_id = (
                    status.retained_partner_id if has_retained else terms.partner_id
                )
                payable_amount = (
                    retained_amount if has_retained else terms.partner_payment_amount
                )
                if payable_partner_id is None:
                    continue
                if payable_amount is None or payable_amount <= 0:
                    continue
                if partner_ids is not None and payable_partner_id not in partner_ids:
                    continue
                rows.append(
                    RecurringMonthlySettlementRow(
                        contract_id=contract.id,
                        contract_label=contract.label,
                        month=month,
                        month_start=date(int(month[:4]), int(month[5:7]), 1),
                        partner_id=payable_partner_id,
                        amount=Decimal(str(payable_amount)),
                        paid=bool(status.partner_payment_paid) if status is not None else False,
                    )
                )
        return rows

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
