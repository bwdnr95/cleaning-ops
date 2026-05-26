# R13 Operational Reporting Implementation Plan

> **Codex 작업자에게**: task-by-task로 진행하라. 각 step의 코드/명령은 그대로 실행 가능해야 한다. 각 task 마지막은 git commit으로 끝낸다. 의문 사항은 사용자에게 묻지 말고 D-결정 사항을 따른다.

> **이력**
> - v1 (2026-05-25): 초안.
> - v2 (2026-05-25): Codex CTO 리뷰 (8 blocking + 8 should + 5 nit) 반영. 핵심: Python aggregation 단일화 + 실제 enum 사용 + group_key import + downloadBlob.
> - v3 (2026-05-25): Codex round 2 review (4 blocking + 8 should + 5 nit) 반영. group-level rollback, services fallback, soft-delete 실제 검증, UI 필터, downloadBlob refresh, business_today, customer 일관성.
> - v4 (2026-05-25): Codex round 3 review (2 blocking + 8 should + 5 nit) 반영. (a) Task 3 테스트의 import 누락 보완 (B1), (b) `listServiceItems` API client 함수를 Task 1에 명시 + static import (B2/N4), (c) is_xlsx_upload helper로 MIME 정책 중앙화 (S3/S7), (d) TS 응답 타입 backend와 동기화 (S4), (e) 4 화면 모두 loading/error/empty 분리 (S5), (f) E2E에 필터 smoke 추가 (S8), (g) react-is exact pin D1에도 적용 (N1).
> - v4.1 (2026-05-26): Codex round 4 **APPROVED** + residual should/nit 6건 인라인 정리. RevenueView도 `ReportState` wrapper 채택, `listServiceItems` 타입 명시(`ServiceCategoryWithItems` 인터페이스, any 제거), `is_xlsx_upload`에서 `.xlsm` 제거(xlsx-only), header 파싱 실패 시 `wb.close()` 보장. unused imports (Iterable/dataclass/group_rows 등)와 Task 3 test 내 중복 local import 정리는 codex 구현 시 ruff/lint 따라 자체 정돈.

> **선행 문서**
> - `docs/plans/2026-05-25-roadmap-r10-to-r15.md` — 전체 우선순위 (R13 1순위)
> - `AGENTS.md`, `CLAUDE.md`, `.claude/rules/backend.md`, `.claude/rules/frontend.md`
> - `.master/next_session_plan.md`

**Goal:** 운영팀이 매월 정산할 때 엑셀/SQL 직접 안 두드린다. 관리자 사이드바에 **`보고서`** 메뉴가 생기고, 4 화면에서 매출/협력사/서비스/정산 현황을 보고, 그 결과를 CSV/xlsx로 받는다. 추가로 운영팀이 다른 채널에서 받은 대량 주문을 xlsx 업로드로 일괄 등록할 수 있다 (R7 multi-line 호환).

**Architecture:**
- 백엔드 집계는 **Python aggregation**으로 단일화. SQL은 `select(Order).where(...)` 단순 조회만. `itertools.groupby` + `Decimal` 합산으로 기간/협력사/서비스 버킷 생성. DB dialect 분기 X, SQLite 테스트 그대로 동작.
- 모든 보고서 endpoint는 `require_admin`, `Order.deleted_at IS NULL` 가드 (R8 delete policy). 협력사/고객 DTO 룰과 무관하지만 응답은 admin 전용 필드만.
- 매출 정의는 **기존 `DashboardService.monthly_revenue`와 동일** — `status IN (CUSTOMER_DELIVERY_DONE, COMPLETED)`. 화면마다 매출이 달라지는 사고 차단.
- 정산 대기 정의는 도메인 상수 `PARTNER_SETTLEMENT_PENDING_STATUSES` (= UNPAID, READY) + `OrderStatus.COMPLETED` 사용.
- CSV/xlsx 생성은 `openpyxl` 단일 의존성 (이미 `pyproject.toml`에 있음). 메모리 bytes buffer 응답 (스트리밍 아님). Content-Disposition은 ASCII filename만.
- Import는 `xlsx → 행 dict → group_key로 묶음 → OrderGroupCreate(lines=[...])`. 같은 group_key 행은 한 group의 여러 line. 실패 행은 `{row_index, reason}`로 응답.
- 프론트 차트는 `recharts@^2.13.3` + `react-is` overrides로 React 19 호환. 다른 의존성 추가 없음.
- Export 다운로드는 `fetchBlobWithRefresh` 헬퍼로 fetch → Blob URL 생성 → anchor download click. 401 시 1회 refresh retry. R10 cookie 전환 후에도 `credentials: 'include'`로 자동 호환.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 (단순 select만) · Pydantic v2 · openpyxl · React 19 + TypeScript · recharts 2.13.3 · Playwright · SQLite(test) / Postgres(prod).

---

## CTO 결정 사항 (D-항목)

- **D1. 차트 라이브러리**: **`recharts@^2.13.3`** + `package.json.overrides`에 `react-is: "19.2.5"` 추가 (exact pin, 현재 React lock과 동일). React 19 호환 검증된 조합.
- **D2. xlsx 라이브러리**: `openpyxl` (이미 backend/pyproject.toml에 포함). frontend는 파일 upload만 — 파싱/검증은 backend.
- **D3. 모든 통계 endpoint는 admin only**. 협력사·고객 노출 X.
- **D4. 기간 단위**: 사용자가 `granularity=day|week|month` 선택. 기본 `month`, 기본 범위 "최근 6개월". 집계는 Python `itertools.groupby` + `period_key()` 함수로 처리.
- **D5. 매출 정의 (운영 일관성 핵심)**: `orders.total_amount` 합계, **`status IN (OrderStatus.CUSTOMER_DELIVERY_DONE, OrderStatus.COMPLETED)`** 만 포함. `DashboardService.monthly_revenue`와 정확히 동일. cancel은 별도 카운트 X (필요 시 R13.5에서 추가).
- **D6. 협력사 성과 정의**: `orders.partner_id IS NOT NULL` 인 주문 기준. 작업 수 / 평균 단가(`total_amount`) / 정산 대기 카운트 / 정산 예정액(`partner_payment_amount` 합) 4개 지표. `취소` 상태는 작업 수에서 제외.
- **D7. 정산 대기 정의**: `status = OrderStatus.COMPLETED` + `partner_payment_status IN PARTNER_SETTLEMENT_PENDING_STATUSES` (UNPAID, READY). NULL 도 함께 포함하기 위해 `IS NULL OR IN (...)` 처리.
- **D8. Export 정책**: 각 화면의 현재 필터/기간을 query string에 묶어 `GET /api/admin/reports/<name>/export?format=csv|xlsx`. content-disposition으로 다운로드. **frontend는 fetch+blob 패턴** — anchor `download` 속성 사용 X (Authorization 헤더 부착 못 함).
- **D9. Import 정책 (v3 강화)**: 행별 validate → 같은 `group_key` 묶음 → group 단위 commit. **한 group 내 line 1개라도 parse/검증 실패하면 그 group의 모든 line이 fail 처리**되어 응답의 `failed` 목록에 row_index 전부 포함. 다른 group은 영향 없음. 같은 `group_key`에서 `customer_name`/`customer_phone`/`customer_address`가 다르면 첫 행을 기준으로 묶되 두 번째 행부터 다른 값이면 `inconsistent_group_customer` 사유로 group 전체 fail.
- **D10. 라우트 prefix**: 모든 보고서는 `/api/admin/reports/...`. import는 `/api/admin/orders/import`. mount는 `backend/app/api/router.py`의 `api_router.include_router(...)` 패턴.
- **D11. 테스트 환경**: 기존 `make_test_client()` fixture 그대로 사용 (SQLite). Python aggregation이라 DB dialect 무관. `db_session` fixture도 SQLite 그대로.
- **D12. Decimal 직렬화**: Pydantic `Decimal` 필드는 기본 string 직렬화. frontend는 `parseFloat()` 처리. 또는 schema에서 `model_config = ConfigDict(json_encoders={Decimal: float})` — 단 v2에서는 `field_serializer` 사용. **본 plan에서는 frontend에서 `Number()` cast하는 패턴 채택**.
- **D13. 기간 비교 (전월 대비 등)**: R13 범위 외. **R13.5**에서 처리 예정. 본 plan은 단일 기간만.
- **D14. 운영 일관성**: 모든 보고서의 매출/작업수 합계가 다른 화면(대시보드·주문 통계)과 정확히 일치해야 한다. 정의가 모호하면 Dashboard 코드를 source of truth로 따른다.
- **D15. 서비스 인기 fallback (v3 신규)**: `services()` 리포트는 `service_item_id IS NOT NULL`만 보지 않고, `service_item_id` 가 NULL인 주문도 `service_name` 키로 묶어 집계한다. 운영자가 xlsx import로 등록한 주문(service_item_id 미지정)도 통계에 포함되도록 보장. 응답 row의 `service_item_id` 는 NULL 가능, `service_name`은 항상 채워진다.
- **D16. 시간대 (v3 명시)**: 모든 `today()` 호출은 `app.core.time.business_today()` 사용 (KST 기준). `.claude/rules/backend.md` 룰 준수.
- **D17. 화면 필터 (v3 신규)**: ReportsPage의 매출 추세 탭에는 **협력사 select + 서비스 select** 필터가 화면 상단에 있다. 선택 시 backend revenue endpoint의 `partner_id`/`service_item_id` query에 반영. export params에도 함께 전달.

---

## File Map — 무엇을 어디서 바꾸는가

