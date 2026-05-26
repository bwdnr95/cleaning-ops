# R10 Production Foundation Implementation Plan

> **Codex 작업자에게**: task-by-task로 진행하라. 각 step의 코드/명령은 그대로 실행 가능해야 한다. 각 task 마지막은 git commit으로 끝낸다. 의문 사항은 사용자에게 묻지 말고 D-결정 사항을 따른다.

> **이력**
> - v1 (2026-05-25): 초안. R1–R9 완료 + R8 cross-review APPROVED 시점 기준.

> **선행 문서**
> - `docs/plans/2026-05-25-roadmap-r10-to-r15.md` — 전체 로드맵 + 우선순위 근거
> - `AGENTS.md`, `CLAUDE.md`, `.claude/rules/backend.md`, `.claude/rules/frontend.md`
> - `.master/next_session_plan.md` — 최신 상태

**Goal:** production 환경에서 발생하는 사고를 사전에 차단할 수 있는 기반을 갖춘다. 구체적으로:
1. **인증 보안**: localStorage 기반 JWT → httpOnly + Secure cookie. XSS로 토큰 탈취 불가.
2. **장애 가시화**: Sentry 실연동 + structured logging(JSON, request_id) + health check 분리.
3. **데이터 안전망**: Postgres 자동 백업(pg_dump → 로컬 + S3 옵션) + 복구 절차 runbook.
4. **CI 기본**: GitHub Actions로 PR 시 lint/test 자동 실행. main 머지 시 자동 빌드 산출물 생성.
5. **secret 관리 위생**: secret_key 자동 생성 가이드, `.env.example` 신설, 운영용 `.env.production` 템플릿.

**Architecture:**
- 인증은 **httpOnly cookie + double-submit CSRF token** 패턴. Access는 짧은 TTL의 cookie, Refresh는 더 긴 TTL의 cookie. CSRF 토큰은 별도 non-httpOnly cookie로 전달하고, 변경 메서드(POST/PUT/PATCH/DELETE) 호출 시 `X-CSRF-Token` 헤더로 검증.
- 로깅은 `structlog` + JSON renderer. `X-Request-ID`가 모든 로그 라인에 포함되어 trace 가능.
- Sentry는 `sentry-sdk[fastapi]`로 wiring, `sentry_environment`, `sentry_release` 환경 변수 사용. PII는 `send_default_pii=False`.
- 백업은 `docker exec cleanops_postgres pg_dump`를 호스트의 cron이 호출하고 `backups/` 디렉터리에 `cleaning_ops_YYYYMMDD_HHMM.dump.gz`로 저장. 7일 보관 정책.
- CI는 GitHub Actions에서 backend `python -m pytest -q` + frontend `npm run lint && npm run typecheck && npm run build`. E2E는 별도 워크플로(수동 트리거)로 분리.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 · Pydantic v2 · React 19 + TypeScript · Playwright · Alembic · structlog · sentry-sdk · GitHub Actions.

---

## CTO 결정 사항 (D-항목)

- **D1. 인증 저장 방식**: **httpOnly Secure SameSite=Lax cookie**. JS에서 토큰을 만질 수 없다. CSRF 방어는 double-submit cookie 패턴 (`csrftoken` 비-HttpOnly 쿠키 + `X-CSRF-Token` 헤더 매칭).
- **D2. cookie TTL**: access cookie 60분, refresh cookie 7일 (R8.6의 24h + 7d 정책 유지하되 access는 60분으로 단축 — cookie는 자동 갱신되므로 짧아도 운영 불편 X).
- **D3. logout 시 처리**: `/api/auth/logout` 호출 시 서버가 `Set-Cookie: ...; Max-Age=0` 으로 두 cookie 만료 + refresh token revoke.
- **D4. localStorage 정리**: 기존 `cleaning_ops_auth_sessions_v2` localStorage 키는 frontend boot 시점에 1회 삭제. 마이그레이션 코드는 1년 후 제거.
- **D5. 로깅 포맷**: 모든 로그는 JSON 한 줄. 필수 필드: `ts`, `level`, `msg`, `request_id`, `user_id`, `route`, `latency_ms`, `status`. 비밀번호/토큰/PII는 절대 로깅 X.
- **D6. Sentry sampling**: traces_sample_rate는 production 0.1, development 0.0. before_send에서 password/token 필드 strip.
- **D7. 백업 보관**: 로컬 `backups/` 7일 + 옵션 S3 30일. S3는 R12와 연동되므로 R10에서는 로컬만 의무, S3는 환경변수 있을 때 추가 업로드.
- **D8. CI 트리거**: PR open/push 시 lint+test, main push 시 lint+test+build artifact 업로드. 실제 배포는 사용자가 수동 (R10 범위 외).
- **D9. secret_key 강제**: production에서 길이 32자 미만이거나 default 값이면 `Settings.model_post_init` 단계에서 ValueError로 부팅 거부 (R8에서 이미 구현됨, 재확인).
- **D10. CSRF 적용 범위**: 모든 state-changing 라우트(POST/PUT/PATCH/DELETE). GET/HEAD/OPTIONS는 제외. webhook(`/api/webhooks/*`)은 별도 signature 검증이므로 CSRF 면제.

---

## File Map — 무엇을 어디서 바꾸는가

