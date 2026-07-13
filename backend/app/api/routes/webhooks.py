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
    x_solapi_signature: str | None = Header(default=None, alias="X-Solapi-Signature"),
    db: Session = Depends(get_session),
) -> dict[str, int]:
    body = await read_limited_body(request, max_bytes=SOLAPI_WEBHOOK_MAX_BYTES)
    try:
        verify_solapi_webhook_auth(
            body=body,
            received_secret=x_solapi_secret,
            received_signature=x_solapi_signature,
        )
    except HTTPException as exc:
        logger.warning(
            "SOLAPI webhook rejected (%s): header_keys=%s body_len=%d "
            "x_solapi_secret_present=%s secret_configured=%s",
            exc.detail,
            sorted(request.headers.keys()),
            len(body),
            x_solapi_secret is not None,
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


def verify_solapi_webhook_auth(
    *,
    body: bytes,
    received_secret: str | None,
    received_signature: str | None,
) -> None:
    if not settings.solapi_webhook_secret:
        raise HTTPException(status_code=401, detail="solapi_webhook_secret_required")

    if received_secret:
        verify_solapi_webhook_secret(received_secret)
        return

    normalized_signature = (received_signature or "").strip().lower()
    if normalized_signature.startswith("sha256="):
        normalized_signature = normalized_signature.removeprefix("sha256=")
    expected_signature = hmac.new(
        settings.solapi_webhook_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    if not normalized_signature or not hmac.compare_digest(
        normalized_signature, expected_signature
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
