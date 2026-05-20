from typing import Any
from urllib.parse import urlparse

from app.core.config import settings


class SecurityHeadersMiddleware:
    def __init__(self, app: Any) -> None:
        self.app = app
        self._headers = _build_security_headers()

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: dict) -> None:
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