| 영역 | 파일 | 종류 |
|---|---|---|
| 정책 | `AGENTS.md` | 수정 (Security And Privacy Rules: localStorage 금지 + CSRF 정책) |
| 정책 | `CLAUDE.md` | 수정 (§ "three rules" 인근에 logging/observability 1줄) |
| 백엔드 의존성 | `backend/requirements.txt` 또는 `pyproject.toml` | 수정 (structlog, sentry-sdk[fastapi]) |
| 백엔드 설정 | `backend/app/core/config.py` | 수정 (cookie TTL, secure flag) |
| 백엔드 코어 | `backend/app/core/cookies.py` | 신규 (cookie set/clear 헬퍼) |
| 백엔드 코어 | `backend/app/core/csrf.py` | 신규 (double-submit CSRF) |
| 백엔드 코어 | `backend/app/core/logging.py` | 신규 (structlog 설정) |
| 백엔드 코어 | `backend/app/core/observability.py` | 신규 (Sentry init) |
| 백엔드 코어 | `backend/app/main.py` | 수정 (logging/sentry/CSRF middleware 등록) |
| 백엔드 미들웨어 | `backend/app/core/middleware.py` | 수정 (request_id, access log) |
| 백엔드 라우터 | `backend/app/api/routes/auth.py` (또는 동등 위치) | 수정 (login은 Set-Cookie, refresh/logout 동일) |
| 백엔드 deps | `backend/app/api/deps.py` | 수정 (require_admin/partner가 cookie에서 토큰 read) |
| 백엔드 헬스 | `backend/app/api/routes/health.py` | 수정 (`/live`, `/ready` 분리 + DB ping) |
| 백엔드 알embic | (없음) | — (스키마 변경 없음) |
| 백엔드 테스트 | `backend/tests/test_auth_cookie.py` | 신규 |
| 백엔드 테스트 | `backend/tests/test_csrf.py` | 신규 |
| 백엔드 테스트 | `backend/tests/test_logging.py` | 신규 |
| 백엔드 테스트 | `backend/tests/test_health.py` | 신규 |
| 프론트 API | `frontend/src/api/client.ts` | 수정 (Authorization 헤더 제거, credentials: 'include', CSRF 헤더 자동 부여) |
| 프론트 store | `frontend/src/store/authStore.tsx` | 수정 (localStorage 삭제, 토큰 state 제거, `me` 응답만 보관) |
| 프론트 API | `frontend/src/api/auth.ts` | 수정 (login 응답에서 access/refresh 제거, `me` 호출) |
| 프론트 신규 | `frontend/src/api/me.ts` | 신규 (`GET /api/auth/me` wrapper) |
| 프론트 boot | `frontend/src/main.tsx` 또는 App boot | 수정 (legacy localStorage 1회 정리) |
| 운영 스크립트 | `scripts/backup.sh` | 신규 (pg_dump → backups/) |
| 운영 스크립트 | `scripts/restore.sh` | 신규 (gz dump → docker exec psql) |
| 운영 문서 | `docs/runbooks/r10-backup-and-restore.md` | 신규 |
| 운영 문서 | `docs/runbooks/r10-observability.md` | 신규 (Sentry/logging 사용법) |
| 환경 템플릿 | `backend/.env.example` | 신규 |
| 환경 템플릿 | `backend/.env.production.example` | 신규 |
| CI | `.github/workflows/ci.yml` | 신규 |
| 핸드오프 | `.master/next_session_plan.md` | 수정 (R10 마감 후) |

---

## Task 1 — 정책 문서 갱신 (AGENTS.md + CLAUDE.md)

**Files:**
- Modify: `AGENTS.md` (§ "Security And Privacy Rules" 인근)
- Modify: `CLAUDE.md` (§ "three rules" 인근)

정책 문서를 코드보다 먼저 갱신해야 후속 task에서 가정이 정렬된다.

- [ ] **Step 1: AGENTS.md에 cookie/CSRF 정책 추가**

`## Security And Privacy Rules` 마지막에 다음을 삽입한다.

