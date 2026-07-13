from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.constants import TimelineEventType
from app.models.order import Order
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

    def latest_event(
        self,
        *,
        order_id: str,
        event_type: TimelineEventType,
    ) -> OrderTimeline | None:
        stmt = (
            select(OrderTimeline)
            .where(
                OrderTimeline.order_id == order_id,
                OrderTimeline.event_type == event_type,
            )
            .order_by(OrderTimeline.created_at.desc(), OrderTimeline.id.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def latest_accepted_as_created_at(
        self,
        *,
        order_id: str,
        active_as_request_id: str | None,
    ) -> datetime | None:
        for event in reversed(self.list_for_order(order_id)):
            metadata = event.event_metadata or {}
            if event.event_type != TimelineEventType.AS_REQUESTED:
                continue
            if metadata.get("source") == "customer":
                continue
            if active_as_request_id and metadata.get("as_request_id") != active_as_request_id:
                continue
            return event.created_at
        return None

    def list_admin_notification_candidates(
        self,
        *,
        limit: int,
        offset: int = 0,
    ) -> list[tuple[OrderTimeline, Order]]:
        stmt = (
            select(OrderTimeline, Order)
            .join(Order, Order.id == OrderTimeline.order_id)
            .where(Order.deleted_at.is_(None))
            .order_by(OrderTimeline.created_at.desc(), OrderTimeline.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.db.execute(stmt).all())
