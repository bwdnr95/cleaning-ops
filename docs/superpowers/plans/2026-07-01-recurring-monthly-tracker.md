# 정기청소 월 트래커 재설계 (#4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 정기청소를 회차 주문 생성에서 **계약×월 단위 세금계산서/잔금 토글 트래커**로 전환한다(생성·B 집계 제거, 월 상태 모델·트래커 추가).

**Architecture:** 신규 `RecurringMonthlyStatus`(계약×월, 2 boolean) + `RecurringMonthlyService`(월 조회 시 lazy upsert, 토글 set). 회차 생성(sync/approve/skip)·B(recurring_billing 주문집계)는 코드/라우트/UI 제거. 계약(CRUD·스케줄=주기표시)은 유지. `RecurringOccurrence` 테이블은 비활성 유지(drop 안 함).

**Tech Stack:** FastAPI / SQLAlchemy / Alembic / pytest, React + TS.

**설계 출처:** `docs/superpowers/specs/2026-07-01-recurring-monthly-tracker-design.md`. 브랜치 `feature/recurring-monthly-tracker`(main 분기).

---

## File Structure
- Create: `backend/app/models/recurring_monthly_status.py`, `backend/app/schemas/recurring_monthly.py`, `backend/app/services/recurring_monthly.py`, `backend/app/api/routes/admin/recurring_monthly.py`, `backend/alembic/versions/0018_recurring_monthly_status.py`, `frontend/src/api/recurringMonthly.ts`
- Modify: `backend/app/repositories/recurring.py`(+monthly repo), `backend/app/api/router.py`, `backend/app/services/recurring.py`(remove generation), `backend/app/schemas/recurring.py`(remove occurrence DTOs), `frontend/src/features/admin/recurring/RecurringContractsPage.tsx`(remove 승인 패널, tab), `frontend/src/features/admin/recurring/RecurringBillingView.tsx`→tracker
- Remove: `backend/app/api/routes/admin/recurring_billing.py`, `backend/app/services/recurring_billing.py`, `backend/app/schemas/recurring_billing.py`, `backend/app/domain/recurring_billing.py`, occurrences routes(in recurring.py), `frontend/src/api/recurringBilling.ts`, + 관련 테스트
- Test: `backend/tests/test_recurring_monthly.py`

---

## Task 1: 모델 + 마이그 0018 + 리포

**Files:** Create `backend/app/models/recurring_monthly_status.py`, `backend/alembic/versions/0018_recurring_monthly_status.py`; Modify `backend/app/repositories/recurring.py`, `backend/app/models/__init__.py`; Test `backend/tests/test_recurring_monthly.py`

- [ ] **Step 1: 실패 테스트** — `backend/tests/test_recurring_monthly.py`

```python
from datetime import date
from uuid import uuid4

from app.domain.constants import RecurrenceMode, RecurringContractStatus
from app.models.order_group import OrderGroup
from app.models.recurring_contract import RecurringContract
from app.models.recurring_monthly_status import RecurringMonthlyStatus
from app.repositories.recurring import RecurringMonthlyStatusRepository


def _contract(db):
    g = OrderGroup(id=str(uuid4()), customer_token=f"t-{uuid4()}", customer_name="강남",
                   customer_phone="01011112222", customer_address="A", customer_visible_payment=False)
    db.add(g); db.flush()
    c = RecurringContract(id=str(uuid4()), label="L", order_group_id=g.id,
                          recurrence_mode=RecurrenceMode.MONTHLY, day_of_month=10, start_date=date(2026, 6, 10),
                          status=RecurringContractStatus.ACTIVE, service_name="청소", total_amount=150000)
    db.add(c); db.flush()
    return c


def test_monthly_status_persists_and_lookup(db_session):
    repo = RecurringMonthlyStatusRepository(db_session)
    c = _contract(db_session)
    repo.add(RecurringMonthlyStatus(id=str(uuid4()), contract_id=c.id, billing_month="2026-06"))
    db_session.flush()
    found = repo.get_by_contract_and_month(c.id, "2026-06")
    assert found is not None and found.tax_invoice_issued is False and found.balance_paid is False
    assert repo.get_by_contract_and_month(c.id, "2026-07") is None
```

