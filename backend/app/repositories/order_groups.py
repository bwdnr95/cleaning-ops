from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.order_group import OrderGroup
from app.repositories.base import Repository


class OrderGroupRepository(Repository[OrderGroup]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, OrderGroup)

    def get(self, id_: str, *, include_deleted: bool = False) -> OrderGroup | None:
        obj = self.db.get(OrderGroup, id_)
        if obj is None:
            return None
        if obj.deleted_at is not None and not include_deleted:
            return None
        return obj

    def get_by_customer_token(self, token: str) -> OrderGroup | None:
        stmt = select(OrderGroup).where(
            OrderGroup.customer_token == token,
            OrderGroup.deleted_at.is_(None),
        )
        return self.db.scalar(stmt)

    def list_lines(self, group_id: str) -> list[Order]:
        stmt = (
            select(Order)
            .where(Order.group_id == group_id, Order.deleted_at.is_(None))
            .order_by(Order.created_at.asc(), Order.id.asc())
        )
        return list(self.db.scalars(stmt))
