from datetime import datetime

from app.domain.constants import MessageChannel, MessageStatus, MessageType, PhotoType, RecipientType
from app.schemas.common import ApiModel


class DashboardSummary(ApiModel):
    today_jobs: int
    tomorrow_notice_targets: int
    partner_pending: int
    photo_review_pending: int
    customer_delivery_needed: int
    payment_check_needed: int
    monthly_completed: int
    monthly_revenue: float


class DashboardRecentPhoto(ApiModel):
    photo_id: str
    order_id: str
    photo_type: PhotoType
    file_url: str
    file_name: str | None = None
    is_customer_visible: bool
    uploaded_at: datetime | None = None
    service_name: str
    size_or_quantity: str | None = None
    customer_name: str
    team_name: str | None = None


class DashboardRecentMessage(ApiModel):
    id: str
    order_id: str
    message_type: MessageType
    recipient_type: RecipientType
    recipient_name: str
    recipient_phone: str
    channel: MessageChannel
    status: MessageStatus
    sent_at: datetime | None = None
    created_at: datetime | None = None
    service_name: str


class DashboardRecentActivity(ApiModel):
    photos: list[DashboardRecentPhoto]
    messages: list[DashboardRecentMessage]
