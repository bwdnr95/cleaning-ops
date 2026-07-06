from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.constants import TimelineEventType
from app.models.timeline import OrderTimeline
from app.repositories.base import Repository


class TimelineRepository(Repository[OrderTimeline]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, OrderTimeline)

    def list_for_order(self, order_id: str) -> list[OrderTimeline]:
        stmt = (
            select(OrderTimeline)
            .where(OrderTimeline.order_id == order_id)
            .order_by(OrderTimeline.created_at.asc(), OrderTimeline.id.asc())
        )
        return list(self.db.scalars(stmt))

    def latest_created_at(
        self,
        *,
        order_id: str,
        event_type: TimelineEventType,
    ) -> datetime | None:
        stmt = (
            select(OrderTimeline.created_at)
            .where(
                OrderTimeline.order_id == order_id,
                OrderTimeline.event_type == event_type,
            )
            .order_by(OrderTimeline.created_at.desc(), OrderTimeline.id.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)
