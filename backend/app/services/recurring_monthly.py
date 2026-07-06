from __future__ import annotations

from calendar import monthrange
from datetime import date
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.time import business_today
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

        per_visit는 '실제 발생한 방문'만 청구한다: 그달의 살아있는(삭제/취소 제외) 정기 회차 주문을
        방문일(scheduled_date) 기준으로 센다 → 회차를 삭제/취소/이동하면 청구액이 실제 발생과 일치한다.
        그달 회차가 아직 생성되지 않았으면(미래 달 등) 계약 스케줄 기준으로 예상 청구액을 보여준다.
        """
        if contract.total_amount is None:
            return None
        amount = float(contract.total_amount)
        if contract.billing_mode == RecurringBillingMode.MONTHLY:
            return amount
        first, last = _month_bounds(month)
        # 청구 대상 = 살아있는(soft-delete 아님) + 취소 아님 + 방문일이 그달인 정기 회차.
        billable = self.db.scalar(
            select(func.count(Order.id)).where(
                Order.recurring_contract_id == contract.id,
                Order.deleted_at.is_(None),
                Order.status != OrderStatus.CANCELLED,
                Order.scheduled_date >= first,
                Order.scheduled_date <= last,
            )
        ) or 0
        if billable > 0:
            # 실제 발생 회차 + 아직 생성 안 된 '미래' 예정 슬롯을 더한다. 이동 회차 때문에 billable>0가 된
            # 미래 달이 자기 예정 방문(N건)을 빠뜨려 과소청구되는 것을 막는다(과거 미생성분은 발생 안 했으니 제외).
            return amount * (billable + self._ungenerated_upcoming_count(contract, first, last))
        # 살아있는 방문이 0: 그달 회차가 이미 생성됐다면(전부 취소/삭제) 0, 미생성이면 스케줄 예상.
        generated = self.db.scalar(
            select(func.count(Order.id)).where(
                Order.recurring_contract_id == contract.id,
                Order.recurring_planned_date >= first,
                Order.recurring_planned_date <= last,
            )
        ) or 0
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
        billable = self.db.scalar(
            select(func.count(Order.id)).where(
                Order.recurring_contract_id == contract.id,
                Order.deleted_at.is_(None),
                Order.status != OrderStatus.CANCELLED,
                Order.scheduled_date >= first,
                Order.scheduled_date <= last,
            )
        ) or 0
        if billable > 0:
            return amount * (billable + self._ungenerated_upcoming_count(contract, first, last))
        generated = self.db.scalar(
            select(func.count(Order.id)).where(
                Order.recurring_contract_id == contract.id,
                Order.recurring_planned_date >= first,
                Order.recurring_planned_date <= last,
            )
        ) or 0
        if generated > 0:
            return 0.0
        scheduled_visits = sum(
            1
            for _seq, due in iter_due_dates(self._recurring._spec(contract), until=last)
            if first <= due <= last
        )
        return amount * scheduled_visits

    def _ungenerated_upcoming_count(self, contract: RecurringContract, first: date, last: date) -> int:
        """그달 예정 방문 중 아직 회차가 생성되지 않은 '미래(오늘 이후)' 슬롯 수.

        과거 달은 예정 슬롯을 예상치로 더하지 않는다(실제 발생분만 청구). 미래/현재 달만,
        스케줄상 예정이지만 아직 주문이 없는(recurring_planned_date 미존재) 방문을 예상 청구로 더한다.
        """
        today = business_today()
        if last < today:
            return 0
        generated_planned = set(
            self.db.scalars(
                select(Order.recurring_planned_date).where(
                    Order.recurring_contract_id == contract.id,
                    Order.recurring_planned_date >= first,
                    Order.recurring_planned_date <= last,
                )
            )
        )
        return sum(
            1
            for _seq, due in iter_due_dates(self._recurring._spec(contract), until=last)
            if first <= due <= last and due >= today and due not in generated_planned
        )

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
