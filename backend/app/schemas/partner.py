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
    manager_phone: str | None = None
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
    manager_phone: str | None = None
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
    address_detail: str | None = None
    consumer_price: float | None = None
    partner_price: float | None = None
    partner_payment_status: str | None = None
    settled_at: datetime | None = None
    # 이 라인이 속한 그룹(고객)의 합계. 0원 라인 보조표시용(취소/삭제 제외).
    group_consumer_total: float = 0
    group_partner_total: float = 0


class PartnerRecurringMonthlySettlementRead(ApiModel):
    """월 청구 정기계약의 계약×월 도급 지급 행(관리자 전용).

    월 트래커(정기청소 탭)의 지급 체크와 같은 DB 행을 보여준다 — 협력사관리에서도
    월 도급비 지급/이력이 보이고 실행 가능해야 배지·목록·트래커가 일치한다.
    """

    contract_id: str
    contract_label: str
    month: str  # "YYYY-MM"
    month_start: date
    partner_price: float
    paid: bool


class PartnerSettlementListRead(ApiModel):
    items: list[PartnerSettlementItemRead]
    # 월 청구 정기계약의 월정산 행. 주문(items)과 별개 축(계약×월)이라 분리한다.
    monthly_items: list[PartnerRecurringMonthlySettlementRead] = Field(
        default_factory=list
    )
    total_partner_price: float
    total_consumer_price: float
    count: int


class PartnerSettlementActionRequest(ApiModel):
    order_ids: list[str] = Field(min_length=1)
    memo: str | None = None


class PartnerSettlementActionResult(ApiModel):
    updated_order_ids: list[str]
    skipped_order_ids: list[str] = Field(default_factory=list)


class PartnerRecurringMonthlySettlementActionRequest(ApiModel):
    contract_id: str
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")


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
