from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.constants import RecurringContractStatus
from app.models.recurring_contract import RecurringContract
from app.models.recurring_monthly_status import RecurringMonthlyStatus
from app.repositories.base import Repository


class RecurringContractRepository(Repository[RecurringContract]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, RecurringContract)

    def get(self, contract_id: str, *, include_deleted: bool = False) -> RecurringContract | None:
        obj = self.db.get(RecurringContract, contract_id)
        if obj is None:
            return None
        if obj.deleted_at is not None and not include_deleted:
            return None
        return obj

    def get_for_update(
        self,
        contract_id: str,
        *,
        include_deleted: bool = False,
    ) -> RecurringContract | None:
        stmt = (
            select(RecurringContract)
            .where(RecurringContract.id == contract_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        obj = self.db.scalar(stmt)
        if obj is None:
            return None
        if obj.deleted_at is not None and not include_deleted:
            return None
        return obj

    def lock_ids(self, contract_ids: list[str]) -> list[RecurringContract]:
        ids = sorted(set(contract_ids))
        if not ids:
            return []
        stmt = (
            select(RecurringContract)
            .where(RecurringContract.id.in_(ids))
            .order_by(RecurringContract.id.asc())
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return list(self.db.scalars(stmt))

    def list_all(self) -> list[RecurringContract]:
        stmt = (
            select(RecurringContract)
            .where(RecurringContract.deleted_at.is_(None))
            .order_by(RecurringContract.created_at.desc())
        )
        return list(self.db.scalars(stmt))

    def list_active(self) -> list[RecurringContract]:
        stmt = select(RecurringContract).where(
            RecurringContract.deleted_at.is_(None),
            RecurringContract.status == RecurringContractStatus.ACTIVE,
        )
        return list(self.db.scalars(stmt))


class RecurringMonthlyStatusRepository(Repository[RecurringMonthlyStatus]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, RecurringMonthlyStatus)

    def get_by_contract_and_month(self, contract_id: str, billing_month: str) -> RecurringMonthlyStatus | None:
        stmt = select(RecurringMonthlyStatus).where(
            RecurringMonthlyStatus.contract_id == contract_id,
            RecurringMonthlyStatus.billing_month == billing_month,
        )
        return self.db.scalar(stmt)

    def get_for_update(
        self,
        contract_id: str,
        billing_month: str,
    ) -> RecurringMonthlyStatus | None:
        stmt = (
            select(RecurringMonthlyStatus)
            .where(
                RecurringMonthlyStatus.contract_id == contract_id,
                RecurringMonthlyStatus.billing_month == billing_month,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return self.db.scalar(stmt)

    def list_by_month(self, billing_month: str) -> list[RecurringMonthlyStatus]:
        stmt = select(RecurringMonthlyStatus).where(RecurringMonthlyStatus.billing_month == billing_month)
        return list(self.db.scalars(stmt))
