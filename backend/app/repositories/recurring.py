from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.constants import RecurringContractStatus, RecurringOccurrenceStatus
from app.models.recurring_contract import RecurringContract
from app.models.recurring_occurrence import RecurringOccurrence
from app.repositories.base import Repository


class RecurringContractRepository(Repository[RecurringContract]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, RecurringContract)

    def get(self, id_: str, *, include_deleted: bool = False) -> RecurringContract | None:
        obj = self.db.get(RecurringContract, id_)
        if obj is None:
            return None
        if obj.deleted_at is not None and not include_deleted:
            return None
        return obj

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


class RecurringOccurrenceRepository(Repository[RecurringOccurrence]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, RecurringOccurrence)

    def get(self, id_: str) -> RecurringOccurrence | None:
        return self.db.get(RecurringOccurrence, id_)

    def get_by_contract_and_due(self, contract_id: str, due_date: date) -> RecurringOccurrence | None:
        stmt = select(RecurringOccurrence).where(
            RecurringOccurrence.contract_id == contract_id,
            RecurringOccurrence.due_date == due_date,
        )
        return self.db.scalar(stmt)

    def list_by_contract(self, contract_id: str) -> list[RecurringOccurrence]:
        stmt = (
            select(RecurringOccurrence)
            .where(RecurringOccurrence.contract_id == contract_id)
            .order_by(RecurringOccurrence.due_date.asc())
        )
        return list(self.db.scalars(stmt))

    def list_pending(self) -> list[RecurringOccurrence]:
        stmt = (
            select(RecurringOccurrence)
            .where(RecurringOccurrence.status == RecurringOccurrenceStatus.PENDING)
            .order_by(RecurringOccurrence.due_date.asc())
        )
        return list(self.db.scalars(stmt))
