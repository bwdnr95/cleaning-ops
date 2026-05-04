from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TimelineEventRead(ApiModel):
    id: str
    order_id: str
    actor_user_id: str | None = None
    event_type: str
    title: str
    description: str | None = None
    event_metadata: dict | None = None
    created_at: datetime | None = None
