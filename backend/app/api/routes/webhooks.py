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
SOLAPI_WEBHOOK_MAX_BYTES = 1_000_000


@router.post("/solapi")
async def receive_solapi_webhook(
    request: Request,
    x_solapi_secret: str | None = Header(default=None, alias="X-Solapi-Secret"),
    db: Session = Depends(get_session),
) -> dict[str, int]:
    try:
        verify_solapi_webhook_secret(x_solapi_secret)
    except HTTPException as exc:
        logger.warning(
            "SOLAPI webhook rejected (%s): header_keys=%s body_len=%d "
            "x_solapi_secret_present=%s secret_configured=%s",
            exc.detail,
            sorted(request.headers.keys()),
            0,
            x_solapi_secret is not None,
            bool(settings.solapi_webhook_secret),
        )
        raise

    body = await read_limited_body(request, max_bytes=SOLAPI_WEBHOOK_MAX_BYTES)

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


def verify_solapi_webhook_secret(received_secret: str | None) -> None:
    if not settings.solapi_webhook_secret:
        raise HTTPException(status_code=401, detail="solapi_webhook_secret_required")

    expected_secret = hashlib.sha1(
        settings.solapi_webhook_secret.encode("utf-8")
    ).hexdigest()
    normalized_secret = (received_secret or "").strip().lower()
    if not normalized_secret or not hmac.compare_digest(
        normalized_secret,
        expected_secret,
    ):
        raise HTTPException(status_code=401, detail="invalid_solapi_webhook_secret")


async def read_limited_body(request: Request, *, max_bytes: int) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > max_bytes:
                raise HTTPException(status_code=413, detail="solapi_webhook_payload_too_large")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid_content_length") from exc

    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > max_bytes:
            raise HTTPException(status_code=413, detail="solapi_webhook_payload_too_large")
        chunks.append(chunk)
    return b"".join(chunks)
