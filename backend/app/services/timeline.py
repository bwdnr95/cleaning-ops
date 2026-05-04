from uuid import uuid4

from sqlalchemy.orm import Session

from app.domain.constants import TimelineEventType
from app.models.timeline import OrderTimeline
from app.repositories.timeline import TimelineRepository


class TimelineService:
    def __init__(self, db: Session) -> None:
        self.repo = TimelineRepository(db)

    def record(
        self,
        *,
        order_id: str,
        event_type: TimelineEventType,
        title: str,
        actor_user_id: str | None = None,
        description: str | None = None,
        metadata: dict | None = None,
    ) -> OrderTimeline:
        event = OrderTimeline(
            id=str(uuid4()),
            order_id=order_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            title=title,
            description=description,
            event_metadata=metadata,
        )
        return self.repo.add(event)
