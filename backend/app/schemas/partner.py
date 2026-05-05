from datetime import datetime
from datetime import date

from pydantic import Field

from app.domain.constants import OrderStatus
from app.schemas.common import ApiModel


class PartnerBase(ApiModel):
    name: str
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
    manager_name: str | None = None
    phone: str | None = None
    service_areas: str | None = None
    available_services: str | None = None
    memo: str | None = None
    is_active: bool | None = None


class PartnerRead(PartnerBase):
    id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PartnerAdminRead(PartnerRead):
    scheduled_job_count: int = 0
    active_job_count: int = 0
    completed_job_count: int = 0
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


class PartnerDetailRead(PartnerAdminRead):
    jobs: list[PartnerAssignedOrderRead]


class PartnerPasswordResetRequest(ApiModel):
    login_phone: str | None = None
    password: str | None = Field(default=None, min_length=10)


class PartnerPasswordResetRead(ApiModel):
    partner_id: str
    user_id: str
    login_phone: str
    temporary_password: str
