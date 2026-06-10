from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.constants import UserRole
from app.models.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"
    # login_phone(=phone) 중복 시 협력사 로그인이 엉뚱한 계정으로 인증되는 것을 막는다.
    # NULL/빈 문자열(미연결 계정)은 부분 인덱스 조건으로 제외한다. (migration 0012)
    __table_args__ = (
        Index(
            "uq_users_phone",
            "phone",
            unique=True,
            postgresql_where=text("phone IS NOT NULL AND phone <> ''"),
            sqlite_where=text("phone IS NOT NULL AND phone <> ''"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    role: Mapped[UserRole] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    phone: Mapped[str | None] = mapped_column(String(30))
    password_hash: Mapped[str] = mapped_column(String(255))
    partner_id: Mapped[str | None] = mapped_column(ForeignKey("partners.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
