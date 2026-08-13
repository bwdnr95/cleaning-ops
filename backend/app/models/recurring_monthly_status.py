from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, UniqueConstraint
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
    partner_payment_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    retained_partner_id: Mapped[str | None] = mapped_column(ForeignKey("partners.id"))
    retained_partner_payment_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
