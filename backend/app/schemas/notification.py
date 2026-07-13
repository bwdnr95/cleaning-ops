from datetime import datetime

from app.schemas.common import ApiModel


class AdminNotificationRead(ApiModel):
    id: str
    order_id: str
    event_type: str
    title: str
    description: str | None = None
    created_at: datetime | None = None
    service_name: str
    customer_name: str
    actor_label: str
