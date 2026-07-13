from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.domain.constants import MessageChannel, MessageStatus, MessageType, RecipientType
from app.schemas.common import ApiModel


class MessageSendRequest(ApiModel):
    order_id: str
    message_type: MessageType
    recipient_type: RecipientType
    channel: MessageChannel | None = None
    memo: str | None = Field(default=None, max_length=2000)


class MessageUnknownOutcomeResolutionRequest(ApiModel):
    resolution: Literal["confirmed_sent", "confirmed_not_sent"]


class MessageLogRead(ApiModel):
    id: str
    order_id: str
    order_customer_name: str | None = None
    recipient_type: RecipientType
    recipient_name: str
    recipient_phone: str
    message_type: MessageType
    channel: MessageChannel
    content: str
    status: MessageStatus
    error_message: str | None = None
    provider: str | None = None
    provider_message_id: str | None = None
    provider_group_id: str | None = None
    provider_error_code: str | None = None
    provider_status_code: str | None = None
    provider_status_message: str | None = None
    provider_response: dict[str, object] | None = Field(default=None, exclude=True)
    requested_at: datetime | None = None
    provider_reported_at: datetime | None = None
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    created_at: datetime | None = None


class PartnerMessageRead(ApiModel):
    id: str
    message_type: MessageType
    channel: MessageChannel
    content: str
    status: MessageStatus
    sent_at: datetime | None = None
    created_at: datetime | None = None


class MessagePreviewRead(ApiModel):
    order_id: str
    message_type: MessageType
    recipient_type: RecipientType
    recipient_name: str
    recipient_phone: str
    channel: MessageChannel
    content: str
    kakao_template_id: str | None = None
    kakao_variables: dict[str, str] | None = None
    fallback_sms_content: str | None = None
    kakao_channel_id_configured: bool = False
    kakao_template_configured: bool = False
    fallback_sms_enabled: bool = False
    can_send: bool = True
    warnings: list[str] = Field(default_factory=list)


class MessageSettingsRead(ApiModel):
    provider: str
    kakao_channel_url: str | None = None
    solapi_credentials_configured: bool
    solapi_sender_configured: bool
    solapi_webhook_configured: bool
    kakao_channel_id_configured: bool
    kakao_templates_configured: dict[str, bool] = Field(default_factory=dict)
    alimtalk_fallback_sms: bool
    can_send_sms: bool
    can_send_alimtalk: bool
    warnings: list[str] = Field(default_factory=list)


class DayBeforeNoticeRunRead(ApiModel):
    target_date: date
    scanned: int
    sent: int
    skipped_already_sent: int
    failed: int
    skipped_unconfirmed: int = 0
    retryable: int = 0
    sent_order_ids: list[str] = Field(default_factory=list)
    skipped_order_ids: list[str] = Field(default_factory=list)
    unconfirmed_order_ids: list[str] = Field(default_factory=list)
    failed_order_ids: list[str] = Field(default_factory=list)
    retryable_order_ids: list[str] = Field(default_factory=list)
