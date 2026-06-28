# 정기청소 서브시스템 B (월 합산 청구·정산) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A가 만든 정기 주문을 (계약, 월) 단위로 집계해 고객 청구·협력사 정산을 조회하고, 월 단위 일괄 입금/정산 마킹 + CSV 내보내기를 제공한다.

**Architecture:** 새 테이블 없는 **파생 집계**. 대상 = `Order.recurring_contract_id` + `scheduled_date`의 월(취소/삭제 제외). 집계는 순수 함수(`domain/recurring_billing.py`, `Decimal`), 일괄 액션은 기존 `OrderService.update`(입금)·`PartnerSettlementService.settle`(정산)·`OrderExportService`(CSV)를 재사용한다. 매출/미정산 정의는 `domain/order_metrics`·`partner_settlements`의 단일 출처를 그대로 import.

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy 2.0 / Pydantic / pytest (backend), Vite + React 19 + TS / plain CSS / Playwright (frontend).

**설계 출처:** `docs/superpowers/specs/2026-06-28-recurring-billing-B-design.md`. 작업 브랜치: `feature/recurring-billing`(main=A에서 분기, 별도 worktree `design_handoff_cleaning_ops-B`). **마이그레이션 없음.**

**전제 규칙:** `AGENTS.md`(매출=`REVENUE_STATUSES` 합·미정산=`unpaid_partner_condition`·정산 가드=`is_unpaid_partner_order`·집계는 Python/Decimal·역할 DTO 화이트리스트·타임라인) · `.claude/rules/*`.

---

## File Structure

**Backend (create):**
- `backend/app/domain/recurring_billing.py` — 순수 집계(주문 목록 → 집계 dataclass)
- `backend/app/schemas/recurring_billing.py` — DTO
- `backend/app/services/recurring_billing.py` — `RecurringBillingService`
- `backend/app/api/routes/admin/recurring_billing.py` — 라우트
- `backend/tests/test_recurring_billing_aggregate.py`, `test_recurring_billing_service.py`, `test_recurring_billing_api.py`

**Backend (modify):**
- `backend/app/repositories/orders.py` — 월 청구용 조회 메서드 추가(취소 제외·전 계약)
- `backend/app/api/router.py` — 라우터 등록

**Frontend (create):**
- `frontend/src/api/recurringBilling.ts` — 호출 + 타입
- `frontend/src/features/admin/recurring/RecurringBillingView.tsx` — 월 정산 뷰

**Frontend (modify):**
- `frontend/src/features/admin/recurring/RecurringContractsPage.tsx` 또는 `App.tsx` — 정기청소 영역에 `계약/월 정산` 탭

---

## Task 1: OrderRepository — 월 청구 대상 주문 조회

**Files:**
- Modify: `backend/app/repositories/orders.py`
- Test: `backend/tests/test_recurring_billing_repo.py`

기존 `list_recurring_orders_in_month(contract_id, billing_month)`는 A 요약이 쓰므로 **시그니처 보존**하고, B용 메서드를 신설한다(취소 제외 + 전 계약 옵션 + 관계 로딩).

- [ ] **Step 1: 실패 테스트** — `backend/tests/test_recurring_billing_repo.py`

```python
from datetime import date
from uuid import uuid4

from app.domain.constants import OrderStatus
from app.models.order import Order
from app.models.order_group import OrderGroup
from app.repositories.orders import OrderRepository


def _order(db, *, contract_id, scheduled, status=OrderStatus.COMPLETED, deleted=False):
    group = OrderGroup(
        id=str(uuid4()), customer_token=f"t-{uuid4()}", customer_name="C",
        customer_phone="01000000000", customer_address="A", customer_visible_payment=False,
    )
    db.add(group)
    db.flush()
    o = Order(
        id=str(uuid4()), group_id=group.id, status=status, received_date=date(2026, 6, 1),
        scheduled_date=scheduled, service_name="S", recurring_contract_id=contract_id,
        customer_token=group.customer_token, customer_name="C", customer_phone="01000000000",
        customer_address="A",
    )
    if deleted:
        from app.core.time import utc_now
        o.deleted_at = utc_now()
    db.add(o)
    db.flush()
    return o


def test_list_billing_orders_filters_month_contract_and_excludes_cancelled_deleted(db_session):
    repo = OrderRepository(db_session)
    keep = _order(db_session, contract_id="c1", scheduled=date(2026, 6, 10))
    _order(db_session, contract_id="c1", scheduled=date(2026, 7, 10))  # 다른 달
    _order(db_session, contract_id="c2", scheduled=date(2026, 6, 10))  # 다른 계약
    _order(db_session, contract_id="c1", scheduled=date(2026, 6, 11), status=OrderStatus.CANCELLED)  # 취소
    _order(db_session, contract_id="c1", scheduled=date(2026, 6, 12), deleted=True)  # 삭제

    rows = repo.list_recurring_billing_orders(month="2026-06", contract_id="c1")
    assert [o.id for o in rows] == [keep.id]


def test_list_billing_orders_all_contracts(db_session):
    repo = OrderRepository(db_session)
    a = _order(db_session, contract_id="c1", scheduled=date(2026, 6, 10))
    b = _order(db_session, contract_id="c2", scheduled=date(2026, 6, 10))
    rows = repo.list_recurring_billing_orders(month="2026-06", contract_id=None)
    assert {o.id for o in rows} == {a.id, b.id}
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python -m pytest tests/test_recurring_billing_repo.py -q`
Expected: FAIL — `AttributeError: ... 'list_recurring_billing_orders'`.

