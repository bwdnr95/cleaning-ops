from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_session, require_admin
from app.domain.constants import TimelineEventType
from app.models.order import Order
from app.models.timeline import OrderTimeline
from app.repositories.timeline import TimelineRepository
from app.schemas.notification import AdminNotificationRead

router = APIRouter()

_PARTNER_STATUS_TITLES = {"작업 일정 확인", "작업 시작", "작업 완료", "AS 작업 완료"}


@router.get("", response_model=list[AdminNotificationRead])
def list_admin_notifications(
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> list[AdminNotificationRead]:
    rows: list[AdminNotificationRead] = []
    repository = TimelineRepository(db)
    batch_size = max(limit * 5, 100)
    offset = 0
    while len(rows) < limit:
        candidates = repository.list_admin_notification_candidates(
            limit=batch_size,
            offset=offset,
        )
        if not candidates:
            break
        offset += len(candidates)
        for event, order in candidates:
            if not _is_admin_notification(event):
                continue
            rows.append(_to_notification(event, order))
            if len(rows) >= limit:
                break
    return rows


def _is_admin_notification(event: OrderTimeline) -> bool:
    metadata = event.event_metadata or {}
    if event.event_type == TimelineEventType.AS_REQUESTED and metadata.get("source") == "customer":
        return True
    if event.event_type == TimelineEventType.MEMO_ADDED and metadata.get("author_role") == "partner":
        return True
    if event.event_type == TimelineEventType.PHOTO_UPLOADED:
        return True
    if event.event_type == TimelineEventType.PHOTO_APPROVED and metadata.get("auto") is True:
        return True
    return event.event_type == TimelineEventType.STATUS_CHANGED and event.title in _PARTNER_STATUS_TITLES


def _to_notification(event: OrderTimeline, order: Order) -> AdminNotificationRead:
    return AdminNotificationRead(
        id=event.id,
        order_id=order.id,
        event_type=event.event_type,
        title=event.title,
        description=event.description,
        created_at=event.created_at,
        service_name=order.service_name,
        customer_name=order.customer_name,
        actor_label=_actor_label(event),
    )


def _actor_label(event: OrderTimeline) -> str:
    metadata = event.event_metadata or {}
    if metadata.get("source") in {"customer", "customer_as"}:
        return "고객"
    if metadata.get("author_role") == "partner" or event.title in _PARTNER_STATUS_TITLES:
        return "협력사"
    if event.event_type in {TimelineEventType.PHOTO_UPLOADED, TimelineEventType.PHOTO_APPROVED}:
        return "협력사"
    return "시스템"
