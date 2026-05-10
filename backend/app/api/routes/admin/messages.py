from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_session, require_admin
from app.schemas.message import (
    MessageLogRead,
    MessagePreviewRead,
    MessageSendRequest,
    MessageSettingsRead,
)
from app.services.messages import MessageService

router = APIRouter()


@router.get("", response_model=list[MessageLogRead])
def list_messages(
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> list:
    return MessageService(db).list_logs()


@router.get("/settings", response_model=MessageSettingsRead)
def get_message_settings(
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> MessageSettingsRead:
    return MessageService(db).settings_status()


@router.post("/send", response_model=MessageLogRead)
def send_message(
    payload: MessageSendRequest,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
):
    try:
        return MessageService(db).send(payload, actor_user_id=user.id)
    except ValueError as exc:
        if str(exc) == "order_not_found":
            raise HTTPException(status_code=404, detail="order_not_found") from exc
        if str(exc) == "no_customer_visible_photos":
            raise HTTPException(status_code=400, detail="no_customer_visible_photos") from exc
        if str(exc) in {"partner_not_assigned", "partner_not_found", "invalid_recipient_type"}:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        raise


@router.post("/preview", response_model=MessagePreviewRead)
def preview_message(
    payload: MessageSendRequest,
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
):
    try:
        return MessageService(db).preview(payload)
    except ValueError as exc:
        if str(exc) == "order_not_found":
            raise HTTPException(status_code=404, detail="order_not_found") from exc
        if str(exc) == "no_customer_visible_photos":
            raise HTTPException(status_code=400, detail="no_customer_visible_photos") from exc
        if str(exc) in {"partner_not_assigned", "partner_not_found", "invalid_recipient_type"}:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        raise