- [ ] **Step 2: 실패 확인** — Run `cd backend && python -m pytest tests/test_recurring_monthly.py -q` → FAIL(모듈 없음).

- [ ] **Step 3: 모델** — `backend/app/models/recurring_monthly_status.py`

```python
from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class RecurringMonthlyStatus(TimestampMixin, Base):
    __tablename__ = "recurring_monthly_status"
    __table_args__ = (
        UniqueConstraint("contract_id", "billing_month", name="uq_recurring_monthly_contract_month"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    contract_id: Mapped[str] = mapped_column(ForeignKey("recurring_contracts.id"), index=True)
    billing_month: Mapped[str] = mapped_column(String(7), index=True)  # "YYYY-MM"
    tax_invoice_issued: Mapped[bool] = mapped_column(Boolean, default=False)
    balance_paid: Mapped[bool] = mapped_column(Boolean, default=False)
```

`backend/app/models/__init__.py`에 import + `__all__` 추가:
```python
from app.models.recurring_monthly_status import RecurringMonthlyStatus
```

- [ ] **Step 4: 마이그** — `backend/alembic/versions/0018_recurring_monthly_status.py`

```python
"""정기청소 월 트래커 — recurring_monthly_status

Revision ID: 0018_recurring_monthly_status
Revises: 0017_recurring_weekdays
Create Date: 2026-07-01
"""

from alembic import op
import sqlalchemy as sa

revision = "0018_recurring_monthly_status"
down_revision = "0017_recurring_weekdays"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recurring_monthly_status",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("contract_id", sa.String(length=36), nullable=False),
        sa.Column("billing_month", sa.String(length=7), nullable=False),
        sa.Column("tax_invoice_issued", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("balance_paid", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["contract_id"], ["recurring_contracts.id"], name="fk_recurring_monthly_status_contract_id_recurring_contracts"),
        sa.PrimaryKeyConstraint("id", name="pk_recurring_monthly_status"),
        sa.UniqueConstraint("contract_id", "billing_month", name="uq_recurring_monthly_contract_month"),
    )
    op.create_index("ix_recurring_monthly_status_contract_id", "recurring_monthly_status", ["contract_id"])
    op.create_index("ix_recurring_monthly_status_billing_month", "recurring_monthly_status", ["billing_month"])


def downgrade() -> None:
    op.drop_table("recurring_monthly_status")
```

- [ ] **Step 5: 리포** — `backend/app/repositories/recurring.py`에 추가

```python
from app.models.recurring_monthly_status import RecurringMonthlyStatus


class RecurringMonthlyStatusRepository(Repository[RecurringMonthlyStatus]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, RecurringMonthlyStatus)

    def get_by_contract_and_month(self, contract_id: str, billing_month: str) -> RecurringMonthlyStatus | None:
        stmt = select(RecurringMonthlyStatus).where(
            RecurringMonthlyStatus.contract_id == contract_id,
            RecurringMonthlyStatus.billing_month == billing_month,
        )
        return self.db.scalar(stmt)

    def list_by_month(self, billing_month: str) -> list[RecurringMonthlyStatus]:
        stmt = select(RecurringMonthlyStatus).where(RecurringMonthlyStatus.billing_month == billing_month)
        return list(self.db.scalars(stmt))
```

- [ ] **Step 6: 통과 + 렌더** — Run `cd backend && python -m pytest tests/test_recurring_monthly.py -q && python -m alembic upgrade 0017_recurring_weekdays:0018_recurring_monthly_status --sql 2>&1 | tail -5` → PASS + CREATE TABLE 렌더.

- [ ] **Step 7: 커밋**
```bash
git add backend/app/models/recurring_monthly_status.py backend/app/models/__init__.py backend/alembic/versions/0018_recurring_monthly_status.py backend/app/repositories/recurring.py backend/tests/test_recurring_monthly.py
git commit -m "feat(recurring): RecurringMonthlyStatus 모델+마이그0018+리포"
```

---

## Task 2: 스키마 + RecurringMonthlyService

