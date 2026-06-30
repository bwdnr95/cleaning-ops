from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class RecurringMonthlyStatus(TimestampMixin, Base):
    __tablename__ = "recurring_monthly_status"
    __table_args__ = (
        UniqueConstraint("contract_id", "billing_month", name="uq_recurring_monthly_contract_month"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    contract_id: Mapped[str] = mapped_column(ForeignKey("recurring_contracts.id"), index=True)
    billing_month: Mapped[str] = mapped_column(String(7), index=True)  # "YYYY-MM"
    tax_invoice_issued: Mapped[bool] = mapped_column(Boolean, default=False)
    balance_paid: Mapped[bool] = mapped_column(Boolean, default=False)
