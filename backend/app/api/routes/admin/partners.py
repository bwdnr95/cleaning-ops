from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_session, require_admin
from app.schemas.partner import (
    PartnerAdminRead,
    PartnerCreate,
    PartnerDetailRead,
    PartnerPasswordResetRead,
    PartnerPasswordResetRequest,
    PartnerUpdate,
)
from app.services.partners import PartnerService

router = APIRouter()


@router.get("", response_model=list[PartnerAdminRead])
def list_partners(
    include_inactive: bool = False,
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> list:
    return PartnerService(db).list_partners(include_inactive=include_inactive)


@router.post("", response_model=PartnerDetailRead, status_code=201)
def create_partner(
    payload: PartnerCreate,
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> PartnerDetailRead:
    return PartnerService(db).create(payload)


@router.get("/{partner_id}", response_model=PartnerDetailRead)
def get_partner(
    partner_id: str,
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> PartnerDetailRead:
    try:
        return PartnerService(db).get_detail(partner_id)
    except ValueError as exc:
        if str(exc) == "partner_not_found":
            raise HTTPException(status_code=404, detail="partner_not_found") from exc
        raise


@router.patch("/{partner_id}", response_model=PartnerDetailRead)
def update_partner(
    partner_id: str,
    payload: PartnerUpdate,
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> PartnerDetailRead:
    try:
        return PartnerService(db).update(partner_id, payload)
    except ValueError as exc:
        if str(exc) == "partner_not_found":
            raise HTTPException(status_code=404, detail="partner_not_found") from exc
        raise


@router.delete("/{partner_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_partner(
    partner_id: str,
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> Response:
    try:
        PartnerService(db).delete(partner_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ValueError as exc:
        if str(exc) == "partner_not_found":
            raise HTTPException(status_code=404, detail="partner_not_found") from exc
        if str(exc) == "partner_in_use":
            raise HTTPException(status_code=400, detail="partner_in_use") from exc
        raise


@router.post("/{partner_id}/reset-password", response_model=PartnerPasswordResetRead)
def reset_partner_password(
    partner_id: str,
    payload: PartnerPasswordResetRequest,
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> PartnerPasswordResetRead:
    try:
        return PartnerService(db).reset_password(
            partner_id,
            login_phone=payload.login_phone,
            password=payload.password,
        )
    except ValueError as exc:
        if str(exc) == "partner_not_found":
            raise HTTPException(status_code=404, detail="partner_not_found") from exc
        raise
