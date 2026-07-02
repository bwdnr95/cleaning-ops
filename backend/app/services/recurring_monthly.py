from __future__ import annotations

from calendar import monthrange
from datetime import date
from uuid import uuid4

from sqlalchemy import func, select
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
            tax_invoice_issued=False, balance_paid=False,
        )
        self.statuses.add(status)
        return status

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
            tax_invoice_issued=status.tax_invoice_issued,
            balance_paid=status.balance_paid,
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
            return amount * billable
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

    def list_month(self, month: str) -> list[RecurringMonthlyRowRead]:
        first, last = _month_bounds(month)
        created = False
        rows: list[RecurringMonthlyRowRead] = []
        for contract in self.contracts.list_active():
            if not self._active_in_month(contract, first, last):
                continue
            status = self.statuses.get_by_contract_and_month(contract.id, month)
            if status is None:
                status = self._new_status(contract.id, month)
                created = True
            rows.append(self._to_row(contract, month, status))
        if created:
            self.db.commit()
        rows.sort(key=lambda r: r.label)
        return rows

    def set_status(
        self, contract_id: str, month: str, *,
        tax_invoice_issued: bool | None = None, balance_paid: bool | None = None,
    ) -> RecurringMonthlyRowRead:
        contract = self.contracts.get(contract_id)
        if contract is None:
            raise ValueError("recurring_contract_not_found")
        status = self.statuses.get_by_contract_and_month(contract_id, month)
        if status is None:
            status = self._new_status(contract_id, month)
        if tax_invoice_issued is not None:
            status.tax_invoice_issued = tax_invoice_issued
        if balance_paid is not None:
            status.balance_paid = balance_paid
        self.db.commit()
        return self._to_row(contract, month, status)