```markdown
- 인증 토큰은 **httpOnly + Secure + SameSite=Lax cookie**로만 전달한다. `localStorage`/`sessionStorage`/JS 접근 가능한 위치에 access/refresh token을 저장하지 않는다.
- 상태 변경 API(POST/PUT/PATCH/DELETE)는 double-submit CSRF 토큰을 요구한다. 클라이언트는 `csrftoken` 비-HttpOnly 쿠키 값을 `X-CSRF-Token` 헤더로 함께 보낸다. GET/HEAD/OPTIONS 및 `/api/webhooks/*` 는 면제.
- 모든 요청은 `X-Request-ID` 헤더를 갖는다 (없으면 서버가 생성). 모든 로그 라인에 `request_id`가 포함되어야 한다.
- 비밀번호, 토큰, 결제정보, 전화번호 끝 4자리는 절대 로깅하지 않는다.
```

- [ ] **Step 2: CLAUDE.md § "three rules" 다음에 4번 룰을 5번으로 확장**

기존 4번(soft-delete) 다음에 추가:

```markdown
5. **모든 mutation은 구조화 로그를 남긴다.** structlog가 자동으로 `request_id`/`user_id`/`route`/`latency_ms`/`status`를 JSON으로 출력한다. Sentry는 production에서만 enabled. 자세한 내용은 `docs/runbooks/r10-observability.md`.
```

- [ ] **Step 3: 커밋**

```bash
git add AGENTS.md CLAUDE.md
git commit -m "docs(policy): R10 httpOnly cookie + CSRF + observability 정책 명시"
```

---

## Task 2 — 의존성 추가 + 환경 템플릿

**Files:**
- Modify: `backend/requirements.txt` (없으면 `pyproject.toml`)
- Create: `backend/.env.example`
- Create: `backend/.env.production.example`

- [ ] **Step 1: 의존성 추가**

`backend/requirements.txt`가 있다면 다음 줄을 추가. 없으면 `pip install` 결과를 `pip freeze`로 동기화하는 절차 사용.

```
structlog>=24.4
sentry-sdk[fastapi]>=2.18
```

확인:
```bash
cd backend && python -c "import structlog, sentry_sdk; print(structlog.__version__, sentry_sdk.VERSION)"
```

- [ ] **Step 2: `.env.example` 작성 (개발자가 참고)**

```dotenv
# 개발 기본값. 실제 .env에 복사 후 사용.
ENVIRONMENT=development
DATABASE_URL=postgresql+psycopg://cleanops:cleanops_local_dev@localhost:5434/cleaning_ops?client_encoding=utf8
SECRET_KEY=please-generate-with-python-c-import-secrets-print-secrets-token-urlsafe-48
STORAGE_ROOT=local_storage
MESSAGE_PROVIDER=mock
FRONTEND_URL=http://localhost:5175
CORS_ORIGINS=["http://localhost:5175"]
COOKIE_SECURE=false  # local http 개발용
COOKIE_DOMAIN=
SENTRY_DSN=
SENTRY_ENVIRONMENT=development
SENTRY_TRACES_SAMPLE_RATE=0.0
LOG_LEVEL=DEBUG
```

- [ ] **Step 3: `.env.production.example` 작성 (운영 owner가 채워서 사용)**

```dotenv
ENVIRONMENT=production
DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:5432/cleaning_ops?client_encoding=utf8
SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(48))" 결과>
STORAGE_PROVIDER=s3
S3_BUCKET=<bucket-name>
S3_REGION=ap-northeast-2
S3_ACCESS_KEY_ID=<key>
S3_SECRET_ACCESS_KEY=<secret>
S3_PUBLIC_BASE_URL=https://<cdn-domain>
MESSAGE_PROVIDER=solapi
SOLAPI_API_KEY=<key>
SOLAPI_API_SECRET=<secret>
SOLAPI_SENDER_NUMBER=<발신번호>
SOLAPI_WEBHOOK_SECRET=<webhook-shared-secret>
FRONTEND_URL=https://cleanjob.tono-operation.com
CORS_ORIGINS=["https://cleanjob.tono-operation.com"]
COOKIE_SECURE=true
COOKIE_DOMAIN=cleanjob.tono-operation.com
SENTRY_DSN=https://...@sentry.io/...
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1
LOG_LEVEL=INFO
```

- [ ] **Step 4: 커밋**

```bash
git add backend/requirements.txt backend/.env.example backend/.env.production.example
git commit -m "chore(deps): R10 structlog + sentry-sdk 추가 + .env 템플릿"
```

---

## Task 3 — Settings 확장 (cookie + 새 환경변수)

**Files:**
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: Settings 클래스에 필드 추가**

`Settings` 클래스 내부에 추가:

```python
# Cookie / CSRF
cookie_secure: bool = False
cookie_domain: str = ""
cookie_samesite: str = "lax"
access_cookie_name: str = "cleanops_access"
refresh_cookie_name: str = "cleanops_refresh"
csrf_cookie_name: str = "csrftoken"
csrf_header_name: str = "X-CSRF-Token"

# Logging
log_level: str = "INFO"
log_format: str = "json"  # "json" | "console"
```

- [ ] **Step 2: production 강제 검증을 `model_post_init`에 추가**

기존 `model_post_init` 마지막에 다음 블록 추가:

```python
if self.environment == "production":
    if not self.cookie_secure:
        raise ValueError("production requires cookie_secure=true")
    if not self.cookie_domain:
        raise ValueError("production requires cookie_domain (e.g. cleanjob.tono-operation.com)")
    if self.sentry_traces_sample_rate < 0.0 or self.sentry_traces_sample_rate > 1.0:
        raise ValueError("sentry_traces_sample_rate must be in [0.0, 1.0]")
```

- [ ] **Step 3: 빠른 검증**

```bash
cd backend && python -c "from app.core.config import settings; print('cookie_secure:', settings.cookie_secure, 'log_level:', settings.log_level)"
```
Expected: 에러 없이 출력.

- [ ] **Step 4: 커밋**

```bash
git add backend/app/core/config.py
git commit -m "feat(config): R10 cookie/CSRF/logging 환경변수 추가 + production 강제 검증"
```

---

## Task 4 — Structured Logging (structlog)

**Files:**
- Create: `backend/app/core/logging.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/core/middleware.py`
- Test: `backend/tests/test_logging.py` (신규)

- [ ] **Step 1: 실패 테스트 — 로그가 JSON으로 나오는지 + request_id 포함**

`backend/tests/test_logging.py`:

```python
import json

from app.core.logging import configure_logging, get_logger


def test_log_output_is_single_line_json(capsys):
    configure_logging(level="INFO", fmt="json")
    log = get_logger(__name__)
    log.info("hello", request_id="r-123", user_id="u-1", route="/test")
    captured = capsys.readouterr().out.strip()
    payload = json.loads(captured.splitlines()[-1])
    assert payload["msg"] == "hello"
    assert payload["request_id"] == "r-123"
    assert payload["user_id"] == "u-1"
    assert payload["route"] == "/test"
    assert payload["level"] == "info"
    assert "ts" in payload


def test_log_redacts_password(capsys):
    configure_logging(level="INFO", fmt="json")
    log = get_logger(__name__)
    log.info("login_attempt", password="should-not-leak", username="admin@x.kr")
    captured = capsys.readouterr().out.strip()
    payload = json.loads(captured.splitlines()[-1])
    assert payload.get("password") == "***"
    assert payload["username"] == "admin@x.kr"
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
cd backend && python -m pytest tests/test_logging.py -v
```
Expected: ImportError (`configure_logging`, `get_logger` 미정의).

- [ ] **Step 3: `app/core/logging.py` 구현**

```python
import logging
import sys
from typing import Any

import structlog

_REDACT_KEYS = {"password", "token", "access_token", "refresh_token", "secret"}


def _redact_secrets(_, __, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key in list(event_dict.keys()):
        if key.lower() in _REDACT_KEYS:
            event_dict[key] = "***"
    return event_dict


def configure_logging(*, level: str = "INFO", fmt: str = "json") -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
        structlog.processors.add_log_level,
        _redact_secrets,
    ]
    if fmt == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=False))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def bind_request_context(*, request_id: str, user_id: str | None = None, route: str | None = None) -> None:
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        user_id=user_id or "",
        route=route or "",
    )


def clear_request_context() -> None:
    structlog.contextvars.clear_contextvars()
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_logging.py -v
```
Expected: 2 passed.

- [ ] **Step 5: `app/main.py` 시작 시점에 logging 초기화 + middleware에 request context 바인딩**

`app/main.py` 상단(FastAPI 인스턴스 생성 직후)에 추가:

```python
from app.core.logging import configure_logging
from app.core.config import settings

configure_logging(level=settings.log_level, fmt=settings.log_format)
```

`app/core/middleware.py`에 access log middleware 추가 — 기존 middleware 옆에 `add_request_logging_middleware(app)` 같은 패턴으로 wiring:

```python
import time
import uuid

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.logging import bind_request_context, clear_request_context, get_logger

_log = get_logger("http")


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _extract_or_create_request_id(scope)
        route = scope.get("path", "")
        bind_request_context(request_id=request_id, route=route)

        started = time.perf_counter()
        status_code_holder = {"status": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code_holder["status"] = message["status"]
                headers = list(message.get("headers") or [])
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            latency_ms = round((time.perf_counter() - started) * 1000, 1)
            _log.info(
                "http_access",
                method=scope.get("method"),
                status=status_code_holder["status"],
                latency_ms=latency_ms,
            )
            clear_request_context()


def _extract_or_create_request_id(scope: Scope) -> str:
    for name, value in scope.get("headers") or []:
        if name == b"x-request-id":
            return value.decode("ascii", errors="ignore") or _new_id()
    return _new_id()


def _new_id() -> str:
    return uuid.uuid4().hex
```

`app/main.py`에서 미들웨어 등록 (기존 미들웨어 등록 위치 다음):

```python
from app.core.middleware import RequestLoggingMiddleware

app.add_middleware(RequestLoggingMiddleware)
```

- [ ] **Step 6: 회귀 확인**

```bash
python -m pytest -q
```
Expected: 모두 통과 (121+).

- [ ] **Step 7: 커밋**

```bash
git add backend/app/core/logging.py backend/app/core/middleware.py backend/app/main.py backend/tests/test_logging.py
git commit -m "feat(observability): R10 structlog 기반 구조화 로그 + request_id 추적"
```

---

## Task 5 — Sentry wiring

**Files:**
- Create: `backend/app/core/observability.py`
- Modify: `backend/app/main.py`
- Create: `docs/runbooks/r10-observability.md`

- [ ] **Step 1: `app/core/observability.py` 작성**

```python
from __future__ import annotations

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.core.config import settings

_SENSITIVE_KEYS = {"password", "token", "access_token", "refresh_token", "secret"}


def _before_send(event, hint):
    request = event.get("request") or {}
    headers = request.get("headers") or {}
    if isinstance(headers, dict):
        for key in list(headers.keys()):
            if key.lower() in {"authorization", "cookie", "x-csrf-token"}:
                headers[key] = "***"
    data = request.get("data")
    if isinstance(data, dict):
        for key in list(data.keys()):
            if key.lower() in _SENSITIVE_KEYS:
                data[key] = "***"
    return event


def init_sentry() -> None:
    dsn = settings.sentry_dsn.strip()
    if not dsn:
        return
    sentry_sdk.init(
        dsn=dsn,
        environment=settings.sentry_environment or settings.environment,
        release=settings.sentry_release or None,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=settings.sentry_send_default_pii,
        before_send=_before_send,
        integrations=[
            FastApiIntegration(),
            StarletteIntegration(),
            SqlalchemyIntegration(),
        ],
    )
```

- [ ] **Step 2: `app/main.py`에 wiring**

`configure_logging` 호출 다음에:

```python
from app.core.observability import init_sentry

init_sentry()
```

- [ ] **Step 3: 임시 검증용 라우트 (실 배포 X)**

별도 endpoint를 만들지 않고, 다음 1회 명령으로 Sentry로 이벤트가 가는지만 본다 (로컬에 DSN을 .env에 채워 둔 상태에서):

```bash
cd backend && python -c "from app.core.observability import init_sentry; init_sentry(); import sentry_sdk; sentry_sdk.capture_message('R10 wiring check')"
```

(DSN이 없으면 no-op; CI에서는 검증 X.)

- [ ] **Step 4: runbook 작성**

`docs/runbooks/r10-observability.md`:

```markdown
# R10 운영 관측 (Sentry + 구조화 로그)

## Sentry 사용법
- DSN: 운영 owner가 sentry.io 프로젝트 생성 후 .env의 SENTRY_DSN에 채움.
- environment: production / staging / development 구분.
- traces_sample_rate: production 0.1 (10% 샘플링), development 0.0.
- 자동 캡쳐: FastAPI 5xx, unhandled exception, SQLAlchemy 에러.
- 수동 캡쳐: 코드에서 `import sentry_sdk; sentry_sdk.capture_message("msg")` 또는 `capture_exception(exc)`.

## 로그 조회
- 운영 서버 stdout이 JSON 한 줄.
- 모든 라인에 `request_id` 포함. 운영팀이 사고 보고 시 브라우저 콘솔의 `X-Request-ID`를 받아 grep:
  ```
  docker logs cleanops_postgres ... | grep '"request_id":"<id>"'
  ```
  (실제 배포 환경에서는 backend 로그 위치에 맞춰 grep)

## 민감 정보 정책
- password/token/cookie/CSRF 헤더는 자동 redact.
- 운영팀이 "이 사진 누가 올렸어?"를 묻는 경우 user_id로만 추적 (이름/전화 직접 안 씀).
```

- [ ] **Step 5: 회귀**

```bash
python -m pytest -q
```

- [ ] **Step 6: 커밋**

```bash
git add backend/app/core/observability.py backend/app/main.py docs/runbooks/r10-observability.md
git commit -m "feat(observability): R10 Sentry wiring + before_send PII redact + runbook"
```

---

## Task 6 — Health Check 분리 (`/live`, `/ready`)

**Files:**
- Modify: `backend/app/api/routes/health.py` (없으면 생성)
- Test: `backend/tests/test_health.py` (신규)

운영자가 reverse proxy / docker healthcheck에서 사용. `/live`는 프로세스 존재만, `/ready`는 DB ping 포함.

- [ ] **Step 1: 실패 테스트**

```python
from fastapi.testclient import TestClient

from app.main import app


def test_liveness_returns_200_without_db():
    client = TestClient(app)
    response = client.get("/api/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "live"}


def test_readiness_pings_db():
    client = TestClient(app)
    response = client.get("/api/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["db"] == "ok"
```

- [ ] **Step 2: 라우트 구현**

`backend/app/api/routes/health.py`에 (기존 `/health` 유지 + 신규 path 추가):

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_session

router = APIRouter()


@router.get("/live", summary="Liveness")
def liveness() -> dict[str, str]:
    return {"status": "live"}


@router.get("/ready", summary="Readiness")
def readiness(db: Session = Depends(get_session)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="db_unreachable") from exc
    return {"status": "ready", "db": "ok"}
```

- [ ] **Step 3: 테스트 통과**

```bash
python -m pytest tests/test_health.py -v
```
Expected: 2 passed.

- [ ] **Step 4: 커밋**

```bash
git add backend/app/api/routes/health.py backend/tests/test_health.py
git commit -m "feat(health): R10 /live + /ready 분리 + DB ping"
```

---

## Task 7 — httpOnly Cookie 기반 인증 (Backend)

**Files:**
- Create: `backend/app/core/cookies.py`
- Create: `backend/app/core/csrf.py`
- Modify: `backend/app/api/deps.py`
- Modify: 인증 라우트 (예: `backend/app/api/routes/auth.py` — 실제 위치 확인 후)
- Test: `backend/tests/test_auth_cookie.py` (신규)
- Test: `backend/tests/test_csrf.py` (신규)

⚠️ **이 task는 가장 큼**. 여러 step으로 분할.

- [ ] **Step 1: `app/core/cookies.py` — Set/Clear 헬퍼**

```python
from __future__ import annotations

from fastapi import Response

from app.core.config import settings


def set_access_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.access_cookie_name,
        value=token,
        max_age=settings.access_token_ttl_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain or None,
        path="/",
    )


def set_refresh_cookie(response: Response, token: str, *, role: str) -> None:
    ttl_days = (
        settings.partner_refresh_token_ttl_days
        if role == "partner"
        else settings.admin_refresh_token_ttl_days
    )
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=ttl_days * 24 * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain or None,
        path="/api/auth",  # refresh는 auth endpoint에서만 보내짐
    )


def set_csrf_cookie(response: Response, token: str) -> None:
    # CSRF는 비-HttpOnly. JS가 읽어 헤더에 복사한다.
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=token,
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain or None,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    for name, path in (
        (settings.access_cookie_name, "/"),
        (settings.refresh_cookie_name, "/api/auth"),
        (settings.csrf_cookie_name, "/"),
    ):
        response.delete_cookie(
            key=name,
            domain=settings.cookie_domain or None,
            path=path,
        )
```

- [ ] **Step 2: `app/core/csrf.py` — double-submit 검증**

```python
from __future__ import annotations

import hmac
import secrets

from fastapi import HTTPException, Request, status

from app.core.config import settings

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_CSRF_EXEMPT_PATHS = ("/api/webhooks/",)


def issue_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def enforce_csrf(request: Request) -> None:
    if request.method in _SAFE_METHODS:
        return
    if any(request.url.path.startswith(p) for p in _CSRF_EXEMPT_PATHS):
        return

    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    header_token = request.headers.get(settings.csrf_header_name)
    if not cookie_token or not header_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="csrf_missing")
    if not hmac.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="csrf_mismatch")
```

`enforce_csrf`는 FastAPI middleware로 등록한다 (`app/main.py`):

```python
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.csrf import enforce_csrf


class CsrfMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        enforce_csrf(request)
        return await call_next(request)


app.add_middleware(CsrfMiddleware)
```

- [ ] **Step 3: deps.py — cookie에서 access token 읽기**

`backend/app/api/deps.py`의 `require_admin`/`require_partner` 의존성을 갱신. 기존 Authorization 헤더 fallback은 일정 기간 유지 (R10 → R11 마이그레이션 안전망):

```python
def _extract_access_token(request: Request) -> str | None:
    token = request.cookies.get(settings.access_cookie_name)
    if token:
        return token
    # Fallback: Authorization 헤더 (legacy 클라이언트). R11에서 제거.
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return None
```

`get_current_user` 패턴을 위 함수로 통일.

- [ ] **Step 4: 인증 라우트 — login 응답에서 토큰을 body 대신 Set-Cookie로**

먼저 실제 인증 라우트 파일 위치를 확인:
```
Grep: pattern="admin_login\|partner_login\|/auth/admin/login" type="py"
```

해당 라우트에서 (예시 — 실제 패턴은 위 grep으로 찾아 적용):

```python
@router.post("/admin/login")
def admin_login(payload: LoginInput, response: Response, db: Session = Depends(get_session)):
    session = AuthService(db).admin_login(payload.identifier, payload.password)
    set_access_cookie(response, session.access_token)
    set_refresh_cookie(response, session.refresh_token, role="admin")
    set_csrf_cookie(response, issue_csrf_token())
    return {"user": to_user_dto(session.user)}  # 토큰 body 제거
```

`logout`, `refresh` 라우트도 동일 패턴으로 갱신.

- [ ] **Step 5: `/api/auth/me` 신설 — frontend boot 시 사용자 정보 조회**

```python
@router.get("/me")
def me(user: CurrentUser = Depends(get_current_user_optional)) -> dict:
    if user is None:
        raise HTTPException(status_code=401, detail="unauthenticated")
    return {"user": to_user_dto(user)}
```

- [ ] **Step 6: 통합 테스트 — login → cookie set → /me → logout → cookie clear**

`backend/tests/test_auth_cookie.py`:

```python
from fastapi.testclient import TestClient

from app.main import app
from app.db.seed import DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD


def test_admin_login_sets_httponly_cookies():
    client = TestClient(app)
    response = client.post(
        "/api/auth/admin/login",
        json={"identifier": DEV_ADMIN_EMAIL, "password": DEV_ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    cookies = response.cookies
    assert "cleanops_access" in cookies
    assert "cleanops_refresh" in cookies
    assert "csrftoken" in cookies

    # body에 access_token 없음
    body = response.json()
    assert "access_token" not in body
    assert "refresh_token" not in body
    assert body["user"]["role"] == "admin"


def test_me_returns_user_from_cookie():
    client = TestClient(app)
    client.post(
        "/api/auth/admin/login",
        json={"identifier": DEV_ADMIN_EMAIL, "password": DEV_ADMIN_PASSWORD},
    )
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "admin"


def test_logout_clears_cookies():
    client = TestClient(app)
    client.post(
        "/api/auth/admin/login",
        json={"identifier": DEV_ADMIN_EMAIL, "password": DEV_ADMIN_PASSWORD},
    )
    # CSRF 토큰 동봉
    csrf = client.cookies.get("csrftoken")
    response = client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 204
    me = client.get("/api/auth/me")
    assert me.status_code == 401
```

- [ ] **Step 7: CSRF 테스트**

`backend/tests/test_csrf.py`:

```python
from fastapi.testclient import TestClient

from app.main import app
from app.db.seed import DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD


def _login(client: TestClient) -> str:
    client.post(
        "/api/auth/admin/login",
        json={"identifier": DEV_ADMIN_EMAIL, "password": DEV_ADMIN_PASSWORD},
    )
    return client.cookies.get("csrftoken")


def test_post_without_csrf_header_is_403():
    client = TestClient(app)
    _login(client)
    response = client.post("/api/admin/orders", json={})  # 잘못된 body지만 CSRF 가드가 먼저 막아야 함
    assert response.status_code == 403
    assert response.json()["detail"] in {"csrf_missing", "csrf_mismatch"}


def test_post_with_correct_csrf_passes_gate():
    client = TestClient(app)
    csrf = _login(client)
    response = client.post(
        "/api/admin/orders",
        json={},
        headers={"X-CSRF-Token": csrf},
    )
    # 422 (validation) 또는 다른 4xx가 와도 됨. 403만 아니면 CSRF는 통과.
    assert response.status_code != 403


def test_get_is_exempt_from_csrf():
    client = TestClient(app)
    _login(client)
    response = client.get("/api/admin/orders")
    assert response.status_code == 200
```

- [ ] **Step 8: 회귀 확인**

```bash
python -m pytest -q
```

기존 테스트 중 Authorization 헤더 사용하던 코드는 deps의 fallback이 받아주므로 통과해야 한다. 만약 회귀가 발생하면 fallback 분기에 로그를 추가하고 R11에서 정리.

- [ ] **Step 9: 커밋**

```bash
git add backend/app/core/cookies.py backend/app/core/csrf.py backend/app/api/deps.py backend/app/api/routes/auth.py backend/app/main.py backend/tests/test_auth_cookie.py backend/tests/test_csrf.py
git commit -m "feat(auth): R10 httpOnly cookie 인증 + double-submit CSRF"
```

---

## Task 8 — Frontend: localStorage 제거 + cookie 자동 송신 + CSRF 헤더

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/store/authStore.tsx`
- Modify: `frontend/src/api/auth.ts`
- Create: `frontend/src/api/me.ts`
- Modify: `frontend/src/main.tsx` (legacy localStorage 정리)

- [ ] **Step 1: `client.ts` — `credentials: 'include'` + CSRF 헤더 자동**

`fetch` 호출 부분(line 89~ 영역)에서:

```ts
return fetch(toApiUrl(path), {
  ...options,
  credentials: 'include',
  headers,
  body: options.body === undefined || isFormData ? options.body : JSON.stringify(options.body),
});
```

요청 빌더(line 73 인근)에서 CSRF 자동 부착:

```ts
const isMutation = (options.method || 'GET').toUpperCase() !== 'GET'
  && (options.method || 'GET').toUpperCase() !== 'HEAD';
if (isMutation && !path.startsWith('/webhooks/')) {
  const csrf = readCookie('csrftoken');
  if (csrf) {
    headers.set('X-CSRF-Token', csrf);
  }
}
```

`readCookie` 헬퍼:

```ts
function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp('(?:^|; )' + name.replace(/[.$?*|{}()[\]\\\/+^]/g, '\\$&') + '=([^;]*)'));
  return match ? decodeURIComponent(match[1]) : null;
}
```

Authorization 헤더 부착 코드는 제거 (cookie로 대체). `authHandlers.getAccessToken()`/`getRefreshToken()` 호출 모두 삭제 — refresh 자동 재시도 흐름은 cookie 만료 시 `/api/auth/refresh`를 호출하는 것으로 대체:

```ts
async function refreshSilently(): Promise<boolean> {
  try {
    await apiRequest('/auth/refresh', { method: 'POST', retryOnUnauthorized: false });
    return true;
  } catch {
    return false;
  }
}
```

401 자동 재시도 분기에서 위 함수 사용.

- [ ] **Step 2: `authStore.tsx` — 토큰 state 제거**

state schema 변경:

```tsx
const initialState = { activeRole: 'admin', user: null };

// ...
const login = async (role, identifier, password) => {
  await (role === 'admin' ? adminLogin : partnerLogin)({ identifier, password });
  const me = await fetchMe();
  setState({ activeRole: role, user: me.user });
};

const logout = async () => {
  await requestLogout();
  setState({ activeRole: 'admin', user: null });
};

// boot 시 /me 1회 호출하여 user 복원
React.useEffect(() => {
  fetchMe()
    .then((me) => setState((s) => ({ ...s, user: me.user })))
    .catch(() => { /* 미인증 */ });
}, []);
```

기존 `localStorage.setItem`/`getItem` 코드 모두 제거. `setApiAuthHandlers` 호출도 제거 (client.ts가 cookie 자체로 동작).

- [ ] **Step 3: `api/me.ts` 신설**

```ts
import { apiRequest } from './client';

