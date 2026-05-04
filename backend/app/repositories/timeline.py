from sqlalchemy import select
from sqlalchemy.orm import Session

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
