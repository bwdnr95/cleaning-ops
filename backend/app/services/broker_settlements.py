from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.domain.constants import OrderStatus, TimelineEventType
from app.domain.order_pricing import order_consumer_total
from app.domain.payment_status import PARTNER_SETTLEMENT_PENDING_STATUSES, PartnerPaymentStatus
from app.models.order import Order
from app.models.order_group import OrderGroup
from app.repositories.brokers import BrokerRepository
from app.repositories.order_groups import OrderGroupRepository
from app.schemas.broker import (
    BrokerSettlementActionResult,
    BrokerSettlementItemRead,
    BrokerSettlementListRead,
)
from app.services.timeline import TimelineService

# 정산 상태값은 협력사와 동일한 settlement status(unpaid/ready/paid)를 재사용한다.


def unpaid_broker_condition():
    """미정산 중개 수수료 SQL 조건(전 화면 공통).

    협력사 정산과 달리 작업 완료 요건을 두지 않는다(소개 수수료는 완료와 무관). 대신
    '중개 수수료가 0보다 크고 아직 지급완료가 아닌' 취소 아닌 주문만 미정산으로 본다
    → 미정산 목록/합계/정산가능 집합 + 프론트 isSettleable(>0)까지 모두 일치시킨다.
    (NULL·0원은 정산할 것이 없으므로 미정산에서 제외 — NULL>0/0>0 모두 false.)
    """
    return (
        (Order.status != OrderStatus.CANCELLED)
        & (Order.broker_payment_amount > 0)
        & (
            Order.broker_payment_status.is_(None)
            | Order.broker_payment_status.in_(PARTNER_SETTLEMENT_PENDING_STATUSES)
        )
    )