export interface MeResponse {
  user: { id: string; name: string; role: 'admin' | 'partner'; partner_id?: string | null };
}

export function fetchMe(): Promise<MeResponse> {
  return apiRequest('/auth/me');
}
```

- [ ] **Step 4: legacy localStorage 1회 정리**

`frontend/src/main.tsx` 또는 App boot 코드 최상단에:

```ts
try {
  localStorage.removeItem('cleaning_ops_auth_sessions_v2');
  localStorage.removeItem('cleaning_ops_auth_session');
} catch {
  // ignore
}
```

- [ ] **Step 5: typecheck + lint + build**

```bash
cd frontend && npm run typecheck && npm run lint && npm run build
```
Expected: 통과.

- [ ] **Step 6: 커밋**

```bash
git add frontend/src/api/client.ts frontend/src/store/authStore.tsx frontend/src/api/auth.ts frontend/src/api/me.ts frontend/src/main.tsx
git commit -m "feat(auth): R10 frontend localStorage 제거 + cookie 자동 + CSRF 헤더"
```

---

## Task 9 — Postgres 자동 백업 + 복구 스크립트

**Files:**
- Create: `scripts/backup.sh`
- Create: `scripts/restore.sh`
- Create: `docs/runbooks/r10-backup-and-restore.md`
- Modify: `.gitignore` (backups/ 제외)

- [ ] **Step 1: `scripts/backup.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

