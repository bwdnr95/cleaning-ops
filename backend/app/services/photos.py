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

        photo = OrderPhoto(
            id=str(uuid4()),
            uploaded_by_user_id=user_id,
            is_customer_visible=True,
            **payload.model_dump(),
        )
        self.photos.add(photo)
        self.timeline.record(
            order_id=payload.order_id,
            actor_user_id=user_id,
            event_type=TimelineEventType.PHOTO_UPLOADED,
            title="사진 업로드",
            metadata={"photo_id": photo.id, "photo_type": payload.photo_type},
        )
        self.timeline.record(
            order_id=payload.order_id,
            actor_user_id=None,
            event_type=TimelineEventType.PHOTO_APPROVED,
            title="사진 자동 공개",
            description="협력사 업로드 사진이 정책에 따라 자동 공개되었습니다.",
            metadata={"photo_id": photo.id, "auto": True},
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
        """
        Legacy compatibility hook. Publishing a photo records PHOTO_APPROVED only;
        order status changes happen through the partner completion action.
        """
        photo = self.photos.get(photo_id)
        if photo is None:
            raise ValueError("photo_not_found")
        if photo.is_customer_visible:
            return photo
        photo.is_customer_visible = True
        self.timeline.record(
            order_id=photo.order_id,
            actor_user_id=actor_user_id,
            event_type=TimelineEventType.PHOTO_APPROVED,
            title="사진 고객 공개 승인",
            metadata={"photo_id": photo.id},
        )
        self.db.commit()
        self.db.refresh(photo)
        return photo

    def revoke_visibility(self, photo_id: str, *, actor_user_id: str | None = None) -> OrderPhoto:
        from sqlalchemy import func, select

        from app.models.order import Order
        from app.models.photo import OrderPhoto as OrderPhotoModel

        photo = self.photos.get(photo_id)
        if photo is None:
            raise ValueError("photo_not_found")

        order = self.db.execute(
            select(Order).where(Order.id == photo.order_id).with_for_update()
        ).scalar_one_or_none()
        self.db.refresh(photo)
        if not photo.is_customer_visible:
            return photo

        photo.is_customer_visible = False
        self.db.flush()

        self.timeline.record(
            order_id=photo.order_id,
            actor_user_id=actor_user_id,
            event_type=TimelineEventType.PHOTO_REVOKED,
            title="사진 비공개로 되돌림",
            metadata={"photo_id": photo.id},
        )

        if order is not None:
            old_status = order.status
            remaining_visible = self.db.execute(
                select(func.count(OrderPhotoModel.id)).where(
                    OrderPhotoModel.order_id == order.id,
                    OrderPhotoModel.is_customer_visible.is_(True),
                )
            ).scalar_one()

            if remaining_visible == 0 and order.status == OrderStatus.CUSTOMER_DELIVERY_NEEDED:
                order.status = OrderStatus.IN_PROGRESS
                self.timeline.record(
                    order_id=photo.order_id,
                    actor_user_id=actor_user_id,
                    event_type=TimelineEventType.STATUS_CHANGED,
                    title="작업 진행으로 되돌림",
                    description="공개 사진이 모두 비공개로 처리되어 작업 진행 상태로 되돌렸습니다.",
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
