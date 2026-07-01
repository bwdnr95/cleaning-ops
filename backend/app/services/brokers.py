from dataclasses import dataclass, field
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.domain.constants import OrderStatus
from app.domain.order_metrics import REVENUE_STATUSES
from app.domain.order_pricing import order_consumer_total
from app.domain.phone import normalize_phone
from app.models.broker import Broker
from app.models.order import Order
from app.repositories.brokers import BrokerRepository
from app.schemas.broker import (
    BrokerAdminRead,
    BrokerAssignedOrderRead,
    BrokerCreate,
    BrokerDetailRead,
    BrokerUpdate,
)


@dataclass(frozen=True)
class BrokerAdminContext:
    stats: dict[str, dict[str, float | int]] = field(default_factory=dict)


class BrokerService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.brokers = BrokerRepository(db)

    def list_brokers(self, *, include_inactive: bool = False) -> list[BrokerAdminRead]:
        brokers = self.brokers.list_all() if include_inactive else self.brokers.list_active()
        context = self._build_admin_context(brokers)
        return [self.to_admin_dto(broker, context=context) for broker in brokers]

    def get_detail(self, broker_id: str) -> BrokerDetailRead:
        broker = self.brokers.get(broker_id)
        if broker is None:
            raise ValueError("broker_not_found")
        base = self.to_admin_dto(broker)
        return BrokerDetailRead(
            **base.model_dump(),
            orders=[_to_assigned_order_dto(order) for order in self._list_recent_orders(broker_id)],
        )

    def create(self, payload: BrokerCreate) -> BrokerDetailRead:
        broker = Broker(
            id=str(uuid4()),
            name=payload.name,
            manager_name=payload.manager_name,
            phone=normalize_phone(payload.phone) if payload.phone else None,
            manager_phone=normalize_phone(payload.manager_phone) if payload.manager_phone else None,
            memo=payload.memo,
            is_active=payload.is_active,
        )
        self.brokers.add(broker)
        self.db.commit()
        return self.get_detail(broker.id)

    def update(self, broker_id: str, payload: BrokerUpdate) -> BrokerDetailRead:
        broker = self.brokers.get(broker_id)
        if broker is None:
            raise ValueError("broker_not_found")

        changes = payload.model_dump(exclude_unset=True)
        for key, value in changes.items():
            if key in ("phone", "manager_phone") and value:
                value = normalize_phone(value)
            setattr(broker, key, value)

        self.db.commit()
        return self.get_detail(broker_id)

    def delete(self, broker_id: str) -> None:
        broker = self.brokers.get(broker_id)
        if broker is None:
            raise ValueError("broker_not_found")
        # 협력사와 동일: 소개 이력(주문)이 있으면 하드 삭제를 막고 비활성(is_active=False)을 유도한다.
        # soft-delete된 주문도 broker_id FK를 그대로 들고 있어(감사 보존), 카운트에 포함해야
        # Postgres FK(RESTRICT) 위반으로 인한 500 대신 명확한 broker_in_use(400)로 막을 수 있다.
        in_use = self.db.scalar(
            select(func.count()).select_from(Order).where(Order.broker_id == broker_id)
        )
        if int(in_use or 0) > 0:
            raise ValueError("broker_in_use")
        self.db.delete(broker)
        self.db.commit()

    def to_admin_dto(
        self,
        broker: Broker,
        *,
        context: BrokerAdminContext | None = None,
    ) -> BrokerAdminRead:
        stats = (
            context.stats.get(broker.id, _empty_stats())
            if context is not None
            else self._stats(broker.id)
        )
        return BrokerAdminRead(
            id=broker.id,
            name=broker.name,
            manager_name=broker.manager_name,
            phone=broker.phone,
            manager_phone=broker.manager_phone,
            memo=broker.memo,
            is_active=broker.is_active,
            created_at=broker.created_at,
            updated_at=broker.updated_at,
            order_count=int(stats["count"]),
            revenue_total=float(stats["revenue"]),
        )

    def _build_admin_context(self, brokers: list[Broker]) -> BrokerAdminContext:
        broker_ids = [broker.id for broker in brokers]
        if not broker_ids:
            return BrokerAdminContext()
        stats = {broker_id: _empty_stats() for broker_id in broker_ids}
        consumer = func.coalesce(Order.total_amount, 0) + func.coalesce(Order.onsite_extra_amount, 0)
        stmt = (
            select(
                Order.broker_id,
                # 건수: 취소 제외 소개 주문 수. 매출: 앱 표준 매출 집합(REVENUE_STATUSES)만 합산해
                # 대시보드/리포트 '매출'과 정의를 일치시킨다(미완료 파이프라인 금액 제외).
                func.coalesce(func.sum(case((Order.status != OrderStatus.CANCELLED, 1), else_=0)), 0),
                func.coalesce(
                    func.sum(case((Order.status.in_(REVENUE_STATUSES), consumer), else_=0)),
                    0,
                ),
            )
            .where(Order.deleted_at.is_(None), Order.broker_id.in_(broker_ids))
            .group_by(Order.broker_id)
        )
        for broker_id, count, revenue in self.db.execute(stmt):
            if broker_id is None:
                continue
            stats[broker_id] = {
                "count": int(count or 0),
                "revenue": float(Decimal(str(revenue or 0))),
            }
        return BrokerAdminContext(stats=stats)

    def _stats(self, broker_id: str) -> dict[str, float | int]:
        consumer = func.coalesce(Order.total_amount, 0) + func.coalesce(Order.onsite_extra_amount, 0)
        stmt = select(
            func.coalesce(func.sum(case((Order.status != OrderStatus.CANCELLED, 1), else_=0)), 0),
            func.coalesce(
                func.sum(case((Order.status.in_(REVENUE_STATUSES), consumer), else_=0)),
                0,
            ),
        ).where(Order.deleted_at.is_(None), Order.broker_id == broker_id)
        count, revenue = self.db.execute(stmt).one()
        return {"count": int(count or 0), "revenue": float(Decimal(str(revenue or 0)))}

    def _list_recent_orders(self, broker_id: str) -> list[Order]:
        stmt = (
            select(Order)
            .where(
                Order.broker_id == broker_id,
                Order.deleted_at.is_(None),
                Order.status != OrderStatus.CANCELLED,
            )
            .order_by(Order.scheduled_date.desc().nulls_last(), Order.id.desc())
            .limit(50)
        )
        return list(self.db.scalars(stmt))


def _empty_stats() -> dict[str, float | int]:
    return {"count": 0, "revenue": 0.0}


def _to_assigned_order_dto(order: Order) -> BrokerAssignedOrderRead:
    return BrokerAssignedOrderRead(
        id=order.id,
        status=order.status,
        scheduled_date=order.scheduled_date,
        service_name=order.service_name,
        customer_name=order.customer_name or "",
        customer_address=order.customer_address or "",
        consumer_price=float(order_consumer_total(order)),
        partner_id=order.partner_id,
    )
