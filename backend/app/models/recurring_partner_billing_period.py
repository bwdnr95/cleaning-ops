from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class RecurringPartnerBillingPeriod(TimestampMixin, Base):
    __tablename__ = "recurring_partner_billing_periods"

    contract_id: Mapped[str] = mapped_column(
        ForeignKey("recurring_contracts.id"),
        primary_key=True,
    )
    effective_month: Mapped[str] = mapped_column(String(7), primary_key=True)
    partner_id: Mapped[str | None] = mapped_column(ForeignKey("partners.id"))
    billing_mode: Mapped[str] = mapped_column(String(20))
    partner_payment_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
