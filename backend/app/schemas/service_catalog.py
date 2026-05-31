from datetime import datetime

from pydantic import Field

from app.domain.service_catalog import ServiceUnit
from app.schemas.common import ApiModel


class ServiceCategoryCreate(ApiModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    is_active: bool = True
    sort_order: int = 0


class ServiceCategoryUpdate(ApiModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class ServiceItemCreate(ApiModel):
    category_id: str
    name: str = Field(min_length=1, max_length=120)
    unit: ServiceUnit = ServiceUnit.CASE
    base_price: float = Field(default=0, ge=0)
    partner_base_price: float = Field(default=0, ge=0)
    description: str | None = None
    is_active: bool = True
    sort_order: int = 0


class ServiceItemUpdate(ApiModel):
    category_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    unit: ServiceUnit | None = None
    base_price: float | None = Field(default=None, ge=0)
    partner_base_price: float | None = Field(default=None, ge=0)
    description: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class ServiceItemRead(ApiModel):
    id: str
    category_id: str
    name: str
    unit: ServiceUnit
    base_price: float
    partner_base_price: float
    description: str | None = None
    is_active: bool
    sort_order: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ServiceCategoryRead(ApiModel):
    id: str
    name: str
    description: str | None = None
    is_active: bool
    sort_order: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ServiceCategoryDetailRead(ServiceCategoryRead):
    items: list[ServiceItemRead] = Field(default_factory=list)
