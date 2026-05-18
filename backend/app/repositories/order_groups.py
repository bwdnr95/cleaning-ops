from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.order_group import OrderGroup
from app.repositories.base import Repository


class OrderGroupRepository(Repository[OrderGroup]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, OrderGroup)

    def get_by_customer_token(self, token: str) -> OrderGroup | None:
        stmt = select(OrderGroup).where(OrderGroup.customer_token == token)
        return self.db.scalar(stmt)

    def list_lines(self, group_id: str) -> list[Order]:
        stmt = (
            select(Order)
            .where(Order.group_id == group_id)
            .order_by(Order.created_at.asc(), Order.id.asc())
        )
        return list(self.db.scalars(stmt))
