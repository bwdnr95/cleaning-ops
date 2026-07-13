from typing import Final
from urllib.parse import urlparse

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings

_CUSTOMER_AS_PATH_PREFIX: Final = "/api/customer/orders/"
_CUSTOMER_AS_PATH_SUFFIX: Final = "/as-request"
_TOO_LARGE_BODY: Final = b'{"detail":"as_photos_total_too_large"}'


class RequestBodyTooLargeError(Exception):
    pass


class CustomerAsRequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not _is_customer_as_upload_request(scope):
            await self.app(scope, receive, send)
            return

        max_body_bytes = _customer_as_max_request_body_bytes()
        content_length = _content_length(scope)
        if content_length is not None and content_length > max_body_bytes:
            await _send_customer_as_too_large(send)
            return

        received_bytes = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                received_bytes += len(body)
                if received_bytes > max_body_bytes:
                    raise RequestBodyTooLargeError
            return message

        async def send_with_state(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, send_with_state)
        except RequestBodyTooLargeError:
            if response_started:
                raise
            await _send_customer_as_too_large(send)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._headers = _build_security_headers()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(self._headers)
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


def _build_security_headers() -> list[tuple[bytes, bytes]]:
    headers: list[tuple[bytes, bytes]] = [
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"referrer-policy", b"strict-origin-when-cross-origin"),
        (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
    ]

    csp = _build_csp_value()
    headers.append((b"content-security-policy", csp.encode("ascii")))

    if settings.environment == "production":
        headers.append(
            (
                b"strict-transport-security",
                b"max-age=31536000; includeSubDomains; preload",
            )
        )

    return headers


def _is_customer_as_upload_request(scope: Scope) -> bool:
    path = scope.get("path", "")
    return (
        scope.get("type") == "http"
        and scope.get("method") == "POST"
        and isinstance(path, str)
        and path.startswith(_CUSTOMER_AS_PATH_PREFIX)
        and path.endswith(_CUSTOMER_AS_PATH_SUFFIX)
    )


def _customer_as_max_request_body_bytes() -> int:
    return settings.customer_as_max_upload_bytes + settings.customer_as_request_body_overhead_bytes


def _content_length(scope: Scope) -> int | None:
    for key, value in scope.get("headers", []):
        if key.lower() != b"content-length":
            continue
        try:
            return int(value.decode("latin1"))
        except ValueError:
            return None
    return None


async def _send_customer_as_too_large(send: Send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(_TOO_LARGE_BODY)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": _TOO_LARGE_BODY})


def _build_csp_value() -> str:
    img_sources = {"'self'", "data:", "blob:"}
    connect_sources = {"'self'", "https://postcode.map.kakao.com"}
    script_sources = {"'self'", "https://t1.daumcdn.net"}
    frame_sources = {"https://postcode.map.kakao.com"}
    public_storage = settings.s3_public_base_url.strip()
    if public_storage:
        img_sources.add(_origin(public_storage))

    sentry_dsn = settings.sentry_dsn.strip()
    if sentry_dsn:
        sentry_origin = _origin(sentry_dsn)
        if sentry_origin:
            connect_sources.add(sentry_origin)

    for origin in settings.cors_origins:
        if origin and origin != "*":
            connect_sources.add(origin)

    parts = [
        "default-src 'self'",
        f"img-src {' '.join(sorted(img_sources))}",
        f"connect-src {' '.join(sorted(connect_sources))}",
        f"script-src {' '.join(sorted(script_sources))}",
        f"frame-src {' '.join(sorted(frame_sources))}",
        "style-src 'self' 'unsafe-inline'",
        "font-src 'self' data:",
        "object-src 'none'",
        "base-uri 'self'",
        "frame-ancestors 'none'",
        "form-action 'self'",
    ]
    return "; ".join(parts)


def _origin(url: str) -> str:
    try:
        parsed = urlparse(url)
    except ValueError:
        return ""
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"
