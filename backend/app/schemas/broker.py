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
    # order_count: 취소 제외 소개 주문 수. revenue_total: 앱 표준 매출 집합(고객전달완료·서비스완료)
    # 기준 실현 매출 — 대시보드/리포트 '매출'과 동일 정의로 화면 간 값이 어긋나지 않게 한다.
    order_count: int = 0
    revenue_total: float = 0


class BrokerAssignedOrderRead(ApiModel):
    id: str
    status: OrderStatus
    scheduled_date: date | None = None
    service_name: str
    customer_name: str
    customer_address: str
    consumer_price: float | None = None
    partner_id: str | None = None


class BrokerDetailRead(BrokerAdminRead):
    orders: list[BrokerAssignedOrderRead] = Field(default_factory=list)