CONTAINER="${CONTAINER:-cleanops_postgres}"
DB_USER="${DB_USER:-cleanops}"
DB_NAME="${DB_NAME:-cleaning_ops}"
OUT_DIR="${OUT_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
TS="$(date -u +%Y%m%d_%H%M%SZ)"

mkdir -p "$OUT_DIR"
OUT_FILE="$OUT_DIR/cleaning_ops_${TS}.dump.gz"

echo "[backup] dumping $DB_NAME → $OUT_FILE"
docker exec "$CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc \
  | gzip -9 > "$OUT_FILE"

echo "[backup] cleaning files older than ${RETENTION_DAYS} days under $OUT_DIR"
find "$OUT_DIR" -maxdepth 1 -name 'cleaning_ops_*.dump.gz' -mtime "+${RETENTION_DAYS}" -delete

ls -la "$OUT_DIR"
```

- [ ] **Step 2: `scripts/restore.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

CONTAINER="${CONTAINER:-cleanops_postgres}"
DB_USER="${DB_USER:-cleanops}"
DB_NAME="${DB_NAME:-cleaning_ops}"
SRC="${1:-}"

if [ -z "$SRC" ] || [ ! -f "$SRC" ]; then
  echo "Usage: $0 <backup-file.dump.gz>"
  exit 1
