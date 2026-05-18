from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class OrderGroup(TimestampMixin, Base):
    __tablename__ = "order_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_token: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(80), index=True)
    customer_phone: Mapped[str] = mapped_column(String(30), index=True)
    customer_address: Mapped[str] = mapped_column(Text)
    source_channel: Mapped[str | None] = mapped_column(String(120))
    customer_visible_payment: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
