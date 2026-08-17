from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.order import Order


class OrderVisit(TimestampMixin, Base):
    __tablename__ = "order_visits"
    __table_args__ = (
        UniqueConstraint("order_id", "visit_date", name="uq_order_visits_order_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    visit_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    order: Mapped["Order"] = relationship(back_populates="visits")
