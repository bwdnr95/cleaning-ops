from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_session, require_admin
from app.domain.constants import MessageType, OrderStatus
from app.repositories.messages import MessageRepository
from app.repositories.photos import PhotoRepository
from app.schemas.photo import AdminPhotoReviewItem, PhotoRead
from app.services.photos import PhotoService

router = APIRouter()


@router.get("/review-queue", response_model=list[AdminPhotoReviewItem])
def list_photo_review_queue(
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> list[AdminPhotoReviewItem]:
    message_repo = MessageRepository(db)
    items = []
    for order, photos, approved_count in PhotoRepository(db).list_review_queue():
        pending_count = len([photo for photo in photos if not photo.is_customer_visible])
        items.append(
            AdminPhotoReviewItem(
                order_id=order.id,
                status=order.status,
                service_name=order.service_name,
                size_or_quantity=order.size_or_quantity,
                customer_name=order.customer_name,
                team_name=order.team_name,
                scheduled_date=order.scheduled_date.isoformat() if order.scheduled_date else None,
                requested_time=order.requested_time,
                pending_photo_count=pending_count,
                approved_photo_count=approved_count,
                can_send_customer_link=(
                    approved_count > 0 and order.status != OrderStatus.CANCELLED
                ),
                last_customer_link_sent_at=message_repo.last_sent_at(
                    order_id=order.id,
                    message_type=MessageType.CUSTOMER_PHOTO_READY,
                ),
                photos=photos,
            )
        )
    return items


@router.post("/{photo_id}/approve", response_model=PhotoRead)
def approve_photo(
    photo_id: str,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
):
    try:
        return PhotoService(db).approve(photo_id, actor_user_id=user.id)
    except ValueError as exc:
        if str(exc) == "photo_not_found":
            raise HTTPException(status_code=404, detail="photo_not_found") from exc
        raise
