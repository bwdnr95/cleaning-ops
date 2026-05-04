from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
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
    message_type: Mapped[MessageType] = mapped_column(String(80), index=True)
    channel: Mapped[MessageChannel] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[MessageStatus] = mapped_column(String(20), index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