**Files:** Create `backend/app/schemas/recurring_monthly.py`, `backend/app/services/recurring_monthly.py`; Test: `test_recurring_monthly.py`(추가)

- [ ] **Step 1: 실패 테스트 추가** — `backend/tests/test_recurring_monthly.py`

```python
from app.services.recurring_monthly import RecurringMonthlyService


def test_list_month_upserts_active_contracts_idempotently(db_session):
    c = _contract(db_session)  # start 2026-06-10, ACTIVE
    db_session.commit()
    svc = RecurringMonthlyService(db_session)
    rows1 = svc.list_month("2026-06")
    assert any(r.contract_id == c.id and r.amount == 150000 for r in rows1)
    n_before = len(RecurringMonthlyStatusRepository(db_session).list_by_month("2026-06"))
    svc.list_month("2026-06")  # 멱등
    assert len(RecurringMonthlyStatusRepository(db_session).list_by_month("2026-06")) == n_before


def test_list_month_excludes_before_start(db_session):
    c = _contract(db_session)  # start 2026-06
    db_session.commit()
    rows = RecurringMonthlyService(db_session).list_month("2026-05")
    assert all(r.contract_id != c.id for r in rows)  # 시작 전 달 제외


def test_set_status_toggles(db_session):
    c = _contract(db_session)
    db_session.commit()
    svc = RecurringMonthlyService(db_session)
    row = svc.set_status(c.id, "2026-06", tax_invoice_issued=True, actor_user_id="admin")
    assert row.tax_invoice_issued is True and row.balance_paid is False
    row2 = svc.set_status(c.id, "2026-06", balance_paid=True, actor_user_id="admin")
    assert row2.tax_invoice_issued is True and row2.balance_paid is True
```

- [ ] **Step 2: 실패 확인** — Run `cd backend && python -m pytest tests/test_recurring_monthly.py -k "list_month or set_status" -q` → FAIL.

- [ ] **Step 3: 스키마** — `backend/app/schemas/recurring_monthly.py`

```python
from pydantic import Field

from app.schemas.common import ApiModel


class RecurringMonthlyRowRead(ApiModel):
    contract_id: str
    label: str
    customer_name: str
    schedule_text: str
    month: str
    amount: float | None = None
    tax_invoice_issued: bool
    balance_paid: bool


class SetMonthlyStatusRequest(ApiModel):
    contract_id: str
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    tax_invoice_issued: bool | None = None
    balance_paid: bool | None = None
```

- [ ] **Step 4: 서비스** — `backend/app/services/recurring_monthly.py`

