from datetime import date, datetime

from pydantic import Field

from app.domain.constants import OrderStatus
from app.schemas.common import ApiModel


class BrokerBase(ApiModel):
    name: str
    manager_name: str | None = None
    phone: str | None = None
    manager_phone: str | None = None
    memo: str | None = None
    is_active: bool = True


class BrokerCreate(BrokerBase):
    pass


class BrokerUpdate(ApiModel):
    name: str | None = None
    manager_name: str | None = None
    phone: str | None = None
    manager_phone: str | None = None
    memo: str | None = None
    is_active: bool | None = None


class BrokerRead(BrokerBase):
    id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BrokerAdminRead(BrokerRead):
    # order_count: 취소 제외 소개 주문 수. 미정산 수수료 합계·건수는 협력사 미정산 지표와 동형
    # (중개 수수료가 입력됐고 아직 지급완료가 아닌 건).
    order_count: int = 0
    unpaid_broker_amount_total: float = 0
    unpaid_broker_order_count: int = 0


class BrokerDetailRead(BrokerAdminRead):
    pass


# --- 중개 수수료 정산 (협력사 정산 스키마 미러) ---
class BrokerSettlementItemRead(ApiModel):
    order_id: str
    status: OrderStatus
    scheduled_date: date | None = None
    service_name: str
    customer_name: str
    address_short: str
    address_detail: str | None = None
    consumer_price: float | None = None
    broker_price: float | None = None
    broker_payment_status: str | None = None
    settled_at: datetime | None = None


class BrokerSettlementListRead(ApiModel):
    items: list[BrokerSettlementItemRead]
    total_broker_price: float
    total_consumer_price: float
    count: int


class BrokerSettlementActionRequest(ApiModel):
    order_ids: list[str] = Field(min_length=1)
    memo: str | None = None


class BrokerSettlementActionResult(ApiModel):
    updated_order_ids: list[str]
    skipped_order_ids: list[str] = Field(default_factory=list)
