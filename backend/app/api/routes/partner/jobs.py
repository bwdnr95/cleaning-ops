from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, ensure_partner_scope, get_session, require_partner
from app.core.config import settings
from app.domain.constants import PhotoType, RecipientType, TimelineEventType
from app.repositories.messages import MessageRepository
from app.repositories.order_groups import OrderGroupRepository
from app.repositories.orders import OrderRepository
from app.repositories.photos import PhotoRepository
from app.repositories.timeline import TimelineRepository
from app.schemas.message import PartnerMessageRead
from app.schemas.order import PartnerJobCompleteRequest, PartnerJobRead, PartnerMemoCreate
from app.schemas.photo import PartnerPhotoRead
from app.services.orders import (
    OrderService,
    is_partner_confirmation_required,
    is_partner_photo_uploadable,
    partner_memo_events,
    to_partner_job_dto,
)
from app.services.photos import PhotoService, normalize_uploaded_photo_content_type
from app.services.storage import get_storage_provider
from app.services.timeline import TimelineService

router = APIRouter()


@router.get("", response_model=list[PartnerJobRead])
def list_my_jobs(
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_partner),
) -> list[PartnerJobRead]:
    partner_id = ensure_partner_scope(user)
    photo_repo = PhotoRepository(db)
    group_repo = OrderGroupRepository(db)
    timeline_repo = TimelineRepository(db)
    return [
        to_partner_job_dto(
            order,
            group=group_repo.get(order.group_id),
            photos=photo_repo.list_for_order(order.id),
            as_requested_at=timeline_repo.latest_created_at(
                order_id=order.id,
                event_type=TimelineEventType.AS_REQUESTED,
            ),
            evidence_required_after=TimelineService(db).latest_partner_work_epoch(
                order_id=order.id,
                partner_id=order.partner_id,
                work_completed_at=order.work_completed_at,
                work_is_active=is_partner_photo_uploadable(order),
            ),
            partner_confirmation_required=is_partner_confirmation_required(
                order,
                TimelineService(db),
            ),
        )
        for order in OrderRepository(db).list_for_partner(partner_id)
    ]


@router.get("/{order_id}", response_model=PartnerJobRead)
def get_my_job(
    order_id: str,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_partner),
) -> PartnerJobRead:
    partner_id = ensure_partner_scope(user)
    try:
        order = OrderService(db).get_for_partner(order_id, partner_id=partner_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="order_not_found") from exc
    photos = PhotoRepository(db).list_for_order(order.id)
    group = OrderGroupRepository(db).get(order.group_id)
    timeline_repo = TimelineRepository(db)
    memos = partner_memo_events(timeline_repo.list_for_order(order.id), partner_id)
    return to_partner_job_dto(
        order,
        group=group,
        photos=photos,
        memos=memos,
        as_requested_at=timeline_repo.latest_created_at(
            order_id=order.id,
            event_type=TimelineEventType.AS_REQUESTED,
        ),
        evidence_required_after=TimelineService(db).latest_partner_work_epoch(
            order_id=order.id,
            partner_id=order.partner_id,
            work_completed_at=order.work_completed_at,
            work_is_active=is_partner_photo_uploadable(order),
        ),
        partner_confirmation_required=is_partner_confirmation_required(
            order,
            TimelineService(db),
        ),
    )


