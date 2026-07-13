from __future__ import annotations

from calendar import monthrange
from datetime import date
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.constants import OrderStatus, RecurringBillingMode
from app.domain.recurrence import iter_due_dates
from app.models.order import Order
from app.models.recurring_contract import RecurringContract
from app.models.recurring_monthly_status import RecurringMonthlyStatus
from app.repositories.order_groups import OrderGroupRepository
from app.repositories.recurring import RecurringContractRepository, RecurringMonthlyStatusRepository
from app.schemas.recurring_monthly import RecurringMonthlyRowRead
from app.services.recurring import RecurringService


def _month_bounds(month: str) -> tuple[date, date]:
    year, mon = int(month[:4]), int(month[5:7])
    return date(year, mon, 1), date(year, mon, monthrange(year, mon)[1])


class RecurringMonthlyService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.statuses = RecurringMonthlyStatusRepository(db)
        self.contracts = RecurringContractRepository(db)
        self.groups = OrderGroupRepository(db)
        self._recurring = RecurringService(db)  # _schedule_text 재사용

    def _active_in_month(self, contract: RecurringContract, first: date, last: date) -> bool:
        if contract.start_date > last:
            return False
        if contract.end_date is not None and contract.end_date < first:
            return False
        return True

    def _new_status(self, contract_id: str, month: str) -> RecurringMonthlyStatus:
        # Boolean default(False)는 flush 시점에만 적용된다. 행을 commit 전에 DTO로 매핑하므로
        # in-memory 객체가 None을 노출하지 않도록 생성 시 명시적으로 False를 채운다.
        status = RecurringMonthlyStatus(
            id=str(uuid4()), contract_id=contract_id, billing_month=month,
            tax_invoice_issued=False, balance_paid=False, partner_payment_paid=False,
        )
        self.statuses.add(status)
        return status

    def _get_or_create_status(self, contract_id: str, month: str) -> tuple[RecurringMonthlyStatus, bool]:
        """(status, created)를 반환. 조회 시 없으면 생성한다.

        스케줄러가 없어 GET(list_month)/POST(set_status)에서 lazy 생성하므로, 아직 없는 달을
        두 요청이 거의 동시에 열면 같은 (contract_id, billing_month)를 둘 다 INSERT해 유니크
        위반이 난다. 계약 단위 savepoint 안에서 생성하고, 충돌 시 savepoint만 롤백한 뒤 재조회해
        요청 전체(다른 계약 포함)가 500으로 실패하지 않도록 격리한다.
        (같은 방어를 RecurringService._generate_month가 begin_nested로 이미 사용한다.)
        """
        status = self.statuses.get_by_contract_and_month(contract_id, month)
        if status is not None:
            return status, False
        try:
            with self.db.begin_nested():
                status = self._new_status(contract_id, month)
                self.db.flush()  # 유니크 위반을 여기서 유발 → savepoint만 롤백된다.
            return status, True
        except IntegrityError:
            existing = self.statuses.get_by_contract_and_month(contract_id, month)
            if existing is None:
                raise
            return existing, False

    def _to_row(
        self, contract: RecurringContract, month: str, status: RecurringMonthlyStatus
    ) -> RecurringMonthlyRowRead:
        group = self.groups.get(contract.order_group_id)
        return RecurringMonthlyRowRead(
            contract_id=contract.id,
            label=contract.label,
            customer_name=group.customer_name if group else "",
            schedule_text=self._recurring._schedule_text(contract),
            month=month,
            amount=self._month_amount(contract, month),
            partner_amount=self._partner_month_amount(contract, month),
            partner_billing_mode=contract.partner_billing_mode or RecurringBillingMode.PER_VISIT,
            tax_invoice_issued=bool(status.tax_invoice_issued),
            balance_paid=bool(status.balance_paid),
            partner_payment_paid=bool(status.partner_payment_paid),
        )

    def _month_amount(self, contract: RecurringContract, month: str) -> float | None:
        """월 청구 금액. per_visit=회당 금액×그달 청구 대상 방문 수, monthly=월 고정 금액.

        per_visit는 살아있는(삭제/취소 제외) 정기 회차를 생성 당시 예정 슬롯 기준으로 센다.
        요일 변경/방문일 조정 뒤에도 해당 월에 이미 생성된 정기 슬롯이 월 청구액에서 빠지지 않는다.
        recurring_planned_date가 없는 구버전/수기 데이터만 방문일로 보정한다.
        """
        if contract.total_amount is None:
            return None
        amount = float(contract.total_amount)
        if contract.billing_mode == RecurringBillingMode.MONTHLY:
            return amount
        first, last = _month_bounds(month)
        billable = self._billable_generated_count(contract, first, last)
        if billable > 0:
            return amount * billable
        # 살아있는 방문이 0: 그달 회차가 이미 생성됐다면(전부 취소/삭제) 0, 미생성이면 스케줄 예상.
        generated = self._generated_slot_count(contract, first, last)
        if generated > 0:
            return 0.0
        scheduled_visits = sum(
            1
            for _seq, due in iter_due_dates(self._recurring._spec(contract), until=last)
            if first <= due <= last
        )
        return amount * scheduled_visits

    def _partner_month_amount(self, contract: RecurringContract, month: str) -> float | None:
        if contract.partner_payment_amount is None:
            return None
        amount = float(contract.partner_payment_amount)
        if (contract.partner_billing_mode or RecurringBillingMode.PER_VISIT) == RecurringBillingMode.MONTHLY:
            return amount
        first, last = _month_bounds(month)
        billable = self._billable_generated_count(contract, first, last)
        if billable > 0:
            return amount * billable
        generated = self._generated_slot_count(contract, first, last)
        if generated > 0:
            return 0.0
        scheduled_visits = sum(
            1
            for _seq, due in iter_due_dates(self._recurring._spec(contract), until=last)
            if first <= due <= last
        )
        return amount * scheduled_visits

    def _billable_generated_count(self, contract: RecurringContract, first: date, last: date) -> int:
        rows = self.db.scalars(
            select(Order.id).where(
                Order.recurring_contract_id == contract.id,
                Order.deleted_at.is_(None),
                Order.status != OrderStatus.CANCELLED,
                or_(
                    (
                        (Order.recurring_planned_date >= first)
                        & (Order.recurring_planned_date <= last)
                    ),
                    (
                        Order.recurring_planned_date.is_(None)
                        & (Order.scheduled_date >= first)
                        & (Order.scheduled_date <= last)
                    ),
                ),
            )
        ).all()
        return len(set(rows))

    def _generated_slot_count(self, contract: RecurringContract, first: date, last: date) -> int:
        return self.db.scalar(
            select(func.count(Order.id)).where(
                Order.recurring_contract_id == contract.id,
                Order.recurring_planned_date >= first,
                Order.recurring_planned_date <= last,
            )
        ) or 0

    def list_month(self, month: str) -> list[RecurringMonthlyRowRead]:
        first, last = _month_bounds(month)
        created = False
        rows: list[RecurringMonthlyRowRead] = []
        for contract in self.contracts.list_active():
            if not self._active_in_month(contract, first, last):
                continue
            status, was_created = self._get_or_create_status(contract.id, month)
            created = created or was_created
            rows.append(self._to_row(contract, month, status))
        if created:
            self.db.commit()
        rows.sort(key=lambda r: r.label)
        return rows

    def set_status(
        self, contract_id: str, month: str, *,
        tax_invoice_issued: bool | None = None,
        balance_paid: bool | None = None,
        partner_payment_paid: bool | None = None,
    ) -> RecurringMonthlyRowRead:
        contract = self.contracts.get(contract_id)
        if contract is None:
            raise ValueError("recurring_contract_not_found")
        status, _ = self._get_or_create_status(contract_id, month)
        if tax_invoice_issued is not None:
            status.tax_invoice_issued = tax_invoice_issued
        if balance_paid is not None:
            status.balance_paid = balance_paid
        if partner_payment_paid is not None:
            status.partner_payment_paid = partner_payment_paid
        self.db.commit()
        return self._to_row(contract, month, status)
