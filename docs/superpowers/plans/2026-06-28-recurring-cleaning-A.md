# 정기청소 서브시스템 A (정기계약 + 회차 자동생성) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 정기청소 계약을 등록하면 주기에 맞춰 도래한 회차를 운영자가 일괄 승인해 주문관리에 1주기 금액의 주문 라인이 생성되는 기능(서브시스템 A)을 구현한다.

**Architecture:** `RecurringContract`(공유 OrderGroup + 스케줄 + 회차 템플릿)와 `RecurringOccurrence`(PENDING/GENERATED/SKIPPED 원장)를 신설한다. 스케줄러 없이 운영자가 화면을 열 때 `sync`가 도래분을 계산·upsert하고, 승인 시 기존 `OrderService` 경로로 계약 그룹에 라인을 추가한다. 서브시스템 B(월 합산 청구·정산)는 범위 밖이며 `Order.recurring_contract_id`·`RecurringOccurrence.billing_month` 연결고리만 심는다.

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy 2.0 / Alembic / Pydantic / pytest (backend), Vite + React 19 + TS / plain CSS tokens / Playwright (frontend).

**설계 출처:** `docs/superpowers/specs/2026-06-28-recurring-cleaning-A-design.md`. 작업 브랜치: `feature/recurring-cleaning`.

**전제 규칙(준수):** `AGENTS.md`(역할 DTO 화이트리스트, 협력사/고객 민감필드 차단, soft-delete, 타임라인) · `.claude/rules/backend.md`(repo `__init__(self, db)`+`self.db`, repo commit 금지, SQLAlchemy 2.0 select/where, KST `business_today()`) · `.claude/rules/frontend.md`(768px, 로딩/에러/빈 3종, `apiRequest` 사용).

---

## File Structure

**Backend (create):**
- `backend/app/models/recurring_contract.py` — `RecurringContract` ORM
- `backend/app/models/recurring_occurrence.py` — `RecurringOccurrence` ORM
- `backend/app/domain/recurrence.py` — 순수 스케줄 계산 + 상수(HORIZON_DAYS 등)
- `backend/app/repositories/recurring.py` — 두 리포지토리
- `backend/app/services/recurring.py` — `RecurringService`
- `backend/app/schemas/recurring.py` — 역할별 DTO
- `backend/app/api/routes/admin/recurring.py` — admin 라우트
- `backend/alembic/versions/0015_recurring_contracts.py` — 마이그레이션
- `backend/tests/test_recurrence_schedule.py`, `backend/tests/test_recurring_service.py`, `backend/tests/test_recurring_api.py`

**Backend (modify):**
- `backend/app/domain/constants.py` — enum 3종 추가
- `backend/app/models/order.py` — `recurring_contract_id` 컬럼
- `backend/app/models/__init__.py` — 신규 모델 export
- `backend/app/services/orders.py` — 빈 그룹 생성 + 정기 라인 생성 메서드, `to_admin_order_dto`에 `recurring_contract_id`
- `backend/app/schemas/order.py` — `AdminOrderRead`에 `recurring_contract_id`
- `backend/app/api/router.py` — recurring 라우터 등록

**Frontend (create):**
- `frontend/src/api/recurring.ts` — API 호출 + 타입
- `frontend/src/domain/recurrence.ts` — 라벨/배지/스케줄 포맷
- `frontend/src/features/admin/recurring/RecurringContractsPage.tsx` — 목록 + 승인 대기 패널
- `frontend/src/features/admin/recurring/RecurringContractForm.tsx` — 생성/수정
- `frontend/src/features/admin/recurring/RecurringContractDetail.tsx` — 상세
- `frontend/e2e/recurring.spec.ts` — E2E

**Frontend (modify):**
- `frontend/src/components/layout/AdminShell.tsx` — `NAV`에 정기청소 탭
- `frontend/src/app/App.tsx` — 페이지 라우팅
- 주문 상세/목록 — '정기' 배지

---

## Task 1: 스케줄 도메인 (enum + 순수 계산)

**Files:**
- Modify: `backend/app/domain/constants.py`
- Create: `backend/app/domain/recurrence.py`
- Test: `backend/tests/test_recurrence_schedule.py`

- [ ] **Step 1: enum 3종 추가** — `backend/app/domain/constants.py`의 기존 enum들 사이(예: `VatType` 아래)에 추가.

```python
class RecurrenceMode(StrEnum):
    MONTHLY = "monthly"   # 매월 지정일
    WEEKLY = "weekly"     # N주 간격, start_date 요일 기준


class RecurringContractStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"


class RecurringOccurrenceStatus(StrEnum):
    PENDING = "pending"
    GENERATED = "generated"
    SKIPPED = "skipped"
```

- [ ] **Step 2: 실패 테스트 작성** — `backend/tests/test_recurrence_schedule.py`

```python
from datetime import date

from app.domain.constants import RecurrenceMode
from app.domain.recurrence import ScheduleSpec, billing_month_of, iter_due_dates


def _dates(spec, until):
    return [d for _, d in iter_due_dates(spec, until=until)]


def test_monthly_basic_lists_each_month_on_day():
    spec = ScheduleSpec(mode=RecurrenceMode.MONTHLY, start_date=date(2026, 6, 10), day_of_month=10)
    assert _dates(spec, until=date(2026, 8, 31)) == [date(2026, 6, 10), date(2026, 7, 10), date(2026, 8, 10)]


def test_monthly_clamps_day_to_month_end():
    spec = ScheduleSpec(mode=RecurrenceMode.MONTHLY, start_date=date(2026, 1, 31), day_of_month=31)
    assert _dates(spec, until=date(2026, 3, 31)) == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)]


def test_monthly_skips_first_month_when_day_already_passed():
    spec = ScheduleSpec(mode=RecurrenceMode.MONTHLY, start_date=date(2026, 6, 20), day_of_month=10)
    assert _dates(spec, until=date(2026, 8, 31)) == [date(2026, 7, 10), date(2026, 8, 10)]


def test_weekly_biweekly_steps_from_start_keeping_weekday():
    spec = ScheduleSpec(mode=RecurrenceMode.WEEKLY, start_date=date(2026, 6, 2), interval_weeks=2, weekday=1)
    out = _dates(spec, until=date(2026, 7, 1))
    assert out == [date(2026, 6, 2), date(2026, 6, 16), date(2026, 6, 30)]
    assert all(d.weekday() == 1 for d in out)


def test_max_occurrences_stops_enumeration():
    spec = ScheduleSpec(
        mode=RecurrenceMode.MONTHLY, start_date=date(2026, 6, 10), day_of_month=10, max_occurrences=2
    )
    assert _dates(spec, until=date(2027, 1, 1)) == [date(2026, 6, 10), date(2026, 7, 10)]


def test_end_date_stops_enumeration():
    spec = ScheduleSpec(
        mode=RecurrenceMode.MONTHLY, start_date=date(2026, 6, 10), day_of_month=10, end_date=date(2026, 7, 31)
    )
    assert _dates(spec, until=date(2027, 1, 1)) == [date(2026, 6, 10), date(2026, 7, 10)]


def test_until_horizon_excludes_future_beyond():
    spec = ScheduleSpec(mode=RecurrenceMode.MONTHLY, start_date=date(2026, 6, 10), day_of_month=10)
    assert _dates(spec, until=date(2026, 6, 30)) == [date(2026, 6, 10)]


def test_billing_month_of_formats_year_month():
    assert billing_month_of(date(2026, 6, 10)) == "2026-06"
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `cd backend && python -m pytest tests/test_recurrence_schedule.py -q`
Expected: FAIL — `ModuleNotFoundError: app.domain.recurrence`.

- [ ] **Step 4: 구현** — `backend/app/domain/recurrence.py`

```python
from __future__ import annotations

from calendar import monthrange
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta

from app.domain.constants import RecurrenceMode

# 화면 열 때 "오늘 + HORIZON_DAYS"까지의 도래분을 제안한다.
HORIZON_DAYS = 14
# 과거 미생성분은 "오늘 - OVERDUE_GRACE_DAYS"까지만 노출(먼 과거 start_date 폭주 방지).
OVERDUE_GRACE_DAYS = 30


@dataclass(frozen=True)
class ScheduleSpec:
    mode: str
    start_date: date
    day_of_month: int | None = None
    interval_weeks: int | None = None
    weekday: int | None = None
    end_date: date | None = None
    max_occurrences: int | None = None


def billing_month_of(due: date) -> str:
    return f"{due.year:04d}-{due.month:02d}"


def _clamp_day(year: int, month: int, day: int) -> date:
    last_day = monthrange(year, month)[1]
    return date(year, month, min(day, last_day))


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def iter_due_dates(spec: ScheduleSpec, *, until: date) -> Iterator[tuple[int, date]]:
    """start_date부터 until(포함)까지의 (sequence_no, due_date)를 오름차순 산출.

    sequence_no는 계약 내 회차 순번(1부터). end_date/max_occurrences는 종료 조건.
    """
    seq = 0
    if spec.mode == RecurrenceMode.MONTHLY:
        if spec.day_of_month is None:
            raise ValueError("day_of_month_required_for_monthly")
        year, month = spec.start_date.year, spec.start_date.month
        while True:
            due = _clamp_day(year, month, spec.day_of_month)
            if due >= spec.start_date:
                if due > until:
                    return
                if spec.end_date is not None and due > spec.end_date:
                    return
                seq += 1
                if spec.max_occurrences is not None and seq > spec.max_occurrences:
                    return
                yield seq, due
            year, month = _next_month(year, month)
    elif spec.mode == RecurrenceMode.WEEKLY:
        if not spec.interval_weeks:
            raise ValueError("interval_weeks_required_for_weekly")
        step = timedelta(weeks=spec.interval_weeks)
        due = spec.start_date
        while True:
            if due > until:
                return
            if spec.end_date is not None and due > spec.end_date:
                return
            seq += 1
            if spec.max_occurrences is not None and seq > spec.max_occurrences:
                return
            yield seq, due
            due = due + step
    else:
        raise ValueError(f"unknown_recurrence_mode:{spec.mode}")
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd backend && python -m pytest tests/test_recurrence_schedule.py -q`
Expected: PASS (8 passed).

- [ ] **Step 6: 커밋**

```bash
git add backend/app/domain/constants.py backend/app/domain/recurrence.py backend/tests/test_recurrence_schedule.py
git commit -m "feat(recurring): 정기청소 스케줄 enum + 순수 계산(iter_due_dates) 추가"
```

---

## Task 2: 모델 (RecurringContract / RecurringOccurrence / Order 컬럼)

**Files:**
- Create: `backend/app/models/recurring_contract.py`, `backend/app/models/recurring_occurrence.py`
- Modify: `backend/app/models/order.py`, `backend/app/models/__init__.py`
- Test: `backend/tests/test_recurring_models.py`

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_recurring_models.py`

```python
from datetime import date
from uuid import uuid4

from app.domain.constants import RecurrenceMode, RecurringContractStatus, RecurringOccurrenceStatus
from app.models.order_group import OrderGroup
from app.models.recurring_contract import RecurringContract
from app.models.recurring_occurrence import RecurringOccurrence


def test_models_persist_and_relate(db_session):
    group = OrderGroup(
        id=str(uuid4()), customer_token=f"tok-{uuid4()}", customer_name="강남빌딩",
        customer_phone="01011112222", customer_address="서울 강남구 1", customer_visible_payment=False,
    )
    db_session.add(group)
    db_session.flush()

    contract = RecurringContract(
        id=str(uuid4()), label="강남빌딩 정기청소", order_group_id=group.id,
        recurrence_mode=RecurrenceMode.MONTHLY, day_of_month=10, start_date=date(2026, 6, 10),
        status=RecurringContractStatus.ACTIVE, service_name="사무실 정기청소", total_amount=150000,
    )
    db_session.add(contract)
    db_session.flush()

    occ = RecurringOccurrence(
        id=str(uuid4()), contract_id=contract.id, sequence_no=1, due_date=date(2026, 6, 10),
        billing_month="2026-06", status=RecurringOccurrenceStatus.PENDING,
    )
    db_session.add(occ)
    db_session.flush()

    assert contract.deleted_at is None
    assert occ.contract_id == contract.id
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && python -m pytest tests/test_recurring_models.py -q`
Expected: FAIL — `ModuleNotFoundError: app.models.recurring_contract`.

- [ ] **Step 3: `RecurringContract` 구현** — `backend/app/models/recurring_contract.py`

