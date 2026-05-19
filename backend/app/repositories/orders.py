from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.order import Order
from app.repositories.base import Repository


class OrderRepository(Repository[Order]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Order)

    def list_orders(self, *, limit: int | None = None, offset: int = 0) -> list[Order]:
        stmt = select(Order).order_by(Order.scheduled_date.asc().nulls_last(), Order.id.asc())
        if limit is not None:
            stmt = stmt.limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def list_scheduled_between(
        self,
        start_date: date,
        end_date: date,
        *,
        partner_id: str | None = None,
    ) -> list[Order]:
        stmt = (
            select(Order)
            .where(Order.scheduled_date >= start_date, Order.scheduled_date <= end_date)
            .order_by(Order.scheduled_date.asc(), Order.requested_time.asc().nulls_last(), Order.id.asc())
        )
        if partner_id:
            stmt = stmt.where(Order.partner_id == partner_id)
        return list(self.db.scalars(stmt))

    def list_for_partner(self, partner_id: str) -> list[Order]:
        stmt = select(Order).where(Order.partner_id == partner_id).order_by(Order.scheduled_date.asc())
        return list(self.db.scalars(stmt))

    def list_by_group(self, group_id: str) -> list[Order]:
        stmt = select(Order).where(Order.group_id == group_id).order_by(Order.created_at.asc(), Order.id.asc())
        return list(self.db.scalars(stmt))

    def count_scheduled_on(self, target: date) -> int:
        stmt = select(Order).where(Order.scheduled_date == target)
        return len(list(self.db.scalars(stmt)))
