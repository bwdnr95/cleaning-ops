from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.order import Order
from app.repositories.base import Repository


class OrderRepository(Repository[Order]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Order)

    def get(self, id_: str, *, include_deleted: bool = False) -> Order | None:
        obj = self.db.get(Order, id_)
        if obj is None:
            return None
        if obj.deleted_at is not None and not include_deleted:
            return None
        return obj

    def list_orders(self, *, limit: int | None = None, offset: int = 0) -> list[Order]:
        stmt = (
            select(Order)
            .where(Order.deleted_at.is_(None))
            .order_by(Order.scheduled_date.asc().nulls_last(), Order.id.asc())
        )
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
            .where(
                Order.deleted_at.is_(None),
                Order.scheduled_date >= start_date,
                Order.scheduled_date <= end_date,
            )
            .order_by(Order.scheduled_date.asc(), Order.requested_time.asc().nulls_last(), Order.id.asc())
        )
        if partner_id:
            stmt = stmt.where(Order.partner_id == partner_id)
        return list(self.db.scalars(stmt))

    def list_for_partner(self, partner_id: str) -> list[Order]:
        stmt = (
            select(Order)
            .where(Order.deleted_at.is_(None), Order.partner_id == partner_id)
            .order_by(Order.scheduled_date.asc())
        )
        return list(self.db.scalars(stmt))

    def list_by_group(self, group_id: str) -> list[Order]:
        stmt = (
            select(Order)
            .where(Order.deleted_at.is_(None), Order.group_id == group_id)
            .order_by(Order.created_at.asc(), Order.id.asc())
        )
        return list(self.db.scalars(stmt))

    def count_scheduled_on(self, target: date) -> int:
        stmt = select(func.count(Order.id)).where(
            Order.deleted_at.is_(None),
            Order.scheduled_date == target,
        )
        return int(self.db.scalar(stmt) or 0)