```python
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.constants import RecurringContractStatus
from app.models.base import Base, TimestampMixin


class RecurringContract(TimestampMixin, Base):
    __tablename__ = "recurring_contracts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    label: Mapped[str] = mapped_column(String(160))
    order_group_id: Mapped[str] = mapped_column(ForeignKey("order_groups.id"), index=True)
    # 스케줄
    recurrence_mode: Mapped[str] = mapped_column(String(20))
    day_of_month: Mapped[int | None] = mapped_column(Integer)
    interval_weeks: Mapped[int | None] = mapped_column(Integer)
    weekday: Mapped[int | None] = mapped_column(Integer)
    start_date: Mapped[date] = mapped_column(Date, index=True)
    # 라이프사이클
    status: Mapped[str] = mapped_column(String(20), default=RecurringContractStatus.ACTIVE, index=True)
    end_date: Mapped[date | None] = mapped_column(Date)
    max_occurrences: Mapped[int | None] = mapped_column(Integer)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    # 회차 템플릿
    default_partner_id: Mapped[str | None] = mapped_column(ForeignKey("partners.id"))
    team_name: Mapped[str | None] = mapped_column(String(120))
    service_category_id: Mapped[str | None] = mapped_column(ForeignKey("service_categories.id"))
    service_item_id: Mapped[str | None] = mapped_column(ForeignKey("service_items.id"))
    service_name: Mapped[str] = mapped_column(String(160))
    size_or_quantity: Mapped[str | None] = mapped_column(String(80))
    service_detail: Mapped[str | None] = mapped_column(Text)
    special_request: Mapped[str | None] = mapped_column(Text)
    requested_time: Mapped[str | None] = mapped_column(String(80))
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    deposit_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    balance_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    vat_type: Mapped[str | None] = mapped_column(String(20))
    partner_payment_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
```

- [ ] **Step 4: `RecurringOccurrence` 구현** — `backend/app/models/recurring_occurrence.py`

```python
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.constants import RecurringOccurrenceStatus
from app.models.base import Base, TimestampMixin


class RecurringOccurrence(TimestampMixin, Base):
    __tablename__ = "recurring_occurrences"
    __table_args__ = (UniqueConstraint("contract_id", "due_date", name="uq_recurring_occurrence_contract_due"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    contract_id: Mapped[str] = mapped_column(ForeignKey("recurring_contracts.id"), index=True)
    sequence_no: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    billing_month: Mapped[str] = mapped_column(String(7))  # "YYYY-MM" — B 연결고리
    status: Mapped[str] = mapped_column(String(20), default=RecurringOccurrenceStatus.PENDING, index=True)
    generated_order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    skipped_reason: Mapped[str | None] = mapped_column(String(200))
```

- [ ] **Step 5: `Order`에 컬럼 추가** — `backend/app/models/order.py`의 `deleted_at` 위(또는 partner 필드 근처)에 추가.

```python
    recurring_contract_id: Mapped[str | None] = mapped_column(
        ForeignKey("recurring_contracts.id"),
        index=True,
        nullable=True,
    )
```

- [ ] **Step 6: `models/__init__.py`에 export 추가** — 기존 import 목록과 `__all__`에 추가.

```python
from app.models.recurring_contract import RecurringContract
from app.models.recurring_occurrence import RecurringOccurrence
```
`__all__`이 있으면 `"RecurringContract"`, `"RecurringOccurrence"` 항목을 추가한다.

- [ ] **Step 7: 테스트 통과 확인**

Run: `cd backend && python -m pytest tests/test_recurring_models.py -q`
Expected: PASS (1 passed). (conftest의 `db_session`이 `Base.metadata.create_all`로 신규 테이블을 만든다.)

- [ ] **Step 8: 커밋**

```bash
git add backend/app/models/recurring_contract.py backend/app/models/recurring_occurrence.py backend/app/models/order.py backend/app/models/__init__.py backend/tests/test_recurring_models.py
git commit -m "feat(recurring): RecurringContract/Occurrence 모델 + Order.recurring_contract_id"
```

---

## Task 3: 마이그레이션 0015

**Files:**
- Create: `backend/alembic/versions/0015_recurring_contracts.py`

> 테스트는 `create_all`을 쓰므로 마이그레이션을 실행하지 않는다. 본 태스크는 실 Postgres/dev SQLite용이며 **렌더 검증**만 한다(실적용은 Task 11).

- [ ] **Step 1: 마이그레이션 작성** — `backend/alembic/versions/0015_recurring_contracts.py`

```python
"""정기청소 — RecurringContract/Occurrence + orders.recurring_contract_id

Revision ID: 0015_recurring_contracts
Revises: 0014_partner_manager_phone
Create Date: 2026-06-28
"""

from alembic import op
import sqlalchemy as sa

revision = "0015_recurring_contracts"
down_revision = "0014_partner_manager_phone"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recurring_contracts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("order_group_id", sa.String(length=36), nullable=False),
        sa.Column("recurrence_mode", sa.String(length=20), nullable=False),
        sa.Column("day_of_month", sa.Integer(), nullable=True),
        sa.Column("interval_weeks", sa.Integer(), nullable=True),
        sa.Column("weekday", sa.Integer(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("max_occurrences", sa.Integer(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("default_partner_id", sa.String(length=36), nullable=True),
        sa.Column("team_name", sa.String(length=120), nullable=True),
        sa.Column("service_category_id", sa.String(length=36), nullable=True),
        sa.Column("service_item_id", sa.String(length=36), nullable=True),
        sa.Column("service_name", sa.String(length=160), nullable=False),
        sa.Column("size_or_quantity", sa.String(length=80), nullable=True),
        sa.Column("service_detail", sa.Text(), nullable=True),
        sa.Column("special_request", sa.Text(), nullable=True),
        sa.Column("requested_time", sa.String(length=80), nullable=True),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("deposit_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("balance_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("vat_type", sa.String(length=20), nullable=True),
        sa.Column("partner_payment_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["order_group_id"], ["order_groups.id"], name="fk_recurring_contracts_order_group_id_order_groups"),
        sa.ForeignKeyConstraint(["default_partner_id"], ["partners.id"], name="fk_recurring_contracts_default_partner_id_partners"),
        sa.ForeignKeyConstraint(["service_category_id"], ["service_categories.id"], name="fk_recurring_contracts_service_category_id_service_categories"),
        sa.ForeignKeyConstraint(["service_item_id"], ["service_items.id"], name="fk_recurring_contracts_service_item_id_service_items"),
        sa.PrimaryKeyConstraint("id", name="pk_recurring_contracts"),
    )
    op.create_index("ix_recurring_contracts_order_group_id", "recurring_contracts", ["order_group_id"])
    op.create_index("ix_recurring_contracts_start_date", "recurring_contracts", ["start_date"])
    op.create_index("ix_recurring_contracts_status", "recurring_contracts", ["status"])
    op.create_index("ix_recurring_contracts_deleted_at", "recurring_contracts", ["deleted_at"])

    op.add_column(
        "orders",
        sa.Column("recurring_contract_id", sa.String(length=36),
                  sa.ForeignKey("recurring_contracts.id", name="fk_orders_recurring_contract_id_recurring_contracts"),
                  nullable=True),
    )
    op.create_index("ix_orders_recurring_contract_id", "orders", ["recurring_contract_id"])

    op.create_table(
        "recurring_occurrences",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("contract_id", sa.String(length=36), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("billing_month", sa.String(length=7), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("generated_order_id", sa.String(length=36), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("skipped_reason", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["contract_id"], ["recurring_contracts.id"], name="fk_recurring_occurrences_contract_id_recurring_contracts"),
        sa.ForeignKeyConstraint(["generated_order_id"], ["orders.id"], name="fk_recurring_occurrences_generated_order_id_orders"),
        sa.PrimaryKeyConstraint("id", name="pk_recurring_occurrences"),
        sa.UniqueConstraint("contract_id", "due_date", name="uq_recurring_occurrence_contract_due"),
    )
    op.create_index("ix_recurring_occurrences_contract_id", "recurring_occurrences", ["contract_id"])
    op.create_index("ix_recurring_occurrences_due_date", "recurring_occurrences", ["due_date"])
    op.create_index("ix_recurring_occurrences_status", "recurring_occurrences", ["status"])


def downgrade() -> None:
    op.drop_table("recurring_occurrences")
    op.drop_index("ix_orders_recurring_contract_id", table_name="orders")
    op.drop_constraint("fk_orders_recurring_contract_id_recurring_contracts", "orders", type_="foreignkey")
    op.drop_column("orders", "recurring_contract_id")
    op.drop_table("recurring_contracts")
```

- [ ] **Step 2: 렌더 검증 (적용 안 함)**

Run: `cd backend && python -m alembic upgrade head --sql`
Expected: 에러 없이 `0015_recurring_contracts`의 CREATE TABLE/ADD COLUMN SQL이 렌더됨.

- [ ] **Step 3: 커밋**

```bash
git add backend/alembic/versions/0015_recurring_contracts.py
git commit -m "feat(recurring): 0015 마이그레이션(recurring_contracts/occurrences + orders 컬럼)"
```

---

## Task 4: 리포지토리

**Files:**
- Create: `backend/app/repositories/recurring.py`
- Test: `backend/tests/test_recurring_repos.py`

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_recurring_repos.py`

```python
from datetime import date
from uuid import uuid4

from app.domain.constants import RecurrenceMode, RecurringContractStatus, RecurringOccurrenceStatus
from app.models.order_group import OrderGroup
from app.models.recurring_contract import RecurringContract
from app.models.recurring_occurrence import RecurringOccurrence
from app.repositories.recurring import RecurringContractRepository, RecurringOccurrenceRepository


def _contract(db, *, status=RecurringContractStatus.ACTIVE, deleted=False):
    group = OrderGroup(
        id=str(uuid4()), customer_token=f"tok-{uuid4()}", customer_name="C",
        customer_phone="01000000000", customer_address="A", customer_visible_payment=False,
    )
    db.add(group)
    db.flush()
    c = RecurringContract(
        id=str(uuid4()), label="L", order_group_id=group.id, recurrence_mode=RecurrenceMode.MONTHLY,
        day_of_month=10, start_date=date(2026, 6, 10), status=status, service_name="S",
        deleted_at=(date(2026, 1, 1) and None),
    )
    if deleted:
        from app.core.time import utc_now
        c.deleted_at = utc_now()
    db.add(c)
    db.flush()
    return c


def test_contract_get_hides_soft_deleted(db_session):
    repo = RecurringContractRepository(db_session)
    c = _contract(db_session, deleted=True)
    assert repo.get(c.id) is None
    assert repo.get(c.id, include_deleted=True) is not None


def test_list_active_excludes_paused_and_deleted(db_session):
    repo = RecurringContractRepository(db_session)
    active = _contract(db_session)
    _contract(db_session, status=RecurringContractStatus.PAUSED)
    _contract(db_session, deleted=True)
    ids = [c.id for c in repo.list_active()]
    assert active.id in ids
    assert len(ids) == 1


def test_occurrence_get_by_contract_and_due(db_session):
    crepo = RecurringContractRepository(db_session)
    orepo = RecurringOccurrenceRepository(db_session)
    c = _contract(db_session)
    occ = RecurringOccurrence(
        id=str(uuid4()), contract_id=c.id, sequence_no=1, due_date=date(2026, 6, 10),
        billing_month="2026-06", status=RecurringOccurrenceStatus.PENDING,
    )
    orepo.add(occ)
    db_session.flush()
    found = orepo.get_by_contract_and_due(c.id, date(2026, 6, 10))
    assert found is not None and found.id == occ.id
    assert orepo.get_by_contract_and_due(c.id, date(2026, 7, 10)) is None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && python -m pytest tests/test_recurring_repos.py -q`
Expected: FAIL — `ModuleNotFoundError: app.repositories.recurring`.

- [ ] **Step 3: 구현** — `backend/app/repositories/recurring.py`

```python
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.constants import RecurringContractStatus, RecurringOccurrenceStatus
from app.models.recurring_contract import RecurringContract
from app.models.recurring_occurrence import RecurringOccurrence
from app.repositories.base import Repository


class RecurringContractRepository(Repository[RecurringContract]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, RecurringContract)

    def get(self, id_: str, *, include_deleted: bool = False) -> RecurringContract | None:
        obj = self.db.get(RecurringContract, id_)
        if obj is None:
            return None
        if obj.deleted_at is not None and not include_deleted:
            return None
        return obj

    def list_all(self) -> list[RecurringContract]:
        stmt = (
            select(RecurringContract)
            .where(RecurringContract.deleted_at.is_(None))
            .order_by(RecurringContract.created_at.desc())
        )
        return list(self.db.scalars(stmt))

    def list_active(self) -> list[RecurringContract]:
        stmt = select(RecurringContract).where(
            RecurringContract.deleted_at.is_(None),
            RecurringContract.status == RecurringContractStatus.ACTIVE,
        )
        return list(self.db.scalars(stmt))


