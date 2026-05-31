from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.time import business_today
from app.domain.payment_status import PaymentStatus
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

    def list_orders(
        self,
        *,
        limit: int | None = None,
        offset: int = 0,
        sort: str = "visit_asc",
        include_past_paid: bool = False,
    ) -> list[Order]:
        today = business_today()
        stmt = select(Order).where(Order.deleted_at.is_(None))
        rows = list(self.db.scalars(stmt))
        if not include_past_paid:
            rows = [
                order
                for order in rows
                if not (
                    order.scheduled_date is not None
                    and order.scheduled_date < today
                    and not is_overdue_unpaid_order(order, today)
                )
            ]

        if sort in {"received_asc", "received_desc"}:
            rows.sort(
                key=lambda order: order_received_sort_key(order, reverse_received=sort == "received_desc"),
            )
        else:
            reverse_visit = sort == "visit_desc"
            rows.sort(key=lambda order: order_visit_sort_key(order, today, reverse_visit=reverse_visit))
        if offset:
            rows = rows[offset:]
        if limit is not None:
            rows = rows[:limit]
        return rows

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


OVERDUE_UNPAID_PAYMENT_STATUSES: tuple[str, ...] = (
    PaymentStatus.UNPAID,
    PaymentStatus.PENDING,
    PaymentStatus.BALANCE_PENDING,
    PaymentStatus.DEPOSIT_PAID,
)


def is_overdue_unpaid_order(order: Order, today: date) -> bool:
    return (
        order.scheduled_date is not None
        and order.scheduled_date < today
        and order.payment_status in OVERDUE_UNPAID_PAYMENT_STATUSES
    )


def order_visit_sort_key(order: Order, today: date, *, reverse_visit: bool) -> tuple:
    scheduled_date = order.scheduled_date
    if is_overdue_unpaid_order(order, today):
        group = 0
    elif scheduled_date is None or scheduled_date >= today:
        group = 1
    else:
        group = 2

    ordinal = scheduled_date.toordinal() if scheduled_date else 99999999
    if group in {1, 2} and reverse_visit and scheduled_date is not None:
        ordinal = -ordinal
    if group == 2 and not reverse_visit and scheduled_date is not None:
        ordinal = -ordinal
    return (group, ordinal, order.id)


def order_received_sort_key(order: Order, *, reverse_received: bool) -> tuple:
    if order.received_date is None:
        return (1, 0, order.id)
    ordinal = order.received_date.toordinal()
    return (0, -ordinal if reverse_received else ordinal, order.id)
