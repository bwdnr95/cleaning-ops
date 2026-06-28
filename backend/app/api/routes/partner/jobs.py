from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.api.deps import CurrentUser, ensure_partner_scope, get_session, require_partner
from app.domain.constants import PhotoType, RecipientType
from app.domain.phone import normalize_phone
from app.repositories.messages import MessageRepository
from app.repositories.order_groups import OrderGroupRepository
from app.repositories.orders import OrderRepository
from app.repositories.partners import PartnerRepository
from app.repositories.photos import PhotoRepository
from app.repositories.timeline import TimelineRepository
from app.schemas.message import PartnerMessageRead
from app.schemas.order import PartnerJobRead, PartnerMemoCreate
from app.schemas.photo import PartnerPhotoRead
from app.services.orders import OrderService, partner_memo_events, to_partner_job_dto
from app.services.photos import PhotoService, normalize_uploaded_photo_content_type
from app.services.storage import get_storage_provider

router = APIRouter()


@router.get("", response_model=list[PartnerJobRead])
def list_my_jobs(
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_partner),
) -> list[PartnerJobRead]:
    partner_id = ensure_partner_scope(user)
    photo_repo = PhotoRepository(db)
    group_repo = OrderGroupRepository(db)
    return [
        to_partner_job_dto(
            order,
            group=group_repo.get(order.group_id),
            photos=photo_repo.list_for_order(order.id),
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
    memos = partner_memo_events(TimelineRepository(db).list_for_order(order.id), partner_id)
    return to_partner_job_dto(order, group=group, photos=photos, memos=memos)


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
        if str(exc) == "invalid_status_transition":
            raise HTTPException(status_code=409, detail="invalid_status_transition") from exc
        raise HTTPException(status_code=404, detail="order_not_found") from exc
    photos = PhotoRepository(db).list_for_order(order.id)
    group = OrderGroupRepository(db).get(order.group_id)
    return to_partner_job_dto(order, group=group, photos=photos)


@router.post("/{order_id}/complete", response_model=PartnerJobRead)
def complete_my_job(
    order_id: str,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_partner),
) -> PartnerJobRead:
    partner_id = ensure_partner_scope(user)
    try:
        order = OrderService(db).complete_partner_job(
            order_id,
            actor_user_id=user.id,
            partner_id=partner_id,
        )
    except ValueError as exc:
        if str(exc) == "invalid_status_transition":
            raise HTTPException(status_code=409, detail="invalid_status_transition") from exc
        if str(exc) == "photo_required_for_completion":
            raise HTTPException(status_code=422, detail="photo_required_for_completion") from exc
        raise HTTPException(status_code=404, detail="order_not_found") from exc
    photos = PhotoRepository(db).list_for_order(order.id)
    group = OrderGroupRepository(db).get(order.group_id)
    return to_partner_job_dto(order, group=group, photos=photos)


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
    return to_partner_job_dto(order, group=group, photos=photos, memos=memos)


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
    # 협력사 수신 메시지는 '현재 배정 협력사'에게 간 것만 노출한다.
    # recipient_type만으로 거르면 재배정(A→B) 시 B가 이전 협력사 A에게 간
    # 메시지(내용에 협력사명/담당자 포함)를 보게 되어 타 협력사 정보가 샌다.
    # message_logs에는 협력사 식별자가 없어 발송 시점의 수신 전화번호로 스코프한다.
    # (PARTNER_CUSTOMER_INFO는 담당자 연락처로 발송될 수 있어 두 번호 모두 허용)
    partner = PartnerRepository(db).get(partner_id)
    partner_phones = {
        normalize_phone(raw)
        for raw in ((partner.phone, partner.manager_phone) if partner else ())
        if raw and normalize_phone(raw)
    }
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
        if log.recipient_type == RecipientType.PARTNER
        and normalize_phone(log.recipient_phone) in partner_phones
    ]