class BrokerSettlementService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.brokers = BrokerRepository(db)
        self.groups = OrderGroupRepository(db)
        self.timeline = TimelineService(db)

    def list_settlements(
        self,
        *,
        broker_id: str,
        status: str = "unpaid",
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> BrokerSettlementListRead:
        self._require_broker(broker_id)
        orders = self._list_orders(
            broker_id=broker_id, status=status, from_date=from_date, to_date=to_date
        )
        groups_by_id = self.groups.list_by_ids(order.group_id for order in orders)
        # 취소건은 기록 보존을 위해 목록엔 남기되 건수/금액 집계에선 제외한다.
        countable = [order for order in orders if order.status != OrderStatus.CANCELLED]
        total_broker_price = sum(
            (money_decimal(order.broker_payment_amount) for order in countable), Decimal("0")
        )
        total_consumer_price = sum(
            (order_consumer_total(order) for order in countable), Decimal("0")
        )
        items = [
            to_broker_settlement_item(order, group=groups_by_id.get(order.group_id))
            for order in orders
        ]
        return BrokerSettlementListRead(
            items=items,
            total_broker_price=float(total_broker_price),
            total_consumer_price=float(total_consumer_price),
            count=len(countable),
        )

    def settle(
        self, *, broker_id: str, order_ids: list[str], actor_user_id: str, memo: str | None = None
    ) -> BrokerSettlementActionResult:
        self._require_broker(broker_id)
        orders = self._lock_orders(broker_id=broker_id, order_ids=order_ids, action="settle")
        now = utc_now()
        for order in orders:
            order.broker_payment_status = PartnerPaymentStatus.PAID
            order.broker_settled_at = now
            self.timeline.record(
                order_id=order.id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.BROKER_SETTLED,
                title="중개사 정산 완료",
                description=memo,
                metadata={"broker_id": broker_id, "settled_at": now.isoformat()},
            )
        return BrokerSettlementActionResult(
            updated_order_ids=[order.id for order in orders], skipped_order_ids=[]
        )

    def revert(
        self, *, broker_id: str, order_ids: list[str], actor_user_id: str
    ) -> BrokerSettlementActionResult:
        self._require_broker(broker_id)
        orders = self._lock_orders(broker_id=broker_id, order_ids=order_ids, action="revert")
        for order in orders:
            order.broker_payment_status = PartnerPaymentStatus.UNPAID
            order.broker_settled_at = None
            self.timeline.record(
                order_id=order.id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.BROKER_SETTLEMENT_REVERTED,
                title="중개사 정산 되돌리기",
                metadata={"broker_id": broker_id},
            )
        return BrokerSettlementActionResult(
            updated_order_ids=[order.id for order in orders], skipped_order_ids=[]
        )

    def _require_broker(self, broker_id: str) -> None:
        broker = self.brokers.get(broker_id)
        if broker is None:
            raise ValueError("broker_not_found")
        if not broker.is_active:
            raise ValueError("broker_inactive")

    def _list_orders(
        self, *, broker_id: str, status: str, from_date: date | None, to_date: date | None
    ) -> list[Order]:
        stmt = (
            select(Order)
            .where(Order.broker_id == broker_id, Order.deleted_at.is_(None))
            .order_by(Order.scheduled_date.desc().nulls_last(), Order.id.desc())
        )
        if from_date is not None:
            stmt = stmt.where(Order.scheduled_date >= from_date)
        if to_date is not None:
            stmt = stmt.where(Order.scheduled_date <= to_date)
        if status == "unpaid":
            stmt = stmt.where(unpaid_broker_condition())
        elif status == "paid":
            stmt = stmt.where(
                Order.status != OrderStatus.CANCELLED,
                Order.broker_payment_status == PartnerPaymentStatus.PAID,
            )
        elif status == "all":
            # '전체'는 이 중개사가 소개한 모든 주문(상태 무관, 취소 포함)을 보여준다.
            pass
        else:
            raise ValueError("invalid_settlement_status")
        return list(self.db.scalars(stmt))

    def _lock_orders(self, *, broker_id: str, order_ids: list[str], action: str) -> list[Order]:
        if not order_ids:
            return []
        requested_ids = list(dict.fromkeys(order_ids))
        stmt = (
            select(Order)
            .where(Order.id.in_(requested_ids), Order.deleted_at.is_(None))
            .with_for_update()
        )
        orders = list(self.db.scalars(stmt))
        by_id = {order.id: order for order in orders}
        if any(order_id not in by_id for order_id in requested_ids):
            raise ValueError("settlement_order_not_found")
        if any(order.broker_id != broker_id for order in orders):
            raise ValueError("settlement_order_broker_mismatch")
        if action == "settle" and any(not is_unpaid_broker_order(order) for order in orders):
            raise ValueError("invalid_settlement_order")
        if action == "revert" and any(not is_revertible_broker_order(order) for order in orders):
            raise ValueError("invalid_settlement_order")
        if action not in {"settle", "revert"}:
            raise ValueError("invalid_settlement_action")
        return [by_id[order_id] for order_id in requested_ids]


def to_broker_settlement_item(
    order: Order, *, group: OrderGroup | None = None
) -> BrokerSettlementItemRead:
    base_address = (group.customer_address if group else None) or order.customer_address or ""
    address_detail = group.customer_address_detail if group else None
    return BrokerSettlementItemRead(
        order_id=order.id,
        status=order.status,
        scheduled_date=order.scheduled_date,
        service_name=order.service_name,
        customer_name=order.customer_name or "",
        address_short=base_address,
        address_detail=address_detail,
        consumer_price=float(order_consumer_total(order)),
        broker_price=float(order.broker_payment_amount or 0),
        broker_payment_status=order.broker_payment_status,
        settled_at=order.broker_settled_at,
    )


def is_unpaid_broker_order(order: Order) -> bool:
    # 미정산 가시성(unpaid_broker_condition)과 동일 기준: 수수료 > 0 + 미지급 + 취소 아님.
    return (
        order.deleted_at is None
        and order.status != OrderStatus.CANCELLED
        and (order.broker_payment_amount or 0) > 0
        and (
            order.broker_payment_status is None
            or order.broker_payment_status in PARTNER_SETTLEMENT_PENDING_STATUSES
        )
    )


def is_revertible_broker_order(order: Order) -> bool:
    # 정산완료 목록(취소 제외)과 일치시켜, '정산 제외'로 표시된 취소건의 되돌리기를 막는다.
    return (
        order.deleted_at is None
        and order.status != OrderStatus.CANCELLED
        and order.broker_payment_status == PartnerPaymentStatus.PAID
    )


def money_decimal(value: object) -> Decimal:
    return Decimal(str(value or 0))