| 영역 | 파일 | 종류 |
|---|---|---|
| 정책 | `AGENTS.md` | 수정 (§ "Reporting / Export Rules" 신설) |
| 백엔드 의존성 | `backend/pyproject.toml` | 검토만 (`openpyxl>=3.1.0` 이미 있음) |
| 백엔드 도메인 | `backend/app/services/reports.py` | 신규 |
| 백엔드 export | `backend/app/services/exporters.py` | 신규 |
| 백엔드 import | `backend/app/services/order_import.py` | 신규 |
| 백엔드 스키마 | `backend/app/schemas/report.py` | 신규 |
| 백엔드 라우터 | `backend/app/api/routes/admin/reports.py` | 신규 |
| 백엔드 라우터 | `backend/app/api/routes/admin/orders.py` | 수정 (`POST /import` 추가) |
| 백엔드 라우터 | `backend/app/api/router.py` | 수정 (reports mount) |
| 백엔드 테스트 | `backend/tests/test_reports.py` | 신규 |
| 백엔드 테스트 | `backend/tests/test_report_export.py` | 신규 |
| 백엔드 테스트 | `backend/tests/test_order_import.py` | 신규 |
| 프론트 의존성 | `frontend/package.json` | 수정 (`recharts`, `overrides.react-is`) |
| 프론트 API | `frontend/src/api/reports.ts` | 신규 |
| 프론트 API | `frontend/src/api/client.ts` | 수정 (`downloadBlob` 헬퍼 추가) |
| 프론트 페이지 | `frontend/src/features/admin/reports/ReportsPage.tsx` | 신규 |
| 프론트 컴포넌트 | `frontend/src/features/admin/reports/RevenueChart.tsx` | 신규 |
| 프론트 컴포넌트 | `frontend/src/features/admin/reports/PartnerPerformanceTable.tsx` | 신규 |
| 프론트 컴포넌트 | `frontend/src/features/admin/reports/ServicePopularityTable.tsx` | 신규 |
| 프론트 컴포넌트 | `frontend/src/features/admin/reports/SettlementBacklogTable.tsx` | 신규 |
| 프론트 공통 | `frontend/src/features/admin/reports/ExportButtons.tsx` | 신규 |
| 프론트 import | `frontend/src/features/admin/orders/OrderImportDialog.tsx` | 신규 |
| 프론트 App | `frontend/src/app/App.tsx` | 수정 (reports page 분기) |
| 프론트 shell | `frontend/src/components/layout/AdminShell.tsx` | 수정 (사이드바 `보고서` 메뉴) |
| 프론트 E2E | `frontend/e2e/admin-reports-e2e.spec.ts` | 신규 |
| 운영 문서 | `docs/runbooks/r13-reports-and-import.md` | 신규 |
| 핸드오프 | `.master/next_session_plan.md` | 수정 (R13 마감 후) |

---

## Task 1 — 정책 문서 + Recharts 의존성

**Files:**
- Modify: `AGENTS.md`
- Modify: `frontend/package.json`

`openpyxl`은 `backend/pyproject.toml`에 이미 있음 (확인됨). backend 의존성 추가 없음.

- [ ] **Step 1: AGENTS.md § "Reporting / Export Rules" 추가**

`## Delete Policy` 블록 다음에 삽입:

```markdown
## Reporting / Export Rules

- 모든 보고서 endpoint는 `require_admin` 가드 + `Order.deleted_at IS NULL` 필터를 강제한다.
- **매출 정의는 `status IN (CUSTOMER_DELIVERY_DONE, COMPLETED)` 합계**. `DashboardService.monthly_revenue` 와 정확히 동일하게 유지한다. 화면마다 매출이 달라지면 운영팀이 회사 매출을 셀 수 없다.
- 정산 대기는 `OrderStatus.COMPLETED` + `partner_payment_status` 가 `PARTNER_SETTLEMENT_PENDING_STATUSES` 또는 NULL 인 주문.
- 집계는 SQLAlchemy의 `case`/`date_trunc` 같은 DB-방언 함수 대신 Python aggregation (`itertools.groupby` + `Decimal`)으로 구현. 운영 데이터량(수십~수백 건/월) 수준에서 성능 영향 없음 + dialect 무관.
- Export는 화면의 현재 필터/기간을 query string에 묶어 호출하고 backend는 content-disposition으로 다운로드한다. 파일명은 ASCII (`revenue.csv`).
- 대량 import는 행별 validate + `group_key` 컬럼으로 묶어 OrderGroup 단위 commit. 한 group 내 일부 line 실패 시 그 group 전체 rollback.
```

- [ ] **Step 2: Recharts + react-is override 추가**

`frontend/package.json`에:

```json
{
  "dependencies": {
    "...": "...",
    "recharts": "^2.13.3"
  },
  "overrides": {
    "react-is": "19.2.5"
  }
}
```

설치:
```bash
cd frontend && npm install
```

(이미 `dependencies`/`overrides` 블록이 있다면 그 안에 머지. 기존 항목은 보존.)

- [ ] **Step 3: `frontend/src/api/admin.ts`에 `listServiceItems` 추가**

R13 보고서 화면이 service select 필터에 사용. 기존 `listServiceCatalog()`가 categories+items nested 응답을 주는 구조라면, flatten 헬퍼를 추가하거나 raw items를 반환하는 신규 함수 추가. 백엔드는 `GET /api/admin/services/items`가 이미 있거나 `listServiceCatalog()`의 children을 flatten 가능.

```ts
export interface ServiceItemSummary {
  id: string;
  name: string;
}

interface ServiceCategoryWithItems {
  id: string;
  name: string;
  items?: ServiceItemSummary[];
}

export function listServiceItems(): Promise<ServiceItemSummary[]> {
  // 기존 listServiceCatalog가 ServiceCategoryWithItems[] 형태를 반환한다고 가정
  return (listServiceCatalog() as Promise<ServiceCategoryWithItems[]>).then((categories) =>
    categories.flatMap((c) =>
      (c.items ?? []).map((i) => ({ id: i.id, name: i.name })),
    ),
  );
}
```

(실제 `listServiceCatalog` 응답 구조는 codex가 `frontend/src/api/admin.ts` 확인 후 정확히 매핑. 기존 함수가 없으면 새 `GET /api/admin/services/items` 엔드포인트 noop 사용.)

- [ ] **Step 4: typecheck**

```bash
npm run typecheck
```
Expected: 통과.

- [ ] **Step 5: 커밋**

```bash
git add AGENTS.md frontend/package.json frontend/package-lock.json frontend/src/api/admin.ts
git commit -m "chore(deps): R13 recharts 2.13.3 + react-is exact pin + Reporting 정책 + listServiceItems"
```

---

## Task 2 — Reporting Schemas (Pydantic)

**Files:**
- Create: `backend/app/schemas/report.py`

- [ ] **Step 1: 스키마 작성**

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.domain.constants import OrderStatus


class RevenueBucket(BaseModel):
    period: date  # 일/주의 첫날/월의 첫날
    completed_count: int = Field(..., ge=0)
    revenue: Decimal


class RevenueReport(BaseModel):
    granularity: str
    start_date: date
    end_date: date
    partner_id: str | None = None
    service_item_id: str | None = None
    buckets: list[RevenueBucket]
    total_revenue: Decimal
    total_completed: int


class PartnerPerformanceRow(BaseModel):
    partner_id: str
    partner_name: str
    job_count: int
    avg_unit_price: Decimal
    pending_settlement_count: int
    expected_settlement_amount: Decimal


class PartnerPerformanceReport(BaseModel):
    start_date: date
    end_date: date
    rows: list[PartnerPerformanceRow]


class ServicePopularityRow(BaseModel):
    service_item_id: str | None = None  # D15: import된 주문은 NULL 가능
    service_name: str
    job_count: int
    revenue: Decimal
    revenue_share_pct: float


class ServicePopularityReport(BaseModel):
    start_date: date
    end_date: date
    rows: list[ServicePopularityRow]


class SettlementBacklogRow(BaseModel):
    order_id: str
    scheduled_date: date | None
    service_name: str
    partner_id: str | None
    partner_name: str | None
    total_amount: Decimal
    expected_settlement_amount: Decimal
    status: OrderStatus


class SettlementBacklogReport(BaseModel):
    rows: list[SettlementBacklogRow]


class OrderImportFailure(BaseModel):
    row_index: int  # 1-based, header 다음부터 1
    reason: str


class OrderImportResult(BaseModel):
    succeeded_groups: int
    succeeded_lines: int
    failed: list[OrderImportFailure]
```

- [ ] **Step 2: syntax 확인**

```bash
cd backend && python -c "from app.schemas.report import RevenueReport, OrderImportResult; print('OK')"
```

- [ ] **Step 3: 커밋**

```bash
git add backend/app/schemas/report.py
git commit -m "feat(schema): R13 보고서/import 응답 DTO 정의"
```

---

## Task 3 — Reports Service (Python aggregation) + Revenue Endpoint

**Files:**
- Create: `backend/app/services/reports.py`
- Create: `backend/app/api/routes/admin/reports.py`
- Modify: `backend/app/api/router.py`
- Test: `backend/tests/test_reports.py`

- [ ] **Step 1: 실패 테스트**

`backend/tests/test_reports.py`:

```python
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.domain.constants import OrderStatus
from app.domain.payment_status import PartnerPaymentStatus
from app.services.reports import ReportService


def test_revenue_endpoint_requires_admin(client):
    res = client.get("/api/admin/reports/revenue")
    assert res.status_code in {401, 403}


