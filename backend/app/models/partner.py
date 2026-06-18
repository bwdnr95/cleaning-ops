from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PartnerCategory(TimestampMixin, Base):
    __tablename__ = "partner_categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Partner(TimestampMixin, Base):
    __tablename__ = "partners"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    partner_category_id: Mapped[str | None] = mapped_column(
        ForeignKey("partner_categories.id"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), index=True)
    manager_name: Mapped[str | None] = mapped_column(String(80))
    phone: Mapped[str] = mapped_column(String(30))
    # 담당자 연락처(정산 안내 수신용). 대표 연락처(phone)와 별개.
    manager_phone: Mapped[str | None] = mapped_column(String(30))
    service_areas: Mapped[str | None] = mapped_column(Text)
    available_services: Mapped[str | None] = mapped_column(Text)
    memo: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
