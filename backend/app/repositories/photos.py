from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.photo import OrderPhoto
from app.repositories.base import Repository


class PhotoRepository(Repository[OrderPhoto]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, OrderPhoto)

    def list_for_order(self, order_id: str, *, customer_visible_only: bool = False) -> list[OrderPhoto]:
        stmt = select(OrderPhoto).where(OrderPhoto.order_id == order_id)
        if customer_visible_only:
            stmt = stmt.where(OrderPhoto.is_customer_visible.is_(True))
        stmt = stmt.order_by(OrderPhoto.photo_type.asc(), OrderPhoto.created_at.asc(), OrderPhoto.id.asc())
        return list(self.db.scalars(stmt))

    def list_review_queue(self) -> list[tuple[Order, list[OrderPhoto]]]:
        stmt = (
            select(Order, OrderPhoto)
            .join(OrderPhoto, OrderPhoto.order_id == Order.id)
            .where(OrderPhoto.is_customer_visible.is_(False))
            .order_by(OrderPhoto.created_at.asc(), OrderPhoto.id.asc())
        )
        grouped: dict[str, tuple[Order, list[OrderPhoto]]] = {}
        for order, photo in self.db.execute(stmt):
            if order.id not in grouped:
                grouped[order.id] = (order, [])
            grouped[order.id][1].append(photo)
        return list(grouped.values())