fi

echo "[restore] WARNING: this will DROP and recreate '$DB_NAME'. Continue? [y/N]"
read -r ans
if [ "$ans" != "y" ] && [ "$ans" != "Y" ]; then
  exit 1
fi

echo "[restore] dropping and recreating $DB_NAME"
docker exec "$CONTAINER" psql -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME WITH (FORCE);"
docker exec "$CONTAINER" psql -U "$DB_USER" -d postgres -c "CREATE DATABASE $DB_NAME;"

echo "[restore] piping $SRC into pg_restore"
gunzip -c "$SRC" | docker exec -i "$CONTAINER" pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --if-exists --no-owner --no-privileges

echo "[restore] done. tables:"
docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "\dt"
```

- [ ] **Step 3: runbook**

`docs/runbooks/r10-backup-and-restore.md`:

```markdown
# R10 Postgres 백업/복구

## 매일 백업
- 운영 서버 cron (예: 02:30 KST):
  ```
  30 2 * * *  cd /path/to/design_handoff_cleaning_ops && bash scripts/backup.sh >> logs/backup.log 2>&1
  ```
- 결과는 `backups/cleaning_ops_YYYYMMDD_HHMMSSZ.dump.gz`. 7일 보관.

## 복구 절차
1. 운영 backend(uvicorn) 중지.
2. `bash scripts/restore.sh backups/cleaning_ops_20260524_173000Z.dump.gz`.
3. 프롬프트에서 `y` 입력.
4. 마이그레이션 확인: `cd backend && python -m alembic current` → head여야 함.
5. 운영 backend 재시작.

