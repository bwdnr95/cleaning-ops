from datetime import datetime

from app.schemas.common import ApiModel


class PartnerCreate(ApiModel):
    name: str
    manager_name: str | None = None
    phone: str
    service_areas: str | None = None
    available_services: str | None = None
    memo: str | None = None
    is_active: bool = True


class PartnerRead(PartnerCreate):
    id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