- [ ] **Step 3: 구현** — `backend/app/repositories/orders.py`에 메서드 추가(상단에 `from app.domain.constants import OrderStatus` 가 없으면 추가; 이미 있으면 재사용).

```python
    def list_recurring_billing_orders(
        self, *, month: str, contract_id: str | None = None
    ) -> list[Order]:
        """월 청구·정산 집계 대상 정기 주문. scheduled_date의 월 기준, 취소/삭제 제외.

        month: "YYYY-MM". contract_id=None이면 전 계약.
        """
        from sqlalchemy import select

        stmt = select(Order).where(
            Order.recurring_contract_id.is_not(None),
            Order.deleted_at.is_(None),
            Order.status != OrderStatus.CANCELLED,
            Order.scheduled_date.is_not(None),
        )
        if contract_id is not None:
            stmt = stmt.where(Order.recurring_contract_id == contract_id)
        rows = list(self.db.scalars(stmt.order_by(Order.scheduled_date.asc(), Order.id.asc())))
        # scheduled_date 월 필터는 dialect 무관하게 Python으로(.claude/rules + AGENTS 집계 규칙)
        return [o for o in rows if o.scheduled_date.strftime("%Y-%m") == month]
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && python -m pytest tests/test_recurring_billing_repo.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: 커밋**

```bash
git add backend/app/repositories/orders.py backend/tests/test_recurring_billing_repo.py
git commit -m "feat(billing): 월 청구 대상 정기 주문 조회(취소/삭제 제외)"
```

---

## Task 2: 순수 집계 (domain/recurring_billing.py)

**Files:**
- Create: `backend/app/domain/recurring_billing.py`
- Test: `backend/tests/test_recurring_billing_aggregate.py`

- [ ] **Step 1: 실패 테스트** — `backend/tests/test_recurring_billing_aggregate.py`

```python
from decimal import Decimal
from types import SimpleNamespace

from app.domain.constants import OrderStatus
from app.domain.payment_status import PartnerPaymentStatus, PaymentStatus
from app.domain.recurring_billing import aggregate_orders


