from datetime import date, datetime

from pydantic import Field

from app.domain.constants import OrderStatus, PhotoType, ReceiptStatus, ReceiptType, VatType
from app.schemas.common import ApiModel, TimelineEventRead
from app.schemas.message import MessageLogRead
from app.schemas.photo import PartnerPhotoRead, PhotoRead


class OrderGroupBase(ApiModel):
    customer_name: str
    customer_phone: str
    customer_address: str
    customer_address_detail: str | None = None
    source_channel: str | None = None
    customer_visible_payment: bool = False
    notes: str | None = None


class OrderGroupCreate(OrderGroupBase):
    lines: list["OrderLineCreate"] = Field(default_factory=list, min_length=1)


class OrderGroupUpdate(ApiModel):
    customer_name: str | None = None
    customer_phone: str | None = None
    customer_address: str | None = None
    customer_address_detail: str | None = None
    source_channel: str | None = None
    customer_visible_payment: bool | None = None
    notes: str | None = None


class OrderLineBase(ApiModel):
    """Line operation fields only; group/customer metadata lives on OrderGroup."""

    status: OrderStatus = OrderStatus.NEW
    received_date: date
    scheduled_date: date | None = None
    requested_time: str | None = None
    partner_id: str | None = None
    team_name: str | None = None
    service_category_id: str | None = None
    service_item_id: str | None = None
    service_name: str
    size_or_quantity: str | None = None
    service_detail: str | None = None
    special_request: str | None = None
    total_amount: float | None = Field(default=None, ge=0)
    discount_amount: float = Field(default=0, ge=0)
    deposit_amount: float | None = Field(default=None, ge=0)
    balance_amount: float | None = Field(default=None, ge=0)
    # 현장 추가는 부호 있는 현장 조정값(추가/차감)이라 음수를 허용한다.
    onsite_extra_amount: float | None = None
    vat_type: VatType | None = VatType.INCLUDED
    payment_status: str | None = None
    payment_memo: str | None = None
    evidence_memo: str | None = None
    receipt_type: ReceiptType | None = None
    receipt_status: ReceiptStatus | None = None
    partner_payment_amount: float | None = Field(default=None, ge=0)
    partner_payment_status: str | None = None


class OrderLineCreate(OrderLineBase):
    pass


class OrderCreate(OrderLineBase):
    """Deprecated (R7): use OrderGroupCreate. Kept for 1-line wrapper compatibility."""

    customer_name: str
    customer_phone: str
    customer_address: str
    customer_address_detail: str | None = None
    source_channel: str | None = None
    customer_visible_payment: bool = False


class OrderUpdate(ApiModel):
    status: OrderStatus | None = None
    received_date: date | None = None
    scheduled_date: date | None = None
    requested_time: str | None = None
    partner_id: str | None = None
    team_name: str | None = None
    service_category_id: str | None = None
    service_item_id: str | None = None
    service_name: str | None = None
    size_or_quantity: str | None = None
    service_detail: str | None = None
    special_request: str | None = None
    total_amount: float | None = Field(default=None, ge=0)
    discount_amount: float | None = Field(default=None, ge=0)
    deposit_amount: float | None = Field(default=None, ge=0)
    balance_amount: float | None = Field(default=None, ge=0)
    # 현장 추가는 부호 있는 현장 조정값(추가/차감)이라 음수를 허용한다.
    onsite_extra_amount: float | None = None
    vat_type: VatType | None = None
    payment_status: str | None = None
    payment_memo: str | None = None
    evidence_memo: str | None = None
    receipt_type: ReceiptType | None = None
    receipt_status: ReceiptStatus | None = None
    partner_payment_amount: float | None = Field(default=None, ge=0)
    partner_payment_status: str | None = None


class AdminOrderRead(OrderLineBase):
    id: str
    group_id: str
    recurring_contract_id: str | None = None
    customer_name: str
    customer_phone: str
    customer_address: str
    customer_address_detail: str | None = None
    source_channel: str | None = None
    customer_visible_payment: bool = False
    group_notes: str | None = None
    customer_token: str
    consumer_price: float | None = None
    partner_price: float | None = None
    partner_settled_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    timeline: list[TimelineEventRead] = Field(default_factory=list)


