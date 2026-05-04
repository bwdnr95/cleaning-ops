from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.constants import OrderStatus
from app.models.base import Base, TimestampMixin


class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[OrderStatus] = mapped_column(String(40), default=OrderStatus.NEW, index=True)
    received_date: Mapped[date] = mapped_column(Date, index=True)
    scheduled_date: Mapped[date | None] = mapped_column(Date, index=True)
    requested_time: Mapped[str | None] = mapped_column(String(80))
    partner_id: Mapped[str | None] = mapped_column(ForeignKey("partners.id"), index=True)
    team_name: Mapped[str | None] = mapped_column(String(120))
    service_category_id: Mapped[str | None] = mapped_column(ForeignKey("service_categories.id"))
    service_item_id: Mapped[str | None] = mapped_column(ForeignKey("service_items.id"))
    service_name: Mapped[str] = mapped_column(String(160))
    size_or_quantity: Mapped[str | None] = mapped_column(String(80))
    service_detail: Mapped[str | None] = mapped_column(Text)
    special_request: Mapped[str | None] = mapped_column(Text)
    source_channel: Mapped[str | None] = mapped_column(String(120))
    customer_name: Mapped[str] = mapped_column(String(80), index=True)
    customer_phone: Mapped[str] = mapped_column(String(30), index=True)
    customer_address: Mapped[str] = mapped_column(Text)
    total_amount: Mapped[float | None] = mapped_column(Numeric(12, 2))
    deposit_amount: Mapped[float | None] = mapped_column(Numeric(12, 2))
    balance_amount: Mapped[float | None] = mapped_column(Numeric(12, 2))
    onsite_extra_amount: Mapped[float | None] = mapped_column(Numeric(12, 2))
    vat_type: Mapped[str | None] = mapped_column(String(20))
    payment_status: Mapped[str | None] = mapped_column(String(40), index=True)
    payment_memo: Mapped[str | None] = mapped_column(Text)
    evidence_memo: Mapped[str | None] = mapped_column(Text)
    partner_payment_amount: Mapped[float | None] = mapped_column(Numeric(12, 2))
    partner_payment_status: Mapped[str | None] = mapped_column(String(40))
    customer_token: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    customer_visible_payment: Mapped[bool] = mapped_column(Boolean, default=False)