```python
from __future__ import annotations

from calendar import monthrange
from datetime import date
from uuid import uuid4

from sqlalchemy.orm import Session

from app.domain.constants import RecurringContractStatus
from app.models.recurring_contract import RecurringContract
from app.models.recurring_monthly_status import RecurringMonthlyStatus
from app.repositories.order_groups import OrderGroupRepository
from app.repositories.recurring import RecurringContractRepository, RecurringMonthlyStatusRepository
from app.schemas.recurring_monthly import RecurringMonthlyRowRead
from app.services.recurring import RecurringService


def _month_bounds(month: str) -> tuple[date, date]:
    year, mon = int(month[:4]), int(month[5:7])
    return date(year, mon, 1), date(year, mon, monthrange(year, mon)[1])


class RecurringMonthlyService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.statuses = RecurringMonthlyStatusRepository(db)
        self.contracts = RecurringContractRepository(db)
        self.groups = OrderGroupRepository(db)
        self._recurring = RecurringService(db)  # _schedule_text 재사용

    def _active_in_month(self, contract: RecurringContract, first: date, last: date) -> bool:
        if contract.start_date > last:
            return False
        if contract.end_date is not None and contract.end_date < first:
            return False
        return True

    def list_month(self, month: str) -> list[RecurringMonthlyRowRead]:
        first, last = _month_bounds(month)
        created = False
        rows: list[RecurringMonthlyRowRead] = []
        for contract in self.contracts.list_active():
            if not self._active_in_month(contract, first, last):
                continue
            status = self.statuses.get_by_contract_and_month(contract.id, month)
            if status is None:
                status = RecurringMonthlyStatus(id=str(uuid4()), contract_id=contract.id, billing_month=month)
                self.statuses.add(status)
                created = True
            group = self.groups.get(contract.order_group_id)
            rows.append(
                RecurringMonthlyRowRead(
                    contract_id=contract.id, label=contract.label,
                    customer_name=group.customer_name if group else "",
                    schedule_text=self._recurring._schedule_text(contract), month=month,
                    amount=float(contract.total_amount) if contract.total_amount is not None else None,
                    tax_invoice_issued=status.tax_invoice_issued, balance_paid=status.balance_paid,
                )
            )
        if created:
            self.db.commit()
        rows.sort(key=lambda r: r.label)
        return rows

    def set_status(
        self, contract_id: str, month: str, *,
        tax_invoice_issued: bool | None = None, balance_paid: bool | None = None,
        actor_user_id: str | None,
    ) -> RecurringMonthlyRowRead:
        contract = self.contracts.get(contract_id)
        if contract is None:
            raise ValueError("recurring_contract_not_found")
        status = self.statuses.get_by_contract_and_month(contract_id, month)
        if status is None:
            status = RecurringMonthlyStatus(id=str(uuid4()), contract_id=contract_id, billing_month=month)
            self.statuses.add(status)
        if tax_invoice_issued is not None:
            status.tax_invoice_issued = tax_invoice_issued
        if balance_paid is not None:
            status.balance_paid = balance_paid
        self.db.commit()
        group = self.groups.get(contract.order_group_id)
        return RecurringMonthlyRowRead(
            contract_id=contract.id, label=contract.label,
            customer_name=group.customer_name if group else "",
            schedule_text=self._recurring._schedule_text(contract), month=month,
            amount=float(contract.total_amount) if contract.total_amount is not None else None,
            tax_invoice_issued=status.tax_invoice_issued, balance_paid=status.balance_paid,
        )
```

- [ ] **Step 5: 통과** — Run `cd backend && python -m pytest tests/test_recurring_monthly.py -q` → PASS.

- [ ] **Step 6: 커밋**
```bash
git add backend/app/schemas/recurring_monthly.py backend/app/services/recurring_monthly.py backend/tests/test_recurring_monthly.py
git commit -m "feat(recurring): 월 트래커 서비스(월 lazy upsert + 토글)"
```

---

## Task 3: 라우트 + 등록

**Files:** Create `backend/app/api/routes/admin/recurring_monthly.py`; Modify `backend/app/api/router.py`; Test `test_recurring_monthly.py`(API)

- [ ] **Step 1: 실패 테스트 추가**
```python
def test_monthly_api_requires_admin(client):
    assert client.get("/api/admin/recurring/monthly?month=2026-06").status_code == 401


def test_monthly_api_list_and_set(client, seed_admin_token):
    h = {"Authorization": f"Bearer {seed_admin_token}"}
    body = {"label": "강남", "customer_name": "강남", "customer_phone": "01011112222",
            "customer_address": "A", "recurrence_mode": "monthly", "day_of_month": 10,
            "start_date": "2020-01-10", "service_name": "청소", "total_amount": 100000}
    cid = client.post("/api/admin/recurring/contracts", json=body, headers=h).json()["id"]
    lst = client.get("/api/admin/recurring/monthly?month=2026-06", headers=h)
    assert lst.status_code == 200 and any(r["contract_id"] == cid for r in lst.json())
    res = client.post("/api/admin/recurring/monthly/set",
                      json={"contract_id": cid, "month": "2026-06", "tax_invoice_issued": True}, headers=h)
    assert res.status_code == 200 and res.json()["tax_invoice_issued"] is True
```

- [ ] **Step 2: 실패 확인** — 404.

- [ ] **Step 3: 라우트** — `backend/app/api/routes/admin/recurring_monthly.py`
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_session, require_admin
from app.schemas.recurring_monthly import RecurringMonthlyRowRead, SetMonthlyStatusRequest
from app.services.recurring_monthly import RecurringMonthlyService

router = APIRouter()


