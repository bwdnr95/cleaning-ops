from datetime import datetime

from app.domain.constants import MessageChannel, MessageStatus, MessageType, RecipientType
from app.schemas.common import ApiModel


class MessageSendRequest(ApiModel):
    order_id: str
    message_type: MessageType
    recipient_type: RecipientType
    channel: MessageChannel = MessageChannel.SMS


class MessageLogRead(ApiModel):
    id: str
    order_id: str
    recipient_type: RecipientType
    recipient_name: str
    recipient_phone: str
    message_type: MessageType
    channel: MessageChannel
    content: str
    status: MessageStatus
    error_message: str | None = None
    sent_at: datetime | None = None
    created_at: datetime | None = None
