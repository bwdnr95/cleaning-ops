# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Identity

**Cleaning Ops Control Center** — B2B SaaS that consolidates a cleaning company's order intake, partner dispatch, schedule, photo review, and customer notification into one web system. It is **not** a generic CRUD app: every feature must preserve the operational flow `주문 접수 → 협력사 배정 → 일정 확정/안내 → 작업 진행 → 사진 업로드 → 관리자 검수 → 고객 전달 → 완료` so an operator never loses track of what to do today.

Three roles, three contexts:
- **Admin** — desktop, full operations control
- **Partner** — mobile, only their assigned jobs
- **Customer** — mobile, no signup; access via `customer_token` link + last 4 phone digits

## Source-of-Truth Documents — read before non-trivial changes

- **`AGENTS.md`** — binding project rules (security, DTO, photo, message, test, review). Treat as the canonical rule file; CLAUDE.md does not duplicate it.
- **`.master/cleaning_ops_control_center_project_brief.md`** — product/business spec, status enum, data model, screen breakdown.
- **`.master/codex_claude_code_dev_brief.md`** — implementation brief and QA scenarios.
- **`.master/first_demo_code_status_2026-05-06.md`** — current implementation map (file-by-file, layer-by-layer).
- **`.master/next_session_plan.md`** — running handoff between sessions; "next recommended task" lives here.
- **`README.md`** — design handoff: tokens, status colors, screen layouts. The archived `.master/design_handoff_prototype/*.jsx` / `.html` / `styles.css` / `data.jsx` files are the **design prototype, not production code** — re-implement into `backend/`/`frontend/`, do not copy verbatim.

## Stack

- **Backend** (`backend/`): Python 3.11+, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic, bcrypt, python-jose JWT. Lint via ruff. Default DB is SQLite for dev (`backend/cleaning_ops.db`); production target is PostgreSQL.
- **Frontend** (`frontend/`): Vite + React 19 + TypeScript. **No Tailwind, no shadcn** — styling is plain CSS with design tokens in `frontend/src/styles/global.css` and `app.css`, dark mode via `<html data-theme="dark">`. (Older briefs mention Tailwind/shadcn — that recommendation was not adopted; do not introduce them.)
- **E2E**: Playwright, runs both servers via `playwright.config.ts` on isolated ports (default `5176`/`8003`).

## Commands

Backend (run from `backend/`):
```powershell
python -m pytest                                  # full test suite
python -m pytest tests/test_auth_integration.py   # single file
python -m pytest tests/test_auth_integration.py::test_admin_login   # single test
python -m compileall app tests                    # quick syntax check
python -m alembic upgrade head --sql              # render migration SQL (no apply)
python -m alembic upgrade head                    # apply migrations
python scripts/seed_dev.py                        # seed dev data
ruff check .                                      # lint
```

Frontend (run from `frontend/`):
```powershell
npm run typecheck       # tsc --noEmit
npm run lint            # eslint .
npm run build           # vite build
npm run e2e             # playwright (auto-starts backend on 8003 + frontend on 5176)
```

**Do not start `npm run dev` or `uvicorn` on your own.** Ports `5173`, `8000`, `8001` may be in use by other projects on this machine — ask the user first and confirm a free port. E2E ports (`5176`/`8003`) are managed by `playwright.config.ts` and are safe.

## Demo / Seed Credentials

Defined in `backend/app/db/seed.py`:
- Admin: `admin@cleanops.kr` / `AdminPass123!`
- Partner: `01012345678` (or `partner@cleanops.kr`) / `PartnerPass123!`
- Sample order: `seed-order-2450`
- Customer link token: `ct2_seed-customer-token-2450`, phone suffix `5432`

## Architecture (the parts that take multiple files to understand)

### Backend layering — strict, do not bypass
```
api/routes/       FastAPI routes, group by role (admin/, partner/, customer/, webhooks)
   └─ deps.py     require_admin / require_partner / ensure_partner_scope dependencies
services/         business logic; this is where state changes + timeline writes happen
repositories/     DB queries; routes/services do not write raw SQL elsewhere
models/           SQLAlchemy ORM
schemas/          Pydantic DTOs — split per role (Admin/Partner/Customer)
domain/           constants, enums, pure helpers (phone, message_templates, service_catalog)
core/             config, security (JWT/bcrypt), middleware
```
Top-level composition lives in `app/api/router.py` (see `.master/first_demo_code_status_2026-05-06.md` §5 for the route map).

