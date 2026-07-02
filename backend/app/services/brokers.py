from dataclasses import dataclass, field
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.domain.constants import OrderStatus
from app.domain.phone import normalize_phone
from app.models.broker import Broker
from app.models.order import Order
from app.repositories.brokers import BrokerRepository
from app.schemas.broker import BrokerAdminRead, BrokerCreate, BrokerDetailRead, BrokerUpdate
from app.services.broker_settlements import unpaid_broker_condition


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
        # 소개 주문 목록/정산은 별도 정산 엔드포인트(/settlements)가 제공한다(협력사와 동형).
        return BrokerDetailRead(**self.to_admin_dto(broker).model_dump())

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
        self, broker: Broker, *, context: BrokerAdminContext | None = None
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
            unpaid_broker_amount_total=float(stats["unpaid_amount"]),
            unpaid_broker_order_count=int(stats["unpaid_count"]),
        )

    @staticmethod
    def _agg_columns() -> tuple:
        # 소개 건수(취소 제외) / 미정산 수수료 건수·합계(unpaid_broker_condition 기준).
        return (
            func.coalesce(func.sum(case((Order.status != OrderStatus.CANCELLED, 1), else_=0)), 0),
            func.coalesce(func.sum(case((unpaid_broker_condition(), 1), else_=0)), 0),
            func.coalesce(
                func.sum(
                    case(
                        (unpaid_broker_condition(), func.coalesce(Order.broker_payment_amount, 0)),
                        else_=0,
                    )
                ),
                0,
            ),
        )

    def _build_admin_context(self, brokers: list[Broker]) -> BrokerAdminContext:
        broker_ids = [broker.id for broker in brokers]
        if not broker_ids:
            return BrokerAdminContext()
        stats = {broker_id: _empty_stats() for broker_id in broker_ids}
        stmt = (
            select(Order.broker_id, *self._agg_columns())
            .where(Order.deleted_at.is_(None), Order.broker_id.in_(broker_ids))
            .group_by(Order.broker_id)
        )
        for broker_id, count, unpaid_count, unpaid_amount in self.db.execute(stmt):
            if broker_id is None:
                continue
            stats[broker_id] = {
                "count": int(count or 0),
                "unpaid_count": int(unpaid_count or 0),
                "unpaid_amount": float(Decimal(str(unpaid_amount or 0))),
            }
        return BrokerAdminContext(stats=stats)

    def _stats(self, broker_id: str) -> dict[str, float | int]:
        stmt = select(*self._agg_columns()).where(
            Order.deleted_at.is_(None), Order.broker_id == broker_id
        )
        count, unpaid_count, unpaid_amount = self.db.execute(stmt).one()
        return {
            "count": int(count or 0),
            "unpaid_count": int(unpaid_count or 0),
            "unpaid_amount": float(Decimal(str(unpaid_amount or 0))),
        }


def _empty_stats() -> dict[str, float | int]:
    return {"count": 0, "unpaid_count": 0, "unpaid_amount": 0.0}