@router.get("", response_model=list[RecurringMonthlyRowRead])
def list_monthly(month: str, db: Session = Depends(get_session), _: CurrentUser = Depends(require_admin)):
    return RecurringMonthlyService(db).list_month(month)


@router.post("/set", response_model=RecurringMonthlyRowRead)
def set_monthly(payload: SetMonthlyStatusRequest, db: Session = Depends(get_session), user: CurrentUser = Depends(require_admin)):
    try:
        return RecurringMonthlyService(db).set_status(
            payload.contract_id, payload.month,
            tax_invoice_issued=payload.tax_invoice_issued, balance_paid=payload.balance_paid,
            actor_user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404 if str(exc).endswith("_not_found") else 400, detail=str(exc)) from exc
```

- [ ] **Step 4: 등록** — `backend/app/api/router.py`: import `recurring_monthly`, 등록 `api_router.include_router(recurring_monthly.router, prefix="/admin/recurring/monthly", tags=["admin-recurring-monthly"])`.

- [ ] **Step 5: 통과** — Run `cd backend && python -m pytest tests/test_recurring_monthly.py -q` → PASS.

- [ ] **Step 6: 커밋**
```bash
git add backend/app/api/routes/admin/recurring_monthly.py backend/app/api/router.py backend/tests/test_recurring_monthly.py
git commit -m "feat(recurring): 월 트래커 admin 라우트"
```

---

## Task 4: 회차생성·B 제거 (백엔드)

**Files:** Modify `services/recurring.py`, `schemas/recurring.py`, `api/routes/admin/recurring.py`, `api/router.py`, `repositories/recurring.py`, `repositories/orders.py`; Remove `services/recurring_billing.py`, `schemas/recurring_billing.py`, `domain/recurring_billing.py`, `api/routes/admin/recurring_billing.py` + 관련 테스트

- [ ] **Step 1: occurrences 라우트 제거** — `api/routes/admin/recurring.py`에서 `/occurrences/sync`·`/pending`·`/approve`·`/skip` 4개 엔드포인트 삭제(계약 CRUD/pause/resume/end/delete 유지). 미사용 import 정리.

- [ ] **Step 2: RecurringService 생성 메서드 제거** — `services/recurring.py`에서 `sync_due_occurrences`·`list_pending`·`list_pending_views`·`approve_occurrences`·`skip_occurrences` + 그들만 쓰는 import(ApproveItem 등) 제거. **유지**: 계약 CRUD·라이프사이클·`to_contract_read`·`list_contract_summaries`(pending_count/this_month_* 필드 제거)·`_spec`·`_next_due`·`_schedule_text`. `RecurringContractSummaryRead`에서 `pending_count`/`this_month_count`/`this_month_amount` 제거(스키마·매핑 동시).

- [ ] **Step 3: occurrence/approve DTO 제거** — `schemas/recurring.py`에서 `PendingOccurrenceRead`·`ApproveItem`·`ApproveOccurrencesRequest`·`ApproveOccurrencesResult`·`SkipItem`·`SkipOccurrencesRequest`·`SkipOccurrencesResult`·`RecurringOccurrenceRead` 제거.

- [ ] **Step 4: B(recurring_billing) 제거** — 파일 삭제: `api/routes/admin/recurring_billing.py`·`services/recurring_billing.py`·`schemas/recurring_billing.py`·`domain/recurring_billing.py`. `api/router.py`에서 `recurring_billing` import·등록 제거. `repositories/orders.py`의 `list_recurring_billing_orders`·`list_recurring_orders_in_month`(B/요약 전용, 이제 미사용) 제거. `RecurringOccurrenceRepository`는 미사용이면 제거(모델/테이블은 유지).

- [ ] **Step 5: 테스트 정리** — 삭제: `test_recurring_billing_*`(repo/aggregate/service/api), generation 의존 테스트(`test_recurring_service.py`의 sync/approve/skip 테스트, `test_recurring_api.py`의 occurrences/sync/approve 테스트, `test_recurring_repos.py`의 occurrence 테스트, `test_recurring_order_service.py`의 add_recurring_line 관련). **유지**: 계약 CRUD/라이프사이클/스케줄/다중요일/스키마(create 검증). e2e `recurring.spec.ts`·`recurring-billing.spec.ts`는 승인/집계 의존부 제거 또는 삭제(트래커 e2e는 Task 7).
  - 미사용 import·참조가 남지 않게: `grep -rn "recurring_billing\|sync_due_occurrences\|approve_occurrences\|list_recurring_billing_orders\|PendingOccurrence" backend/app backend/tests` 결과 0 확인.

- [ ] **Step 6: 통과 확인** — Run `cd backend && python -m pytest -q` → 전부 PASS(제거 후 회귀 없음). `python -m compileall app tests` → exit 0.

- [ ] **Step 7: 커밋**
```bash
git add -A backend
git commit -m "refactor(recurring): 회차 생성(sync/approve/skip)·B(주문집계) 제거 — 월 트래커로 일원화"
```

---

## Task 5: 백엔드 전체 검증 + Postgres 0018

- [ ] **Step 1: 전체** — Run `cd backend && python -m pytest -q` → PASS. `python -m compileall app tests` → 0.
- [ ] **Step 2: Postgres** — Run `cd backend && DATABASE_URL="postgresql+psycopg2://cleanops:cleanops_local_dev@localhost:5434/cleaning_ops" python -m alembic upgrade head` → 그 후 같은 URL `alembic current` = `0018_recurring_monthly_status (head)`.

---

## Task 6: 프론트 — 승인패널 제거 + 월 트래커

**Files:** Create `frontend/src/api/recurringMonthly.ts`; Modify `RecurringContractsPage.tsx`, `RecurringBillingView.tsx`(→tracker); Remove `frontend/src/api/recurringBilling.ts`

- [ ] **Step 1: API** — `frontend/src/api/recurringMonthly.ts`
```ts
import { apiRequest } from './client';