class RecurringOccurrenceRepository(Repository[RecurringOccurrence]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, RecurringOccurrence)

    def get(self, id_: str) -> RecurringOccurrence | None:
        return self.db.get(RecurringOccurrence, id_)

    def get_by_contract_and_due(self, contract_id: str, due_date: date) -> RecurringOccurrence | None:
        stmt = select(RecurringOccurrence).where(
            RecurringOccurrence.contract_id == contract_id,
            RecurringOccurrence.due_date == due_date,
        )
        return self.db.scalar(stmt)

    def list_by_contract(self, contract_id: str) -> list[RecurringOccurrence]:
        stmt = (
            select(RecurringOccurrence)
            .where(RecurringOccurrence.contract_id == contract_id)
            .order_by(RecurringOccurrence.due_date.asc())
        )
        return list(self.db.scalars(stmt))

    def list_pending(self) -> list[RecurringOccurrence]:
        stmt = (
            select(RecurringOccurrence)
            .where(RecurringOccurrence.status == RecurringOccurrenceStatus.PENDING)
            .order_by(RecurringOccurrence.due_date.asc())
        )
        return list(self.db.scalars(stmt))
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && python -m pytest tests/test_recurring_repos.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: 커밋**

```bash
git add backend/app/repositories/recurring.py backend/tests/test_recurring_repos.py
git commit -m "feat(recurring): RecurringContract/Occurrence 리포지토리"
```

---

## Task 5: 스키마 (DTO)

**Files:**
- Create: `backend/app/schemas/recurring.py`
- Test: `backend/tests/test_recurring_schemas.py`

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_recurring_schemas.py`

```python
from datetime import date

import pytest
from pydantic import ValidationError

from app.domain.constants import RecurrenceMode
from app.schemas.recurring import ApproveOccurrencesRequest, RecurringContractCreate


def test_contract_create_requires_service_and_schedule():
    payload = RecurringContractCreate(
        label="강남빌딩", customer_name="강남빌딩", customer_phone="01011112222",
        customer_address="서울 강남구 1", recurrence_mode=RecurrenceMode.MONTHLY, day_of_month=10,
        start_date=date(2026, 6, 10), service_name="사무실 정기청소", total_amount=150000,
    )
    assert payload.discount_amount == 0
    assert payload.default_partner_id is None


def test_approve_request_requires_at_least_one_item():
    with pytest.raises(ValidationError):
        ApproveOccurrencesRequest(items=[])
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && python -m pytest tests/test_recurring_schemas.py -q`
Expected: FAIL — `ModuleNotFoundError: app.schemas.recurring`.

- [ ] **Step 3: 구현** — `backend/app/schemas/recurring.py`

```python
from datetime import date, datetime

from pydantic import Field

from app.domain.constants import RecurrenceMode, RecurringContractStatus
from app.schemas.common import ApiModel


class RecurringContractBase(ApiModel):
    label: str = Field(min_length=1, max_length=160)
    # 고객정보(공유 그룹에 저장)
    customer_name: str
    customer_phone: str
    customer_address: str
    customer_address_detail: str | None = None
    customer_visible_payment: bool = False
    notes: str | None = None
    # 스케줄
    recurrence_mode: RecurrenceMode
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    interval_weeks: int | None = Field(default=None, ge=1, le=12)
    weekday: int | None = Field(default=None, ge=0, le=6)
    start_date: date
    end_date: date | None = None
    max_occurrences: int | None = Field(default=None, ge=1)
    # 회차 템플릿
    default_partner_id: str | None = None
    team_name: str | None = None
    service_category_id: str | None = None
    service_item_id: str | None = None
    service_name: str
    size_or_quantity: str | None = None
    service_detail: str | None = None
    special_request: str | None = None
    requested_time: str | None = None
    total_amount: float | None = None
    discount_amount: float = 0
    deposit_amount: float | None = None
    balance_amount: float | None = None
    vat_type: str | None = None
    partner_payment_amount: float | None = None


class RecurringContractCreate(RecurringContractBase):
    pass


class RecurringContractUpdate(ApiModel):
    label: str | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    customer_address: str | None = None
    customer_address_detail: str | None = None
    customer_visible_payment: bool | None = None
    notes: str | None = None
    recurrence_mode: RecurrenceMode | None = None
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    interval_weeks: int | None = Field(default=None, ge=1, le=12)
    weekday: int | None = Field(default=None, ge=0, le=6)
    start_date: date | None = None
    end_date: date | None = None
    max_occurrences: int | None = Field(default=None, ge=1)
    default_partner_id: str | None = None
    team_name: str | None = None
    service_category_id: str | None = None
    service_item_id: str | None = None
    service_name: str | None = None
    size_or_quantity: str | None = None
    service_detail: str | None = None
    special_request: str | None = None
    requested_time: str | None = None
    total_amount: float | None = None
    discount_amount: float | None = None
    deposit_amount: float | None = None
    balance_amount: float | None = None
    vat_type: str | None = None
    partner_payment_amount: float | None = None


class RecurringContractRead(RecurringContractBase):
    id: str
    order_group_id: str
    customer_token: str
    status: RecurringContractStatus
    next_due_date: date | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RecurringContractSummaryRead(ApiModel):
    id: str
    label: str
    customer_name: str
    status: RecurringContractStatus
    schedule_text: str
    next_due_date: date | None = None
    pending_count: int = 0
    this_month_count: int = 0
    this_month_amount: float = 0


class RecurringOccurrenceRead(ApiModel):
    id: str
    contract_id: str
    sequence_no: int
    due_date: date
    billing_month: str
    status: str
    generated_order_id: str | None = None
    generated_at: datetime | None = None
    skipped_reason: str | None = None


class PendingOccurrenceRead(ApiModel):
    occurrence_id: str
    contract_id: str
    contract_label: str
    customer_name: str
    sequence_no: int
    due_date: date
    service_name: str
    total_amount: float | None = None
    default_partner_id: str | None = None
    default_partner_name: str | None = None
    is_overdue: bool = False


class ApproveItem(ApiModel):
    occurrence_id: str
    partner_id: str | None = None
    scheduled_date: date | None = None
    total_amount: float | None = None


class ApproveOccurrencesRequest(ApiModel):
    items: list[ApproveItem] = Field(min_length=1)


class ApproveOccurrencesResult(ApiModel):
    generated_order_ids: list[str]
    skipped_occurrence_ids: list[str] = Field(default_factory=list)


class SkipItem(ApiModel):
    occurrence_id: str
    reason: str | None = None


class SkipOccurrencesRequest(ApiModel):
    items: list[SkipItem] = Field(min_length=1)


class SkipOccurrencesResult(ApiModel):
    skipped_occurrence_ids: list[str]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && python -m pytest tests/test_recurring_schemas.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: 커밋**

```bash
git add backend/app/schemas/recurring.py backend/tests/test_recurring_schemas.py
git commit -m "feat(recurring): 정기청소 DTO 스키마"
```

---

## Task 6: OrderService 확장 (빈 그룹 + 정기 라인) + 관리자 DTO 배지

**Files:**
- Modify: `backend/app/services/orders.py`, `backend/app/schemas/order.py`
- Test: `backend/tests/test_recurring_order_service.py`

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_recurring_order_service.py`

```python
from datetime import date
from uuid import uuid4

from app.domain.constants import OrderStatus
from app.schemas.order import OrderGroupCreate, OrderLineCreate
from app.services.orders import OrderService


def test_create_empty_group_has_no_lines(db_session):
    svc = OrderService(db_session)
    group = svc.create_empty_group(
        OrderGroupCreate(
            customer_name="강남빌딩", customer_phone="01011112222", customer_address="서울 강남구 1",
            lines=[OrderLineCreate(service_name="placeholder")],  # lines는 무시됨
        )
    )
    assert group.customer_token
    from app.repositories.order_groups import OrderGroupRepository
    assert OrderGroupRepository(db_session).list_lines(group.id) == []


def test_add_recurring_line_stamps_contract_id_without_commit(db_session):
    svc = OrderService(db_session)
    group = svc.create_empty_group(
        OrderGroupCreate(
            customer_name="강남빌딩", customer_phone="01011112222", customer_address="서울 강남구 1",
            lines=[OrderLineCreate(service_name="x")],
        )
    )
    order = svc.add_recurring_line(
        group,
        OrderLineCreate(service_name="사무실 정기청소", status=OrderStatus.SCHEDULE_CONFIRMED,
                        received_date=date(2026, 6, 28), scheduled_date=date(2026, 7, 10)),
        recurring_contract_id="contract-xyz",
        actor_user_id=None,
    )
    db_session.commit()
    assert order.recurring_contract_id == "contract-xyz"
    assert order.status == OrderStatus.SCHEDULE_CONFIRMED
```

> 참고: `OrderLineCreate`의 필수 필드는 기존 스키마를 따른다. `service_name`만 필수이고 나머지는 기본값이 있는지 `schemas/order.py`에서 확인하고, 필수 필드가 더 있으면 위 호출에 채운다.

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && python -m pytest tests/test_recurring_order_service.py -q`
Expected: FAIL — `AttributeError: 'OrderService' object has no attribute 'create_empty_group'`.

- [ ] **Step 3: 구현** — `backend/app/services/orders.py`의 `OrderService`에 메서드 2개 추가(`add_line_to_group` 아래).

```python
    def create_empty_group(
        self,
        payload: OrderGroupCreate,
        *,
        actor_user_id: str | None = None,
    ) -> OrderGroup:
        """라인 0개 그룹 생성(정기계약 전용). payload.lines는 무시한다."""
        group = OrderGroup(
            id=str(uuid4()),
            customer_token=token_urlsafe(24),
            customer_name=payload.customer_name,
            customer_phone=normalize_phone(payload.customer_phone),
            customer_address=payload.customer_address,
            customer_address_detail=payload.customer_address_detail,
            source_channel=payload.source_channel,
            customer_visible_payment=payload.customer_visible_payment,
            notes=payload.notes,
        )
        self.db.add(group)
        self.db.commit()
        self.db.refresh(group)
        return group

    def add_recurring_line(
        self,
        group: OrderGroup,
        payload: OrderLineCreate,
        *,
        recurring_contract_id: str,
        actor_user_id: str | None = None,
    ) -> Order:
        """정기 회차 라인 생성. commit하지 않는다 — caller(RecurringService)가 트랜잭션 소유."""
        order = self._create_line_internal(group, payload, actor_user_id=actor_user_id)
        order.recurring_contract_id = recurring_contract_id
        return order
```

- [ ] **Step 4: 관리자 주문 DTO에 배지 필드 추가** — `backend/app/schemas/order.py`의 `AdminOrderRead`(또는 admin 라인 Read 클래스)에 추가.

```python
    recurring_contract_id: str | None = None
```
그리고 `backend/app/services/orders.py`의 `to_admin_order_dto`가 dict를 만들 때 `recurring_contract_id`를 명시적으로 포함한다(스프레드 금지 — 화이트리스트). `to_partner_job_dto`·`to_customer_order_dto`에는 **추가하지 않는다.**

> `to_admin_order_dto`가 `AdminOrderRead.model_validate(order)`처럼 ORM에서 자동 매핑하는 구조면 필드 추가만으로 노출된다. 협력사/고객 DTO가 화이트리스트 dict를 직접 구성하는지 확인하고, 그렇다면 거기엔 넣지 않는다.

- [ ] **Step 5: 테스트 통과 확인 + 회귀 확인**

Run: `cd backend && python -m pytest tests/test_recurring_order_service.py tests/test_role_dtos.py -q`
Expected: PASS. (`test_role_dtos.py`가 깨지면 협력사/고객 DTO에 필드가 새지 않았는지 점검.)

- [ ] **Step 6: 커밋**

```bash
git add backend/app/services/orders.py backend/app/schemas/order.py backend/tests/test_recurring_order_service.py
git commit -m "feat(recurring): OrderService 빈 그룹/정기 라인 생성 + 관리자 DTO 배지 필드"
```

---

## Task 7: RecurringService — 계약 CRUD + 라이프사이클

**Files:**
- Create: `backend/app/services/recurring.py`
- Test: `backend/tests/test_recurring_service.py` (이후 Task 8·9에서 확장)

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_recurring_service.py`

```python
from datetime import date

