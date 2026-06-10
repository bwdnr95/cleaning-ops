from datetime import datetime
from datetime import date

from pydantic import Field

from app.domain.constants import OrderStatus
from app.schemas.common import ApiModel


class PartnerBase(ApiModel):
    name: str
    partner_category_id: str | None = None
    manager_name: str | None = None
    phone: str
    service_areas: str | None = None
    available_services: str | None = None
    memo: str | None = None
    is_active: bool = True


class PartnerCreate(PartnerBase):
    login_phone: str | None = None
    login_password: str | None = Field(default=None, min_length=10)


class PartnerUpdate(ApiModel):
    name: str | None = None
    partner_category_id: str | None = None
    manager_name: str | None = None
    phone: str | None = None
    service_areas: str | None = None
    available_services: str | None = None
    memo: str | None = None
    is_active: bool | None = None


class PartnerRead(PartnerBase):
    id: str
    partner_category_name: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PartnerAdminRead(PartnerRead):
    scheduled_job_count: int = 0
    active_job_count: int = 0
    completed_job_count: int = 0
    unpaid_partner_amount_total: float = 0
    unpaid_partner_order_count: int = 0
    user_id: str | None = None
    login_phone: str | None = None
    user_is_active: bool | None = None
    last_login_at: datetime | None = None


class PartnerAssignedOrderRead(ApiModel):
    id: str
    status: OrderStatus
    scheduled_date: date | None = None
    requested_time: str | None = None
    service_name: str
    size_or_quantity: str | None = None
    customer_name: str
    customer_address: str
    consumer_price: float | None = None
    partner_price: float | None = None
    partner_payment_status: str | None = None
    settled_at: datetime | None = None


class PartnerSettlementItemRead(ApiModel):
    order_id: str
    status: OrderStatus
    scheduled_date: date | None = None
    service_name: str
    customer_name: str
    address_short: str
    consumer_price: float | None = None
    partner_price: float | None = None
    partner_payment_status: str | None = None
    settled_at: datetime | None = None


class PartnerSettlementListRead(ApiModel):
    items: list[PartnerSettlementItemRead]
    total_partner_price: float
    total_consumer_price: float
    count: int


class PartnerSettlementActionRequest(ApiModel):
    order_ids: list[str] = Field(min_length=1)
    memo: str | None = None


class PartnerSettlementActionResult(ApiModel):
    updated_order_ids: list[str]
    skipped_order_ids: list[str] = Field(default_factory=list)


class PartnerDetailRead(PartnerAdminRead):
    jobs: list[PartnerAssignedOrderRead]
    # 로그인 계정 신규 생성 시 비밀번호를 자동 생성한 경우에만 1회 노출한다.
    # 관리자가 직접 입력한 비밀번호는 노출하지 않는다.
    temporary_password: str | None = None


class PartnerPasswordResetRequest(ApiModel):
    login_phone: str | None = None
    password: str | None = Field(default=None, min_length=10)


class PartnerPasswordResetRead(ApiModel):
    partner_id: str
    user_id: str
    login_phone: str
    temporary_password: str


class PartnerCategoryCreate(ApiModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    is_active: bool = True
    sort_order: int = 0


class PartnerCategoryUpdate(ApiModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class PartnerCategoryRead(ApiModel):
    id: str
    name: str
    description: str | None = None
    is_active: bool
    sort_order: int
    partner_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
