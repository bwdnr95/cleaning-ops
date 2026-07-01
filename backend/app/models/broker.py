from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Broker(TimestampMixin, Base):
    """중개사(주문을 소개한 중개업체). 협력사(Partner)와 달리 로그인 계정이 없다."""

    __tablename__ = "brokers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    manager_name: Mapped[str | None] = mapped_column(String(80))
    phone: Mapped[str | None] = mapped_column(String(30))
    # 담당자 연락처. 대표 연락처(phone)와 별개.
    manager_phone: Mapped[str | None] = mapped_column(String(30))
    memo: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
