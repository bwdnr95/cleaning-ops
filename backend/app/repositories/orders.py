from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.time import business_today
from app.domain.constants import OrderStatus
from app.domain.payment_status import PaymentStatus
from app.models.order import Order
from app.models.order_visit import OrderVisit
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
        stmt = select(Order).where(
            Order.deleted_at.is_(None),
            Order.recurring_contract_id.is_(None),
        )
        if not include_past_paid:
            stmt = stmt.where(
                or_(
                    Order.scheduled_date.is_(None),
                    Order.scheduled_date >= today,
                    Order.visits.any(OrderVisit.visit_date >= today),
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
    ) -> list["OrderVisitOccurrence"]:
        # 달력에는 취소건을 기본 숨김(카운트 정의와 일치). 기록은 주문목록 '취소' 탭에서 확인.
        stmt = (
            select(Order)
            .where(
                Order.deleted_at.is_(None),
                Order.status != OrderStatus.CANCELLED,
                or_(
                    Order.scheduled_date.between(start_date, end_date),
                    Order.visits.any(OrderVisit.visit_date.between(start_date, end_date)),
                ),
            )
        )
        if partner_id:
            stmt = stmt.where(Order.partner_id == partner_id)
        occurrences: list[OrderVisitOccurrence] = []
        for order in self.db.scalars(stmt):
            visit_ids = {visit.visit_date: visit.id for visit in order.visits}
            for visit_date in order.visit_dates:
                if start_date <= visit_date <= end_date:
                    occurrences.append(
                        OrderVisitOccurrence(
                            order=order,
                            visit_id=visit_ids.get(
                                visit_date,
                                f"legacy:{order.id}:{visit_date.isoformat()}",
                            ),
                            visit_date=visit_date,
                        )
                    )
        occurrences.sort(
            key=lambda row: (
                row.visit_date,
                row.order.requested_time or "",
                row.order.id,
            )
        )
        return occurrences

    def list_for_partner(self, partner_id: str) -> list[Order]:
        # 협력사 작업목록에도 취소건은 기본 숨김.
        stmt = select(Order).where(
            Order.deleted_at.is_(None),
            Order.partner_id == partner_id,
            Order.status != OrderStatus.CANCELLED,
        )
        rows = list(self.db.scalars(stmt))
        today = business_today()
        rows.sort(key=lambda order: order_visit_sort_key(order, today, reverse_visit=False))
        return rows

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
            or_(
                Order.scheduled_date == target,
                Order.visits.any(OrderVisit.visit_date == target),
            ),
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
                or_(
                    Order.scheduled_date == target_date,
                    Order.visits.any(OrderVisit.visit_date == target_date),
                ),
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


@dataclass(frozen=True)
class OrderVisitOccurrence:
    order: Order
    visit_id: str
    visit_date: date


def is_overdue_unpaid_order(order: Order, today: date) -> bool:
    last_visit_date = order.visit_dates[-1] if order.visit_dates else None
    return (
        last_visit_date is not None
        and last_visit_date < today
        and order.payment_status in OVERDUE_UNPAID_PAYMENT_STATUSES
    )


def order_visit_sort_key(order: Order, today: date, *, reverse_visit: bool) -> tuple:
    visit_dates = order.visit_dates
    future_dates = [visit_date for visit_date in visit_dates if visit_date >= today]
    sort_date = (
        min(future_dates)
        if future_dates
        else (visit_dates[-1] if visit_dates else None)
    )
    if future_dates:
        group = 0  # 오늘·미래 방문예정
    elif sort_date is None:
        group = 1  # 미정(신규접수/일정 미확정)
    elif is_overdue_unpaid_order(order, today):
        group = 2  # 과거 일정 중 잔금 미완납
    else:
        group = 3  # 과거 완납

    ordinal = sort_date.toordinal() if sort_date else 0
    if reverse_visit and sort_date is not None:
        ordinal = -ordinal
    return (group, ordinal, order.id)


def order_received_sort_key(order: Order, *, reverse_received: bool) -> tuple:
    if order.received_date is None:
        return (1, 0, order.id)
    ordinal = order.received_date.toordinal()
    return (0, -ordinal if reverse_received else ordinal, order.id)
