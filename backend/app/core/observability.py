"""Sentry, structlog, request_id 통합.

production 환경에서 Sentry 가 의무이고, 모든 요청은 X-Request-ID 로
상관관계 추적이 가능해야 한다. structlog 는 stdout 으로 JSON 출력해서
호스팅 (Railway/Vercel) 의 기본 로그 수집에 그대로 흘러간다.
"""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

import structlog

from app.core.config import Settings

_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return _request_id_ctx.get()


def init_sentry(settings: Settings) -> None:
    if not settings.sentry_dsn:
        return

    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment or settings.environment,
        release=settings.sentry_release or settings.app_version,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=settings.sentry_send_default_pii,
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
        ],
    )


def configure_structlog(settings: Settings) -> None:
    """JSON-line 로그 + request_id 자동 주입."""

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        _inject_request_id,
        structlog.processors.StackInfoRenderer(),
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # stdlib logging 도 같은 형식으로 (uvicorn / sqlalchemy 로그)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processor=structlog.processors.JSONRenderer(),
        )
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO if settings.environment != "test" else logging.WARNING)


def _inject_request_id(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    rid = _request_id_ctx.get()
    if rid and "request_id" not in event_dict:
        event_dict["request_id"] = rid
    return event_dict


class RequestIDMiddleware:
    """X-Request-ID 헤더 수신/발급 + contextvar 주입.

    - 클라이언트가 보낸 X-Request-ID 가 있으면 그대로 사용 (api/client.ts 가 자동 부여 중)
    - 없으면 uuid4 hex 발급
    - 응답 헤더에도 echo
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = _read_header(scope.get("headers") or [], b"x-request-id")
        request_id = incoming or uuid.uuid4().hex
        token = _request_id_ctx.set(request_id)

        async def send_with_header(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        finally:
            _request_id_ctx.reset(token)


def _read_header(headers: list[tuple[bytes, bytes]], name: bytes) -> str | None:
    for key, value in headers:
        if key.lower() == name:
            try:
                return value.decode("ascii").strip() or None
            except UnicodeDecodeError:
                return None
    return None
