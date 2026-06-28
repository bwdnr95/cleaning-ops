from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.constants import RecurringOccurrenceStatus
from app.models.base import Base, TimestampMixin


class RecurringOccurrence(TimestampMixin, Base):
    __tablename__ = "recurring_occurrences"
    __table_args__ = (UniqueConstraint("contract_id", "due_date", name="uq_recurring_occurrence_contract_due"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    contract_id: Mapped[str] = mapped_column(ForeignKey("recurring_contracts.id"), index=True)
    sequence_no: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    billing_month: Mapped[str] = mapped_column(String(7))  # "YYYY-MM" — B 연결고리
    status: Mapped[str] = mapped_column(String(20), default=RecurringOccurrenceStatus.PENDING, index=True)
    generated_order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    skipped_reason: Mapped[str | None] = mapped_column(String(200))
