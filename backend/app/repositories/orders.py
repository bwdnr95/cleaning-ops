from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.time import business_today
from app.domain.constants import OrderStatus
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
        if not include_past_paid:
            stmt = stmt.where(
                or_(
                    Order.scheduled_date.is_(None),
                    Order.scheduled_date >= today,
                    Order.payment_status.in_(OVERDUE_UNPAID_PAYMENT_STATUSES),
                )
            )
        rows = list(self.db.scalars(stmt))

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
        # 달력에는 취소건을 기본 숨김(카운트 정의와 일치). 기록은 주문목록 '취소' 탭에서 확인.
        stmt = (
            select(Order)
            .where(
                Order.deleted_at.is_(None),
                Order.status != OrderStatus.CANCELLED,
                Order.scheduled_date >= start_date,
                Order.scheduled_date <= end_date,
            )
            .order_by(Order.scheduled_date.asc(), Order.requested_time.asc().nulls_last(), Order.id.asc())
        )
        if partner_id:
            stmt = stmt.where(Order.partner_id == partner_id)
        return list(self.db.scalars(stmt))

    def list_for_partner(self, partner_id: str) -> list[Order]:
        # 협력사 작업목록에도 취소건은 기본 숨김.
        stmt = (
            select(Order)
            .where(
                Order.deleted_at.is_(None),
                Order.partner_id == partner_id,
                Order.status != OrderStatus.CANCELLED,
            )
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

    def list_by_ids_preserving_order(self, order_ids: list[str]) -> list[Order]:
        if not order_ids:
            return []
        unique_ids = list(dict.fromkeys(order_ids))
        stmt = select(Order).where(Order.deleted_at.is_(None), Order.id.in_(unique_ids))
        orders_by_id = {order.id: order for order in self.db.scalars(stmt)}
        return [orders_by_id[order_id] for order_id in order_ids if order_id in orders_by_id]

    def count_scheduled_on(self, target: date) -> int:
        stmt = select(func.count(Order.id)).where(
            Order.deleted_at.is_(None),
            Order.scheduled_date == target,
        )
        return int(self.db.scalar(stmt) or 0)

    def list_day_before_notice_candidates(
        self,
        *,
        target_date: date,
        statuses: set[str],
    ) -> list[Order]:
        stmt = (
            select(Order)
            .where(
                Order.deleted_at.is_(None),
                Order.scheduled_date == target_date,
                Order.status.in_(statuses),
            )
            .order_by(Order.requested_time.asc().nulls_last(), Order.id.asc())
        )
        return list(self.db.scalars(stmt))


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
    if scheduled_date is not None and scheduled_date >= today:
        group = 0  # 오늘·미래 방문예정
    elif scheduled_date is None:
        group = 1  # 미정(신규접수/일정 미확정)
    elif is_overdue_unpaid_order(order, today):
        group = 2  # 과거 일정 중 잔금 미완납
    else:
        group = 3  # 과거 완납

    ordinal = scheduled_date.toordinal() if scheduled_date else 0
    if group == 0 and reverse_visit and scheduled_date is not None:
        ordinal = -ordinal
    if group in {2, 3} and scheduled_date is not None:
        ordinal = -ordinal
    return (group, ordinal, order.id)


def order_received_sort_key(order: Order, *, reverse_received: bool) -> tuple:
    if order.received_date is None:
        return (1, 0, order.id)
    ordinal = order.received_date.toordinal()
    return (0, -ordinal if reverse_received else ordinal, order.id)
