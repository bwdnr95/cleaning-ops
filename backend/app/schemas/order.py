from datetime import date, datetime

from pydantic import Field

from app.domain.constants import OrderStatus, PhotoType
from app.schemas.common import ApiModel, TimelineEventRead
from app.schemas.message import MessageLogRead
from app.schemas.photo import PhotoRead


class OrderBase(ApiModel):
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
    source_channel: str | None = None
    customer_name: str
    customer_phone: str
    customer_address: str
    total_amount: float | None = Field(default=None, ge=0)
    deposit_amount: float | None = Field(default=None, ge=0)
    balance_amount: float | None = Field(default=None, ge=0)
    onsite_extra_amount: float | None = Field(default=None, ge=0)
    vat_type: str | None = None
    payment_status: str | None = None
    payment_memo: str | None = None
    evidence_memo: str | None = None
    partner_payment_amount: float | None = Field(default=None, ge=0)
    partner_payment_status: str | None = None
    customer_visible_payment: bool = False


class OrderCreate(OrderBase):
    pass


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
    source_channel: str | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    customer_address: str | None = None
    total_amount: float | None = Field(default=None, ge=0)
    deposit_amount: float | None = Field(default=None, ge=0)
    balance_amount: float | None = Field(default=None, ge=0)
    onsite_extra_amount: float | None = Field(default=None, ge=0)
    vat_type: str | None = None
    payment_status: str | None = None
    payment_memo: str | None = None
    evidence_memo: str | None = None
    partner_payment_amount: float | None = Field(default=None, ge=0)
    partner_payment_status: str | None = None
    customer_visible_payment: bool | None = None


class AdminOrderRead(OrderBase):
    id: str
    customer_token: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    timeline: list[TimelineEventRead] = Field(default_factory=list)


class AdminOrderDetailRead(AdminOrderRead):
    photos: list[PhotoRead] = Field(default_factory=list)
    message_logs: list[MessageLogRead] = Field(default_factory=list)


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
    customer_address: str


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


class CustomerPhotoRead(ApiModel):
    id: str
    photo_type: PhotoType
    file_url: str
    file_name: str | None = None


class CustomerOrderRead(ApiModel):
    id: str
    status: OrderStatus
    scheduled_date: date | None
    requested_time: str | None
    service_name: str
    size_or_quantity: str | None = None
    service_detail: str | None = None
    special_request: str | None = None
    customer_name: str
    customer_address: str
    total_amount: float | None = None
    deposit_amount: float | None = None
    balance_amount: float | None = None
    payment_status: str | None = None
    photos: list[CustomerPhotoRead] = Field(default_factory=list)


class CustomerVerifyRequest(ApiModel):
    phone_suffix: str = Field(min_length=4, max_length=4)
