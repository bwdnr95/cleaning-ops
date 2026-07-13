from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_session, require_admin
from app.core.time import business_today
from app.schemas.message import (
    DayBeforeNoticeRunRead,
    MessageLogRead,
    MessagePreviewRead,
    MessageSendRequest,
    MessageSettingsRead,
    MessageUnknownOutcomeResolutionRequest,
)
from app.services.messages import MessageService

router = APIRouter()


@router.get("", response_model=list[MessageLogRead])
def list_messages(
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> list[MessageLogRead]:
    return MessageService(db).list_logs()


@router.get("/settings", response_model=MessageSettingsRead)
def get_message_settings(
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> MessageSettingsRead:
    return MessageService(db).settings_status()


@router.post("/{message_id}/resolve-unknown", response_model=MessageLogRead)
def resolve_unknown_message_outcome(
    message_id: str,
    payload: MessageUnknownOutcomeResolutionRequest,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
) -> MessageLogRead:
    try:
        return MessageLogRead.model_validate(
            MessageService(db).resolve_unknown_outcome(
                message_id,
                resolution=payload.resolution,
                actor_user_id=user.id,
            )
        )
    except ValueError as exc:
        if str(exc) in {"message_not_found", "order_not_found"}:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if str(exc) in {
            "message_not_unknown_pending",
            "invalid_unknown_outcome_resolution",
        }:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        raise


@router.post("/day-before/run", response_model=DayBeforeNoticeRunRead)
def run_day_before_notices(
    target_date: date | None = None,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
) -> DayBeforeNoticeRunRead:
    tomorrow = business_today() + timedelta(days=1)
    if target_date is not None and target_date != tomorrow:
        raise HTTPException(status_code=409, detail="day_before_notice_not_due")
    return MessageService(db).send_day_before_notices(
        target_date=tomorrow,
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
        if str(exc) == "message_outcome_unknown":
            raise HTTPException(status_code=409, detail="message_outcome_unknown") from exc
        if str(exc) == "message_send_in_progress":
            raise HTTPException(status_code=409, detail="message_send_in_progress") from exc
        if str(exc) in {
            "partner_confirmation_required",
            "schedule_confirmation_not_allowed",
            "schedule_confirmation_target_changed",
            "day_before_notice_not_allowed",
            "day_before_notice_not_due",
            "day_before_notice_target_changed",
        }:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if str(exc) in {"partner_not_assigned", "partner_not_found", "invalid_recipient_type"}:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if str(exc) == "partner_assignment_not_allowed":
            raise HTTPException(status_code=409, detail=str(exc)) from exc
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
        if str(exc) == "message_outcome_unknown":
            raise HTTPException(status_code=409, detail="message_outcome_unknown") from exc
        if str(exc) == "message_send_in_progress":
            raise HTTPException(status_code=409, detail="message_send_in_progress") from exc
        if str(exc) in {
            "partner_confirmation_required",
            "schedule_confirmation_not_allowed",
            "schedule_confirmation_target_changed",
            "day_before_notice_not_allowed",
            "day_before_notice_not_due",
            "day_before_notice_target_changed",
        }:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if str(exc) in {"partner_not_assigned", "partner_not_found", "invalid_recipient_type"}:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if str(exc) == "partner_assignment_not_allowed":
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        raise
