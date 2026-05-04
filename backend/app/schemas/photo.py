from app.domain.constants import PhotoType
from app.schemas.common import ApiModel


class PhotoCreate(ApiModel):
    order_id: str
    photo_type: PhotoType
    file_url: str
    storage_key: str | None = None
    file_name: str | None = None
    file_size: int | None = None
    content_type: str | None = None


class PhotoRead(ApiModel):
    id: str
    order_id: str
    photo_type: PhotoType
    file_url: str
    file_name: str | None = None
    file_size: int | None = None
    content_type: str | None = None
    uploaded_by_user_id: str
    is_customer_visible: bool


class PhotoApprove(ApiModel):
    is_customer_visible: bool = True


class AdminPhotoReviewItem(ApiModel):
    order_id: str
    status: str
    service_name: str
    size_or_quantity: str | None = None
    customer_name: str
    team_name: str | None = None
    scheduled_date: str | None = None
    requested_time: str | None = None
    photos: list[PhotoRead]