## 원격 보관 (옵션)
- backups/ 디렉토리를 별도 백업 서비스(rclone, restic, S3 sync)로 매일 1회 동기화 권장.
- R12에서 S3 활성화되면 backups/도 같이 동기화 가능.

## 무결성 검증 (월 1회)
- 최신 dump를 staging DB에 restore해 보고 row count 비교.
```

- [ ] **Step 4: gitignore**

`.gitignore`에 추가:

```
backups/
logs/
```

- [ ] **Step 5: 실행 권한 부여 + 한 번 실행 검증 (선택, dev에서)**

```bash
chmod +x scripts/backup.sh scripts/restore.sh
bash scripts/backup.sh
ls -la backups/
```

- [ ] **Step 6: 커밋**

```bash
git add scripts/backup.sh scripts/restore.sh docs/runbooks/r10-backup-and-restore.md .gitignore
git commit -m "feat(ops): R10 Postgres 자동 백업 + 복구 스크립트 + runbook"
```

---

## Task 10 — GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: 워크플로 작성**

```yaml
name: CI

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: cleanops
          POSTGRES_PASSWORD: cleanops_local_dev
          POSTGRES_DB: cleaning_ops
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U cleanops -d cleaning_ops"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - name: Install deps
        run: |
          cd backend
          python -m pip install --upgrade pip
          pip install -r requirements.txt || pip install fastapi uvicorn sqlalchemy alembic pydantic-settings bcrypt python-jose[cryptography] psycopg[binary] structlog 'sentry-sdk[fastapi]'
      - name: Alembic upgrade
        env:
          DATABASE_URL: postgresql+psycopg://cleanops:cleanops_local_dev@localhost:5432/cleaning_ops?client_encoding=utf8
        run: |
          cd backend
          python -m alembic upgrade head
      - name: Pytest
        env:
          DATABASE_URL: postgresql+psycopg://cleanops:cleanops_local_dev@localhost:5432/cleaning_ops?client_encoding=utf8
          ENVIRONMENT: test
          SECRET_KEY: ci-secret-key-please-rotate-locally-do-not-use-in-prod
        run: |
          cd backend
          python -m pytest -q
      - name: Ruff
        run: |
          cd backend
          pip install ruff
          ruff check .

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: |
          cd frontend
          npm ci
      - run: |
          cd frontend
          npm run typecheck
      - run: |
          cd frontend
          npm run lint
      - run: |
          cd frontend
          npm run build
      - name: Upload dist artifact
        if: github.ref == 'refs/heads/main'
        uses: actions/upload-artifact@v4
        with:
          name: frontend-dist
          path: frontend/dist
          retention-days: 14