@router.post("/{order_id}/start", response_model=PartnerJobRead)
def start_my_job(
    order_id: str,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_partner),
) -> PartnerJobRead:
    partner_id = ensure_partner_scope(user)
    try:
        order = OrderService(db).start_partner_job(
            order_id,
            actor_user_id=user.id,
            partner_id=partner_id,
        )
    except ValueError as exc:
        if str(exc) == "as_intake_approval_required":
            raise HTTPException(status_code=409, detail="as_intake_approval_required") from exc
        if str(exc) == "invalid_status_transition":
            raise HTTPException(status_code=409, detail="invalid_status_transition") from exc
        if str(exc) == "partner_confirmation_required":
            raise HTTPException(status_code=409, detail="partner_confirmation_required") from exc
        if str(exc) == "before_photo_required_for_start":
            raise HTTPException(status_code=422, detail="before_photo_required_for_start") from exc
        raise HTTPException(status_code=404, detail="order_not_found") from exc
    photos = PhotoRepository(db).list_for_order(order.id)
    group = OrderGroupRepository(db).get(order.group_id)
    return to_partner_job_dto(
        order,
        group=group,
        photos=photos,
        as_requested_at=TimelineRepository(db).latest_created_at(
            order_id=order.id,
            event_type=TimelineEventType.AS_REQUESTED,
        ),
        evidence_required_after=TimelineService(db).latest_partner_work_epoch(
            order_id=order.id,
            partner_id=order.partner_id,
            work_completed_at=order.work_completed_at,
            work_is_active=is_partner_photo_uploadable(order),
        ),
        partner_confirmation_required=is_partner_confirmation_required(
            order,
            TimelineService(db),
        ),
    )


@router.post("/{order_id}/confirm", response_model=PartnerJobRead)
def confirm_my_job(
    order_id: str,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_partner),
) -> PartnerJobRead:
    partner_id = ensure_partner_scope(user)
    try:
        order = OrderService(db).confirm_partner_job(
            order_id,
            actor_user_id=user.id,
            partner_id=partner_id,
        )
    except ValueError as exc:
        if str(exc) == "as_intake_approval_required":
            raise HTTPException(status_code=409, detail="as_intake_approval_required") from exc
        if str(exc) == "invalid_status_transition":
            raise HTTPException(status_code=409, detail="invalid_status_transition") from exc
        if str(exc) == "schedule_required_for_confirmation":
            raise HTTPException(
                status_code=422,
                detail="schedule_required_for_confirmation",
            ) from exc
        raise HTTPException(status_code=404, detail="order_not_found") from exc
    photos = PhotoRepository(db).list_for_order(order.id)
    group = OrderGroupRepository(db).get(order.group_id)
    return to_partner_job_dto(
        order,
        group=group,
        photos=photos,
        as_requested_at=TimelineRepository(db).latest_created_at(
            order_id=order.id,
            event_type=TimelineEventType.AS_REQUESTED,
        ),
        evidence_required_after=TimelineService(db).latest_partner_work_epoch(
            order_id=order.id,
            partner_id=order.partner_id,
            work_completed_at=order.work_completed_at,
            work_is_active=is_partner_photo_uploadable(order),
        ),
        partner_confirmation_required=is_partner_confirmation_required(
            order,
            TimelineService(db),
        ),
    )


@router.post("/{order_id}/complete", response_model=PartnerJobRead)
def complete_my_job(
    order_id: str,
    payload: PartnerJobCompleteRequest | None = None,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_partner),
) -> PartnerJobRead:
    partner_id = ensure_partner_scope(user)
    try:
        order = OrderService(db).complete_partner_job(
            order_id,
            actor_user_id=user.id,
            partner_id=partner_id,
            customer_signature_data_url=payload.customer_signature_data_url if payload else "",
        )
    except ValueError as exc:
        if str(exc) == "as_intake_approval_required":
            raise HTTPException(status_code=409, detail="as_intake_approval_required") from exc
        if str(exc) == "invalid_status_transition":
            raise HTTPException(status_code=409, detail="invalid_status_transition") from exc
        if str(exc) == "completion_evidence_required":
            raise HTTPException(status_code=422, detail="completion_evidence_required") from exc
        raise HTTPException(status_code=404, detail="order_not_found") from exc
    photos = PhotoRepository(db).list_for_order(order.id)
    group = OrderGroupRepository(db).get(order.group_id)
    return to_partner_job_dto(
        order,
        group=group,
        photos=photos,
        as_requested_at=TimelineRepository(db).latest_created_at(
            order_id=order.id,
            event_type=TimelineEventType.AS_REQUESTED,
        ),
        evidence_required_after=TimelineService(db).latest_partner_work_epoch(
            order_id=order.id,
            partner_id=order.partner_id,
            work_completed_at=order.work_completed_at,
            work_is_active=is_partner_photo_uploadable(order),
        ),
        partner_confirmation_required=is_partner_confirmation_required(
            order,
            TimelineService(db),
        ),
    )


