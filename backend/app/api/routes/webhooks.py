import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.core.config import settings
from app.services.messages import MessageService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/solapi")
async def receive_solapi_webhook(
    request: Request,
    x_solapi_signature: str | None = Header(default=None, alias="X-Solapi-Signature"),
    db: Session = Depends(get_session),
) -> dict[str, int]:
    body = await request.body()
    # 첫 실연동 시 SOLAPI 실제 웹훅 규격(서명 헤더명/서명 유무)을 근거로 검증기를 확정하기 위해,
    # 거부 시 헤더 '키'만(값 제외) 기록한다. 값/본문은 남기지 않아 PII 노출이 없다.
    try:
        verify_solapi_webhook_signature(body, x_solapi_signature)
    except HTTPException as exc:
        logger.warning(
            "SOLAPI webhook rejected (%s): header_keys=%s body_len=%d "
            "x_solapi_signature_present=%s secret_configured=%s",
            exc.detail,
            sorted(request.headers.keys()),
            len(body),
            x_solapi_signature is not None,
            bool(settings.solapi_webhook_secret),
        )
        raise

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid_solapi_webhook_payload") from exc
    if not isinstance(payload, list):
        raise HTTPException(status_code=400, detail="invalid_solapi_webhook_payload")

    events: list[dict[str, object]] = []
    for item in payload:
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail="invalid_solapi_webhook_payload")
        events.append(item)

    result = MessageService(db).process_solapi_webhook_events(events)
    return {
        "received": result.received,
        "updated": result.updated,
        "ignored": result.ignored,
        "unknown": result.unknown,
    }


def verify_solapi_webhook_signature(body: bytes, received_signature: str | None) -> None:
    if not settings.solapi_webhook_secret:
        raise HTTPException(status_code=401, detail="solapi_webhook_secret_required")

    expected_signature = hmac.new(
        settings.solapi_webhook_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    normalized_signature = (received_signature or "").strip()
    if normalized_signature.startswith("sha256="):
        normalized_signature = normalized_signature.removeprefix("sha256=")

    if not normalized_signature or not hmac.compare_digest(
        normalized_signature.lower(),
        expected_signature,
    ):
        raise HTTPException(status_code=401, detail="invalid_solapi_webhook_secret")