```

- [ ] **Step 2: 로컬에서 워크플로 syntax 검증 (선택)**

`act` 같은 도구가 있으면 사용. 없으면 GitHub에 push 후 첫 실행 결과 확인.

- [ ] **Step 3: 커밋**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: R10 GitHub Actions backend pytest + frontend lint/typecheck/build"
```

---

## Task 11 — 회귀 + handoff 갱신

**Files:**
- Modify: `.master/next_session_plan.md`

- [ ] **Step 1: backend 전체 회귀**

```bash
cd backend && python -m pytest -q
```
Expected: 121 → 130+ (R10에서 추가된 테스트 포함) passed.

- [ ] **Step 2: frontend 전체 회귀**

```bash
cd frontend
npm run typecheck
npm run lint
npm run build
npm run e2e
```

⚠️ E2E는 cookie 기반으로 동작해야 한다. Playwright `context.cookies` 사용 확인. helpers.ts의 login 함수가 토큰 대신 cookie로 동작하도록 갱신 필요할 수 있음 — 깨지면 task 7.5로 helpers.ts 갱신을 추가하라.

- [ ] **Step 3: `next_session_plan.md` 갱신**

상단에 R10 항목 추가:
```markdown
- `R10 Production Foundation` 완료
  - httpOnly cookie 인증 + CSRF
  - structlog 구조화 로그
  - Sentry wiring + before_send PII redact
  - /live, /ready health 분리
  - Postgres 자동 백업 + 복구 스크립트
  - GitHub Actions CI
```

다음 세션 권장 작업을 "R11 Real Message Delivery"로 갱신.

- [ ] **Step 4: 커밋**

```bash
git add .master/next_session_plan.md
git commit -m "docs(handoff): R10 마감 + R11 진입점 갱신"
```

---

## Self-Review

**1. Spec coverage:**

| Production gap | Task |
|---|---|
| localStorage 토큰 → httpOnly cookie | Task 7, 8 |
| CSRF 보호 | Task 7, 8 |
| Sentry wiring | Task 5 |
| structured logging (request_id) | Task 4 |
| /live, /ready 분리 | Task 6 |
| Postgres 백업/복구 | Task 9 |
| .env 템플릿 / secret 가이드 | Task 2 |
| CI 기본 | Task 10 |
| 정책 문서 갱신 | Task 1 |

전 항목 task에 매핑됨.

**2. Placeholder scan:** 코드 블록은 실제 구현 가능한 코드. 외부 의존(SOLAPI/S3/Sentry 실 DSN)은 R10 범위 외 — `.env`가 비어 있어도 backend가 정상 부팅하도록 init_sentry()가 no-op 처리.

**3. Type consistency:**
- Cookie 이름은 `settings.access_cookie_name` 등으로 일관.
- CSRF 토큰: `csrftoken` 쿠키 ↔ `X-CSRF-Token` 헤더.
- `fetchMe()` ↔ `/api/auth/me` ↔ `MeResponse`.
- `_extract_access_token` 일관.

**4. 실 호환성 위험:**
- 기존 E2E spec의 `Authorization: Bearer` 호출이 깨질 수 있다 — deps의 fallback 분기로 임시 호환, R11에서 정리.
- 기존 admin Playwright spec의 login 단계는 cookie 자동 처리되므로 영향 없을 가능성 높음.

**5. 운영 사전 작업 (사용자 책임):**
- Sentry 프로젝트 생성 + DSN 발급
- 운영 서버 cron 등록 (`30 2 * * *`)
- `.env.production` 채워서 운영 서버 backend 재시작

---

## Execution Handoff

Codex에게:

```
docs/plans/2026-05-25-r10-production-foundation.md 를 처음부터 끝까지 정독한 뒤,
Task 1부터 순서대로 진행한다. 각 task의 step은 TDD 순서(실패 테스트 → 구현 →
통과 → 커밋)를 그대로 따른다. 각 task 끝에 git status / diff 한 줄 보고.
의문 사항은 사용자에게 묻지 말고 D1~D10 결정을 따른다.
계획서에 없는 부수 refactor/rename은 추가하지 마라.
```

CTO 검토 후 codex에 전달.