from app.domain.constants import RecurrenceMode, RecurringContractStatus
from app.repositories.order_groups import OrderGroupRepository
from app.schemas.recurring import RecurringContractCreate, RecurringContractUpdate
from app.services.recurring import RecurringService


def _make_payload(**over):
    base = dict(
        label="강남빌딩 정기청소", customer_name="강남빌딩", customer_phone="01011112222",
        customer_address="서울 강남구 1", recurrence_mode=RecurrenceMode.MONTHLY, day_of_month=10,
        start_date=date(2026, 6, 10), service_name="사무실 정기청소", total_amount=150000,
    )
    base.update(over)
    return RecurringContractCreate(**base)


def test_create_contract_creates_empty_group(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(_make_payload(), actor_user_id=None)
    assert c.status == RecurringContractStatus.ACTIVE
    assert c.order_group_id
    assert OrderGroupRepository(db_session).list_lines(c.order_group_id) == []


def test_update_contract_changes_future_template(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(_make_payload(), actor_user_id=None)
    svc.update_contract(c.id, RecurringContractUpdate(total_amount=200000), actor_user_id=None)
    assert svc.get_contract(c.id).total_amount == 200000


def test_pause_and_resume_and_end(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(_make_payload(), actor_user_id=None)
    svc.set_status(c.id, RecurringContractStatus.PAUSED)
    assert svc.get_contract(c.id).status == RecurringContractStatus.PAUSED
    svc.set_status(c.id, RecurringContractStatus.ACTIVE)
    assert svc.get_contract(c.id).status == RecurringContractStatus.ACTIVE


def test_soft_delete_hides_contract_but_keeps_group(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(_make_payload(), actor_user_id=None)
    gid = c.order_group_id
    svc.delete_contract(c.id, actor_user_id=None)
    assert svc.get_contract(c.id) is None
    assert OrderGroupRepository(db_session).get(gid) is not None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && python -m pytest tests/test_recurring_service.py -q`
Expected: FAIL — `ModuleNotFoundError: app.services.recurring`.

- [ ] **Step 3: 구현(1/2 — CRUD/라이프사이클)** — `backend/app/services/recurring.py`

```python
from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.domain.constants import RecurringContractStatus
from app.models.order_group import OrderGroup
from app.models.recurring_contract import RecurringContract
from app.repositories.order_groups import OrderGroupRepository
from app.repositories.recurring import RecurringContractRepository, RecurringOccurrenceRepository
from app.schemas.order import OrderGroupCreate, OrderLineCreate
from app.schemas.recurring import RecurringContractCreate, RecurringContractUpdate
from app.services.orders import OrderService

# 그룹에 보관되는 고객 필드(계약 수정 시 그룹으로 라우팅)
_GROUP_FIELDS = {
    "customer_name", "customer_phone", "customer_address",
    "customer_address_detail", "customer_visible_payment", "notes",
}


class RecurringService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.contracts = RecurringContractRepository(db)
        self.occurrences = RecurringOccurrenceRepository(db)
        self.groups = OrderGroupRepository(db)
        self.orders = OrderService(db)

    # --- 계약 CRUD ---
    def create_contract(self, payload: RecurringContractCreate, *, actor_user_id: str | None) -> RecurringContract:
        group = self.orders.create_empty_group(
            OrderGroupCreate(
                customer_name=payload.customer_name,
                customer_phone=payload.customer_phone,
                customer_address=payload.customer_address,
                customer_address_detail=payload.customer_address_detail,
                customer_visible_payment=payload.customer_visible_payment,
                notes=payload.notes,
                lines=[OrderLineCreate(service_name=payload.service_name)],  # 무시됨
            )
        )
        data = payload.model_dump()
        for field in _GROUP_FIELDS:
            data.pop(field, None)
        contract = RecurringContract(
            id=str(uuid4()),
            order_group_id=group.id,
            status=RecurringContractStatus.ACTIVE,
            **data,
        )
        self.db.add(contract)
        self.db.commit()
        self.db.refresh(contract)
        return contract

    def get_contract(self, contract_id: str) -> RecurringContract | None:
        return self.contracts.get(contract_id)

    def update_contract(
        self, contract_id: str, payload: RecurringContractUpdate, *, actor_user_id: str | None
    ) -> RecurringContract:
        contract = self.contracts.get(contract_id)
        if contract is None:
            raise ValueError("recurring_contract_not_found")
        changes = payload.model_dump(exclude_unset=True)

        group = self.groups.get(contract.order_group_id)
        for field in list(changes.keys()):
            if field in _GROUP_FIELDS:
                value = changes.pop(field)
                if group is not None and value is not None:
                    setattr(group, field, value)
        for key, value in changes.items():
            setattr(contract, key, value)
        self.db.commit()
        self.db.refresh(contract)
        return contract

    def set_status(self, contract_id: str, status: RecurringContractStatus) -> RecurringContract:
        contract = self.contracts.get(contract_id)
        if contract is None:
            raise ValueError("recurring_contract_not_found")
        contract.status = status
        self.db.commit()
        self.db.refresh(contract)
        return contract

    def delete_contract(self, contract_id: str, *, actor_user_id: str | None) -> None:
        contract = self.contracts.get(contract_id)
        if contract is None:
            raise ValueError("recurring_contract_not_found")
        contract.deleted_at = utc_now()
        self.db.commit()
```

> `RecurringContract(**data)`가 동작하려면 `data`의 키가 모두 모델 컬럼이어야 한다. `RecurringContractCreate`는 고객 필드를 제외하면 정확히 계약 컬럼과 일치하도록 설계됨(Task 5). `total_amount` 등 Numeric은 float로 들어와도 SQLAlchemy가 Decimal로 처리한다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && python -m pytest tests/test_recurring_service.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: 커밋**

```bash
git add backend/app/services/recurring.py backend/tests/test_recurring_service.py
git commit -m "feat(recurring): RecurringService 계약 CRUD + 라이프사이클"
```

---

## Task 8: RecurringService — sync_due_occurrences + list_pending

**Files:**
- Modify: `backend/app/services/recurring.py`
- Test: `backend/tests/test_recurring_service.py` (추가)

- [ ] **Step 1: 실패 테스트 추가** — `backend/tests/test_recurring_service.py`에 함수 추가.

```python
def test_sync_creates_pending_occurrences_idempotently(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(_make_payload(start_date=date(2026, 6, 10)), actor_user_id=None)
    # 2026-06-20 기준, HORIZON 14일 → 6/10(과거, grace 내), 7/10? (7/10은 6/20+14=7/4 초과 → 미포함)
    n1 = svc.sync_due_occurrences(today=date(2026, 6, 20))
    pend1 = svc.occurrences.list_by_contract(c.id)
    assert [o.due_date for o in pend1] == [date(2026, 6, 10)]
    n2 = svc.sync_due_occurrences(today=date(2026, 6, 20))
    pend2 = svc.occurrences.list_by_contract(c.id)
    assert len(pend2) == 1  # 멱등 — 중복 생성 없음
    assert n1 == 1 and n2 == 0


def test_sync_skips_paused_contract(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(_make_payload(start_date=date(2026, 6, 10)), actor_user_id=None)
    svc.set_status(c.id, RecurringContractStatus.PAUSED)
    svc.sync_due_occurrences(today=date(2026, 6, 20))
    assert svc.occurrences.list_by_contract(c.id) == []


def test_sync_excludes_overdue_beyond_grace(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(_make_payload(start_date=date(2026, 1, 10)), actor_user_id=None)
    # today 6/20, grace 30일 → 5/21 이전 due는 제외. 6/10만 노출.
    svc.sync_due_occurrences(today=date(2026, 6, 20))
    dues = [o.due_date for o in svc.occurrences.list_by_contract(c.id)]
    assert dues == [date(2026, 6, 10)]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && python -m pytest tests/test_recurring_service.py -k sync -q`
Expected: FAIL — `AttributeError: ... 'sync_due_occurrences'`.

- [ ] **Step 3: 구현** — `backend/app/services/recurring.py` 상단 import에 추가하고 메서드 구현.

상단 import 추가:
```python
from datetime import date, timedelta

from app.core.time import business_today
from app.domain.constants import RecurrenceMode, RecurringContractStatus, RecurringOccurrenceStatus
from app.domain.recurrence import (
    HORIZON_DAYS,
    OVERDUE_GRACE_DAYS,
    ScheduleSpec,
    billing_month_of,
    iter_due_dates,
)
from app.models.recurring_occurrence import RecurringOccurrence
```

메서드 추가:
```python
    def _spec(self, contract: RecurringContract) -> ScheduleSpec:
        return ScheduleSpec(
            mode=contract.recurrence_mode,
            start_date=contract.start_date,
            day_of_month=contract.day_of_month,
            interval_weeks=contract.interval_weeks,
            weekday=contract.weekday,
            end_date=contract.end_date,
            max_occurrences=contract.max_occurrences,
        )

    def sync_due_occurrences(self, *, today: date | None = None) -> int:
        """ACTIVE 계약의 도래분을 PENDING으로 upsert. 생성 건수 반환. 멱등."""
        today = today or business_today()
        horizon = today + timedelta(days=HORIZON_DAYS)
        floor = today - timedelta(days=OVERDUE_GRACE_DAYS)
        created = 0
        for contract in self.contracts.list_active():
            for seq, due in iter_due_dates(self._spec(contract), until=horizon):
                if due < floor:
                    continue
                if self.occurrences.get_by_contract_and_due(contract.id, due) is not None:
                    continue
                self.occurrences.add(
                    RecurringOccurrence(
                        id=str(uuid4()),
                        contract_id=contract.id,
                        sequence_no=seq,
                        due_date=due,
                        billing_month=billing_month_of(due),
                        status=RecurringOccurrenceStatus.PENDING,
                    )
                )
                created += 1
        if created:
            self.db.commit()
        return created

    def list_pending(self) -> list[RecurringOccurrence]:
        return self.occurrences.list_pending()
```

> 주의: `iter_due_dates`는 `until`까지만 산출하므로 미래 폭주가 없다. `floor`는 과거 grace 하한. ENDED/PAUSED는 `list_active()`가 이미 제외. 스케줄 변경으로 무효해진 PENDING 정리는 Task 9 이후 후속(현재는 새 due만 추가; 무효 PENDING은 운영자가 skip). → 설계 §3.1.6은 후속 개선으로 남긴다(아래 자기리뷰 노트 참조).

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && python -m pytest tests/test_recurring_service.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: 커밋**

```bash
git add backend/app/services/recurring.py backend/tests/test_recurring_service.py
git commit -m "feat(recurring): 도래분 sync(멱등 upsert) + list_pending"
```

---

## Task 9: RecurringService — approve + skip

**Files:**
- Modify: `backend/app/services/recurring.py`
- Test: `backend/tests/test_recurring_service.py` (추가)

- [ ] **Step 1: 실패 테스트 추가** — `backend/tests/test_recurring_service.py`

```python
from app.db.seed import DEV_PARTNER_ID
from app.domain.constants import OrderStatus, RecurringOccurrenceStatus
from app.repositories.orders import OrderRepository
from app.schemas.recurring import ApproveItem, SkipItem


def test_approve_generates_confirmed_order_when_partner_present(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(
        _make_payload(start_date=date(2026, 6, 10), default_partner_id=DEV_PARTNER_ID), actor_user_id=None
    )
    svc.sync_due_occurrences(today=date(2026, 6, 20))
    occ = svc.occurrences.list_by_contract(c.id)[0]
    result = svc.approve_occurrences([ApproveItem(occurrence_id=occ.id)], actor_user_id=None)

    assert len(result.generated_order_ids) == 1
    order = OrderRepository(db_session).get(result.generated_order_ids[0])
    assert order.status == OrderStatus.SCHEDULE_CONFIRMED
    assert order.partner_id == DEV_PARTNER_ID
    assert order.scheduled_date == occ.due_date
    assert order.recurring_contract_id == c.id
    db_session.refresh(occ)
    assert occ.status == RecurringOccurrenceStatus.GENERATED
    assert occ.generated_order_id == order.id


def test_approve_generates_new_order_when_no_partner(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(_make_payload(start_date=date(2026, 6, 10)), actor_user_id=None)
    svc.sync_due_occurrences(today=date(2026, 6, 20))
    occ = svc.occurrences.list_by_contract(c.id)[0]
    result = svc.approve_occurrences([ApproveItem(occurrence_id=occ.id)], actor_user_id=None)
    order = OrderRepository(db_session).get(result.generated_order_ids[0])
    assert order.status == OrderStatus.NEW
    assert order.partner_id is None


def test_approve_skips_non_pending(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(_make_payload(start_date=date(2026, 6, 10)), actor_user_id=None)
    svc.sync_due_occurrences(today=date(2026, 6, 20))
    occ = svc.occurrences.list_by_contract(c.id)[0]
    svc.approve_occurrences([ApproveItem(occurrence_id=occ.id)], actor_user_id=None)
    again = svc.approve_occurrences([ApproveItem(occurrence_id=occ.id)], actor_user_id=None)
    assert again.generated_order_ids == []
    assert occ.id in again.skipped_occurrence_ids


def test_skip_marks_occurrence_skipped(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(_make_payload(start_date=date(2026, 6, 10)), actor_user_id=None)
    svc.sync_due_occurrences(today=date(2026, 6, 20))
    occ = svc.occurrences.list_by_contract(c.id)[0]
    svc.skip_occurrences([SkipItem(occurrence_id=occ.id, reason="고객 휴무")], actor_user_id=None)
    db_session.refresh(occ)
    assert occ.status == RecurringOccurrenceStatus.SKIPPED
    assert occ.skipped_reason == "고객 휴무"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && python -m pytest tests/test_recurring_service.py -k "approve or skip" -q`
Expected: FAIL — `AttributeError: ... 'approve_occurrences'`.

- [ ] **Step 3: 구현** — `backend/app/services/recurring.py`

상단 import 추가:
```python
from app.domain.constants import OrderStatus
from app.schemas.order import OrderLineCreate
from app.schemas.recurring import (
    ApproveItem,
    ApproveOccurrencesResult,
    SkipItem,
    SkipOccurrencesResult,
)
```

메서드 추가:
```python
    def approve_occurrences(
        self, items: list[ApproveItem], *, actor_user_id: str | None
    ) -> ApproveOccurrencesResult:
        generated: list[str] = []
        skipped: list[str] = []
        for item in items:
            occ = self.occurrences.get(item.occurrence_id)
            if occ is None or occ.status != RecurringOccurrenceStatus.PENDING:
                if occ is not None:
                    skipped.append(occ.id)
                continue
            contract = self.contracts.get(occ.contract_id)
            if contract is None:
                skipped.append(occ.id)
                continue
            group = self.groups.get(contract.order_group_id)
            if group is None:
                skipped.append(occ.id)
                continue

            partner_id = item.partner_id or contract.default_partner_id
            status = OrderStatus.SCHEDULE_CONFIRMED if partner_id else OrderStatus.NEW
            scheduled = item.scheduled_date or occ.due_date
            total = item.total_amount if item.total_amount is not None else (
                float(contract.total_amount) if contract.total_amount is not None else None
            )

            line = OrderLineCreate(
                status=status,
                received_date=business_today(),
                scheduled_date=scheduled,
                requested_time=contract.requested_time,
                partner_id=partner_id,
                team_name=contract.team_name,
                service_category_id=contract.service_category_id,
                service_item_id=contract.service_item_id,
                service_name=contract.service_name,
                size_or_quantity=contract.size_or_quantity,
                service_detail=contract.service_detail,
                special_request=contract.special_request,
                total_amount=total,
                discount_amount=float(contract.discount_amount or 0),
                deposit_amount=float(contract.deposit_amount) if contract.deposit_amount is not None else None,
                balance_amount=float(contract.balance_amount) if contract.balance_amount is not None else None,
                vat_type=contract.vat_type,
                partner_payment_amount=(
                    float(contract.partner_payment_amount)
                    if contract.partner_payment_amount is not None else None
                ),
            )
            order = self.orders.add_recurring_line(
                group, line, recurring_contract_id=contract.id, actor_user_id=actor_user_id
            )
            self.db.flush()  # order.id 확보
            occ.status = RecurringOccurrenceStatus.GENERATED
            occ.generated_order_id = order.id
            occ.generated_at = utc_now()
            generated.append(order.id)
        self.db.commit()
        return ApproveOccurrencesResult(generated_order_ids=generated, skipped_occurrence_ids=skipped)

    def skip_occurrences(
        self, items: list[SkipItem], *, actor_user_id: str | None
    ) -> SkipOccurrencesResult:
        skipped: list[str] = []
        for item in items:
            occ = self.occurrences.get(item.occurrence_id)
            if occ is None or occ.status != RecurringOccurrenceStatus.PENDING:
                continue
            occ.status = RecurringOccurrenceStatus.SKIPPED
            occ.skipped_reason = item.reason
            skipped.append(occ.id)
        self.db.commit()
        return SkipOccurrencesResult(skipped_occurrence_ids=skipped)
```

> `OrderLineCreate(...)`의 인자명은 `schemas/order.py`의 실제 필드와 일치해야 한다. 필드명이 다르면(예: `onsite_extra_amount` 필수 여부) 거기에 맞춰 조정. `_create_line_internal`이 `payload.model_dump()`로 `Order(**values)`를 만들기 때문에, `OrderLineCreate`에 없는 필드는 전달되지 않는다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && python -m pytest tests/test_recurring_service.py -q`
Expected: PASS (11 passed).

- [ ] **Step 5: 커밋**

```bash
git add backend/app/services/recurring.py backend/tests/test_recurring_service.py
git commit -m "feat(recurring): 회차 승인(주문 생성)·건너뛰기"
```

---

## Task 10: 라우트 + 라우터 등록

**Files:**
- Create: `backend/app/api/routes/admin/recurring.py`
- Modify: `backend/app/api/router.py`
- Test: `backend/tests/test_recurring_api.py`

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_recurring_api.py`

```python
def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _contract_body(**over):
    body = {
        "label": "강남빌딩 정기청소", "customer_name": "강남빌딩", "customer_phone": "01011112222",
        "customer_address": "서울 강남구 1", "recurrence_mode": "monthly", "day_of_month": 10,
        "start_date": "2026-06-10", "service_name": "사무실 정기청소", "total_amount": 150000,
    }
    body.update(over)
    return body


def test_create_list_contract(client, seed_admin_token):
    r = client.post("/api/admin/recurring/contracts", json=_contract_body(), headers=_auth(seed_admin_token))
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    lst = client.get("/api/admin/recurring/contracts", headers=_auth(seed_admin_token))
    assert lst.status_code == 200
    assert any(c["id"] == cid for c in lst.json())


def test_sync_and_approve_flow(client, seed_admin_token):
    client.post("/api/admin/recurring/contracts", json=_contract_body(start_date="2026-06-10"), headers=_auth(seed_admin_token))
    # sync는 '오늘' 기준이라 미래 start_date면 도래분이 없을 수 있음 → 과거 start_date로 보장
    client.post("/api/admin/recurring/contracts", json=_contract_body(label="과거건", start_date="2020-01-10"), headers=_auth(seed_admin_token))
    synced = client.post("/api/admin/recurring/occurrences/sync", headers=_auth(seed_admin_token))
    assert synced.status_code == 200
    pending = client.get("/api/admin/recurring/occurrences/pending", headers=_auth(seed_admin_token))
    assert pending.status_code == 200


def test_requires_admin(client):
    r = client.get("/api/admin/recurring/contracts")
    assert r.status_code == 401
```

> 주의: `test_sync_and_approve_flow`의 `2020-01-10` 과거 계약은 grace(30일) 때문에 PENDING이 안 생길 수 있다. 본 테스트는 200 응답만 검증(데이터 정확성은 서비스 단위 테스트가 담당). 도래분이 보장된 케이스가 필요하면 `start_date`를 "오늘 기준 최근"으로 동적 계산하거나 서비스 테스트로 검증한다.

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && python -m pytest tests/test_recurring_api.py -q`
Expected: FAIL — 404(라우트 없음).

- [ ] **Step 3: 라우트 구현** — `backend/app/api/routes/admin/recurring.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_session, require_admin
from app.domain.constants import RecurringContractStatus
from app.schemas.recurring import (
    ApproveOccurrencesRequest,
    ApproveOccurrencesResult,
    PendingOccurrenceRead,
    RecurringContractCreate,
    RecurringContractRead,
    RecurringContractSummaryRead,
    RecurringContractUpdate,
    SkipOccurrencesRequest,
    SkipOccurrencesResult,
)
from app.services.recurring import RecurringService

router = APIRouter()


def _err(exc: ValueError) -> HTTPException:
    detail = str(exc)
    return HTTPException(status_code=404 if detail.endswith("_not_found") else 400, detail=detail)


@router.get("/contracts", response_model=list[RecurringContractSummaryRead])
def list_contracts(db: Session = Depends(get_session), _: CurrentUser = Depends(require_admin)):
    return RecurringService(db).list_contract_summaries()


@router.post("/contracts", response_model=RecurringContractRead, status_code=201)
def create_contract(
    payload: RecurringContractCreate,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
):
    svc = RecurringService(db)
    contract = svc.create_contract(payload, actor_user_id=user.id)
    return svc.to_contract_read(contract)


@router.get("/contracts/{contract_id}", response_model=RecurringContractRead)
def get_contract(contract_id: str, db: Session = Depends(get_session), _: CurrentUser = Depends(require_admin)):
    svc = RecurringService(db)
    contract = svc.get_contract(contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="recurring_contract_not_found")
    return svc.to_contract_read(contract)


@router.patch("/contracts/{contract_id}", response_model=RecurringContractRead)
def update_contract(
    contract_id: str,
    payload: RecurringContractUpdate,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
):
    svc = RecurringService(db)
    try:
        contract = svc.update_contract(contract_id, payload, actor_user_id=user.id)
    except ValueError as exc:
        raise _err(exc) from exc
    return svc.to_contract_read(contract)


@router.post("/contracts/{contract_id}/pause", response_model=RecurringContractRead)
def pause_contract(contract_id: str, db: Session = Depends(get_session), _: CurrentUser = Depends(require_admin)):
    svc = RecurringService(db)
    try:
        return svc.to_contract_read(svc.set_status(contract_id, RecurringContractStatus.PAUSED))
    except ValueError as exc:
        raise _err(exc) from exc


@router.post("/contracts/{contract_id}/resume", response_model=RecurringContractRead)
def resume_contract(contract_id: str, db: Session = Depends(get_session), _: CurrentUser = Depends(require_admin)):
    svc = RecurringService(db)
    try:
        return svc.to_contract_read(svc.set_status(contract_id, RecurringContractStatus.ACTIVE))
    except ValueError as exc:
        raise _err(exc) from exc


@router.post("/contracts/{contract_id}/end", response_model=RecurringContractRead)
def end_contract(contract_id: str, db: Session = Depends(get_session), _: CurrentUser = Depends(require_admin)):
    svc = RecurringService(db)
    try:
        return svc.to_contract_read(svc.set_status(contract_id, RecurringContractStatus.ENDED))
    except ValueError as exc:
        raise _err(exc) from exc


@router.delete("/contracts/{contract_id}", status_code=204)
def delete_contract(contract_id: str, db: Session = Depends(get_session), user: CurrentUser = Depends(require_admin)):
    from fastapi import Response
    svc = RecurringService(db)
    try:
        svc.delete_contract(contract_id, actor_user_id=user.id)
    except ValueError as exc:
        raise _err(exc) from exc
    return Response(status_code=204)


@router.post("/occurrences/sync", response_model=list[PendingOccurrenceRead])
def sync_occurrences(db: Session = Depends(get_session), _: CurrentUser = Depends(require_admin)):
    svc = RecurringService(db)
    svc.sync_due_occurrences()
    return svc.list_pending_views()


@router.get("/occurrences/pending", response_model=list[PendingOccurrenceRead])
def list_pending(db: Session = Depends(get_session), _: CurrentUser = Depends(require_admin)):
    return RecurringService(db).list_pending_views()


@router.post("/occurrences/approve", response_model=ApproveOccurrencesResult)
def approve_occurrences(
    payload: ApproveOccurrencesRequest,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
):
    return RecurringService(db).approve_occurrences(payload.items, actor_user_id=user.id)


@router.post("/occurrences/skip", response_model=SkipOccurrencesResult)
def skip_occurrences(
    payload: SkipOccurrencesRequest,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
):
    return RecurringService(db).skip_occurrences(payload.items, actor_user_id=user.id)
```

- [ ] **Step 4: 서비스에 DTO 매핑 메서드 추가** — `backend/app/services/recurring.py`에 추가. (라우트가 쓰는 `to_contract_read`, `list_contract_summaries`, `list_pending_views`)

```python
    # 상단 import 추가
    # from app.domain.constants import RecurringOccurrenceStatus  (이미 있음)
    # from app.repositories.partners import PartnerRepository
    # from app.repositories.orders import OrderRepository
    # from app.schemas.recurring import (RecurringContractRead, RecurringContractSummaryRead, PendingOccurrenceRead)
    # from app.domain.recurrence import iter_due_dates, billing_month_of (이미 있음), HORIZON_DAYS

    def _next_due(self, contract: RecurringContract) -> date | None:
        from datetime import timedelta
        today = business_today()
        for _, due in iter_due_dates(self._spec(contract), until=today + timedelta(days=365)):
            if due >= today:
                return due
        return None

    def _schedule_text(self, contract: RecurringContract) -> str:
        if contract.recurrence_mode == RecurrenceMode.MONTHLY:
            return f"매월 {contract.day_of_month}일"
        weekday_ko = ["월", "화", "수", "목", "금", "토", "일"]
        every = "매주" if contract.interval_weeks == 1 else f"{contract.interval_weeks}주마다"
        wd = weekday_ko[contract.weekday] if contract.weekday is not None else weekday_ko[contract.start_date.weekday()]
        return f"{every} {wd}요일"

    def to_contract_read(self, contract: RecurringContract) -> "RecurringContractRead":
        from app.schemas.recurring import RecurringContractRead
        group = self.groups.get(contract.order_group_id)
        data = {
            **{c.name: getattr(contract, c.name) for c in contract.__table__.columns},
            "customer_name": group.customer_name if group else "",
            "customer_phone": group.customer_phone if group else "",
            "customer_address": group.customer_address if group else "",
            "customer_address_detail": group.customer_address_detail if group else None,
            "customer_visible_payment": group.customer_visible_payment if group else False,
            "notes": group.notes if group else None,
            "customer_token": group.customer_token if group else "",
            "next_due_date": self._next_due(contract),
        }
        return RecurringContractRead.model_validate(data)

    def list_contract_summaries(self) -> list["RecurringContractSummaryRead"]:
        from app.schemas.recurring import RecurringContractSummaryRead
        from app.repositories.orders import OrderRepository
        out = []
        groups = self.groups  # noqa
        pend_by_contract: dict[str, int] = {}
        for occ in self.occurrences.list_pending():
            pend_by_contract[occ.contract_id] = pend_by_contract.get(occ.contract_id, 0) + 1
        order_repo = OrderRepository(self.db)
        month = billing_month_of(business_today())
        for contract in self.contracts.list_all():
            group = self.groups.get(contract.order_group_id)
            this_month = order_repo.list_recurring_orders_in_month(contract.id, month)
            out.append(
                RecurringContractSummaryRead(
                    id=contract.id, label=contract.label,
                    customer_name=group.customer_name if group else "",
                    status=contract.status, schedule_text=self._schedule_text(contract),
                    next_due_date=self._next_due(contract),
                    pending_count=pend_by_contract.get(contract.id, 0),
                    this_month_count=len(this_month),
                    this_month_amount=float(sum((o.total_amount or 0) for o in this_month)),
                )
            )
        return out

    def list_pending_views(self) -> list["PendingOccurrenceRead"]:
        from app.schemas.recurring import PendingOccurrenceRead
        from app.repositories.partners import PartnerRepository
        partner_repo = PartnerRepository(self.db)
        today = business_today()
        views = []
        for occ in self.occurrences.list_pending():
            contract = self.contracts.get(occ.contract_id)
            if contract is None:
                continue
            group = self.groups.get(contract.order_group_id)
            partner = partner_repo.get(contract.default_partner_id) if contract.default_partner_id else None
            views.append(
                PendingOccurrenceRead(
                    occurrence_id=occ.id, contract_id=contract.id, contract_label=contract.label,
                    customer_name=group.customer_name if group else "",
                    sequence_no=occ.sequence_no, due_date=occ.due_date, service_name=contract.service_name,
                    total_amount=float(contract.total_amount) if contract.total_amount is not None else None,
                    default_partner_id=contract.default_partner_id,
                    default_partner_name=partner.name if partner else None,
                    is_overdue=occ.due_date < today,
                )
            )
        return views
```

- [ ] **Step 5: OrderRepository에 헬퍼 추가** — `backend/app/repositories/orders.py`에 메서드 추가(이번 달 정기 주문 집계).

```python
    def list_recurring_orders_in_month(self, contract_id: str, billing_month: str) -> list[Order]:
        from sqlalchemy import select
        stmt = select(Order).where(
            Order.recurring_contract_id == contract_id,
            Order.deleted_at.is_(None),
        )
        rows = list(self.db.scalars(stmt))
        return [o for o in rows if o.scheduled_date is not None and o.scheduled_date.strftime("%Y-%m") == billing_month]
```

> `Order.scheduled_date` 기준 월로 집계(없으면 제외). DB 방언 함수 대신 Python 필터(`AGENTS.md` 집계 규칙).

- [ ] **Step 6: 라우터 등록** — `backend/app/api/router.py`

```python
from app.api.routes.admin import (
    calendar,
    dashboard,
    messages,
    orders,
    partner_settlements,
    partners,
    photos,
    recurring,   # 추가
    reports,
    services,
)
```
그리고 등록부에 추가:
```python
api_router.include_router(recurring.router, prefix="/admin/recurring", tags=["admin-recurring"])
```

- [ ] **Step 7: 테스트 통과 확인**

Run: `cd backend && python -m pytest tests/test_recurring_api.py -q`
Expected: PASS (3 passed).

- [ ] **Step 8: 커밋**

```bash
git add backend/app/api/routes/admin/recurring.py backend/app/api/router.py backend/app/services/recurring.py backend/app/repositories/orders.py backend/tests/test_recurring_api.py
git commit -m "feat(recurring): admin 라우트(계약 CRUD/라이프사이클/sync/approve/skip) + 요약 DTO"
```

---

## Task 11: 백엔드 전체 검증 + Postgres 마이그레이션 적용

**Files:** (없음 — 검증/적용 태스크)

- [ ] **Step 1: 전체 테스트**

Run: `cd backend && python -m pytest -q`
Expected: 전부 PASS. (기존 회귀 없음 — 특히 `test_role_dtos.py`.)

- [ ] **Step 2: 린트 + 컴파일**

Run: `cd backend && ruff check . && python -m compileall app tests`
Expected: 통과.

- [ ] **Step 3: 실 Postgres 마이그레이션 적용** — ⚠️ SQLite 테스트는 FK 순서 버그를 못 잡는다(메모 `sqlite-fk-not-enforced-gap`). 실 DB에서 확인.

Run (앱 DB `cleaning_ops`, 포트 8002/Postgres 5434 환경에서):
`cd backend && python -m alembic upgrade head`
Expected: `0015_recurring_contracts` 적용 성공. 실패 시 FK 생성 순서/이름을 점검.

- [ ] **Step 4: 커밋(검증 로그/변경 없으면 생략)** — 코드 변경이 없으면 커밋 없음.

---

## Task 12: 프론트엔드 API + 도메인 모듈

**Files:**
- Create: `frontend/src/api/recurring.ts`, `frontend/src/domain/recurrence.ts`

- [ ] **Step 1: API 모듈** — `frontend/src/api/recurring.ts` (기존 `apiRequest` 패턴 — `apiGet/apiPost` 없음)

```ts
import { apiRequest } from './client';

export type RecurrenceMode = 'monthly' | 'weekly';
export type RecurringContractStatus = 'active' | 'paused' | 'ended';

export interface RecurringContractInput {
  label: string;
  customer_name: string;
  customer_phone: string;
  customer_address: string;
  customer_address_detail?: string | null;
  customer_visible_payment?: boolean;
  notes?: string | null;
  recurrence_mode: RecurrenceMode;
  day_of_month?: number | null;
  interval_weeks?: number | null;
  weekday?: number | null;
  start_date: string;
  end_date?: string | null;
  max_occurrences?: number | null;
  default_partner_id?: string | null;
  team_name?: string | null;
  service_category_id?: string | null;
  service_item_id?: string | null;
  service_name: string;
  size_or_quantity?: string | null;
  service_detail?: string | null;
  special_request?: string | null;
  requested_time?: string | null;
  total_amount?: number | null;
  discount_amount?: number;
  deposit_amount?: number | null;
  balance_amount?: number | null;
  vat_type?: string | null;
  partner_payment_amount?: number | null;
}

export interface RecurringContractSummary {
  id: string;
  label: string;
  customer_name: string;
  status: RecurringContractStatus;
  schedule_text: string;
  next_due_date: string | null;
  pending_count: number;
  this_month_count: number;
  this_month_amount: number;
}

export interface RecurringContract extends RecurringContractInput {
  id: string;
  order_group_id: string;
  customer_token: string;
  status: RecurringContractStatus;
  next_due_date: string | null;
}

export interface PendingOccurrence {
  occurrence_id: string;
  contract_id: string;
  contract_label: string;
  customer_name: string;
  sequence_no: number;
  due_date: string;
  service_name: string;
  total_amount: number | null;
  default_partner_id: string | null;
  default_partner_name: string | null;
  is_overdue: boolean;
}

export interface ApproveItemInput {
  occurrence_id: string;
  partner_id?: string | null;
  scheduled_date?: string | null;
  total_amount?: number | null;
}

export function listRecurringContracts(): Promise<RecurringContractSummary[]> {
  return apiRequest('/admin/recurring/contracts') as Promise<RecurringContractSummary[]>;
}
export function getRecurringContract(id: string): Promise<RecurringContract> {
  return apiRequest(`/admin/recurring/contracts/${encodeURIComponent(id)}`) as Promise<RecurringContract>;
}
export function createRecurringContract(input: RecurringContractInput): Promise<RecurringContract> {
  return apiRequest('/admin/recurring/contracts', { method: 'POST', body: input }) as Promise<RecurringContract>;
}
export function updateRecurringContract(id: string, input: Partial<RecurringContractInput>): Promise<RecurringContract> {
  return apiRequest(`/admin/recurring/contracts/${encodeURIComponent(id)}`, { method: 'PATCH', body: input }) as Promise<RecurringContract>;
}
export function pauseRecurringContract(id: string) {
  return apiRequest(`/admin/recurring/contracts/${encodeURIComponent(id)}/pause`, { method: 'POST' });
}
export function resumeRecurringContract(id: string) {
  return apiRequest(`/admin/recurring/contracts/${encodeURIComponent(id)}/resume`, { method: 'POST' });
}
export function endRecurringContract(id: string) {
  return apiRequest(`/admin/recurring/contracts/${encodeURIComponent(id)}/end`, { method: 'POST' });
}
export function deleteRecurringContract(id: string) {
  return apiRequest(`/admin/recurring/contracts/${encodeURIComponent(id)}`, { method: 'DELETE' });
}
export function syncRecurringOccurrences(): Promise<PendingOccurrence[]> {
  return apiRequest('/admin/recurring/occurrences/sync', { method: 'POST' }) as Promise<PendingOccurrence[]>;
}
export function listPendingOccurrences(): Promise<PendingOccurrence[]> {
  return apiRequest('/admin/recurring/occurrences/pending') as Promise<PendingOccurrence[]>;
}
export function approveOccurrences(items: ApproveItemInput[]) {
  return apiRequest('/admin/recurring/occurrences/approve', { method: 'POST', body: { items } });
}
export function skipOccurrences(items: { occurrence_id: string; reason?: string }[]) {
  return apiRequest('/admin/recurring/occurrences/skip', { method: 'POST', body: { items } });
}
```

- [ ] **Step 2: 도메인 라벨 모듈** — `frontend/src/domain/recurrence.ts`

```ts
import type { RecurringContractStatus } from '../api/recurring';

export const CONTRACT_STATUS_LABEL: Record<RecurringContractStatus, string> = {
  active: '진행중',
  paused: '일시정지',
  ended: '종료',
};

export const CONTRACT_STATUS_TONE: Record<RecurringContractStatus, string> = {
  active: 'var(--success-bg, #e6f7ed)',
  paused: 'var(--warning-bg, #fff4e5)',
  ended: 'var(--neutral-bg, #eef0f3)',
};

export function formatAmount(value: number | null | undefined): string {
  if (value == null) return '-';
  return `${value.toLocaleString('ko-KR')}원`;
}
```

- [ ] **Step 3: 타입체크**

Run: `cd frontend && npm run typecheck`
Expected: 통과(아직 사용처 없음 — 미사용 export 경고만 없으면 OK).

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/api/recurring.ts frontend/src/domain/recurrence.ts
git commit -m "feat(recurring): 프론트 API/도메인 모듈"
```

---

## Task 13: 네비 탭 + 목록 페이지 + 승인 대기 패널

**Files:**
- Modify: `frontend/src/components/layout/AdminShell.tsx`, `frontend/src/app/App.tsx`
- Create: `frontend/src/features/admin/recurring/RecurringContractsPage.tsx`

- [ ] **Step 1: NAV 탭 추가** — `AdminShell.tsx`의 `NAV` 배열에서 `reports` 위(또는 `partners` 아래)에 추가.

```js
  { key: 'recurring',  label: '정기청소',     icon: 'repeat' },
```
> `icon` 값은 `components/common/ui`의 `Icon`이 지원하는 이름이어야 한다. `repeat`가 없으면 지원되는 이름(`calendar` 등)으로 교체하거나 `Icon`에 아이콘을 추가한다.

- [ ] **Step 2: App 라우팅 연결** — `App.tsx`에서 admin 페이지 분기(`page === 'partners'` 등 처리부)에 `recurring` 케이스를 추가하고 `RecurringContractsPage`를 렌더. 상세/폼 전환은 페이지 내부 상태로 처리(기존 orders 패턴 참고: `OrdersPage`가 목록/상세/폼을 내부에서 라우팅).

```jsx
// import 추가
import { RecurringContractsPage } from '../features/admin/recurring/RecurringContractsPage';
// 분기 추가 (page === 'recurring')
{page === 'recurring' && <RecurringContractsPage />}
```

- [ ] **Step 3: 목록 + 승인 패널 페이지** — `frontend/src/features/admin/recurring/RecurringContractsPage.tsx`

```jsx
import React from 'react';
import {
  approveOccurrences,
  listRecurringContracts,
  skipOccurrences,
  syncRecurringOccurrences,
  type PendingOccurrence,
  type RecurringContractSummary,
} from '../../../api/recurring';
import { CONTRACT_STATUS_LABEL, CONTRACT_STATUS_TONE, formatAmount } from '../../../domain/recurrence';
import { RecurringContractForm } from './RecurringContractForm';
import { RecurringContractDetail } from './RecurringContractDetail';

type View = { mode: 'list' } | { mode: 'create' } | { mode: 'detail'; id: string };

export function RecurringContractsPage() {
  const [view, setView] = React.useState<View>({ mode: 'list' });
  const [contracts, setContracts] = React.useState<RecurringContractSummary[] | null>(null);
  const [pending, setPending] = React.useState<PendingOccurrence[]>([]);
  const [selected, setSelected] = React.useState<Set<string>>(new Set());
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  const load = React.useCallback(async () => {
    setError(null);
    try {
      const [list, due] = await Promise.all([listRecurringContracts(), syncRecurringOccurrences()]);
      setContracts(list);
      setPending(due);
      setSelected(new Set(due.map((d) => d.occurrence_id)));
    } catch (e) {
      setError(e instanceof Error ? e.message : '불러오기에 실패했습니다.');
      setContracts([]);
    }
  }, []);

  React.useEffect(() => {
    if (view.mode === 'list') void load();
  }, [view, load]);

  if (view.mode === 'create') {
    return <RecurringContractForm onDone={() => setView({ mode: 'list' })} onCancel={() => setView({ mode: 'list' })} />;
  }
  if (view.mode === 'detail') {
    return <RecurringContractDetail contractId={view.id} onBack={() => setView({ mode: 'list' })} />;
  }

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const runApprove = async () => {
    setBusy(true);
    setError(null);
    try {
      await approveOccurrences([...selected].map((occurrence_id) => ({ occurrence_id })));
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '승인에 실패했습니다.');
    } finally {
      setBusy(false);
    }
  };

  const runSkip = async () => {
    setBusy(true);
    try {
      await skipOccurrences([...selected].map((occurrence_id) => ({ occurrence_id })));
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '건너뛰기에 실패했습니다.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>정기청소</h1>
        <button className="btn btn--primary btn--sm" style={{ marginLeft: 'auto' }}
          data-testid="recurring-create" onClick={() => setView({ mode: 'create' })}>
          + 정기계약 등록
        </button>
      </div>

      {error && <div role="alert" style={{ color: 'var(--danger, #c0392b)', marginBottom: 8 }}>{error}</div>}

      {/* 승인 대기 패널 */}
      <section style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 12, marginBottom: 16 }}>
        <h2 style={{ fontSize: 14, fontWeight: 700, margin: '0 0 8px' }}>승인 대기 회차 ({pending.length})</h2>
        {pending.length === 0 ? (
          <div style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>도래한 회차가 없습니다.</div>
        ) : (
          <>
            <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ textAlign: 'left', color: 'var(--text-tertiary)' }}>
                  <th style={{ width: 28 }} />
                  <th>계약</th><th>고객</th><th>방문일</th><th>서비스</th><th>금액</th><th>협력사</th>
                </tr>
              </thead>
              <tbody>
                {pending.map((p) => (
                  <tr key={p.occurrence_id} data-testid={`pending-${p.occurrence_id}`}>
                    <td><input type="checkbox" checked={selected.has(p.occurrence_id)} onChange={() => toggle(p.occurrence_id)} /></td>
                    <td>{p.contract_label}</td>
                    <td>{p.customer_name}</td>
                    <td style={{ color: p.is_overdue ? 'var(--danger, #c0392b)' : undefined }}>{p.due_date}</td>
                    <td>{p.service_name}</td>
                    <td>{formatAmount(p.total_amount)}</td>
                    <td>{p.default_partner_name ?? '미배정'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
              <button className="btn btn--primary btn--sm" disabled={busy || selected.size === 0}
                data-testid="recurring-approve" onClick={runApprove}>선택 승인 ({selected.size})</button>
              <button className="btn btn--ghost btn--sm" disabled={busy || selected.size === 0} onClick={runSkip}>건너뛰기</button>
            </div>
          </>
        )}
      </section>

      {/* 계약 목록 */}
      {contracts === null ? (
        <div>불러오는 중…</div>
      ) : contracts.length === 0 ? (
        <div style={{ color: 'var(--text-tertiary)' }}>등록된 정기계약이 없습니다.</div>
      ) : (
        <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ textAlign: 'left', color: 'var(--text-tertiary)' }}>
              <th>계약명</th><th>고객</th><th>주기</th><th>다음 회차</th><th>상태</th><th>이번 달</th>
            </tr>
          </thead>
          <tbody>
            {contracts.map((c) => (
              <tr key={c.id} data-testid={`contract-${c.id}`} style={{ cursor: 'pointer' }}
                onClick={() => setView({ mode: 'detail', id: c.id })}>
                <td>{c.label}</td>
                <td>{c.customer_name}</td>
                <td>{c.schedule_text}</td>
                <td>{c.next_due_date ?? '-'}</td>
                <td><span style={{ padding: '1px 8px', borderRadius: 10, background: CONTRACT_STATUS_TONE[c.status] }}>{CONTRACT_STATUS_LABEL[c.status]}</span></td>
                <td>{c.this_month_count}건 / {formatAmount(c.this_month_amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
```

> 데스크탑+모바일 768px 분기: 표가 좁은 화면에서 가로 스크롤되도록 컨테이너에 `overflow-x:auto`를 두거나, 기존 OrdersPage의 반응형 패턴을 따른다. 로딩/에러/빈 3종은 위에 모두 처리됨.

- [ ] **Step 4: 타입체크 + 빌드**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: 통과. (`RecurringContractForm`/`Detail`는 다음 태스크에서 생성 — 먼저 빈 스텁을 만들어 빌드를 통과시키려면 Task 14·15를 먼저 진행하거나, 임시 스텁 컴포넌트를 만든 뒤 교체.)

> 실행 순서 팁: 빌드 의존성 때문에 **Task 14·15(Form/Detail)를 먼저 만들고 Task 13의 빌드 확인을 마지막에** 수행해도 된다.

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/components/layout/AdminShell.tsx frontend/src/app/App.tsx frontend/src/features/admin/recurring/RecurringContractsPage.tsx
git commit -m "feat(recurring): 정기청소 탭 + 목록 + 승인 대기 패널"
```

---

## Task 14: 계약 등록/수정 폼

**Files:**
- Create: `frontend/src/features/admin/recurring/RecurringContractForm.tsx`

- [ ] **Step 1: 폼 컴포넌트** — `frontend/src/features/admin/recurring/RecurringContractForm.tsx`

```jsx
import React from 'react';
import {
  createRecurringContract,
  updateRecurringContract,
  type RecurringContractInput,
} from '../../../api/recurring';
import { listPartners } from '../../../api/admin';

const EMPTY: RecurringContractInput = {
  label: '', customer_name: '', customer_phone: '', customer_address: '',
  recurrence_mode: 'monthly', day_of_month: 10, start_date: '',
  service_name: '', discount_amount: 0,
};

export function RecurringContractForm({
  initial = null, onDone, onCancel,
}: { initial?: (RecurringContractInput & { id: string }) | null; onDone: () => void; onCancel: () => void }) {
  const [form, setForm] = React.useState<RecurringContractInput>(initial ?? EMPTY);
  const [partners, setPartners] = React.useState<{ id: string; name: string }[]>([]);
  const [error, setError] = React.useState<string | null>(null);
  const [saving, setSaving] = React.useState(false);

  React.useEffect(() => {
    void listPartners().then((rows: any[]) => setPartners(rows.map((p) => ({ id: p.id, name: p.name }))));
  }, []);

  const set = <K extends keyof RecurringContractInput>(k: K, v: RecurringContractInput[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  // weekday는 start_date에서 자동 동기화(설계 §10.1)
  React.useEffect(() => {
    if (form.recurrence_mode === 'weekly' && form.start_date) {
      const wd = (new Date(form.start_date).getDay() + 6) % 7; // JS 일=0 → 월=0 규약 변환
      if (form.weekday !== wd) set('weekday', wd);
    }
  }, [form.recurrence_mode, form.start_date]); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload: RecurringContractInput = {
        ...form,
        day_of_month: form.recurrence_mode === 'monthly' ? form.day_of_month : null,
        interval_weeks: form.recurrence_mode === 'weekly' ? form.interval_weeks ?? 1 : null,
      };
      if (initial) await updateRecurringContract(initial.id, payload);
      else await createRecurringContract(payload);
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : '저장에 실패했습니다.');
    } finally {
      setSaving(false);
    }
  };

  const input = { fontSize: 16, padding: '8px 10px', border: '1px solid var(--border)', borderRadius: 6, width: '100%' };

  return (
    <div style={{ padding: 16, maxWidth: 640 }}>
      <h1 style={{ fontSize: 18, fontWeight: 700 }}>{initial ? '정기계약 수정' : '정기계약 등록'}</h1>
      {initial && <p style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>고객정보 수정은 이 계약의 모든 회차(기존 주문 포함 그룹)에 반영됩니다.</p>}
      {error && <div role="alert" style={{ color: 'var(--danger, #c0392b)' }}>{error}</div>}

      <div style={{ display: 'grid', gap: 10, marginTop: 12 }}>
        <label>계약명<input style={input} value={form.label} onChange={(e) => set('label', e.target.value)} data-testid="rc-label" /></label>
        <label>고객명<input style={input} value={form.customer_name} onChange={(e) => set('customer_name', e.target.value)} data-testid="rc-customer-name" /></label>
        <label>연락처<input style={input} value={form.customer_phone} onChange={(e) => set('customer_phone', e.target.value)} data-testid="rc-customer-phone" /></label>
        <label>주소<input style={input} value={form.customer_address} onChange={(e) => set('customer_address', e.target.value)} /></label>

        <label>주기
          <select style={input} value={form.recurrence_mode} onChange={(e) => set('recurrence_mode', e.target.value as any)} data-testid="rc-mode">
            <option value="monthly">매월 (지정일)</option>
            <option value="weekly">주간 (N주마다)</option>
          </select>
        </label>
        {form.recurrence_mode === 'monthly' ? (
          <label>매월 며칠<input style={input} type="number" min={1} max={31} value={form.day_of_month ?? 10} onChange={(e) => set('day_of_month', Number(e.target.value))} /></label>
        ) : (
          <label>간격(주)
            <select style={input} value={form.interval_weeks ?? 1} onChange={(e) => set('interval_weeks', Number(e.target.value))}>
              <option value={1}>매주</option><option value={2}>격주</option><option value={4}>4주마다</option>
            </select>
          </label>
        )}
        <label>시작일<input style={input} type="date" value={form.start_date} onChange={(e) => set('start_date', e.target.value)} data-testid="rc-start-date" /></label>

        <label>서비스명<input style={input} value={form.service_name} onChange={(e) => set('service_name', e.target.value)} data-testid="rc-service-name" /></label>
        <label>1주기 금액<input style={input} type="number" value={form.total_amount ?? ''} onChange={(e) => set('total_amount', e.target.value === '' ? null : Number(e.target.value))} data-testid="rc-amount" /></label>
        <label>기본 협력사(선택)
          <select style={input} value={form.default_partner_id ?? ''} onChange={(e) => set('default_partner_id', e.target.value || null)}>
            <option value="">미지정</option>
            {partners.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>
      </div>

      <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
        <button className="btn btn--primary" disabled={saving} onClick={submit} data-testid="rc-submit">저장</button>
        <button className="btn btn--ghost" disabled={saving} onClick={onCancel}>취소</button>
      </div>
    </div>
  );
}
```

> input `font-size:16px`(iOS 줌 방지). 필요한 템플릿 필드(요청시간/특이사항/부가세 등)는 동일 패턴으로 추가 가능.

- [ ] **Step 2: 타입체크**

Run: `cd frontend && npm run typecheck`
Expected: 통과.

- [ ] **Step 3: 커밋**

```bash
git add frontend/src/features/admin/recurring/RecurringContractForm.tsx
git commit -m "feat(recurring): 정기계약 등록/수정 폼"
```

---

## Task 15: 계약 상세

**Files:**
- Create: `frontend/src/features/admin/recurring/RecurringContractDetail.tsx`

- [ ] **Step 1: 상세 컴포넌트** — `frontend/src/features/admin/recurring/RecurringContractDetail.tsx`

```jsx
import React from 'react';
import {
  deleteRecurringContract,
  getRecurringContract,
  pauseRecurringContract,
  resumeRecurringContract,
  endRecurringContract,
  updateRecurringContract,
  type RecurringContract,
} from '../../../api/recurring';
import { CONTRACT_STATUS_LABEL, formatAmount } from '../../../domain/recurrence';
import { RecurringContractForm } from './RecurringContractForm';

export function RecurringContractDetail({ contractId, onBack }: { contractId: string; onBack: () => void }) {
  const [contract, setContract] = React.useState<RecurringContract | null>(null);
  const [editing, setEditing] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    setError(null);
    try {
      setContract(await getRecurringContract(contractId));
    } catch (e) {
      setError(e instanceof Error ? e.message : '불러오기에 실패했습니다.');
    }
  }, [contractId]);

  React.useEffect(() => { void load(); }, [load]);

  if (error) return <div style={{ padding: 16 }}><button onClick={onBack}>← 목록</button><div role="alert" style={{ color: 'var(--danger,#c0392b)' }}>{error}</div></div>;
  if (!contract) return <div style={{ padding: 16 }}>불러오는 중…</div>;
  if (editing) {
    return (
      <RecurringContractForm
        initial={{ ...contract }}
        onDone={() => { setEditing(false); void load(); }}
        onCancel={() => setEditing(false)}
      />
    );
  }

  const act = async (fn: () => Promise<unknown>) => {
    try { await fn(); await load(); } catch (e) { setError(e instanceof Error ? e.message : '처리 실패'); }
  };

  return (
    <div style={{ padding: 16, maxWidth: 720 }}>
      <button className="btn btn--ghost btn--sm" onClick={onBack}>← 목록</button>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '8px 0' }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, margin: 0 }} data-testid="rc-detail-label">{contract.label}</h1>
        <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{CONTRACT_STATUS_LABEL[contract.status]}</span>
        <button className="btn btn--ghost btn--sm" style={{ marginLeft: 'auto' }} onClick={() => setEditing(true)}>수정</button>
      </div>

      <dl style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 6, fontSize: 13 }}>
        <dt>고객</dt><dd>{contract.customer_name} ({contract.customer_phone})</dd>
        <dt>주소</dt><dd>{contract.customer_address}</dd>
        <dt>서비스</dt><dd>{contract.service_name}</dd>
        <dt>1주기 금액</dt><dd>{formatAmount(contract.total_amount ?? null)}</dd>
        <dt>다음 회차</dt><dd>{contract.next_due_date ?? '-'}</dd>
        <dt>고객 링크</dt><dd>/c/{contract.customer_token}</dd>
      </dl>

      <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
        {contract.status === 'active' && <button className="btn btn--ghost btn--sm" onClick={() => act(() => pauseRecurringContract(contract.id))}>일시정지</button>}
        {contract.status === 'paused' && <button className="btn btn--ghost btn--sm" onClick={() => act(() => resumeRecurringContract(contract.id))}>재개</button>}
        {contract.status !== 'ended' && <button className="btn btn--ghost btn--sm" onClick={() => act(() => endRecurringContract(contract.id))}>종료</button>}
        <button className="btn btn--ghost btn--sm" style={{ color: 'var(--danger,#c0392b)' }}
          onClick={() => act(async () => { await deleteRecurringContract(contract.id); onBack(); })}>삭제</button>
      </div>
      <p style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 8 }}>
        삭제해도 이미 생성된 주문은 주문관리에 보존됩니다.
      </p>
    </div>
  );
}
```

> `updateRecurringContract` import는 폼 경유로 사용되므로 직접 호출이 없으면 제거(미사용 import 린트 회피). 위 코드에서 실제 미사용이면 import에서 빼라.

- [ ] **Step 2: 타입체크 + 빌드(Task 13 빌드 포함 마무리)**

Run: `cd frontend && npm run typecheck && npm run lint && npm run build`
Expected: 통과.

- [ ] **Step 3: 커밋**

```bash
git add frontend/src/features/admin/recurring/RecurringContractDetail.tsx
git commit -m "feat(recurring): 정기계약 상세 + 라이프사이클 액션"
```

---

## Task 16: 주문에 '정기' 배지

**Files:**
- Modify: `frontend/src/features/admin/orders/OrderDetailPage.tsx` (+ 목록 `OrdersPage.tsx` 선택)

- [ ] **Step 1: 주문 상세에 배지** — `OrderDetailPage.tsx`에서 주문 데이터에 `recurring_contract_id`가 있으면 제목/상단에 배지 표시. (`AdminOrder` 타입에 `recurring_contract_id?` 가 Task 6의 백엔드 DTO 추가로 내려옴 — 프론트 `admin.ts`의 `AdminOrder`/`AdminOrderLineInput`에 `recurring_contract_id?: string | null` 도 추가.)

`frontend/src/api/admin.ts`의 `AdminOrder` 인터페이스에 추가:
```ts
  recurring_contract_id?: string | null;
```
`OrderDetailPage.tsx` 제목 옆에 조건부 배지:
```jsx
{order.recurring_contract_id && (
  <span data-testid="order-recurring-badge"
    style={{ fontSize: 11, fontWeight: 700, padding: '1px 8px', borderRadius: 10, background: 'var(--brand-bg)', color: 'var(--brand)' }}>
    정기
  </span>
)}
```

- [ ] **Step 2: 타입체크 + 빌드**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: 통과.

- [ ] **Step 3: 커밋**

```bash
git add frontend/src/api/admin.ts frontend/src/features/admin/orders/OrderDetailPage.tsx
git commit -m "feat(recurring): 주문 상세에 정기 배지"
```

---

## Task 17: E2E + 최종 검증

**Files:**
- Create: `frontend/e2e/recurring.spec.ts`

- [ ] **Step 1: E2E 작성** — `frontend/e2e/recurring.spec.ts` (기존 e2e 로그인 헬퍼/패턴을 따른다. 아래는 핵심 시나리오 골격.)

```ts
import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './helpers'; // 기존 e2e 헬퍼 경로에 맞게 조정

test('정기계약 생성 → 승인 대기 → 승인하면 주문 생성', async ({ page }) => {
  await loginAsAdmin(page);
  await page.getByTestId('admin-nav-recurring').click();

  await page.getByTestId('recurring-create').click();
  await page.getByTestId('rc-label').fill('E2E 정기');
  await page.getByTestId('rc-customer-name').fill('E2E 고객');
  await page.getByTestId('rc-customer-phone').fill('01099998888');
  await page.getByTestId('rc-service-name').fill('E2E 청소');
  await page.getByTestId('rc-amount').fill('100000');
  // 과거 시작일 → sync 시 도래분 발생
  await page.getByTestId('rc-start-date').fill('2026-06-10');
  await page.getByTestId('rc-submit').click();

  // 목록 복귀 후 승인 패널에 도래분이 보이면 승인
  await expect(page.getByText('승인 대기 회차')).toBeVisible();
});
```

> E2E 환경은 SQLite 시드 + 격리 포트(5176/8003). 시작일/grace에 따라 도래분이 0일 수 있으므로, 도래분이 보장되도록 `rc-start-date`를 "오늘과 같은 달 1일"처럼 동적으로 채우거나, 본 테스트는 "탭 진입 + 계약 생성 + 패널 렌더"까지만 단언하고 승인 단언은 서비스/통합 테스트에 위임한다.

- [ ] **Step 2: E2E 실행**

Run: `cd frontend && npm run e2e -- recurring.spec.ts`
Expected: PASS.

- [ ] **Step 3: 백엔드/프론트 전체 검증**

Run:
```
cd backend && python -m pytest -q && ruff check .
cd ../frontend && npm run typecheck && npm run lint && npm run build
```
Expected: 전부 통과.

- [ ] **Step 4: 커밋 + `.master/next_session_plan.md` 갱신**

```bash
git add frontend/e2e/recurring.spec.ts
git commit -m "test(recurring): 정기청소 E2E + 최종 검증"
```
`.master/next_session_plan.md`에 "정기청소 A 완료, B(월 합산 청구·정산) 다음 사이클" 한 줄 기록(사용자 요청 시).

---

## Self-Review (작성자 체크리스트 결과)

**1. Spec coverage** — 설계 문서 대비:
- §1 데이터 모델 → Task 1·2·3 ✅
- §2 스케줄 계산 → Task 1 ✅
- §3 sync/approve/skip → Task 8·9 ✅
- §4 라이프사이클(빈 그룹 선제 생성·수정 미래반영·PAUSED·소프트삭제) → Task 6·7 ✅
- §5 레이어/엔드포인트/DTO 화이트리스트 → Task 4·5·6·10 ✅
- §6 프론트(탭·목록·승인패널·폼·상세·배지) → Task 13~16 ✅
- §7 B 연결고리(recurring_contract_id·billing_month) → Task 2·8 ✅
- §8 테스트 → 각 Task의 테스트 + Task 17 ✅
- **갭/후속**: 설계 §3.1.6 "스케줄 변경 시 무효 PENDING 정리"는 v1에서 미구현(운영자 skip으로 대체). **후속 개선**으로 남김(아래 명시). 설계 §10.4 메시지 자동발송은 범위 밖(미구현, 의도된 제외).

**2. Placeholder scan** — "TBD/TODO/적절히 처리" 없음. 모든 코드 스텝에 실제 코드 포함. 일부 "실제 필드명 확인" 주석은 기존 스키마와의 정합을 위한 **검증 지시**이며 구현 공백이 아님.

**3. Type consistency** — 서비스/스키마/라우트 시그니처 일치 확인:
- `approve_occurrences(items: list[ApproveItem]) -> ApproveOccurrencesResult` (Task 9 정의 = Task 10 라우트 호출) ✅
- `to_contract_read` / `list_contract_summaries` / `list_pending_views` (Task 10 Step 4에서 정의, 라우트에서 호출) ✅
- `create_empty_group` / `add_recurring_line` (Task 6 정의 = Task 7·9 호출) ✅
- 프론트 `RecurringContractInput`/`Summary`/`PendingOccurrence` 필드 = 백엔드 DTO 필드명 일치 ✅

**알려진 실행 주의(구현자에게):**
- Task 13의 빌드는 Task 14·15(Form/Detail) 생성 후 통과한다 — 실행 순서를 13→14→15→(13빌드확인) 또는 14·15 먼저.
- `OrderLineCreate` 필드명/필수값은 `schemas/order.py` 실제 정의에 맞춰 Task 6·9의 호출 인자를 조정한다.
- 마이그레이션은 SQLite 테스트로 검증되지 않으므로 **Task 11 Step 3의 실 Postgres 적용이 완료 기준**이다.
- `to_admin_order_dto`가 화이트리스트 dict를 직접 구성하는 구조면 `recurring_contract_id`를 명시 추가하고, 협력사/고객 DTO에는 넣지 않는다(Task 6 Step 4).

---
