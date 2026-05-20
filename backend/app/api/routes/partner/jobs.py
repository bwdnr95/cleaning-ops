from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.api.deps import CurrentUser, ensure_partner_scope, get_session, require_partner
from app.domain.constants import PhotoType
from app.repositories.order_groups import OrderGroupRepository
from app.repositories.orders import OrderRepository
from app.repositories.photos import PhotoRepository
from app.schemas.order import PartnerJobRead
from app.schemas.photo import PartnerPhotoRead
from app.services.orders import OrderService, to_partner_job_dto
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
    return to_partner_job_dto(order, group=group, photos=photos)


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
    except Exception:
        db.rollback()
        storage.delete(stored_file.storage_key)
        raise