def _o(**kw):
    base = dict(
        status=OrderStatus.COMPLETED, total_amount=Decimal("100000"), onsite_extra_amount=None,
        payment_status=PaymentStatus.PAID, partner_id="p1", partner_payment_amount=Decimal("60000"),
        partner_payment_status=PartnerPaymentStatus.PAID, deleted_at=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_aggregate_customer_and_partner_sides():
    orders = [
        _o(status=OrderStatus.COMPLETED, payment_status=PaymentStatus.PAID,
           partner_payment_status=PartnerPaymentStatus.PAID),
        _o(status=OrderStatus.CUSTOMER_DELIVERY_DONE, payment_status=PaymentStatus.UNPAID,
           partner_payment_status=PartnerPaymentStatus.UNPAID),
        _o(status=OrderStatus.IN_PROGRESS, payment_status=PaymentStatus.PENDING,
           partner_payment_status=None),  # 미완 → 확정매출 X, 정산 가능 X
    ]
    agg = aggregate_orders(orders)
    assert agg.visit_count == 3
    assert agg.billed_total == Decimal("300000")
    # 확정 매출 = 전달완료/완료 2건
    assert agg.confirmed_revenue == Decimal("200000")
    # 미입금 고객 = UNPAID/PENDING 2건
    assert agg.unpaid_customer_count == 2
    assert agg.partner_total == Decimal("180000")
    # 미정산(정산 가능 = COMPLETED+미정산): 2번째는 전달완료라 settleable 아님, 3번째는 미완.
    # → 정산 가능 0, 미정산 합계 0
    assert agg.unpaid_partner_count == 0
    assert agg.unpaid_partner_total == Decimal("0")


def test_partner_subtotals_group_by_partner():
    orders = [
        _o(partner_id="p1", partner_payment_amount=Decimal("60000"),
           status=OrderStatus.COMPLETED, partner_payment_status=PartnerPaymentStatus.UNPAID),
        _o(partner_id="p2", partner_payment_amount=Decimal("50000"),
           status=OrderStatus.COMPLETED, partner_payment_status=PartnerPaymentStatus.PAID),
    ]
    agg = aggregate_orders(orders)
    subs = {s.partner_id: s for s in agg.partner_subtotals}
    assert subs["p1"].partner_total == Decimal("60000")
    assert subs["p1"].settleable_count == 1  # COMPLETED + UNPAID
    assert subs["p1"].unpaid_partner_total == Decimal("60000")
    assert subs["p2"].settleable_count == 0  # 이미 PAID
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python -m pytest tests/test_recurring_billing_aggregate.py -q`
Expected: FAIL — `ModuleNotFoundError: app.domain.recurring_billing`.

- [ ] **Step 3: 구현** — `backend/app/domain/recurring_billing.py`

```python
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.order_metrics import REVENUE_STATUSES, SETTLEABLE_ORDER_STATUSES
from app.domain.order_pricing import order_consumer_total
from app.domain.payment_status import PARTNER_SETTLEMENT_PENDING_STATUSES, PAYMENT_CHECK_STATUSES


def _is_settleable(order) -> bool:
    # is_unpaid_partner_order와 동일 정의(서비스완료 + 미정산). 순수 함수라 model import 없이 status 비교.
    return order.status in SETTLEABLE_ORDER_STATUSES and (
        order.partner_payment_status is None
        or order.partner_payment_status in PARTNER_SETTLEMENT_PENDING_STATUSES
    )


@dataclass(frozen=True)
class PartnerSubtotal:
    partner_id: str | None
    partner_total: Decimal
    unpaid_partner_total: Decimal
    settleable_count: int


@dataclass(frozen=True)
class BillingAggregate:
    visit_count: int
    billed_total: Decimal
    confirmed_revenue: Decimal
    unpaid_customer_count: int
    payment_breakdown: dict[str, int]
    partner_total: Decimal
    unpaid_partner_total: Decimal
    unpaid_partner_count: int
    partner_subtotals: list[PartnerSubtotal] = field(default_factory=list)


def aggregate_orders(orders: Iterable) -> BillingAggregate:
    orders = list(orders)
    billed_total = sum((order_consumer_total(o) for o in orders), Decimal("0"))
    confirmed_revenue = sum(
        (order_consumer_total(o) for o in orders if o.status in REVENUE_STATUSES), Decimal("0")
    )
    unpaid_customer_count = sum(1 for o in orders if o.payment_status in PAYMENT_CHECK_STATUSES)
    payment_breakdown: dict[str, int] = {}
    for o in orders:
        key = str(o.payment_status) if o.payment_status is not None else "none"
        payment_breakdown[key] = payment_breakdown.get(key, 0) + 1

    partner_total = sum((Decimal(str(o.partner_payment_amount or 0)) for o in orders), Decimal("0"))
    settleable = [o for o in orders if _is_settleable(o)]
    unpaid_partner_total = sum(
        (Decimal(str(o.partner_payment_amount or 0)) for o in settleable), Decimal("0")
    )

    # 협력사별 소계
    by_partner: dict[str | None, list] = {}
    for o in orders:
        by_partner.setdefault(o.partner_id, []).append(o)
    subtotals = []
    for partner_id, group in by_partner.items():
        g_settleable = [o for o in group if _is_settleable(o)]
        subtotals.append(
            PartnerSubtotal(
                partner_id=partner_id,
                partner_total=sum((Decimal(str(o.partner_payment_amount or 0)) for o in group), Decimal("0")),
                unpaid_partner_total=sum(
                    (Decimal(str(o.partner_payment_amount or 0)) for o in g_settleable), Decimal("0")
                ),
                settleable_count=len(g_settleable),
            )
        )

    return BillingAggregate(
        visit_count=len(orders),
        billed_total=billed_total,
        confirmed_revenue=confirmed_revenue,
        unpaid_customer_count=unpaid_customer_count,
        payment_breakdown=payment_breakdown,
        partner_total=partner_total,
        unpaid_partner_total=unpaid_partner_total,
        unpaid_partner_count=len(settleable),
        partner_subtotals=subtotals,
    )
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && python -m pytest tests/test_recurring_billing_aggregate.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: 커밋**

```bash
git add backend/app/domain/recurring_billing.py backend/tests/test_recurring_billing_aggregate.py
git commit -m "feat(billing): 월 청구·정산 순수 집계(매출/미정산 정의 일관)"
```

---

## Task 3: 스키마

**Files:**
- Create: `backend/app/schemas/recurring_billing.py`
- Test: (Task 5 API 테스트에서 검증)

- [ ] **Step 1: 구현** — `backend/app/schemas/recurring_billing.py`

```python
from pydantic import Field

from app.schemas.common import ApiModel


class PartnerSubtotalRead(ApiModel):
    partner_id: str | None = None
    partner_name: str | None = None
    partner_total: float
    unpaid_partner_total: float
    settleable_count: int


class RecurringBillingRowRead(ApiModel):
    contract_id: str
    label: str
    customer_name: str
    month: str
    visit_count: int
    billed_total: float
    confirmed_revenue: float
    unpaid_customer_count: int
    payment_breakdown: dict[str, int]
    partner_total: float
    unpaid_partner_total: float
    unpaid_partner_count: int
    partner_subtotals: list[PartnerSubtotalRead]


class MarkPaidRequest(ApiModel):
    contract_id: str
    month: str = Field(pattern=r"^\d{4}-\d{2}$")


class MarkPaidResult(ApiModel):
    updated_order_ids: list[str]
    skipped_count: int


class SettleMonthRequest(ApiModel):
    contract_id: str
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    partner_id: str | None = None


class SettleMonthResult(ApiModel):
    settled_order_ids: list[str]
    skipped_count: int
```

- [ ] **Step 2: 컴파일 확인**

Run: `cd backend && python -c "import app.schemas.recurring_billing"`
Expected: 출력 없음(성공).

- [ ] **Step 3: 커밋**

```bash
git add backend/app/schemas/recurring_billing.py
git commit -m "feat(billing): 월 청구·정산 DTO(admin 전용)"
```

---

## Task 4: RecurringBillingService

**Files:**
- Create: `backend/app/services/recurring_billing.py`
- Test: `backend/tests/test_recurring_billing_service.py`

서비스는 집계(Task 2) + 조회(Task 1) + 기존 액션 서비스(`OrderService.update`, `PartnerSettlementService.settle`, `OrderExportService`)를 조합한다.

- [ ] **Step 1: 실패 테스트** — `backend/tests/test_recurring_billing_service.py`

```python
from datetime import date

from app.db.seed import DEV_PARTNER_ID
from app.domain.constants import OrderStatus
from app.domain.payment_status import PartnerPaymentStatus, PaymentStatus
from app.repositories.orders import OrderRepository
from app.schemas.recurring import RecurringContractCreate
from app.services.recurring import RecurringService
from app.services.recurring_billing import RecurringBillingService


def _contract_with_order(db, *, status, payment_status, partner_payment_status, partner_id=DEV_PARTNER_ID):
    rsvc = RecurringService(db)
    c = rsvc.create_contract(
        RecurringContractCreate(
            label="L", customer_name="강남", customer_phone="01011112222", customer_address="A",
            recurrence_mode="monthly", day_of_month=10, start_date=date(2026, 6, 10),
            service_name="청소", total_amount=100000, partner_payment_amount=60000,
        ),
        actor_user_id=None,
    )
    rsvc.sync_due_occurrences(today=date(2026, 6, 20))
    occ = rsvc.occurrences.list_by_contract(c.id)[0]
    from app.schemas.recurring import ApproveItem
    res = rsvc.approve_occurrences([ApproveItem(occurrence_id=occ.id)], actor_user_id=None)
    order = OrderRepository(db).get(res.generated_order_ids[0])
    order.status = status
    order.payment_status = payment_status
    order.partner_payment_status = partner_payment_status
    order.partner_id = partner_id
    db.commit()
    return c, order


def test_month_summary_aggregates_per_contract(db_session):
    c, order = _contract_with_order(
        db_session, status=OrderStatus.COMPLETED, payment_status=PaymentStatus.PAID,
        partner_payment_status=PartnerPaymentStatus.UNPAID,
    )
    rows = RecurringBillingService(db_session).month_summary("2026-06")
    row = next(r for r in rows if r.contract_id == c.id)
    assert row.visit_count == 1
    assert row.billed_total == 100000
    assert row.confirmed_revenue == 100000
    assert row.partner_total == 60000
    assert row.unpaid_partner_count == 1  # COMPLETED + UNPAID


def test_mark_month_paid_sets_unpaid_orders_to_paid(db_session):
    c, order = _contract_with_order(
        db_session, status=OrderStatus.COMPLETED, payment_status=PaymentStatus.UNPAID,
        partner_payment_status=PartnerPaymentStatus.PAID,
    )
    res = RecurringBillingService(db_session).mark_month_paid(c.id, "2026-06", actor_user_id="admin")
    assert order.id in res.updated_order_ids
    db_session.refresh(order)
    assert order.payment_status == PaymentStatus.PAID


def test_settle_month_only_completed_unpaid(db_session):
    c, order = _contract_with_order(
        db_session, status=OrderStatus.COMPLETED, payment_status=PaymentStatus.PAID,
        partner_payment_status=PartnerPaymentStatus.UNPAID,
    )
    res = RecurringBillingService(db_session).settle_month(c.id, "2026-06", actor_user_id="admin")
    assert order.id in res.settled_order_ids
    db_session.refresh(order)
    assert order.partner_payment_status == PartnerPaymentStatus.PAID
    assert order.partner_settled_at is not None


def test_settle_month_skips_incomplete(db_session):
    c, order = _contract_with_order(
        db_session, status=OrderStatus.IN_PROGRESS, payment_status=PaymentStatus.PAID,
        partner_payment_status=PartnerPaymentStatus.UNPAID,
    )
    res = RecurringBillingService(db_session).settle_month(c.id, "2026-06", actor_user_id="admin")
    assert res.settled_order_ids == []
    assert res.skipped_count == 1
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python -m pytest tests/test_recurring_billing_service.py -q`
Expected: FAIL — `ModuleNotFoundError: app.services.recurring_billing`.

- [ ] **Step 3: 구현** — `backend/app/services/recurring_billing.py`

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.payment_status import PaymentStatus
from app.domain.recurring_billing import aggregate_orders
from app.repositories.orders import OrderRepository
from app.repositories.partners import PartnerRepository
from app.repositories.recurring import RecurringContractRepository
from app.schemas.order import OrderUpdate
from app.schemas.recurring_billing import (
    MarkPaidResult,
    PartnerSubtotalRead,
    RecurringBillingRowRead,
    SettleMonthResult,
)
from app.services.order_export import OrderExportService
from app.services.orders import OrderService
from app.services.partner_settlements import PartnerSettlementService, is_unpaid_partner_order

_ALREADY_PAID = (PaymentStatus.PAID, PaymentStatus.REFUNDED)


class RecurringBillingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.orders = OrderRepository(db)
        self.contracts = RecurringContractRepository(db)
        self.partners = PartnerRepository(db)

    def month_summary(self, month: str) -> list[RecurringBillingRowRead]:
        all_orders = self.orders.list_recurring_billing_orders(month=month, contract_id=None)
        by_contract: dict[str, list] = {}
        for o in all_orders:
            by_contract.setdefault(o.recurring_contract_id, []).append(o)

        rows: list[RecurringBillingRowRead] = []
        for contract_id, orders in by_contract.items():
            contract = self.contracts.get(contract_id)
            if contract is None:  # soft-deleted 계약은 제외
                continue
            group = self.orders.db.get(type(orders[0].__class__), None)  # noqa: 사용 안 함(아래 group 직접 로딩)
            agg = aggregate_orders(orders)
            rows.append(self._to_row(contract, month, agg))
        rows.sort(key=lambda r: r.label)
        return rows

    def _to_row(self, contract, month: str, agg) -> RecurringBillingRowRead:
        from app.repositories.order_groups import OrderGroupRepository

        grp = OrderGroupRepository(self.db).get(contract.order_group_id)
        partner_names = {
            s.partner_id: (self.partners.get(s.partner_id).name if s.partner_id and self.partners.get(s.partner_id) else None)
            for s in agg.partner_subtotals
        }
        return RecurringBillingRowRead(
            contract_id=contract.id,
            label=contract.label,
            customer_name=grp.customer_name if grp else "",
            month=month,
            visit_count=agg.visit_count,
            billed_total=float(agg.billed_total),
            confirmed_revenue=float(agg.confirmed_revenue),
            unpaid_customer_count=agg.unpaid_customer_count,
            payment_breakdown=agg.payment_breakdown,
            partner_total=float(agg.partner_total),
            unpaid_partner_total=float(agg.unpaid_partner_total),
            unpaid_partner_count=agg.unpaid_partner_count,
            partner_subtotals=[
                PartnerSubtotalRead(
                    partner_id=s.partner_id,
                    partner_name=partner_names.get(s.partner_id),
                    partner_total=float(s.partner_total),
                    unpaid_partner_total=float(s.unpaid_partner_total),
                    settleable_count=s.settleable_count,
                )
                for s in agg.partner_subtotals
            ],
        )

    def mark_month_paid(self, contract_id: str, month: str, *, actor_user_id: str) -> MarkPaidResult:
        orders = self.orders.list_recurring_billing_orders(month=month, contract_id=contract_id)
        updated: list[str] = []
        skipped = 0
        order_service = OrderService(self.db)
        for o in orders:
            if o.payment_status in _ALREADY_PAID:
                skipped += 1
                continue
            order_service.update(o.id, OrderUpdate(payment_status=PaymentStatus.PAID), actor_user_id=actor_user_id)
            updated.append(o.id)
        return MarkPaidResult(updated_order_ids=updated, skipped_count=skipped)

    def settle_month(
        self, contract_id: str, month: str, *, partner_id: str | None = None, actor_user_id: str
    ) -> SettleMonthResult:
        orders = self.orders.list_recurring_billing_orders(month=month, contract_id=contract_id)
        eligible = [o for o in orders if is_unpaid_partner_order(o) and (partner_id is None or o.partner_id == partner_id)]
        skipped = len(orders) - len(eligible)
        settled: list[str] = []
        settlement = PartnerSettlementService(self.db)
        by_partner: dict[str, list[str]] = {}
        for o in eligible:
            by_partner.setdefault(o.partner_id, []).append(o.id)
        for pid, order_ids in by_partner.items():
            result = settlement.settle(partner_id=pid, order_ids=order_ids, actor_user_id=actor_user_id)
            settled.extend(result.updated_order_ids)
        self.db.commit()  # PartnerSettlementService.settle는 commit하지 않으므로 여기서 소유
        return SettleMonthResult(settled_order_ids=settled, skipped_count=skipped)

    def export_table(self, month: str, contract_id: str | None = None):
        orders = self.orders.list_recurring_billing_orders(month=month, contract_id=contract_id)
        return OrderExportService(self.db).build_admin_orders_export([o.id for o in orders])
```

> 주의: `month_summary`의 `group = self.orders.db.get(...)` 줄은 잘못된 잔여 코드다 — **삭제하라**. group은 `_to_row`에서 `OrderGroupRepository`로 직접 로딩한다. (구현 시 그 한 줄을 넣지 말 것.)

- [ ] **Step 4: 통과 확인**

Run: `cd backend && python -m pytest tests/test_recurring_billing_service.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: 커밋**

```bash
git add backend/app/services/recurring_billing.py backend/tests/test_recurring_billing_service.py
git commit -m "feat(billing): RecurringBillingService(집계·일괄 입금/정산·내보내기)"
```

---

## Task 5: 라우트 + 등록

**Files:**
- Create: `backend/app/api/routes/admin/recurring_billing.py`
- Modify: `backend/app/api/router.py`
- Test: `backend/tests/test_recurring_billing_api.py`

- [ ] **Step 1: 실패 테스트** — `backend/tests/test_recurring_billing_api.py`

```python
def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_billing_summary_requires_admin(client):
    r = client.get("/api/admin/recurring/billing?month=2026-06")
    assert r.status_code == 401


def test_billing_summary_ok(client, seed_admin_token):
    r = client.get("/api/admin/recurring/billing?month=2026-06", headers=_auth(seed_admin_token))
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_mark_paid_and_settle_endpoints_exist(client, seed_admin_token):
    mp = client.post(
        "/api/admin/recurring/billing/mark-paid",
        json={"contract_id": "nope", "month": "2026-06"}, headers=_auth(seed_admin_token),
    )
    assert mp.status_code == 200  # 대상 없으면 빈 결과
    st = client.post(
        "/api/admin/recurring/billing/settle",
        json={"contract_id": "nope", "month": "2026-06"}, headers=_auth(seed_admin_token),
    )
    assert st.status_code == 200
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python -m pytest tests/test_recurring_billing_api.py -q`
Expected: FAIL — 404.

- [ ] **Step 3: 라우트** — `backend/app/api/routes/admin/recurring_billing.py`

```python
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_session, require_admin
from app.schemas.recurring_billing import (
    MarkPaidRequest,
    MarkPaidResult,
    RecurringBillingRowRead,
    SettleMonthRequest,
    SettleMonthResult,
)
from app.services.recurring_billing import RecurringBillingService

router = APIRouter()


@router.get("", response_model=list[RecurringBillingRowRead])
def billing_summary(
    month: str, db: Session = Depends(get_session), _: CurrentUser = Depends(require_admin)
):
    return RecurringBillingService(db).month_summary(month)


@router.post("/mark-paid", response_model=MarkPaidResult)
def mark_paid(
    payload: MarkPaidRequest, db: Session = Depends(get_session), user: CurrentUser = Depends(require_admin)
):
    return RecurringBillingService(db).mark_month_paid(payload.contract_id, payload.month, actor_user_id=user.id)


@router.post("/settle", response_model=SettleMonthResult)
def settle(
    payload: SettleMonthRequest, db: Session = Depends(get_session), user: CurrentUser = Depends(require_admin)
):
    return RecurringBillingService(db).settle_month(
        payload.contract_id, payload.month, partner_id=payload.partner_id, actor_user_id=user.id
    )


@router.get("/export")
def export_csv(
    month: str, contract_id: str | None = None,
    db: Session = Depends(get_session), _: CurrentUser = Depends(require_admin),
):
    table = RecurringBillingService(db).export_table(month, contract_id)
    csv_bytes = table.to_csv_bytes()  # 기존 OrderExportTable의 CSV 직렬화 사용
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="recurring-billing-{month}.csv"'},
    )
```

> 구현 주의: `OrderExportTable`의 CSV 직렬화 메서드명이 `to_csv_bytes`가 아닐 수 있다. 기존 주문 내보내기 라우트(`app/api/routes/admin/orders.py`의 export 엔드포인트)가 `OrderExportTable`을 어떻게 CSV로 직렬화하는지 보고 **동일한 방식**으로 맞춰라(BOM/인코딩 포함).

- [ ] **Step 4: 등록** — `backend/app/api/router.py`

```python
from app.api.routes.admin import (
    calendar, dashboard, messages, orders, partner_settlements, partners,
    photos, recurring, recurring_billing, reports, services,
)
```
등록부:
```python
api_router.include_router(
    recurring_billing.router, prefix="/admin/recurring/billing", tags=["admin-recurring-billing"]
)
```

- [ ] **Step 5: 통과 확인**

Run: `cd backend && python -m pytest tests/test_recurring_billing_api.py -q`
Expected: PASS (3 passed).

- [ ] **Step 6: 커밋**

```bash
git add backend/app/api/routes/admin/recurring_billing.py backend/app/api/router.py backend/tests/test_recurring_billing_api.py
git commit -m "feat(billing): 월 청구·정산 admin 라우트"
```

---

## Task 6: 백엔드 전체 검증

- [ ] **Step 1: 전체 테스트** — Run: `cd backend && python -m pytest -q` → 전부 PASS(기존 회귀 없음).
- [ ] **Step 2: 컴파일** — Run: `cd backend && python -m compileall app tests` → exit 0.
- [ ] **Step 3: (가능 시) 린트** — `ruff check app/domain/recurring_billing.py app/services/recurring_billing.py` (ruff 미설치면 생략).
- [ ] **Step 4:** 코드 변경 없으면 커밋 없음.

---

## Task 7: 프론트 API

**Files:**
- Create: `frontend/src/api/recurringBilling.ts`

- [ ] **Step 1: 구현** — `frontend/src/api/recurringBilling.ts`

```ts
import { apiRequest, downloadBlob } from './client';

export interface PartnerSubtotal {
  partner_id: string | null;
  partner_name: string | null;
  partner_total: number;
  unpaid_partner_total: number;
  settleable_count: number;
}
export interface RecurringBillingRow {
  contract_id: string;
  label: string;
  customer_name: string;
  month: string;
  visit_count: number;
  billed_total: number;
  confirmed_revenue: number;
  unpaid_customer_count: number;
  payment_breakdown: Record<string, number>;
  partner_total: number;
  unpaid_partner_total: number;
  unpaid_partner_count: number;
  partner_subtotals: PartnerSubtotal[];
}

export function getRecurringBilling(month: string): Promise<RecurringBillingRow[]> {
  return apiRequest(`/admin/recurring/billing?month=${encodeURIComponent(month)}`) as Promise<RecurringBillingRow[]>;
}
export function markRecurringMonthPaid(contractId: string, month: string) {
  return apiRequest('/admin/recurring/billing/mark-paid', { method: 'POST', body: { contract_id: contractId, month } });
}
export function settleRecurringMonth(contractId: string, month: string, partnerId?: string | null) {
  return apiRequest('/admin/recurring/billing/settle', {
    method: 'POST', body: { contract_id: contractId, month, partner_id: partnerId ?? null },
  });
}
export function exportRecurringBilling(month: string): Promise<void> {
  return downloadBlob(`/admin/recurring/billing/export?month=${encodeURIComponent(month)}`, `recurring-billing-${month}.csv`);
}
```

- [ ] **Step 2: 타입체크** — Run: `cd frontend && npm run typecheck` → 통과.
- [ ] **Step 3: 커밋**

```bash
git add frontend/src/api/recurringBilling.ts
git commit -m "feat(billing): 프론트 월 청구·정산 API"
```

---

## Task 8: 월 정산 뷰 + 탭 통합

**Files:**
- Create: `frontend/src/features/admin/recurring/RecurringBillingView.tsx`
- Modify: `frontend/src/features/admin/recurring/RecurringContractsPage.tsx`(상단 탭 추가) 또는 `App.tsx`

- [ ] **Step 1: 월 정산 뷰** — `frontend/src/features/admin/recurring/RecurringBillingView.tsx`

```jsx
import React from 'react';
import {
  exportRecurringBilling, getRecurringBilling, markRecurringMonthPaid, settleRecurringMonth,
  type RecurringBillingRow,
} from '../../../api/recurringBilling';
import { formatAmount } from '../../../domain/recurrence';

function thisMonth(): string {
  // KST 기준 이번 달. (브라우저 로컬이 KST 타깃)
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

export function RecurringBillingView() {
  const [month, setMonth] = React.useState(thisMonth());
  const [rows, setRows] = React.useState<RecurringBillingRow[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  const load = React.useCallback(async () => {
    setError(null);
    try { setRows(await getRecurringBilling(month)); }
    catch (e) { setError(e instanceof Error ? e.message : '불러오기 실패'); setRows([]); }
  }, [month]);

  React.useEffect(() => { void load(); }, [load]);

  const act = async (fn: () => Promise<unknown>, confirmMsg: string) => {
    if (!window.confirm(confirmMsg)) return;
    setBusy(true);
    try { await fn(); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : '처리 실패'); }
    finally { setBusy(false); }
  };

  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
        <input type="month" value={month} onChange={(e) => setMonth(e.target.value)}
          style={{ fontSize: 16, padding: '6px 8px' }} data-testid="billing-month" />
        <button className="btn btn--ghost btn--sm" data-testid="billing-export"
          onClick={() => exportRecurringBilling(month)}>CSV 내보내기</button>
      </div>
      {error && <div role="alert" style={{ color: 'var(--danger,#c0392b)', marginBottom: 8 }}>{error}</div>}
      {rows === null ? <div>불러오는 중…</div>
        : rows.length === 0 ? <div style={{ color: 'var(--text-tertiary)' }}>이 달 정기 주문이 없습니다.</div>
        : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
              <thead><tr style={{ textAlign: 'left', color: 'var(--text-tertiary)' }}>
                <th>계약</th><th>고객</th><th>방문</th><th>청구합</th><th>확정매출</th><th>미입금</th>
                <th>정산합</th><th>미정산</th><th>액션</th>
              </tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.contract_id} data-testid={`billing-row-${r.contract_id}`}>
                    <td>{r.label}</td>
                    <td>{r.customer_name}</td>
                    <td>{r.visit_count}</td>
                    <td>{formatAmount(r.billed_total)}</td>
                    <td>{formatAmount(r.confirmed_revenue)}</td>
                    <td style={{ color: r.unpaid_customer_count ? 'var(--danger,#c0392b)' : undefined }}>{r.unpaid_customer_count}건</td>
                    <td>{formatAmount(r.partner_total)}</td>
                    <td>{r.unpaid_partner_count}건 / {formatAmount(r.unpaid_partner_total)}</td>
                    <td style={{ display: 'flex', gap: 4 }}>
                      <button className="btn btn--ghost btn--sm" disabled={busy} data-testid={`billing-markpaid-${r.contract_id}`}
                        onClick={() => act(() => markRecurringMonthPaid(r.contract_id, month), `${r.label} ${month} 미입금분을 입금완료 처리할까요?`)}>입금완료</button>
                      <button className="btn btn--ghost btn--sm" disabled={busy || r.unpaid_partner_count === 0} data-testid={`billing-settle-${r.contract_id}`}
                        onClick={() => act(() => settleRecurringMonth(r.contract_id, month), `${r.label} ${month} 정산 가능 ${r.unpaid_partner_count}건을 정산완료 처리할까요?`)}>정산완료</button>
                    </td>
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

- [ ] **Step 2: 탭 통합** — `RecurringContractsPage.tsx` 최상단에 탭 바를 추가해 `계약`(기존 내용) / `월 정산`(`RecurringBillingView`)을 전환한다. 기존 `view` 상태와 별개로 `tab` 상태(`'contracts' | 'billing'`)를 두고, `tab==='billing'`이면 `<RecurringBillingView/>`를, 아니면 기존 목록/폼/상세 렌더를 보여준다.

```jsx
// RecurringContractsPage.tsx 상단(컴포넌트 함수 본문 첫머리)에 추가:
const [tab, setTab] = React.useState<'contracts' | 'billing'>('contracts');
// ...기존 return 직전, list 모드일 때 상단에 탭 바 + 분기:
// (create/detail 서브뷰일 때는 탭 숨김 — 기존 동작 유지)
```
그리고 list 모드 렌더의 맨 위에:
```jsx
<div style={{ display: 'flex', gap: 4, marginBottom: 12, borderBottom: '1px solid var(--border)' }}>
  <button className="btn btn--ghost btn--sm" data-testid="recurring-tab-contracts"
    style={{ fontWeight: tab === 'contracts' ? 700 : 400 }} onClick={() => setTab('contracts')}>계약</button>
  <button className="btn btn--ghost btn--sm" data-testid="recurring-tab-billing"
    style={{ fontWeight: tab === 'billing' ? 700 : 400 }} onClick={() => setTab('billing')}>월 정산</button>
</div>
{tab === 'billing' ? <RecurringBillingView /> : (/* 기존 승인 패널 + 계약 목록 */)}
```
> 실제 통합 시 기존 `RecurringContractsPage`의 list 렌더 구조를 보고, 승인 패널+목록을 `tab==='contracts'` 분기 안으로 감싼다. import: `import { RecurringBillingView } from './RecurringBillingView';`

- [ ] **Step 3: 검증** — Run: `cd frontend && npm run typecheck && npm run lint && npm run build` → 통과.
- [ ] **Step 4: 커밋**

```bash
git add frontend/src/features/admin/recurring/RecurringBillingView.tsx frontend/src/features/admin/recurring/RecurringContractsPage.tsx
git commit -m "feat(billing): 월 정산 뷰 + 정기청소 계약/월정산 탭"
```

---

## Task 9: E2E + 최종 검증

**Files:**
- Create: `frontend/e2e/recurring-billing.spec.ts`

- [ ] **Step 1: E2E** — 기존 `recurring.spec.ts`의 로그인/계약생성/승인 흐름을 재사용해, 승인된 정기 주문이 '월 정산' 탭에 집계로 보이고 입금완료 일괄이 동작하는지 확인. (도래분 보장 위해 start_date=오늘, day_of_month=오늘 일자.) e2e 인프라가 2~3회로 불안정하면 루프 말고 보고.

```ts
import { expect, test, type Page } from '@playwright/test';

const ADMIN_EMAIL = 'admin@cleanops.kr';
const ADMIN_PASSWORD = 'AdminPass123!';

test('정기 주문이 월 정산 탭에 집계된다', async ({ page }) => {
  await loginAsAdmin(page);
  await page.getByTestId('admin-nav-recurring').click();
  await page.getByTestId('recurring-tab-billing').click();
  await expect(page.getByTestId('billing-month')).toBeVisible();
  // 최소 단언: 월 정산 탭 진입 + 테이블/빈상태 렌더(데이터 의존 단언은 서비스 테스트가 담당)
});

async function loginAsAdmin(page: Page) {
  await page.goto('/');
  await page.getByTestId('admin-login-identifier').fill(ADMIN_EMAIL);
  await page.getByTestId('admin-login-password').fill(ADMIN_PASSWORD);
  await page.getByTestId('admin-login-submit').click();
  await expect(page.getByTestId('admin-shell')).toBeVisible();
}
```

- [ ] **Step 2: E2E 실행** — Run: `cd frontend && npm run e2e -- recurring-billing.spec.ts` → PASS.
- [ ] **Step 3: 최종 검증** —
```
cd backend && python -m pytest -q
cd ../frontend && npm run typecheck && npm run lint && npm run build
```
모두 통과.
- [ ] **Step 4: 커밋** — `git add frontend/e2e/recurring-billing.spec.ts && git commit -m "test(billing): 월 정산 E2E + 최종 검증"`

---

## Self-Review (작성자 체크리스트 결과)

**1. Spec coverage:** §1 데이터흐름→Task1, §2 집계 정의→Task2, §3 일괄 액션(입금/정산)→Task4, §4 내보내기→Task4·5, §5 백엔드 레이어→Task1~5, §6 프론트(탭/뷰)→Task7·8, §7 테스트→각 Task+9. ✅ 갭 없음.

**2. Placeholder scan:** 실제 코드 포함. 두 곳의 "구현 주의"는 기존 코드 정합 지시(잘못된 잔여 줄 삭제 / `OrderExportTable` CSV 직렬화 메서드명 확인)이며 구현 공백이 아님 — 명시적으로 처리 지시함.

**3. Type consistency:** `aggregate_orders`→`BillingAggregate`(Task2) = `_to_row`가 소비(Task4) ✅. `RecurringBillingRowRead`/`PartnerSubtotalRead`(Task3) = 서비스 반환 = 라우트 response_model = 프론트 타입(Task7) 필드 일치 ✅. `list_recurring_billing_orders(month, contract_id)`(Task1) = 서비스 호출(Task4) ✅. `PartnerSettlementService.settle(partner_id, order_ids, actor_user_id)`·`is_unpaid_partner_order`(기존) = settle_month 사용 ✅.

**알려진 실행 주의:**
- Task4 `month_summary`의 잘못된 `group = self.orders.db.get(...)` 한 줄은 넣지 말 것(주석으로 명시).
- Task5 export의 CSV 직렬화는 기존 주문 export 라우트와 동일 방식으로(메서드명 실제 확인).
- 프론트 탭 통합은 기존 `RecurringContractsPage` list 렌더 구조에 맞춰 승인패널+목록을 `tab==='contracts'`로 감쌀 것.
- B는 main(=A)에서 분기한 worktree에서 작업 — partner 브랜치와 무관.

---
