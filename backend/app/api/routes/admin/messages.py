from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_session, require_admin
from app.schemas.message import MessageLogRead, MessageSendRequest
from app.services.messages import MessageService

router = APIRouter()


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
        raise