export interface RecurringMonthlyRow {
  contract_id: string; label: string; customer_name: string; schedule_text: string;
  month: string; amount: number | null; tax_invoice_issued: boolean; balance_paid: boolean;
}
export function getRecurringMonthly(month: string): Promise<RecurringMonthlyRow[]> {
  return apiRequest(`/admin/recurring/monthly?month=${encodeURIComponent(month)}`) as Promise<RecurringMonthlyRow[]>;
}
export function setRecurringMonthlyStatus(
  contractId: string, month: string, patch: { tax_invoice_issued?: boolean; balance_paid?: boolean },
): Promise<RecurringMonthlyRow> {
  return apiRequest('/admin/recurring/monthly/set', {
    method: 'POST', body: { contract_id: contractId, month, ...patch },
  }) as Promise<RecurringMonthlyRow>;
}
```

- [ ] **Step 2: 월 트래커 뷰** — `RecurringBillingView.tsx`를 월 트래커로 교체(또는 `RecurringMonthlyTracker.tsx` 신규 후 import 교체). 월 피커(기본 이번 달) + 행: 계약명/고객/주기(schedule_text)/월 금액/세금계산서(체크박스)/잔금입금(체크박스). 체크박스 onChange → `setRecurringMonthlyStatus(...)` 후 재조회. 로딩/에러/빈 3종.
```jsx
import React from 'react';
import { getRecurringMonthly, setRecurringMonthlyStatus, type RecurringMonthlyRow } from '../../../api/recurringMonthly';
import { formatAmount } from '../../../domain/recurrence';

