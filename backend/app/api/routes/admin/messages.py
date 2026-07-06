from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_session, require_admin
from app.schemas.message import (
    MessageLogRead,
    MessagePreviewRead,
    MessageSendRequest,
    MessageSettingsRead,
    DayBeforeNoticeRunRead,
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


@router.post("/day-before/run", response_model=DayBeforeNoticeRunRead)
def run_day_before_notices(
    target_date: date | None = None,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
) -> DayBeforeNoticeRunRead:
    return MessageService(db).send_day_before_notices(
        target_date=target_date,
        actor_user_id=user.id,
    )


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
        if str(exc) in {
            "no_customer_visible_photos",
            "customer_photo_evidence_incomplete",
            "customer_photo_ready_not_allowed",
        }:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if str(exc) == "customer_balance_not_due":
            raise HTTPException(status_code=400, detail="customer_balance_not_due") from exc
        if str(exc) == "as_request_required":
            raise HTTPException(status_code=400, detail="as_request_required") from exc
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
        if str(exc) in {
            "no_customer_visible_photos",
            "customer_photo_evidence_incomplete",
            "customer_photo_ready_not_allowed",
        }:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if str(exc) == "customer_balance_not_due":
            raise HTTPException(status_code=400, detail="customer_balance_not_due") from exc
        if str(exc) == "as_request_required":
            raise HTTPException(status_code=400, detail="as_request_required") from exc
        if str(exc) in {"partner_not_assigned", "partner_not_found", "invalid_recipient_type"}:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        raise