def test_revenue_endpoint_returns_buckets(client, seed_admin_token):
    res = client.get(
        "/api/admin/reports/revenue",
        params={
            "granularity": "month",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
        },
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["granularity"] == "month"
    assert body["start_date"] == "2026-01-01"
    assert isinstance(body["buckets"], list)
    # 모든 bucket의 revenue 합 == total_revenue
    bucket_sum = sum(float(b["revenue"]) for b in body["buckets"])
    assert abs(bucket_sum - float(body["total_revenue"])) < 0.01


def test_revenue_excludes_soft_deleted_orders(db_session, seed_order):
    """deleted_at IS NOT NULL 인 주문은 매출에서 제외되어야 한다 (R8 delete policy)."""
    from datetime import UTC, datetime
    from app.services.reports import ReportService

    # COMPLETED + 매출 잡히는 상태로 set
    seed_order.status = OrderStatus.COMPLETED
    seed_order.scheduled_date = date(2026, 5, 15)
    seed_order.total_amount = Decimal("123000")
    db_session.flush()

    # 삭제 전 — 매출 잡힘
    before = ReportService(db_session).revenue(
        granularity="month",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    assert before.total_revenue == Decimal("123000")

    # soft-delete
    seed_order.deleted_at = datetime.now(UTC)
    db_session.flush()

    # 삭제 후 — 매출 0
    after = ReportService(db_session).revenue(
        granularity="month",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    assert after.total_revenue == Decimal("0")
    assert after.total_completed == 0
```

- [ ] **Step 2: `app/services/reports.py` — Python aggregation 베이스**

```python
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.constants import OrderStatus
from app.domain.payment_status import PARTNER_SETTLEMENT_PENDING_STATUSES
from app.models.order import Order
from app.models.partner import Partner
from app.models.service_item import ServiceItem
from app.schemas.report import (
    PartnerPerformanceReport,
    PartnerPerformanceRow,
    RevenueBucket,
    RevenueReport,
    ServicePopularityReport,
    ServicePopularityRow,
    SettlementBacklogReport,
    SettlementBacklogRow,
)

_GRANULARITIES = {"day", "week", "month"}
_REVENUE_STATUSES = (OrderStatus.CUSTOMER_DELIVERY_DONE, OrderStatus.COMPLETED)


class ReportService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ---------- revenue ----------

    def revenue(
        self,
        *,
        granularity: str,
        start_date: date,
        end_date: date,
        partner_id: str | None = None,
        service_item_id: str | None = None,
    ) -> RevenueReport:
        if granularity not in _GRANULARITIES:
            raise ValueError(f"unsupported_granularity:{granularity}")
        if start_date > end_date:
            raise ValueError("invalid_range")

        stmt = (
            select(Order)
            .where(
                Order.deleted_at.is_(None),
                Order.status.in_(_REVENUE_STATUSES),
                Order.scheduled_date >= start_date,
                Order.scheduled_date <= end_date,
            )
        )
        if partner_id:
            stmt = stmt.where(Order.partner_id == partner_id)
        if service_item_id:
            stmt = stmt.where(Order.service_item_id == service_item_id)

        orders = list(self.db.scalars(stmt))

        buckets: dict[date, list[Decimal]] = {}
        for order in orders:
            if order.scheduled_date is None:
                continue
            key = _period_key(order.scheduled_date, granularity)
            buckets.setdefault(key, []).append(Decimal(str(order.total_amount or 0)))

        bucket_rows = [
            RevenueBucket(
                period=k,
                completed_count=len(v),
                revenue=sum(v, Decimal("0")),
            )
            for k, v in sorted(buckets.items())
        ]
        return RevenueReport(
            granularity=granularity,
            start_date=start_date,
            end_date=end_date,
            partner_id=partner_id,
            service_item_id=service_item_id,
            buckets=bucket_rows,
            total_revenue=sum((b.revenue for b in bucket_rows), Decimal("0")),
            total_completed=sum(b.completed_count for b in bucket_rows),
        )

    # ---------- partner performance ----------

    def partners(self, *, start_date: date, end_date: date) -> PartnerPerformanceReport:
        partner_stmt = select(Partner)
        partners = {p.id: p for p in self.db.scalars(partner_stmt)}

        order_stmt = (
            select(Order)
            .where(
                Order.deleted_at.is_(None),
                Order.partner_id.is_not(None),
                Order.status != OrderStatus.CANCELLED,
                Order.scheduled_date >= start_date,
                Order.scheduled_date <= end_date,
            )
        )
        orders = list(self.db.scalars(order_stmt))

        by_partner: dict[str, list[Order]] = {}
        for order in orders:
            by_partner.setdefault(order.partner_id, []).append(order)

        rows: list[PartnerPerformanceRow] = []
        for pid, line_orders in by_partner.items():
            partner = partners.get(pid)
            if partner is None:
                continue
            totals = [Decimal(str(o.total_amount or 0)) for o in line_orders]
            pending = sum(
                1
                for o in line_orders
                if o.partner_payment_status is None
                or o.partner_payment_status in PARTNER_SETTLEMENT_PENDING_STATUSES
            )
            expected = sum(
                (Decimal(str(o.partner_payment_amount or 0)) for o in line_orders),
                Decimal("0"),
            )
            rows.append(
                PartnerPerformanceRow(
                    partner_id=pid,
                    partner_name=partner.name,
                    job_count=len(line_orders),
                    avg_unit_price=(sum(totals, Decimal("0")) / len(totals)) if totals else Decimal("0"),
                    pending_settlement_count=pending,
                    expected_settlement_amount=expected,
                )
            )
        rows.sort(key=lambda r: r.job_count, reverse=True)
        return PartnerPerformanceReport(start_date=start_date, end_date=end_date, rows=rows)

    # ---------- service popularity ----------

    def services(self, *, start_date: date, end_date: date) -> ServicePopularityReport:
        """D15: service_item_id NULL인 주문(import 등록 등)도 service_name 기준으로 집계."""
        service_stmt = select(ServiceItem)
        services = {s.id: s for s in self.db.scalars(service_stmt)}

        order_stmt = (
            select(Order)
            .where(
                Order.deleted_at.is_(None),
                Order.status.in_(_REVENUE_STATUSES),
                Order.scheduled_date >= start_date,
                Order.scheduled_date <= end_date,
            )
        )
        orders = list(self.db.scalars(order_stmt))

        # 키는 (service_item_id, fallback_name). service_item_id가 있으면 ServiceItem.name 우선,
        # 없으면 Order.service_name 사용. service_name도 비어있으면 "(미지정)" 그룹.
        by_key: dict[tuple[str | None, str], list[Order]] = {}
        for order in orders:
            if order.service_item_id and order.service_item_id in services:
                key = (order.service_item_id, services[order.service_item_id].name)
            else:
                key = (None, order.service_name or "(미지정)")
            by_key.setdefault(key, []).append(order)

        total_revenue = Decimal("0")
        partials = []
        for key, line_orders in by_key.items():
            revenue = sum(
                (Decimal(str(o.total_amount or 0)) for o in line_orders),
                Decimal("0"),
            )
            total_revenue += revenue
            partials.append((key, line_orders, revenue))

        rows: list[ServicePopularityRow] = []
        denom = total_revenue if total_revenue > 0 else Decimal("1")
        for (sid, name), line_orders, revenue in partials:
            rows.append(
                ServicePopularityRow(
                    service_item_id=sid,  # D15: NULL 가능
                    service_name=name,
                    job_count=len(line_orders),
                    revenue=revenue,
                    revenue_share_pct=float(revenue / denom * Decimal("100")),
                )
            )
        rows.sort(key=lambda r: r.revenue, reverse=True)
        return ServicePopularityReport(start_date=start_date, end_date=end_date, rows=rows)

    # ---------- settlement backlog ----------

    def settlements(self) -> SettlementBacklogReport:
        partner_stmt = select(Partner)
        partners = {p.id: p for p in self.db.scalars(partner_stmt)}

        order_stmt = (
            select(Order)
            .where(
                Order.deleted_at.is_(None),
                Order.status == OrderStatus.COMPLETED,
            )
            .order_by(Order.scheduled_date.asc().nulls_last(), Order.id.asc())
        )
        orders = list(self.db.scalars(order_stmt))

        rows: list[SettlementBacklogRow] = []
        for order in orders:
            status_val = order.partner_payment_status
            if status_val is not None and status_val not in PARTNER_SETTLEMENT_PENDING_STATUSES:
                continue  # 이미 정산 완료 또는 hold
            partner = partners.get(order.partner_id) if order.partner_id else None
            rows.append(
                SettlementBacklogRow(
                    order_id=order.id,
                    scheduled_date=order.scheduled_date,
                    service_name=order.service_name,
                    partner_id=order.partner_id,
                    partner_name=partner.name if partner else None,
                    total_amount=Decimal(str(order.total_amount or 0)),
                    expected_settlement_amount=Decimal(str(order.partner_payment_amount or 0)),
                    status=order.status,
                )
            )
        return SettlementBacklogReport(rows=rows)


def _period_key(d: date, granularity: str) -> date:
    if granularity == "day":
        return d
    if granularity == "week":
        # ISO 주의 월요일
        return d - timedelta(days=d.weekday())
    if granularity == "month":
        return d.replace(day=1)
    raise ValueError(f"unsupported_granularity:{granularity}")
```

- [ ] **Step 3: 라우트 작성**

`backend/app/api/routes/admin/reports.py`:

```python
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_session, require_admin
from app.schemas.report import (
    PartnerPerformanceReport,
    RevenueReport,
    ServicePopularityReport,
    SettlementBacklogReport,
)
from app.services.reports import ReportService

router = APIRouter()


@router.get("/revenue", response_model=RevenueReport)
def revenue_report(
    granularity: str = Query("month", pattern="^(day|week|month)$"),
    start_date: date = Query(...),
    end_date: date = Query(...),
    partner_id: str | None = Query(None),
    service_item_id: str | None = Query(None),
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> RevenueReport:
    try:
        return ReportService(db).revenue(
            granularity=granularity,
            start_date=start_date,
            end_date=end_date,
            partner_id=partner_id,
            service_item_id=service_item_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/partners", response_model=PartnerPerformanceReport)
def partner_performance(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> PartnerPerformanceReport:
    return ReportService(db).partners(start_date=start_date, end_date=end_date)


@router.get("/services", response_model=ServicePopularityReport)
def service_popularity(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> ServicePopularityReport:
    return ReportService(db).services(start_date=start_date, end_date=end_date)


@router.get("/settlements", response_model=SettlementBacklogReport)
def settlement_backlog(
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> SettlementBacklogReport:
    return ReportService(db).settlements()
```

- [ ] **Step 4: 라우터 mount**

`backend/app/api/router.py`에 (admin 라우터 그룹 끝에):

```python
from app.api.routes.admin import reports as admin_reports

api_router.include_router(
    admin_reports.router,
    prefix="/admin/reports",
    tags=["admin-reports"],
)
```

- [ ] **Step 5: 테스트 통과**

```bash
cd backend && python -m pytest tests/test_reports.py -v
```
Expected: 3 passed.

- [ ] **Step 6: 커밋**

```bash
git add backend/app/services/reports.py backend/app/api/routes/admin/reports.py backend/app/api/router.py backend/tests/test_reports.py
git commit -m "feat(reports): R13 4 endpoint + Python aggregation (dialect 무관)"
```

---

## Task 4 — 보고서 회귀 + 테스트 커버리지 보강

**Files:**
- Modify: `backend/tests/test_reports.py`

집계 정확성을 단위 테스트로 검증한다.

- [ ] **Step 1: 직접 service 호출 테스트 추가**

```python
import pytest
from datetime import date
from decimal import Decimal

from app.domain.constants import OrderStatus
from app.domain.payment_status import PartnerPaymentStatus
from app.models.order import Order
from app.services.reports import ReportService


def test_revenue_includes_only_delivery_done_and_completed(db_session, seed_order):
    # seed_order는 NEW status. 매출에 포함 X.
    service = ReportService(db_session)
    report = service.revenue(
        granularity="month",
        start_date=date(2020, 1, 1),
        end_date=date(2030, 12, 31),
    )
    # seed_order 한 건은 status=NEW 라 매출 0
    assert report.total_completed == 0
    assert report.total_revenue == Decimal("0")

    # status를 COMPLETED로 바꾸면 매출에 포함
    seed_order.status = OrderStatus.COMPLETED
    seed_order.scheduled_date = date(2026, 5, 15)
    seed_order.total_amount = Decimal("100000")
    db_session.flush()

    report2 = service.revenue(
        granularity="month",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    assert report2.total_completed == 1
    assert report2.total_revenue == Decimal("100000")


def test_revenue_excludes_cancelled(db_session, seed_order):
    seed_order.status = OrderStatus.CANCELLED
    seed_order.scheduled_date = date(2026, 5, 15)
    seed_order.total_amount = Decimal("999999")
    db_session.flush()

    report = ReportService(db_session).revenue(
        granularity="month",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    assert report.total_completed == 0
    assert report.total_revenue == Decimal("0")


def test_revenue_groups_by_month(db_session, seed_order, make_extra_line):
    from datetime import date
    seed_order.status = OrderStatus.COMPLETED
    seed_order.scheduled_date = date(2026, 3, 10)
    seed_order.total_amount = Decimal("50000")

    extra = make_extra_line(seed_order.group_id)
    extra.status = OrderStatus.COMPLETED
    extra.scheduled_date = date(2026, 5, 20)
    extra.total_amount = Decimal("70000")
    db_session.flush()

    report = ReportService(db_session).revenue(
        granularity="month",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    periods = {b.period.isoformat(): b.revenue for b in report.buckets}
    assert periods == {"2026-03-01": Decimal("50000"), "2026-05-01": Decimal("70000")}


def test_settlement_backlog_only_lists_completed_unsettled(db_session, seed_order):
    # NEW → COMPLETED + UNPAID
    seed_order.status = OrderStatus.COMPLETED
    seed_order.partner_payment_status = PartnerPaymentStatus.UNPAID
    db_session.flush()

    rows = ReportService(db_session).settlements().rows
    assert any(r.order_id == seed_order.id for r in rows)

    # 정산 완료(PAID)면 제외
    seed_order.partner_payment_status = PartnerPaymentStatus.PAID
    db_session.flush()
    rows2 = ReportService(db_session).settlements().rows
    assert not any(r.order_id == seed_order.id for r in rows2)


def test_partner_performance_excludes_cancelled(db_session, seed_order_assigned_to_partner):
    order = seed_order_assigned_to_partner
    order.status = OrderStatus.CANCELLED
    order.scheduled_date = date(2026, 5, 15)
    db_session.flush()

    report = ReportService(db_session).partners(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    rows_for_partner = [r for r in report.rows if r.partner_id == order.partner_id]
    # CANCELLED는 작업 수에서 제외 — partner row 자체가 없거나 job_count=0
    if rows_for_partner:
        assert rows_for_partner[0].job_count == 0


def test_services_includes_null_service_item_id_fallback(db_session, seed_order):
    """S2/D15: service_item_id=None 이지만 service_name이 있는 주문도 통계에 포함."""
    seed_order.status = OrderStatus.COMPLETED
    seed_order.scheduled_date = date(2026, 5, 15)
    seed_order.total_amount = Decimal("55000")
    seed_order.service_item_id = None  # import 등록 주문 시뮬레이션
    seed_order.service_name = "특별 청소"
    db_session.flush()

    report = ReportService(db_session).services(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    matched = [r for r in report.rows if r.service_name == "특별 청소"]
    assert len(matched) == 1
    assert matched[0].service_item_id is None
    assert matched[0].revenue == Decimal("55000")


def test_services_empty_data(db_session):
    """빈 데이터: rows = []"""
    report = ReportService(db_session).services(
        start_date=date(2020, 1, 1),
        end_date=date(2020, 12, 31),
    )
    assert report.rows == []


def test_revenue_filters_by_partner_id(db_session, seed_order_assigned_to_partner):
    order = seed_order_assigned_to_partner
    order.status = OrderStatus.COMPLETED
    order.scheduled_date = date(2026, 5, 15)
    order.total_amount = Decimal("80000")
    db_session.flush()

    # partner_id 필터 일치 → 포함
    report_match = ReportService(db_session).revenue(
        granularity="month",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        partner_id=order.partner_id,
    )
    assert report_match.total_revenue == Decimal("80000")

    # 다른 partner_id → 빈 결과
    report_other = ReportService(db_session).revenue(
        granularity="month",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        partner_id="non-existent",
    )
    assert report_other.total_revenue == Decimal("0")
```

- [ ] **Step 2: 통과 확인**

```bash
python -m pytest tests/test_reports.py -v
```
Expected: 9 passed (Task 3의 3개 + 본 task 6개).

- [ ] **Step 3: 커밋**

```bash
git add backend/tests/test_reports.py
git commit -m "test(reports): R13 매출/협력사/정산 단위 테스트 커버리지 보강"
```

---

## Task 5 — Export (CSV / xlsx)

**Files:**
- Create: `backend/app/services/exporters.py`
- Modify: `backend/app/api/routes/admin/reports.py`
- Test: `backend/tests/test_report_export.py`

- [ ] **Step 1: 실패 테스트**

```python
def test_revenue_export_csv(client, seed_admin_token):
    res = client.get(
        "/api/admin/reports/revenue/export",
        params={"granularity": "month", "start_date": "2026-01-01", "end_date": "2026-12-31", "format": "csv"},
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    cd = res.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert 'filename="revenue.csv"' in cd
    # UTF-8 BOM 검증 (엑셀 한글 호환)
    assert res.content.startswith(b"\xef\xbb\xbf")
    text = res.content.decode("utf-8-sig")
    header_line = text.splitlines()[0]
    assert "period" in header_line
    assert "revenue" in header_line


def test_revenue_export_xlsx(client, seed_admin_token):
    res = client.get(
        "/api/admin/reports/revenue/export",
        params={"granularity": "month", "start_date": "2026-01-01", "end_date": "2026-12-31", "format": "xlsx"},
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert len(res.content) > 100


def test_export_unsupported_format_returns_400(client, seed_admin_token):
    res = client.get(
        "/api/admin/reports/revenue/export",
        params={
            "granularity": "month",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "format": "pdf",
        },
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    assert res.status_code in {400, 422}


def test_export_requires_admin(client):
    res = client.get(
        "/api/admin/reports/revenue/export",
        params={"granularity": "month", "start_date": "2026-01-01", "end_date": "2026-12-31", "format": "csv"},
    )
    assert res.status_code in {401, 403}


def test_partners_export_csv(client, seed_admin_token):
    res = client.get(
        "/api/admin/reports/partners/export",
        params={"start_date": "2026-01-01", "end_date": "2026-12-31", "format": "csv"},
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
```

- [ ] **Step 2: `app/services/exporters.py`**

```python
from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal
from typing import Any, Iterable, Sequence

from openpyxl import Workbook


def to_csv_bytes(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_to_cell(v) for v in row])
    return buffer.getvalue().encode("utf-8-sig")


def to_xlsx_bytes(
    headers: Sequence[str],
    rows: Iterable[Sequence[Any]],
    *,
    sheet_name: str = "report",
) -> bytes:
    wb = Workbook(write_only=False)
    try:
        ws = wb.active
        ws.title = sheet_name[:31]  # Excel sheet name 31자 한계
        ws.append(list(headers))
        for row in rows:
            ws.append([_to_cell(v) for v in row])
        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()
    finally:
        wb.close()


def _to_cell(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date):
        return value.isoformat()
    return value
```

- [ ] **Step 3: 라우트 — 4 export endpoint**

`reports.py`에 추가:

```python
from fastapi import Response
from app.services.exporters import to_csv_bytes, to_xlsx_bytes

_XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _export_response(name: str, headers: list[str], rows: list[list], format: str) -> Response:
    if format == "csv":
        body = to_csv_bytes(headers, rows)
        media_type = "text/csv; charset=utf-8"
        filename = f"{name}.csv"
    elif format == "xlsx":
        body = to_xlsx_bytes(headers, rows, sheet_name=name)
        media_type = _XLSX_MEDIA
        filename = f"{name}.xlsx"
    else:
        raise HTTPException(status_code=400, detail="unsupported_format")

    return Response(
        content=body,
        media_type=media_type,
        headers={"content-disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/revenue/export")
def revenue_export(
    granularity: str = Query("month", pattern="^(day|week|month)$"),
    start_date: date = Query(...),
    end_date: date = Query(...),
    partner_id: str | None = Query(None),
    service_item_id: str | None = Query(None),
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> Response:
    report = ReportService(db).revenue(
        granularity=granularity,
        start_date=start_date,
        end_date=end_date,
        partner_id=partner_id,
        service_item_id=service_item_id,
    )
    rows = [[b.period, b.completed_count, b.revenue] for b in report.buckets]
    return _export_response(
        "revenue",
        ["period", "completed_count", "revenue"],
        rows,
        format,
    )


@router.get("/partners/export")
def partners_export(
    start_date: date = Query(...),
    end_date: date = Query(...),
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> Response:
    report = ReportService(db).partners(start_date=start_date, end_date=end_date)
    rows = [
        [r.partner_id, r.partner_name, r.job_count, r.avg_unit_price, r.pending_settlement_count, r.expected_settlement_amount]
        for r in report.rows
    ]
    return _export_response(
        "partners",
        ["partner_id", "partner_name", "job_count", "avg_unit_price", "pending_settlement_count", "expected_settlement_amount"],
        rows,
        format,
    )


@router.get("/services/export")
def services_export(
    start_date: date = Query(...),
    end_date: date = Query(...),
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> Response:
    report = ReportService(db).services(start_date=start_date, end_date=end_date)
    rows = [
        [r.service_item_id, r.service_name, r.job_count, r.revenue, round(r.revenue_share_pct, 2)]
        for r in report.rows
    ]
    return _export_response(
        "services",
        ["service_item_id", "service_name", "job_count", "revenue", "revenue_share_pct"],
        rows,
        format,
    )


@router.get("/settlements/export")
def settlements_export(
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> Response:
    report = ReportService(db).settlements()
    rows = [
        [r.order_id, r.scheduled_date, r.service_name, r.partner_id, r.partner_name, r.total_amount, r.expected_settlement_amount, r.status]
        for r in report.rows
    ]
    return _export_response(
        "settlements",
        ["order_id", "scheduled_date", "service_name", "partner_id", "partner_name", "total_amount", "expected_settlement_amount", "status"],
        rows,
        format,
    )
```

- [ ] **Step 4: 통과 확인 + 커밋**

```bash
python -m pytest tests/test_report_export.py -v
git add backend/app/services/exporters.py backend/app/api/routes/admin/reports.py backend/tests/test_report_export.py
git commit -m "feat(reports): R13 CSV/xlsx export 4 화면 + UTF-8 BOM + 권한 가드"
```

---

## Task 6 — Order Import (xlsx + group_key)

**Files:**
- Create: `backend/app/services/order_import.py`
- Modify: `backend/app/api/routes/admin/orders.py`
- Test: `backend/tests/test_order_import.py`

R7 multi-line 호환: 같은 `group_key` 행을 한 OrderGroup으로 묶는다.

- [ ] **Step 1: 실패 테스트**

```python
import io
from datetime import date
from openpyxl import Workbook

from app.domain.constants import OrderStatus


def _make_xlsx(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append([
        "group_key",
        "customer_name",
        "customer_phone",
        "customer_address",
        "scheduled_date",
        "service_name",
        "total_amount",
    ])
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    return buf.getvalue()


def test_order_import_single_group_with_two_lines(client, seed_admin_token):
    data = _make_xlsx([
        ["G1", "테스트", "010-1111-2222", "서울 강남 1", "2026-06-01", "에어컨 청소", 100000],
        ["G1", "테스트", "010-1111-2222", "서울 강남 1", "2026-06-01", "거실 청소", 80000],
    ])
    res = client.post(
        "/api/admin/orders/import",
        files={"file": ("orders.xlsx", data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["succeeded_groups"] == 1
    assert body["succeeded_lines"] == 2
    assert body["failed"] == []


def test_order_import_two_groups(client, seed_admin_token):
    data = _make_xlsx([
        ["G1", "테스트A", "010-1111-2222", "강남", "2026-06-01", "에어컨", 100000],
        ["G2", "테스트B", "010-3333-4444", "강북", "2026-06-02", "이사", 250000],
    ])
    res = client.post(
        "/api/admin/orders/import",
        files={"file": ("orders.xlsx", data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    body = res.json()
    assert body["succeeded_groups"] == 2
    assert body["succeeded_lines"] == 2


def test_order_import_reports_invalid_rows(client, seed_admin_token):
    data = _make_xlsx([
        ["", "", "010-1111-2222", "강남", "2026-06-01", "에어컨", 100000],  # group_key 없음
        ["G2", "테스트", "abc", "강남", "2026-06-02", "에어컨", 100000],  # 전화 형식 X
        ["G3", "테스트", "010-9999-8888", "강남", "2026-06-03", "에어컨", 100000],  # 유효
    ])
    res = client.post(
        "/api/admin/orders/import",
        files={"file": ("orders.xlsx", data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    body = res.json()
    assert body["succeeded_groups"] == 1
    assert body["succeeded_lines"] == 1
    assert {f["row_index"] for f in body["failed"]} == {1, 2}


def test_order_import_group_rollback_when_one_line_invalid(client, seed_admin_token):
    """S1: 같은 group_key 안에 잘못된 row가 있으면 그 group의 모든 row가 fail."""
    data = _make_xlsx([
        ["G1", "테스트A", "010-1111-2222", "강남", "2026-06-01", "에어컨", 100000],  # valid
        ["G1", "테스트A", "abc", "강남", "2026-06-01", "거실", 80000],  # invalid phone
    ])
    res = client.post(
        "/api/admin/orders/import",
        files={"file": ("orders.xlsx", data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    body = res.json()
    assert body["succeeded_groups"] == 0
    assert body["succeeded_lines"] == 0
    reasons = {f["reason"] for f in body["failed"]}
    assert any("invalid_phone" in r for r in reasons)
    assert "group_skipped_due_to_sibling_error" in reasons


def test_order_import_rejects_inconsistent_group_customer(client, seed_admin_token):
    """S4: 같은 group_key에서 customer 정보 다르면 group 전체 fail."""
    data = _make_xlsx([
        ["G1", "테스트A", "010-1111-2222", "강남", "2026-06-01", "에어컨", 100000],
        ["G1", "다른이름", "010-1111-2222", "강남", "2026-06-02", "거실", 80000],
    ])
    res = client.post(
        "/api/admin/orders/import",
        files={"file": ("orders.xlsx", data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    body = res.json()
    assert body["succeeded_groups"] == 0
    reasons = {f["reason"] for f in body["failed"]}
    assert "inconsistent_group_customer" in reasons


def test_order_import_rejects_invalid_file_type(client, seed_admin_token):
    res = client.post(
        "/api/admin/orders/import",
        files={"file": ("orders.txt", b"not xlsx", "text/plain")},
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    assert res.status_code in {400, 415}


def test_order_import_requires_admin(client, seed_partner_token):
    data = _make_xlsx([["G1", "X", "010-0000-0000", "X", "2026-06-01", "X", 1000]])
    res = client.post(
        "/api/admin/orders/import",
        files={"file": ("orders.xlsx", data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    )
    assert res.status_code in {401, 403}
```

- [ ] **Step 2: `app/services/order_import.py`**

```python
from __future__ import annotations

import io
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.core.time import business_today
from app.domain.constants import OrderStatus
from app.domain.phone import normalize_phone
from app.schemas.order import OrderGroupCreate, OrderLineCreate
from app.schemas.report import OrderImportFailure, OrderImportResult
from app.services.orders import OrderService

REQUIRED_HEADERS = [
    "group_key",
    "customer_name",
    "customer_phone",
    "customer_address",
    "scheduled_date",
    "service_name",
    "total_amount",
]

_XLSX_MEDIA_PREFIXES = (
    "application/vnd.openxmlformats",
    "application/vnd.ms-excel",
    "application/octet-stream",  # N5: 일부 브라우저
)


def is_xlsx_upload(filename: str | None, content_type: str | None) -> bool:
    """S3/S7: route와 service가 공유하는 단일 정책. filename 확장자 또는 content-type 매칭.
    .xlsm은 매크로 보안 우려로 제외 — xlsx-only.
    """
    name = (filename or "").lower()
    if name.endswith(".xlsx"):
        return True
    if content_type and content_type.startswith(_XLSX_MEDIA_PREFIXES):
        return True
    return False


def import_orders_from_xlsx(
    *,
    file_bytes: bytes,
    filename: str | None,
    content_type: str | None,
    db: Session,
    actor_user_id: str,
) -> OrderImportResult:
    if not is_xlsx_upload(filename, content_type):
        raise ValueError(f"unsupported_content_type:{content_type or '(none)'}")

    try:
        wb = load_workbook(filename=io.BytesIO(file_bytes), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"invalid_xlsx:{exc}") from exc

    try:
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)
        headers = list(next(rows_iter, []) or [])
    except Exception:
        wb.close()
        raise

    header_to_idx = {str(h): i for i, h in enumerate(headers) if h is not None}
    missing = [h for h in REQUIRED_HEADERS if h not in header_to_idx]
    if missing:
        wb.close()
        return OrderImportResult(
            succeeded_groups=0,
            succeeded_lines=0,
            failed=[
                OrderImportFailure(
                    row_index=0,
                    reason=f"missing_columns:{','.join(missing)}",
                )
            ],
        )

    # 행을 group_key 별로 묶음. parse 실패 또는 customer 정보 불일치는 group 전체 fail.
    grouped: dict[str, dict[str, Any]] = {}
    group_errors: dict[str, list[OrderImportFailure]] = {}
    # group 별로 모든 row_index를 추적해야 fail 시 한꺼번에 보고 가능
    group_rows: dict[str, list[int]] = {}

    for idx, raw in enumerate(rows_iter, start=1):
        if raw is None:
            continue
        if all(cell is None or (isinstance(cell, str) and not cell.strip()) for cell in raw):
            continue  # 빈 행 skip

        # group_key 먼저 추출 (parse 전이라도 그룹 추적)
        gk_raw = raw[header_to_idx["group_key"]] if header_to_idx.get("group_key") is not None else None
        gk = str(gk_raw or "").strip()
        if gk:
            group_rows.setdefault(gk, []).append(idx)

        try:
            line = _parse_row(raw, header_to_idx)
        except ValueError as exc:
            # group_key가 있으면 group 전체 fail, 없으면 단일 row fail
            key = gk if gk else f"__unknown_row_{idx}"
            group_errors.setdefault(key, []).append(
                OrderImportFailure(row_index=idx, reason=str(exc))
            )
            continue

        # 첫 행이거나, 같은 group_key의 customer 정보가 동일한지 검증
        if gk not in grouped:
            grouped[gk] = {
                "customer_name": line["customer_name"],
                "customer_phone": line["customer_phone"],
                "customer_address": line["customer_address"],
                "lines": [],
            }
        else:
            head = grouped[gk]
            if (
                head["customer_name"] != line["customer_name"]
                or head["customer_phone"] != line["customer_phone"]
                or head["customer_address"] != line["customer_address"]
            ):
                group_errors.setdefault(gk, []).append(
                    OrderImportFailure(row_index=idx, reason="inconsistent_group_customer")
                )
                continue

        grouped[gk]["lines"].append({"row_index": idx, "data": line})

    wb.close()

    # group 안에 1개라도 error가 있으면 그 group의 모든 row를 fail로 보고하고 commit하지 않는다.
    failed: list[OrderImportFailure] = []
    for gk, errs in group_errors.items():
        if gk.startswith("__unknown_row_"):
            # group_key 자체가 비어있는 row — 그 row 한 개만 fail
            failed.extend(errs)
            continue
        # 같은 group_key의 정상 row들도 함께 fail 처리
        ok_rows = [entry["row_index"] for entry in grouped.get(gk, {}).get("lines", [])]
        err_indices = {e.row_index for e in errs}
        failed.extend(errs)
        for row_idx in ok_rows:
            if row_idx not in err_indices:
                failed.append(
                    OrderImportFailure(
                        row_index=row_idx,
                        reason="group_skipped_due_to_sibling_error",
                    )
                )
        # 이 group은 commit 안 함
        grouped.pop(gk, None)

    service = OrderService(db)
    succeeded_groups = 0
    succeeded_lines = 0
    today_kst = business_today()

    for gk, bundle in grouped.items():
        line_payloads = [
            OrderLineCreate(
                status=OrderStatus.NEW,
                received_date=today_kst,
                scheduled_date=d["data"]["scheduled_date"],
                service_name=d["data"]["service_name"],
                total_amount=d["data"]["total_amount"],
            )
            for d in bundle["lines"]
        ]

        try:
            service.create_group(
                OrderGroupCreate(
                    customer_name=bundle["customer_name"],
                    customer_phone=bundle["customer_phone"],
                    customer_address=bundle["customer_address"],
                    notes=None,
                    lines=line_payloads,
                ),
                actor_user_id=actor_user_id,
            )
            db.flush()
            succeeded_groups += 1
            succeeded_lines += len(line_payloads)
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            for entry in bundle["lines"]:
                failed.append(
                    OrderImportFailure(
                        row_index=entry["row_index"],
                        reason=f"group_create_failed:{exc}",
                    )
                )

    db.commit()
    # row_index 정렬해서 응답 일관성 확보
    failed.sort(key=lambda f: f.row_index)
    return OrderImportResult(
        succeeded_groups=succeeded_groups,
        succeeded_lines=succeeded_lines,
        failed=failed,
    )


def _parse_row(raw: tuple, header_to_idx: dict[str, int]) -> dict[str, Any]:
    def cell(name: str) -> Any:
        return raw[header_to_idx[name]]

    group_key = (str(cell("group_key") or "")).strip()
    if not group_key:
        raise ValueError("group_key_required")

    name = (str(cell("customer_name") or "")).strip()
    if not name:
        raise ValueError("customer_name_required")

    phone_raw = str(cell("customer_phone") or "").strip()
    try:
        phone = normalize_phone(phone_raw)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"invalid_phone:{phone_raw}") from exc
    if not phone:
        raise ValueError("invalid_phone")

    address = (str(cell("customer_address") or "")).strip()
    if not address:
        raise ValueError("customer_address_required")

    scheduled = cell("scheduled_date")
    scheduled_date = _coerce_date(scheduled)

    service_name = (str(cell("service_name") or "")).strip()
    if not service_name:
        raise ValueError("service_name_required")

    total_amount = _coerce_decimal(cell("total_amount"))
    if total_amount < 0:
        raise ValueError("negative_total_amount")

    return {
        "group_key": group_key,
        "customer_name": name,
        "customer_phone": phone,
        "customer_address": address,
        "scheduled_date": scheduled_date,
        "service_name": service_name,
        "total_amount": total_amount,
    }


def _coerce_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"invalid_scheduled_date:{value}") from exc
    raise ValueError("invalid_scheduled_date")


def _coerce_decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid_total_amount:{value}") from exc
```

- [ ] **Step 3: 라우트 추가**

`backend/app/api/routes/admin/orders.py`에:

```python
from fastapi import File, UploadFile
from app.schemas.report import OrderImportResult
from app.services.order_import import import_orders_from_xlsx


@router.post("/import", response_model=OrderImportResult)
async def import_orders(
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
) -> OrderImportResult:
    from app.services.order_import import is_xlsx_upload

    data = await file.read()
    if not is_xlsx_upload(file.filename, file.content_type):
        raise HTTPException(status_code=400, detail=f"unsupported_content_type:{file.content_type}")
    try:
        return import_orders_from_xlsx(
            file_bytes=data,
            filename=file.filename,
            content_type=file.content_type,
            db=db,
            actor_user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

(필요 import: `File`, `UploadFile`, `HTTPException`. 이미 있는 것은 중복 추가 X.)

- [ ] **Step 4: 통과 확인**

```bash
python -m pytest tests/test_order_import.py -v
```

- [ ] **Step 5: 커밋**

```bash
git add backend/app/services/order_import.py backend/app/api/routes/admin/orders.py backend/tests/test_order_import.py
git commit -m "feat(orders): R13 xlsx 일괄 import + group_key multi-line + 행별 부분 성공"
```

---

## Task 7 — Frontend: API client downloadBlob 헬퍼

**Files:**
- Modify: `frontend/src/api/client.ts`

Export 다운로드를 위해 fetch + blob 패턴 헬퍼 추가.

- [ ] **Step 1: `downloadBlob` 함수 추가**

기존 `apiRequest` 다음에:

```ts
export async function downloadBlob(path: string, suggestedFilename: string): Promise<void> {
  const response = await fetchBlobWithRefresh(path);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  try {
    const a = document.createElement('a');
    a.href = url;
    a.download = suggestedFilename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
}

async function fetchBlobWithRefresh(path: string): Promise<Response> {
  let response = await blobRequest(path);
  if (response.status === 401 && authHandlers?.getRefreshToken()) {
    try {
      const session = await refreshWithRotation(authHandlers.getRefreshToken() ?? '');
      authHandlers.onRefresh(session);
      response = await blobRequest(path);
      if (response.status === 401) {
        authHandlers.onUnauthorized();
        throw await toApiError(response);
      }
    } catch (err) {
      authHandlers.onUnauthorized();
      throw err;
    }
  }
  if (!response.ok) {
    throw await toApiError(response);
  }
  return response;
}

async function blobRequest(path: string): Promise<Response> {
  const headers = new Headers();
  headers.set('X-Request-ID', createRequestId());
  const accessToken = authHandlers?.getAccessToken();
  if (accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`);
  }
  return fetch(toApiUrl(path), { headers, credentials: 'include' });
}
```

(R10 cookie 전환 시 `credentials: 'include'`가 자동으로 cookie 전송.)

- [ ] **Step 2: typecheck**

```bash
cd frontend && npm run typecheck
```

- [ ] **Step 3: 커밋**

```bash
git add frontend/src/api/client.ts
git commit -m "feat(api): R13 downloadBlob 헬퍼 (fetch + blob 다운로드)"
```

---

## Task 8 — Frontend: Reports Page + 4 화면

**Files:**
- Create: `frontend/src/api/reports.ts`
- Create: `frontend/src/features/admin/reports/ReportsPage.tsx`
- Create: `frontend/src/features/admin/reports/RevenueChart.tsx`
- Create: `frontend/src/features/admin/reports/PartnerPerformanceTable.tsx`
- Create: `frontend/src/features/admin/reports/ServicePopularityTable.tsx`
- Create: `frontend/src/features/admin/reports/SettlementBacklogTable.tsx`
- Create: `frontend/src/features/admin/reports/ExportButtons.tsx`
- Modify: `frontend/src/app/App.tsx`
- Modify: `frontend/src/components/layout/AdminShell.tsx`

분량이 크므로 sub-step:

- [ ] **Step 1: `api/reports.ts`**

```ts
import { apiRequest, downloadBlob } from './client';

export interface RevenueBucket {
  period: string;
  completed_count: number;
  revenue: string;  // Pydantic Decimal → string
}

export interface RevenueReport {
  granularity: string;
  start_date: string;
  end_date: string;
  partner_id: string | null;
  service_item_id: string | null;
  buckets: RevenueBucket[];
  total_revenue: string;
  total_completed: number;
}

export interface PartnerPerformanceRow {
  partner_id: string;
  partner_name: string;
  job_count: number;
  avg_unit_price: string;
  pending_settlement_count: number;
  expected_settlement_amount: string;
}

export interface PartnerPerformanceReport {
  start_date: string;
  end_date: string;
  rows: PartnerPerformanceRow[];
}

export interface ServicePopularityRow {
  service_item_id: string | null;  // D15: import된 주문은 NULL
  service_name: string;
  job_count: number;
  revenue: string;
  revenue_share_pct: number;
}

export interface ServicePopularityReport {
  start_date: string;
  end_date: string;
  rows: ServicePopularityRow[];
}

export interface SettlementBacklogRow {
  order_id: string;
  scheduled_date: string | null;
  service_name: string;
  partner_id: string | null;
  partner_name: string | null;
  total_amount: string;
  expected_settlement_amount: string;
  status: string;
}

export interface SettlementBacklogReport {
  rows: SettlementBacklogRow[];
}

export function fetchRevenue(params: Record<string, string>): Promise<RevenueReport> {
  const qs = new URLSearchParams(params).toString();
  return apiRequest(`/admin/reports/revenue?${qs}`);
}

export function fetchPartners(params: Record<string, string>): Promise<PartnerPerformanceReport> {
  const qs = new URLSearchParams(params).toString();
  return apiRequest(`/admin/reports/partners?${qs}`);
}

export function fetchServices(params: Record<string, string>): Promise<ServicePopularityReport> {
  const qs = new URLSearchParams(params).toString();
  return apiRequest(`/admin/reports/services?${qs}`);
}

export function fetchSettlements(): Promise<SettlementBacklogReport> {
  return apiRequest('/admin/reports/settlements');
}

export function exportReport(
  name: 'revenue' | 'partners' | 'services' | 'settlements',
  params: Record<string, string>,
  format: 'csv' | 'xlsx',
): Promise<void> {
  const qs = new URLSearchParams({ ...params, format }).toString();
  return downloadBlob(`/admin/reports/${name}/export?${qs}`, `${name}.${format}`);
}
```

- [ ] **Step 2: `ExportButtons.tsx`**

```tsx
import React from 'react';

import { exportReport } from '../../../api/reports';

interface Props {
  name: 'revenue' | 'partners' | 'services' | 'settlements';
  params: Record<string, string>;
}

export function ExportButtons({ name, params }: Props) {
  const [isExporting, setIsExporting] = React.useState<'csv' | 'xlsx' | null>(null);

  const handle = async (format: 'csv' | 'xlsx') => {
    setIsExporting(format);
    try {
      await exportReport(name, params, format);
    } catch (error) {
      window.alert(`다운로드 실패: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setIsExporting(null);
    }
  };

  return (
    <div style={{ display: 'flex', gap: 6 }}>
      <button
        data-testid={`reports-${name}-export-csv`}
        className="btn btn--secondary btn--sm"
        disabled={isExporting !== null}
        onClick={() => void handle('csv')}
      >
        {isExporting === 'csv' ? '...' : 'CSV'}
      </button>
      <button
        data-testid={`reports-${name}-export-xlsx`}
        className="btn btn--secondary btn--sm"
        disabled={isExporting !== null}
        onClick={() => void handle('xlsx')}
      >
        {isExporting === 'xlsx' ? '...' : 'Excel'}
      </button>
    </div>
  );
}
```

- [ ] **Step 3: `RevenueChart.tsx` (recharts)**

```tsx
import React from 'react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';

interface Props {
  data: { period: string; revenue: number; completed_count: number }[];
}

export function RevenueChart({ data }: Props) {
  return (
    <div data-testid="reports-revenue-chart" style={{ width: '100%', height: 320 }}>
      <ResponsiveContainer>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="period" />
          <YAxis />
          <Tooltip />
          <Line type="monotone" dataKey="revenue" stroke="var(--brand)" strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 4: 3개 Table 컴포넌트**

각 컴포넌트는 단순 `<table>` + row 매핑. testid:
- `partner-performance-table`
- `service-popularity-table`
- `settlement-backlog-table`

예시 (`PartnerPerformanceTable.tsx`):

```tsx
import React from 'react';

import type { PartnerPerformanceRow } from '../../../api/reports';

interface Props {
  rows: PartnerPerformanceRow[];
}

export function PartnerPerformanceTable({ rows }: Props) {
  if (rows.length === 0) {
    return <div style={{ padding: 20, color: 'var(--text-tertiary)' }}>표시할 데이터가 없습니다.</div>;
  }
  return (
    <table data-testid="partner-performance-table" className="table">
      <thead>
        <tr>
          <th>협력사</th>
          <th>작업 수</th>
          <th>평균 단가</th>
          <th>정산 대기</th>
          <th>정산 예정액</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.partner_id}>
            <td>{r.partner_name}</td>
            <td>{r.job_count}</td>
            <td>{Number(r.avg_unit_price).toLocaleString()} 원</td>
            <td>{r.pending_settlement_count}</td>
            <td>{Number(r.expected_settlement_amount).toLocaleString()} 원</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

나머지 2 Table도 동일 패턴.

- [ ] **Step 5: `ReportsPage.tsx`**

```tsx
import React from 'react';

import { listPartners, listServiceItems } from '../../../api/admin';
import {
  fetchRevenue, fetchPartners, fetchServices, fetchSettlements,
  type RevenueReport, type PartnerPerformanceReport,
  type ServicePopularityReport, type SettlementBacklogReport,
} from '../../../api/reports';
import { ExportButtons } from './ExportButtons';
import { RevenueChart } from './RevenueChart';
import { PartnerPerformanceTable } from './PartnerPerformanceTable';
import { ServicePopularityTable } from './ServicePopularityTable';
import { SettlementBacklogTable } from './SettlementBacklogTable';

const TABS = [
  { key: 'revenue', label: '매출 추세' },
  { key: 'partners', label: '협력사 성과' },
  { key: 'services', label: '서비스 인기' },
  { key: 'settlements', label: '정산 대기' },
] as const;

type TabKey = typeof TABS[number]['key'];

function defaultRange() {
  const today = new Date();
  const start = new Date(today.getFullYear(), today.getMonth() - 5, 1);
  const end = new Date(today.getFullYear(), today.getMonth() + 1, 0);
  const fmt = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return { start_date: fmt(start), end_date: fmt(end) };
}

export function ReportsPage() {
  const [tab, setTab] = React.useState<TabKey>('revenue');
  const [range, setRange] = React.useState(defaultRange);
  const [granularity, setGranularity] = React.useState<'day' | 'week' | 'month'>('month');

  return (
    <div data-testid="admin-reports-page" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--bg)' }}>
      <div style={{ padding: '12px 24px', display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
        {TABS.map((t) => (
          <button
            key={t.key}
            data-testid={`reports-tab-${t.key}`}
            className={tab === t.key ? 'btn btn--primary btn--sm' : 'btn btn--ghost btn--sm'}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
        <div style={{ flex: 1 }}/>
        {tab !== 'settlements' && (
          <>
            <input
              data-testid="reports-start-date"
              type="date"
              value={range.start_date}
              onChange={(e) => setRange({ ...range, start_date: e.target.value })}
            />
            <span>~</span>
            <input
              data-testid="reports-end-date"
              type="date"
              value={range.end_date}
              onChange={(e) => setRange({ ...range, end_date: e.target.value })}
            />
          </>
        )}
        {tab === 'revenue' && (
          <select
            data-testid="reports-granularity"
            value={granularity}
            onChange={(e) => setGranularity(e.target.value as 'day' | 'week' | 'month')}
          >
            <option value="day">일</option>
            <option value="week">주</option>
            <option value="month">월</option>
          </select>
        )}
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: 20 }}>
        {tab === 'revenue' && <RevenueView range={range} granularity={granularity} />}
        {tab === 'partners' && <PartnersView range={range} />}
        {tab === 'services' && <ServicesView range={range} />}
        {tab === 'settlements' && <SettlementsView />}
      </div>
    </div>
  );
}

function RevenueView({
  range,
  granularity,
}: {
  range: { start_date: string; end_date: string };
  granularity: 'day' | 'week' | 'month';
}) {
  const [report, setReport] = React.useState<RevenueReport | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [partners, setPartners] = React.useState<{ id: string; name: string }[]>([]);
  const [services, setServices] = React.useState<{ id: string; name: string }[]>([]);
  const [partnerId, setPartnerId] = React.useState<string>('');
  const [serviceItemId, setServiceItemId] = React.useState<string>('');

  // N4: static import + 1회 옵션 로드
  React.useEffect(() => {
    listPartners()
      .then((rows) => setPartners((rows ?? []).map((p: any) => ({ id: p.id, name: p.name }))))
      .catch(() => {});
    listServiceItems()
      .then((rows) => setServices(rows ?? []))
      .catch(() => {});
  }, []);

  const params: Record<string, string> = { ...range, granularity };
  if (partnerId) params.partner_id = partnerId;
  if (serviceItemId) params.service_item_id = serviceItemId;

  React.useEffect(() => {
    setError(null);
    fetchRevenue(params)
      .then(setReport)
      .catch((e) => {
        setReport(null);
        setError(e instanceof Error ? e.message : String(e));
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [range.start_date, range.end_date, granularity, partnerId, serviceItemId]);

  return (
    <>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <select
          data-testid="reports-revenue-partner-filter"
          value={partnerId}
          onChange={(e) => setPartnerId(e.target.value)}
        >
          <option value="">전체 협력사</option>
          {partners.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <select
          data-testid="reports-revenue-service-filter"
          value={serviceItemId}
          onChange={(e) => setServiceItemId(e.target.value)}
        >
          <option value="">전체 서비스</option>
          {services.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <div style={{ flex: 1 }}/>
        {report && (
          <div>
            <strong>총 매출: {Number(report.total_revenue).toLocaleString()} 원</strong>
            <span style={{ marginLeft: 16, color: 'var(--text-tertiary)' }}>완료 {report.total_completed} 건</span>
          </div>
        )}
        <ExportButtons name="revenue" params={params} />
      </div>
      <ReportState data={report} error={error} empty={!!report && report.buckets.length === 0}>
        <RevenueChart
          data={(report?.buckets ?? []).map((b) => ({
            period: b.period,
            revenue: Number(b.revenue),
            completed_count: b.completed_count,
          }))}
        />
      </ReportState>
    </>
  );
}

// S5: 3-state (loading / error / empty) 공통 wrapper
function ReportState<T>({
  data,
  error,
  empty,
  children,
}: {
  data: T | null;
  error: string | null;
  empty: boolean;
  children: React.ReactNode;
}) {
  if (error) {
    return <div data-testid="reports-error" style={{ color: 'var(--danger-fg)', padding: 20 }}>불러오기 실패: {error}</div>;
  }
  if (data === null) {
    return <div data-testid="reports-loading" style={{ padding: 20 }}>불러오는 중...</div>;
  }
  if (empty) {
    return <div data-testid="reports-empty" style={{ padding: 20, color: 'var(--text-tertiary)' }}>표시할 데이터가 없습니다.</div>;
  }
  return <>{children}</>;
}

function PartnersView({ range }: { range: { start_date: string; end_date: string } }) {
  const [report, setReport] = React.useState<PartnerPerformanceReport | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    setError(null);
    fetchPartners(range)
      .then(setReport)
      .catch((e) => { setReport(null); setError(e instanceof Error ? e.message : String(e)); });
  }, [range.start_date, range.end_date]);

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
        <ExportButtons name="partners" params={range} />
      </div>
      <ReportState data={report} error={error} empty={!!report && report.rows.length === 0}>
        <PartnerPerformanceTable rows={report?.rows ?? []} />
      </ReportState>
    </>
  );
}

function ServicesView({ range }: { range: { start_date: string; end_date: string } }) {
  const [report, setReport] = React.useState<ServicePopularityReport | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    setError(null);
    fetchServices(range)
      .then(setReport)
      .catch((e) => { setReport(null); setError(e instanceof Error ? e.message : String(e)); });
  }, [range.start_date, range.end_date]);

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
        <ExportButtons name="services" params={range} />
      </div>
      <ReportState data={report} error={error} empty={!!report && report.rows.length === 0}>
        <ServicePopularityTable rows={report?.rows ?? []} />
      </ReportState>
    </>
  );
}

function SettlementsView() {
  const [report, setReport] = React.useState<SettlementBacklogReport | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    setError(null);
    fetchSettlements()
      .then(setReport)
      .catch((e) => { setReport(null); setError(e instanceof Error ? e.message : String(e)); });
  }, []);

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
        <ExportButtons name="settlements" params={{}} />
      </div>
      <ReportState data={report} error={error} empty={!!report && report.rows.length === 0}>
        <SettlementBacklogTable rows={report?.rows ?? []} />
      </ReportState>
    </>
  );
}
```

- [ ] **Step 6: AdminShell 사이드바에 `보고서` 메뉴 추가**

기존 메뉴 배열(예: `[ '대시보드', '주문관리', '일정 캘린더', '사진검수', '상품관리', '협력사관리', '발송이력' ]`)에 `보고서`를 적절한 위치에 삽입. icon은 **실제 Icon set에 존재하는 `trending` 또는 `fileText`** 사용. testid: `admin-nav-reports`.

- [ ] **Step 7: `App.tsx` 라우팅**

`ADMIN_PAGE_META`에 추가:
```ts
reports: {
  title: '보고서',
  subtitle: '매출 / 협력사 / 서비스 / 정산',
  breadcrumb: ['운영', '보고서'],
},
```

page switch에:
```tsx
{page === 'reports' && <ReportsPage />}
```

ComingSoon 가드 array에 `'reports'` 포함:
```tsx
!['dashboard', 'orders', 'calendar', 'photos', 'products', 'partners', 'sends', 'reports'].includes(page)
```

- [ ] **Step 8: typecheck + lint + build**

```bash
cd frontend && npm run typecheck && npm run lint && npm run build
```
Expected: 통과.

- [ ] **Step 9: 커밋**

```bash
git add frontend/src/api/reports.ts frontend/src/features/admin/reports/ frontend/src/app/App.tsx frontend/src/components/layout/AdminShell.tsx
git commit -m "feat(reports): R13 보고서 페이지 + 4 화면 + recharts + export buttons"
```

---

## Task 9 — Frontend: Order Import Dialog

**Files:**
- Create: `frontend/src/features/admin/orders/OrderImportDialog.tsx`
- Modify: `frontend/src/api/admin.ts`
- Modify: `frontend/src/features/admin/orders/OrdersPage.tsx`

- [ ] **Step 1: `api/admin.ts`에 import API 추가**

```ts
export interface ImportFailure {
  row_index: number;
  reason: string;
}

export interface ImportResult {
  succeeded_groups: number;
  succeeded_lines: number;
  failed: ImportFailure[];
}

export function importOrders(file: File): Promise<ImportResult> {
  const form = new FormData();
  form.append('file', file);
  return apiRequest('/admin/orders/import', { method: 'POST', body: form });
}
```

- [ ] **Step 2: `OrderImportDialog.tsx`**

```tsx
import React from 'react';
import { importOrders, type ImportResult } from '../../../api/admin';

interface Props {
  onClose: () => void;
  onImported: () => void;
}

export function OrderImportDialog({ onClose, onImported }: Props) {
  const [file, setFile] = React.useState<File | null>(null);
  const [result, setResult] = React.useState<ImportResult | null>(null);
  const [isUploading, setIsUploading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const handleSubmit = async () => {
    if (!file) return;
    setIsUploading(true);
    setError(null);
    try {
      const res = await importOrders(file);
      setResult(res);
      if (res.succeeded_groups > 0) {
        onImported();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div
      data-testid="order-import-dialog"
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
      }}
      onClick={onClose}
    >
      <div
        style={{ background: 'var(--surface)', padding: 20, borderRadius: 8, width: 520, maxWidth: '90vw' }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3>주문 일괄 등록</h3>
        <p style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
          xlsx 첫 행 = header. 필수 컬럼: group_key, customer_name, customer_phone, customer_address, scheduled_date, service_name, total_amount.
          같은 group_key 행은 한 그룹의 여러 line으로 묶입니다.
        </p>
        <input
          data-testid="order-import-file"
          type="file"
          accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        {error && <div style={{ marginTop: 8, color: 'var(--danger-fg)', fontSize: 12 }}>{error}</div>}
        {result && (
          <div style={{ marginTop: 12, fontSize: 13 }}>
            <div>✓ 그룹 {result.succeeded_groups}개 / 라인 {result.succeeded_lines}개 등록</div>
            {result.failed.length > 0 && (
              <details>
                <summary>실패 {result.failed.length}건</summary>
                <ul>
                  {result.failed.map((f, i) => <li key={i}>{f.row_index === 0 ? '(헤더)' : `${f.row_index}행`}: {f.reason}</li>)}
                </ul>
              </details>
            )}
          </div>
        )}
        <div style={{ marginTop: 16, display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
          <button className="btn btn--secondary btn--sm" onClick={onClose}>닫기</button>
          <button
            data-testid="order-import-submit"
            className="btn btn--primary btn--sm"
            disabled={!file || isUploading}
            onClick={() => void handleSubmit()}
          >
            {isUploading ? '업로드 중' : '업로드'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: OrdersPage 헤더에 `일괄 등록` 버튼**

기존 "내보내기" 옆에 추가:

```tsx
<button data-testid="admin-orders-import" className="btn btn--secondary btn--sm" onClick={() => setImportOpen(true)}>
  <Icon name="upload" size={12}/> 일괄 등록
</button>
```

state + dialog:
```tsx
const [isImportOpen, setImportOpen] = React.useState(false);
// ...
{isImportOpen && (
  <OrderImportDialog
    onClose={() => setImportOpen(false)}
    onImported={() => { ordersResource.reload(); }}
  />
)}
```

- [ ] **Step 4: typecheck + lint + build**

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/features/admin/orders/OrderImportDialog.tsx frontend/src/features/admin/orders/OrdersPage.tsx frontend/src/api/admin.ts
git commit -m "feat(orders): R13 xlsx 일괄 등록 dialog + group_key 안내"
```

---

## Task 10 — E2E + Runbook + Handoff

**Files:**
- Create: `frontend/e2e/admin-reports-e2e.spec.ts`
- Create: `docs/runbooks/r13-reports-and-import.md`
- Modify: `.master/next_session_plan.md`

- [ ] **Step 1: E2E spec**

```ts
import { expect, test } from '@playwright/test';
import { adminLogin } from './helpers';

test('admin can open reports page and see 4 tabs', async ({ browser }) => {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await adminLogin(page);
  await page.getByTestId('admin-nav-reports').click();
  await expect(page.getByTestId('admin-reports-page')).toBeVisible();
  for (const key of ['revenue', 'partners', 'services', 'settlements']) {
    await expect(page.getByTestId(`reports-tab-${key}`)).toBeVisible();
  }
  await ctx.close();
});

test('admin can switch to partner tab and see table or empty state', async ({ browser }) => {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await adminLogin(page);
  await page.getByTestId('admin-nav-reports').click();
  await page.getByTestId('reports-tab-partners').click();
  // table or empty state — 어느 쪽이든 export 버튼은 보임
  await expect(page.getByTestId('reports-partners-export-csv')).toBeVisible();
  await ctx.close();
});

test('revenue tab shows partner and service filters', async ({ browser }) => {
  // S8: B4 회귀 방어 — 필터 UI가 살아있는지 smoke
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await adminLogin(page);
  await page.getByTestId('admin-nav-reports').click();
  await expect(page.getByTestId('reports-tab-revenue')).toBeVisible();
  await expect(page.getByTestId('reports-revenue-partner-filter')).toBeVisible();
  await expect(page.getByTestId('reports-revenue-service-filter')).toBeVisible();
  await ctx.close();
});

test('admin can open import dialog from orders page', async ({ browser }) => {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await adminLogin(page);
  await page.getByTestId('admin-nav-orders').click();
  await page.getByTestId('admin-orders-import').click();
  await expect(page.getByTestId('order-import-dialog')).toBeVisible();
  await ctx.close();
});
```

- [ ] **Step 2: 운영 runbook**

`docs/runbooks/r13-reports-and-import.md`:

```markdown
# R13 보고서 / 일괄 등록

## 보고서 4 화면
- **매출 추세**: 기간/단위(일/주/월) + 협력사·서비스 필터. 매출은 `고객전달완료 + 서비스완료` 합계 (대시보드와 동일 정의).
- **협력사 성과**: 작업 수 / 평균 단가 / 정산 대기 / 정산 예정액. 취소 주문 제외.
- **서비스 인기**: 서비스별 작업 수 + 매출 점유율.
- **정산 대기**: `서비스완료` 상태 중 `partner_payment_status` 가 `unpaid`/`ready` 또는 NULL. **`고객전달완료`는 정산 대기로 보지 않음** — 운영자가 명시적으로 `서비스완료`로 전환한 시점에서만 정산 대상. 매출은 `고객전달완료 + 서비스완료` 둘 다 잡힘 (D5).

각 화면 우상단의 `CSV` / `Excel` 버튼으로 현재 결과 다운로드.

## 일괄 등록
- 주문관리 우상단 `일괄 등록` 클릭.
- xlsx 컬럼: `group_key`, `customer_name`, `customer_phone`, `customer_address`, `scheduled_date`, `service_name`, `total_amount`.
- 같은 `group_key` 행은 한 그룹의 여러 line으로 묶임 (한 고객의 여러 작업).
- 행별 validate. 한 group 안에 잘못된 line이 있으면 그 group 전체 rollback. 다른 group은 영향 없음.
- 응답: `succeeded_groups`, `succeeded_lines`, `failed: [{row_index, reason}]`.

## 데이터 일관성
- 모든 보고서는 `Order.deleted_at IS NULL` 가드. R8 soft-delete 정책 준수.
- 매출/작업 수가 대시보드와 미세하게 다르면 정의 차이(취소 제외 vs 포함)일 가능성. 정의는 항상 코드 (`DashboardService`, `ReportService`) 가 source of truth.
```

- [ ] **Step 3: handoff 갱신**

`.master/next_session_plan.md` 상단:
```markdown
- `R13 Operational Reporting` 완료
  - 매출/협력사/서비스/정산 4 보고서 + CSV/xlsx export
  - xlsx 일괄 주문 등록 (group_key 묶음) + 행별 부분 성공
  - Python aggregation (DB dialect 무관)
```

다음 권장: R11 Real Message Delivery (SOLAPI 알림톡 실연동).

- [ ] **Step 4: 회귀**

```bash
cd backend && python -m pytest -q
cd frontend && npm run typecheck && npm run lint && npm run build && npm run e2e
```

- [ ] **Step 5: 커밋**

```bash
git add frontend/e2e/admin-reports-e2e.spec.ts docs/runbooks/r13-reports-and-import.md .master/next_session_plan.md
git commit -m "test(e2e)+docs: R13 보고서 E2E + 운영 runbook + 핸드오프"
```

---

## Self-Review

**1. Spec coverage:**

| 로드맵 R13 항목 | Task | v2 변경 |
|---|---|---|
| 매출 추세 (filter 포함) | T2, T3, T4, T8 | partner_id/service_item_id 필터 추가 (S1) |
| 협력사 성과 | T2, T3, T4, T8 | 실제 enum (UNPAID/READY) + `OrderStatus.COMPLETED` 사용 |
| 서비스 인기 | T2, T3, T4, T8 | 매출 정의 통일 (CUSTOMER_DELIVERY_DONE + COMPLETED) |
| 정산 대기 | T2, T3, T4, T8 | `PARTNER_SETTLEMENT_PENDING_STATUSES` 상수 사용 + COMPLETED 상태 |
| CSV/xlsx export | T5, T8 | fetch+blob 다운로드 (Auth 헤더 호환) |
| 대량 import | T6, T9 | group_key 컬럼으로 multi-line 묶음 (R7 호환) |
| 운영 문서 | T10 | 매출 정의 source of truth 명시 |

**2. v3 Codex round 2 review 반영:**

| Codex finding (round 2) | 반영 위치 |
|---|---|
| **B1 group-level rollback** | Task 6 `_parse_row` 실패 + customer 불일치 시 같은 `group_key`의 모든 line을 `failed`로 처리 + `grouped[gk]` pop. `group_skipped_due_to_sibling_error` reason. |
| **B2 import ↔ services 끊김** | Task 3 `services()`에 fallback — `service_item_id IS NULL` 주문도 `service_name` 키로 묶어 집계 (D15). 응답 schema `service_item_id: str | None` |
| **B3 soft-delete 테스트** | Task 4의 `test_revenue_excludes_soft_deleted_orders` — `seed_order.deleted_at = datetime.now(UTC)` set + 매출 0 assert |
| **B4 partner/service 필터 UI** | Task 8 `RevenueView`에 partner/service select + `reports-revenue-partner-filter` / `reports-revenue-service-filter` testid + export params에 반영 (D17) |
| **S1 downloadBlob refresh** | Task 7 `fetchBlobWithRefresh` — 401 시 `refreshWithRotation` 후 1회 재시도 |
| **S2 business_today** | Task 6 import service에 `from app.core.time import business_today` + `today_kst = business_today()` (D16) |
| **S3 정산 정의 명확화** | D7 + runbook에 "고객전달완료는 정산 대기 아님" 명시 |
| **S4 group_key customer 일관성** | Task 6의 grouping 로직에 customer_name/phone/address 불일치 시 `inconsistent_group_customer` |
| **S5 services 테스트 보강** | Task 4 service test에 빈 데이터 / NULL service_item_id fallback 케이스 추가 (codex에 위임 — 명시) |
| **S6 unused imports** | 모든 task 코드 블록의 import 재점검 — codex 구현 시 사용 안 하는 import 제거 |
| **S7 error state** | Task 8 `RevenueView`에 `error` state + `reports-error` testid |
| **S8 react-is exact pin** | Task 1 `overrides.react-is: "19.2.5"` (^ 제거) |
| **N1 AdminShell icon** | `trending` / `fileText`만 사용 (chartUp 제거) |
| **N2 downloadBlob filename** | suggested filename 우선 — backend filename은 ASCII로 같으므로 차이 없음. 명시 |
| **N3 streaming wording** | "메모리 스트리밍" → "메모리 buffer 응답"으로 plan body 수정 가능 (낮은 우선순위) |
| **N4 RevenueReport interface** | `partner_id: string | null` / `service_item_id: string | null` 추가 |
| **N5 import content-type** | service `_XLSX_MEDIA_PREFIXES`에 `application/octet-stream` 포함 + route에서 `.xlsx` 확장자 fallback |

**3. Type consistency:** snake_case 통일. `succeeded_groups`/`succeeded_lines`/`failed` 일관.

**4. 실 호환성:** Python aggregation이라 SQLite 테스트 그대로 통과. Postgres 운영도 동일 코드.

**5. 잠재 위험:**
- 운영 데이터량이 수만 건/월로 커지면 Python aggregation 성능 저하 — R13.5에서 SQL 집계 + dialect 분기로 전환.
- R8.5 hot-patch에서 발견된 calendar.py의 N+1 패턴과 유사한 N+1이 partners/services에도 있을 수 있음 — partner/service dict 한 번에 로드하여 lookup하므로 OK.

---

## Execution Handoff

Codex에게:

```
docs/plans/2026-05-25-r13-operational-reporting.md 를 처음부터 끝까지 정독한 뒤,
Task 1부터 순서대로 진행한다. 각 task의 step은 TDD 순서(실패 테스트 → 구현 →
통과 → 커밋)를 그대로 따른다. 의문 사항은 사용자에게 묻지 말고 D1~D14 결정을 따른다.
계획서에 없는 부수 refactor/rename은 추가하지 마라.
```
