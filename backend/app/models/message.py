from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.constants import MessageChannel, MessageStatus, MessageType, RecipientType
from app.models.base import Base, CreatedAtMixin


class MessageLog(CreatedAtMixin, Base):
    __tablename__ = "message_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    recipient_type: Mapped[RecipientType] = mapped_column(String(20), index=True)
    recipient_name: Mapped[str] = mapped_column(String(80))
    recipient_phone: Mapped[str] = mapped_column(String(30))
    # 협력사 수신 메시지의 '받는 협력사' 식별자(발송 시점 order.partner_id).
    # 전화번호 대신 이 값으로 스코프해 공유 전화번호/재배정 시 협력사 간 누출을 막는다.
    recipient_partner_id: Mapped[str | None] = mapped_column(String(36), index=True)
    message_type: Mapped[MessageType] = mapped_column(String(80), index=True)
    channel: Mapped[MessageChannel] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[MessageStatus] = mapped_column(String(20), index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(String(40), index=True, default="mock")
    provider_message_id: Mapped[str | None] = mapped_column(String(160))
    provider_group_id: Mapped[str | None] = mapped_column(String(160), index=True)
    provider_error_code: Mapped[str | None] = mapped_column(String(80))
    provider_status_code: Mapped[str | None] = mapped_column(String(80))
    provider_status_message: Mapped[str | None] = mapped_column(String(255))
    provider_response: Mapped[dict[str, object] | None] = mapped_column(JSON)
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
