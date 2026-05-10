from uuid import uuid4

from sqlalchemy.orm import Session

from app.domain.constants import OrderStatus, TimelineEventType
from app.models.photo import OrderPhoto
from app.repositories.orders import OrderRepository
from app.repositories.photos import PhotoRepository
from app.schemas.photo import PhotoCreate
from app.services.storage import StoredFile
from app.services.timeline import TimelineService

PHOTO_CONTENT_TYPE_ALIASES = {
    "image/jpg": "image/jpeg",
    "image/jpeg": "image/jpeg",
    "image/png": "image/png",
    "image/webp": "image/webp",
}


class PhotoService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.photos = PhotoRepository(db)
        self.orders = OrderRepository(db)
        self.timeline = TimelineService(db)

    def upload_for_partner(self, payload: PhotoCreate, *, user_id: str, partner_id: str) -> OrderPhoto:
        order = self.orders.get(payload.order_id)
        if order is None or order.partner_id != partner_id:
            raise ValueError("order_not_found")

        old_status = order.status
        photo = OrderPhoto(
            id=str(uuid4()),
            uploaded_by_user_id=user_id,
            is_customer_visible=False,
            **payload.model_dump(),
        )
        self.photos.add(photo)
        order.status = OrderStatus.PHOTO_REVIEW_PENDING
        self.timeline.record(
            order_id=payload.order_id,
            actor_user_id=user_id,
            event_type=TimelineEventType.PHOTO_UPLOADED,
            title="사진 업로드",
            metadata={"photo_id": photo.id, "photo_type": payload.photo_type},
        )
        if old_status != order.status:
            self.timeline.record(
                order_id=payload.order_id,
                actor_user_id=user_id,
                event_type=TimelineEventType.STATUS_CHANGED,
                title="사진 검수 요청",
                description="협력사 사진 업로드로 관리자 검수 대기 상태가 되었습니다.",
                metadata={"from": old_status, "to": order.status},
            )
        self.db.commit()
        self.db.refresh(photo)
        return photo

    def upload_stored_for_partner(
        self,
        *,
        order_id: str,
        photo_type: str,
        stored_file: StoredFile,
        user_id: str,
        partner_id: str,
    ) -> OrderPhoto:
        payload = PhotoCreate(
            order_id=order_id,
            photo_type=photo_type,
            storage_key=stored_file.storage_key,
            file_url=stored_file.file_url,
            file_name=stored_file.file_name,
            file_size=stored_file.file_size,
            content_type=stored_file.content_type,
        )
        return self.upload_for_partner(payload, user_id=user_id, partner_id=partner_id)

    def approve(self, photo_id: str, *, actor_user_id: str | None = None) -> OrderPhoto:
        photo = self.photos.get(photo_id)
        if photo is None:
            raise ValueError("photo_not_found")
        photo.is_customer_visible = True
        order = self.orders.get(photo.order_id)
        old_status = order.status if order is not None else None
        if order is not None and order.status not in {
            OrderStatus.CUSTOMER_DELIVERY_NEEDED,
            OrderStatus.CUSTOMER_DELIVERY_DONE,
            OrderStatus.COMPLETED,
        }:
            order.status = OrderStatus.CUSTOMER_DELIVERY_NEEDED
        self.timeline.record(
            order_id=photo.order_id,
            actor_user_id=actor_user_id,
            event_type=TimelineEventType.PHOTO_APPROVED,
            title="사진 고객 공개 승인",
            metadata={"photo_id": photo.id},
        )
        if order is not None and old_status != order.status:
            self.timeline.record(
                order_id=photo.order_id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.STATUS_CHANGED,
                title="고객 전달 대기",
                description="관리자가 고객 공개 사진을 승인했습니다.",
                metadata={"from": old_status, "to": order.status},
            )
        self.db.commit()
        self.db.refresh(photo)
        return photo


def normalize_uploaded_photo_content_type(content_type: str, data: bytes) -> str:
    normalized_request = content_type.split(";", 1)[0].strip().lower()
    requested_type = PHOTO_CONTENT_TYPE_ALIASES.get(normalized_request)
    if content_type and requested_type is None:
        raise ValueError("unsupported_photo_type")

    detected_type = detect_photo_content_type(data)
    if detected_type is None:
        raise ValueError("unsupported_photo_type")

    if requested_type is not None and requested_type != detected_type:
        raise ValueError("unsupported_photo_type")

    return detected_type


def detect_photo_content_type(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return None