@router.post("/{order_id}/photos", response_model=PartnerPhotoRead)
async def upload_photo(
    order_id: str,
    photo_type: PhotoType = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_partner),
):
    partner_id = ensure_partner_scope(user)
    order = OrderRepository(db).get(order_id)
    if order is None or order.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="order_not_found")

    data = await file.read()
    if len(data) > settings.photo_max_upload_bytes:
        raise HTTPException(status_code=413, detail="photo_too_large")

    try:
        content_type = normalize_uploaded_photo_content_type(file.content_type or "", data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    storage = get_storage_provider()
    stored_file = storage.save(
        data=data,
        file_name=file.filename or "photo",
        content_type=content_type,
    )
    try:
        return PhotoService(db).upload_stored_for_partner(
            order_id=order_id,
            photo_type=photo_type,
            stored_file=stored_file,
            user_id=user.id,
            partner_id=partner_id,
        )
    except ValueError as exc:
        db.rollback()
        storage.delete(stored_file.storage_key)
        if str(exc) == "invalid_status_for_upload":
            raise HTTPException(status_code=409, detail="invalid_status_for_upload") from exc
        if str(exc) == "order_not_found":
            raise HTTPException(status_code=404, detail="order_not_found") from exc
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        storage.delete(stored_file.storage_key)
        raise


@router.post("/{order_id}/memo", response_model=PartnerJobRead)
def add_job_memo(
    order_id: str,
    payload: PartnerMemoCreate,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_partner),
) -> PartnerJobRead:
    partner_id = ensure_partner_scope(user)
    try:
        order = OrderService(db).add_partner_memo(
            order_id,
            text=payload.text,
            actor_user_id=user.id,
            partner_id=partner_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="order_not_found") from exc
    photos = PhotoRepository(db).list_for_order(order.id)
    group = OrderGroupRepository(db).get(order.group_id)
    memos = partner_memo_events(TimelineRepository(db).list_for_order(order.id), partner_id)
    return to_partner_job_dto(
        order,
        group=group,
        photos=photos,
        memos=memos,
        as_requested_at=TimelineRepository(db).latest_created_at(
            order_id=order.id,
            event_type=TimelineEventType.AS_REQUESTED,
        ),
        evidence_required_after=TimelineService(db).latest_partner_work_epoch(
            order_id=order.id,
            partner_id=order.partner_id,
            work_completed_at=order.work_completed_at,
            work_is_active=is_partner_photo_uploadable(order),
        ),
        partner_confirmation_required=is_partner_confirmation_required(
            order,
            TimelineService(db),
        ),
    )


@router.get("/{order_id}/messages", response_model=list[PartnerMessageRead])
def list_job_messages(
    order_id: str,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_partner),
) -> list[PartnerMessageRead]:
    partner_id = ensure_partner_scope(user)
    try:
        order = OrderService(db).get_for_partner(order_id, partner_id=partner_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="order_not_found") from exc
    # 협력사 수신 메시지는 '발송 시점 배정 협력사' 식별자(recipient_partner_id)로만 노출한다.
    # 전화번호가 아니라 식별자로 스코프하므로, 두 협력사가 같은 전화번호를 쓰거나
    # 재배정(A→B)이 일어나도 타 협력사 메시지(내용에 협력사명/담당자 포함)가 새지 않는다.
    # 식별자가 없는 과거(컬럼 도입 전) 로그는 노출하지 않는다(fail-closed).
    logs = MessageRepository(db).list_for_order(order.id)
    return [
        PartnerMessageRead(
            id=log.id,
            message_type=log.message_type,
            channel=log.channel,
            content=log.content,
            status=log.status,
            sent_at=log.sent_at,
            created_at=log.created_at,
        )
        for log in logs
        if log.recipient_type == RecipientType.PARTNER and log.recipient_partner_id == partner_id
    ]