### The three rules that drive everything

1. **Role separation is server-enforced.** Every admin route depends on `require_admin`; every partner route depends on `require_partner` and goes through `ensure_partner_scope`; every customer route requires `customer_token` + phone-suffix verification. UI gating is not security.

2. **Role-specific DTOs, whitelisted.** `services/orders.py` has `to_admin_order_dto` / `to_partner_job_dto` / `to_customer_order_dto`. Add fields explicitly. Never `{...order, secret: undefined}` or spread-then-delete. Sensitive fields banned from partner/customer DTOs are listed in `AGENTS.md` — consult that list, don't guess.

3. **Every operational mutation writes a timeline event.** Status change, partner assignment, photo upload, photo approval, message send, customer link send, memo — all go through `services/timeline.py` (or the corresponding service that wraps it). If your change does not write a timeline row for a meaningful state transition, it's incomplete.

4. **Soft-delete는 timeline 보존을 위한 합의다.** 주문/그룹 삭제는 `deleted_at` 컬럼을 채우고, 모든 조회 경로는 `deleted_at IS NULL` 필터를 강제한다. 자세한 내용은 `AGENTS.md` § "Delete Policy"를 본다.

### Photo flow invariant
Partner upload → `is_customer_visible=true` (자동 공개). **상태는 변경되지 않는다** (협력사가 사진을 여러 번 나눠 올려도 IN_PROGRESS 그대로). timeline에는 `photo_uploaded` + `photo_approved`(system actor)만 기록된다. 협력사가 명시적으로 "작업 완료" 액션을 실행하면 비로소 `IN_PROGRESS → 고객전달필요`로 전환(사진 1장 이상 + IN_PROGRESS 가드 통과 시). 관리자는 잘못 올라온 사진을 `POST /api/admin/photos/{id}/revoke`로 비공개로 되돌릴 수 있고, 이 때 `photo_revoked` 이벤트가 남는다. 마지막 공개 사진이 사라지고 주문이 `고객전달필요` 상태였다면 `작업진행`으로 되돌아간다(`고객전달완료`/`서비스완료`는 유지). 파일 타입은 **byte signature**로 검증한다 (`services/photos.py`).

### Message provider abstraction
`services/messages.py` exposes a `MessageProvider` interface. `MockMessageProvider` and the SOLAPI provider both exist; provider is selected via `core/config.py` settings. Production fails closed unless the approved SOLAPI profile and all nine template IDs are configured. Webhook receiver is at `api/routes/webhooks.py`. Both success and failure must land in `message_logs`. Templates and required variables live in `domain/message_templates.py`.

### Domain constants — one place
`backend/app/domain/constants.py` is the central definition for the 14 order statuses, photo types (`before` / `after` / `etc`), message types, and timeline event types. Do not introduce parallel string literals.

### Frontend wiring
- `src/api/client.ts` — `apiRequest` wrapper. Attaches `Authorization`, generates `X-Request-ID`, retries once on 401 via the refresh-token flow, normalizes FastAPI validation errors. Never call `fetch` directly from features.
- `src/store/authStore.tsx` — auth state; tokens currently in `localStorage` (R1 convenience; httpOnly cookie is the eventual target).
- `src/app/App.tsx` — assembles admin desktop / partner mobile / customer mobile shells; mode switch is a demo affordance.
- `src/features/<role>/<screen>/` — feature-organized screens. Backend DTOs map 1:1 to feature page concerns.
- Customer link routing: only `/c#token=<customer-token>` carries an authentication token. Startup captures the fragment into redacted history state, clears the URL to `/c`, and customer API calls use the stable path plus `X-Customer-Token`. Legacy path/query token URLs are discarded and must not be generated.

## Working Style for This Repo

- **Plan → Implement → Test → Review** for any non-trivial change. Update `.master/next_session_plan.md` when you finish a labeled "Rx" milestone.
- **Korean is the default working language** — comments, commit messages, and PR descriptions in the existing codebase are Korean. Match that.
- **Do not lift code from `tono-operation`.** It's a reference for security patterns only; rewrite for this project's structure.
- **Migrations**: every schema change needs an Alembic revision. Existing revisions are numbered (`0001_…`, `0002_…` …) — continue the sequence.
- **Don't touch `.master/`, `.claude/`** unless the user explicitly asks. They're operator workspace and excluded from git.
