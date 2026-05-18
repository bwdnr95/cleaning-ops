from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.domain.constants import OrderStatus
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

    def count_visible_for_order(self, order_id: str) -> int:
        return self.db.execute(
            select(func.count(OrderPhoto.id)).where(
                OrderPhoto.order_id == order_id,
                OrderPhoto.is_customer_visible.is_(True),
            )
        ).scalar_one()

    def list_review_queue(self) -> list[tuple[Order, list[OrderPhoto], int]]:
        stmt = (
            select(Order)
            .join(OrderPhoto, OrderPhoto.order_id == Order.id)
            .where(
                or_(
                    OrderPhoto.is_customer_visible.is_(False),
                    Order.status == OrderStatus.CUSTOMER_DELIVERY_NEEDED,
                    Order.status == OrderStatus.CUSTOMER_DELIVERY_DONE,
                )
            )
            .distinct()
            .order_by(Order.scheduled_date.asc().nulls_last(), Order.id.asc())
        )
        items: list[tuple[Order, list[OrderPhoto], int]] = []
        for order in self.db.scalars(stmt):
            all_photos = self.list_for_order(order.id)
            pending_photos = [photo for photo in all_photos if not photo.is_customer_visible]
            approved_count = len(all_photos) - len(pending_photos)
            if pending_photos or (order.status in {OrderStatus.CUSTOMER_DELIVERY_NEEDED, OrderStatus.CUSTOMER_DELIVERY_DONE} and approved_count > 0):
                items.append((order, all_photos, approved_count))
        return items
