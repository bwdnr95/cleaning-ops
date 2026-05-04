from uuid import uuid4

from sqlalchemy.orm import Session

from app.domain.constants import OrderStatus, TimelineEventType
from app.models.photo import OrderPhoto
from app.repositories.orders import OrderRepository
from app.repositories.photos import PhotoRepository
from app.schemas.photo import PhotoCreate
from app.services.storage import StoredFile
from app.services.timeline import TimelineService


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
        if order is not None:
            order.status = OrderStatus.CUSTOMER_DELIVERY_NEEDED
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