class AdminOrderPageSummary(ApiModel):
    count: int = 0
    consumer_total: float = 0.0
    partner_total: float = 0.0
    profit: float = 0.0


class AdminOrderPageInsight(ApiModel):
    today_jobs: int = 0
    unassigned: int = 0
    schedule_confirmed: int = 0
    work_done: int = 0
    unpaid_total: float = 0.0
    month_total: float = 0.0


class AdminOrderPageRead(ApiModel):
    items: list[AdminOrderRead] = Field(default_factory=list)
    total: int = 0
    status_counts: dict[str, int] = Field(default_factory=dict)
    summary: AdminOrderPageSummary = Field(default_factory=AdminOrderPageSummary)
    insight: AdminOrderPageInsight = Field(default_factory=AdminOrderPageInsight)


class AdminOrderGroupRead(OrderGroupBase):
    id: str
    customer_token: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    lines: list[AdminOrderRead] = Field(default_factory=list)


class AdminOrderSiblingRead(ApiModel):
    id: str
    status: OrderStatus
    service_name: str
    partner_id: str | None = None
    team_name: str | None = None
    total_amount: float | None = None


class AdminOrderDetailRead(AdminOrderRead):
    photos: list[PhotoRead] = Field(default_factory=list)
    message_logs: list[MessageLogRead] = Field(default_factory=list)
    sibling_lines: list[AdminOrderSiblingRead] = Field(default_factory=list)


class AdminCalendarOrderRead(ApiModel):
    id: str
    status: OrderStatus
    scheduled_date: date
    requested_time: str | None = None
    partner_id: str | None = None
    team_name: str | None = None
    service_name: str
    size_or_quantity: str | None = None
    customer_name: str
    customer_phone: str | None = None
    customer_address: str
    customer_address_detail: str | None = None


class PartnerMemoCreate(ApiModel):
    text: str = Field(min_length=1, max_length=1000)


class PartnerMemoRead(ApiModel):
    id: str
    text: str
    created_at: datetime | None = None


class PartnerJobRead(ApiModel):
    id: str
    status: OrderStatus
    scheduled_date: date | None
    requested_time: str | None
    service_name: str
    size_or_quantity: str | None = None
    service_detail: str | None = None
    special_request: str | None = None
    customer_name: str
    customer_phone: str
    customer_address: str
    customer_address_detail: str | None = None
    is_recurring: bool = False
    photos: list[PartnerPhotoRead] = Field(default_factory=list)
    memos: list[PartnerMemoRead] = Field(default_factory=list)


class CustomerPhotoRead(ApiModel):
    id: str
    photo_type: PhotoType
    file_url: str
    file_name: str | None = None


class CustomerOrderLineRead(ApiModel):
    id: str
    status: OrderStatus
    scheduled_date: date | None
    requested_time: str | None
    service_name: str
    size_or_quantity: str | None = None
    service_detail: str | None = None
    special_request: str | None = None
    total_amount: float | None = None
    deposit_amount: float | None = None
    balance_amount: float | None = None
    payment_status: str | None = None
    photos: list[CustomerPhotoRead] = Field(default_factory=list)


class CustomerOrderGroupRead(ApiModel):
    id: str
    customer_name: str
    customer_phone: str
    customer_address: str
    customer_address_detail: str | None = None
    customer_visible_payment: bool = False
    lines: list[CustomerOrderLineRead] = Field(default_factory=list)


class CustomerVerifyRequest(ApiModel):
    phone_suffix: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")


CustomerOrderRead = CustomerOrderGroupRead

OrderGroupCreate.model_rebuild()
AdminOrderGroupRead.model_rebuild()
AdminOrderDetailRead.model_rebuild()
CustomerOrderLineRead.model_rebuild()