function thisMonth(): string { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`; }

export function RecurringMonthlyTracker() {
  const [month, setMonth] = React.useState(thisMonth());
  const [rows, setRows] = React.useState<RecurringMonthlyRow[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const load = React.useCallback(async () => {
    setError(null);
    try { setRows(await getRecurringMonthly(month)); }
    catch (e) { setError(e instanceof Error ? e.message : '불러오기 실패'); setRows([]); }
  }, [month]);
  React.useEffect(() => { void load(); }, [load]);

  const toggle = async (r: RecurringMonthlyRow, field: 'tax_invoice_issued' | 'balance_paid') => {
    try { await setRecurringMonthlyStatus(r.contract_id, month, { [field]: !r[field] }); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : '처리 실패'); }
  };

  return (
    <div style={{ padding: 16 }}>
      <input type="month" value={month} onChange={(e) => setMonth(e.target.value)}
        style={{ fontSize: 16, padding: '6px 8px', marginBottom: 12 }} data-testid="monthly-month" />
      {error && <div role="alert" style={{ color: 'var(--danger-fg,#c0392b)', marginBottom: 8 }}>{error}</div>}
      {rows === null ? <div>불러오는 중…</div> : rows.length === 0 ? (
        <div style={{ color: 'var(--text-tertiary)' }}>이 달 활성 정기계약이 없습니다.</div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
            <thead><tr style={{ textAlign: 'left', color: 'var(--text-tertiary)' }}>
              <th>계약</th><th>고객</th><th>주기</th><th>월 금액</th><th>세금계산서</th><th>잔금입금</th>
            </tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.contract_id} data-testid={`monthly-row-${r.contract_id}`}>
                  <td>{r.label}</td><td>{r.customer_name}</td><td>{r.schedule_text}</td>
                  <td>{formatAmount(r.amount)}</td>
                  <td><input type="checkbox" checked={r.tax_invoice_issued} data-testid={`monthly-tax-${r.contract_id}`}
                    onChange={() => void toggle(r, 'tax_invoice_issued')} /></td>
                  <td><input type="checkbox" checked={r.balance_paid} data-testid={`monthly-paid-${r.contract_id}`}
                    onChange={() => void toggle(r, 'balance_paid')} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```
> `RecurringContractsPage`의 탭 import를 `RecurringBillingView`→`RecurringMonthlyTracker`로 교체, 탭 라벨 '월 정산'→'월 트래커', testid 유지/조정. 기존 `RecurringBillingView` 파일은 신규 컴포넌트로 대체(또는 삭제 후 신규).

- [ ] **Step 3: 승인 패널 제거** — `RecurringContractsPage.tsx`: '승인 대기 회차' 패널·`sync`/`approve`/`skip` 호출·관련 state 제거. 계약 목록·등록/상세 유지. `api/recurring.ts`에서 occurrences(sync/pending/approve/skip) 호출 + `api/recurringBilling.ts` 제거(파일 삭제). 미사용 import 정리.

- [ ] **Step 4: 검증** — Run `cd frontend && npm run typecheck && npm run lint && npm run build` → green. (`grep -rn "recurringBilling\|occurrences/approve\|승인 대기" frontend/src` 0 확인.)

- [ ] **Step 5: 커밋**
```bash
git add -A frontend
git commit -m "feat(recurring): 정기청소 화면을 월 트래커로 전환(승인패널·B 제거)"
```

---

## Task 7: 최종 검증 (+ e2e 선택)
- [ ] **Step 1: 백엔드** — `cd backend && python -m pytest -q` PASS + compileall.
- [ ] **Step 2: 프론트** — `cd frontend && npm run typecheck && npm run lint && npm run build` green.
- [ ] **Step 3: (선택) e2e** — 월 트래커 진입·토글 스모크(`monthly-month`·`monthly-tax-*`). 인프라 불안정하면 보고.

---

## Self-Review
**1. Spec coverage:** §1 모델→T1, §2 서비스→T2, §3 라우트→T3, §4 제거→T4, §5 프론트→T6, §6 테스트→각 T+T7, §7 마이그→T1·T5. ✅
**2. Placeholder scan:** 신규 코드 완전. 제거(T4)는 파일·심볼·grep 0 확인 지시(공백 아님).
**3. Type consistency:** `RecurringMonthlyRowRead`(T2) = 서비스 반환 = 라우트 response = 프론트 `RecurringMonthlyRow`(T6) 일치 ✅. `RecurringMonthlyStatusRepository`(T1) = 서비스 사용(T2) ✅. `_schedule_text` 재사용(유지) ✅.
**주의:** T4 제거 시 grep로 잔여 참조 0 확인 후 커밋(suite 그린 유지). main 분기 `feature/recurring-monthly-tracker`, 완료 후 main 머지 + Postgres 0018 적용.
