# R7 — 다중 상품 주문 + 라인별 협력사 배정 구현 명세 v1

> **이력**
> - v1 (2026-05-18): brief 승인 후 작성. 코드 가정을 사전 grep으로 검증.
> - v2 (2026-05-18): v1 review에서 발견된 6건 해소 — (1) Alembic 0008 백필 SQL을 Python loop + uuid.uuid4()로 교체해 Postgres 호환 (blocker), (2) `_create_line_internal`이 그룹의 customer_*/token/source_channel/customer_visible_payment를 신규 line의 deprecated 컬럼에 복사해 R6 consumer 호환 유지 (high), (3) `CustomerOrderGroupRead`에 `customer_visible_payment` 필드 추가 + 금액 false 시 null 처리, (4) `PATCH /admin/orders/groups/{id}` 엔드포인트 추가 + edit 모드 submit이 group 정보도 함께 PATCH, (5) `OrderService.create` wrapper를 실제 1-line group 위임으로 구현 + 기존 `POST /admin/orders` 라우트는 deprecated 표시 후 호환 유지, (6) `createMultiLineOrder` 헬퍼를 실제 구현 코드로 명세.
> - v3 (2026-05-18): v2 review의 P1 해소 — (a) `Order.customer_token`의 `unique=True`를 모델 정의에서 완전히 제거 (v2에서 누락), (b) 0008 마이그레이션이 일반 인덱스 drop·재생성에 더해 0001에서 만들어진 **실제 unique constraint**를 dialect 분기 raw SQL로 명시적 drop하도록 보강. 같은 그룹의 line 2개 이상이 같은 customer_token을 가져도 unique violation이 나지 않음.
> - v4 (2026-05-18): v3 review의 P1 해소 — SQLite의 `batch_alter_table`이 reflection으로 기존 unnamed unique constraint를 새 테이블에 복사할 수 있는 문제 처리. `batch_alter_table(copy_from=<명시적 Table 정의>)` 패턴으로 v3 시점의 orders 스키마(customer_token unique=True 없음)를 명시. Postgres는 v3 그대로 raw SQL drop.
> - v5 (2026-05-18): v4 review의 P2 해소 — `copy_from`이 reflection을 건너뛰면서 0001의 8개 기존 인덱스(`ix_orders_status`, `ix_orders_received_date`, `ix_orders_scheduled_date`, `ix_orders_partner_id`, `ix_orders_customer_name`, `ix_orders_customer_phone`, `ix_orders_customer_token`, `ix_orders_payment_status`)가 SQLite에서 유실되는 문제 처리. `orders_target` Table 정의에 모든 인덱스를 `sa.Index(...)` 객체로 포함시켜 SQLite가 새 테이블에 자동 재생성하게 한다. Postgres는 ALTER TABLE이므로 인덱스 보존 그대로.

> **Codex 작업자에게**: 이 문서는 R7(다중 상품 주문 + 라인별 협력사 배정)의 task 단위 구현 명세서다. 각 task는 독립 커밋 단위이며, 위에서 아래로 순서대로 진행한다. 작업 전 `AGENTS.md`, `CLAUDE.md`, brief(`docs/plans/2026-05-18-r7-multi-line-orders-brief.md`)를 먼저 읽는다.

**Goal:** 한 고객의 묶음 주문(예: "사무실 청소 + 화장실 청소")을 라인 N개로 분리해 라인별 협력사·결제·상태·사진·메시지·취소가 모두 독립적으로 동작하게 한다.

**Architecture:**
- `Order = 1개의 작업 라인`을 유지한다. R6의 자동공개 정책, 사진/메시지/협력사 권한 흐름, 13개 status enum은 **전부 그대로**.
- 새 상위 묶음 `OrderGroup`을 1개 추가한다. `customer_token`은 그룹 단위, 고객 정보·주소·`source_channel`·`customer_visible_payment`는 그룹에 1번만 저장.
- 기존 Order의 customer_* 컬럼은 R7에서 **deprecated(nullable)로 유지**하고 데이터는 그룹으로 이동. drop은 R7.5 cleanup PR에서.
- 협력사·메시지·사진 라우트는 변경하지 않는다 (협력사는 본인 Order만 보고, 메시지·사진은 order_id 기반 그대로).

**Tech Stack:** FastAPI · SQLAlchemy 2.0 · Pydantic · Alembic · React 19 + TypeScript (no Tailwind) · Playwright.

---

## CTO 결정 사항 (brief 승인 완료)

- **D1.** 묶음은 `OrderGroup` 1개만 신설. status enum, 사진, 결제는 절대 그룹 레벨로 올리지 않는다.
- **D2.** `customer_token`은 **그룹 단위로만** 발급. `Order.customer_token`은 R7에서 deprecated(nullable). 새 주문은 항상 그룹에서 발급.
- **D3.** 협력사 모바일은 본인 배정된 Order(line)만 본다. PartnerJobRead DTO에 group_id 노출 X. R6 권한 흐름 그대로.
- **D4.** timeline은 line별 유지. 그룹 통합 timeline 없음.
- **D5.** 신규 주문 폼: 고객 정보·주소는 그룹 1번 입력. 라인 추가 시 자동 상속.
- **D6.** 부분 취소: 라인 1개만 `OrderStatus.CANCELLED` 전환 가능. "그룹 취소"는 모든 라인이 취소된 시각 표시일 뿐, 별도 enum 안 만듦.
- **D7.** 레거시 데이터: 기존 Order들은 각자 자기 자신만 담은 1-line 그룹으로 자동 백필.

---

## File Map

| 영역 | 파일 | 종류 |
|---|---|---|
| 도메인/모델 | `backend/app/models/order_group.py` | 신규 |
| 도메인/모델 | `backend/app/models/order.py` | 수정 (group_id FK 추가, customer_* nullable) |
| 마이그레이션 | `backend/alembic/versions/0008_order_groups.py` | 신규 |
| 레포지토리 | `backend/app/repositories/order_groups.py` | 신규 |
| 레포지토리 | `backend/app/repositories/orders.py` | 수정 (get_by_customer_token 제거, list_by_group 추가) |
| 서비스 | `backend/app/services/orders.py` | 수정 (create_group, add_line_to_group 신설) |
| 라우터 | `backend/app/api/routes/admin/orders.py` | 수정 (group 엔드포인트 추가) |
| 라우터 | `backend/app/api/routes/customer/orders.py` | 수정 (token → group, line 리스트 반환) |
| 라우터 | `backend/app/api/routes/partner/jobs.py` | **변경 없음** (D3) |
| 라우터 | `backend/app/api/router.py` | 수정 (`/admin/order-groups` 등록) |
| 스키마 | `backend/app/schemas/order.py` | 수정 (Admin/Customer 그룹 DTO 신설, customer_* 위치 변경) |
| 서비스 | `backend/app/services/dashboard.py`, `messages.py`, `photos.py` | **변경 없음** |
| 시드 | `backend/app/db/seed.py` | 수정 (group + line 1개로 분리 생성) |
| 백엔드 테스트 | `backend/tests/test_order_groups.py` | 신규 |
| 백엔드 테스트 | `backend/tests/test_auth_integration.py`, `test_photo_auto_visibility.py`, `test_photo_revoke.py` | 수정 (그룹 생성 후 line이라는 가정) |
| 프론트 API | `frontend/src/api/admin.ts` | 수정 (createOrderGroup 등 신설) |
| 프론트 API | `frontend/src/api/customer.ts` | 수정 (응답 타입 group + lines) |
| 프론트 폼 | `frontend/src/features/admin/orders/OrderFormPage.tsx` | 대규모 수정 (라인 리스트 편집 UI) |
| 프론트 목록 | `frontend/src/features/admin/orders/OrdersPage.tsx` | 수정 (그룹 시각 묶음) |
| 프론트 상세 | `frontend/src/features/admin/orders/OrderDetailPage.tsx` | 수정 (그룹 다른 라인 패널) |
| 프론트 고객 | `frontend/src/features/customer/CustomerReservation.tsx` | 수정 (line 카드 N개) |
| 프론트 협력사 | `frontend/src/features/partner/PartnerJobDetail.tsx` | **변경 없음** (D3) |
| 프론트 E2E | `frontend/e2e/admin-multi-line-e2e.spec.ts` | 신규 |
| 프론트 E2E | `frontend/e2e/partner-customer-e2e.spec.ts`, `admin-e2e.spec.ts` | 수정 (그룹 생성 흐름) |
| 프론트 E2E | `frontend/e2e/helpers.ts` | 수정 (`createAssignedOrder` → 그룹 생성 + line 1개 추가) |
| 핸드오프 | `.master/next_session_plan.md` | 수정 (R7 마감) |

---

## Task 1 — 도메인 모델 신설: `OrderGroup`

**Files:**
- Create: `backend/app/models/order_group.py`
- Modify: `backend/app/models/order.py` (group_id FK 추가, customer_* nullable로)
- Modify: `backend/app/models/__init__.py` (export 추가)

- [ ] **Step 1: `OrderGroup` 모델 신규**

`backend/app/models/order_group.py`:

```python
from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class OrderGroup(TimestampMixin, Base):
    __tablename__ = "order_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_token: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(80), index=True)
    customer_phone: Mapped[str] = mapped_column(String(30), index=True)
    customer_address: Mapped[str] = mapped_column(Text)
    source_channel: Mapped[str | None] = mapped_column(String(120))
    customer_visible_payment: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
```

> relationship은 R7 범위 밖. 그룹 → line 조회는 명시적인 repository 메서드(`list_by_group`)로 수행.

- [ ] **Step 2: `Order` 모델 수정**

`backend/app/models/order.py`의 컬럼 정의를 다음 의도로 갱신:

1. `group_id` FK 컬럼 추가 (NOT NULL, FK → order_groups.id, indexed).
2. `customer_token`, `customer_name`, `customer_phone`, `customer_address`, `source_channel`, `customer_visible_payment` 6개 컬럼을 모두 **nullable로 변경**하고 docstring에 `# R7 deprecated: see OrderGroup. drop in R7.5` 주석.

```python
# 추가
group_id: Mapped[str] = mapped_column(ForeignKey("order_groups.id"), index=True)

# 기존 6개 컬럼은 nullable로 변경 (drop은 R7.5에서)
# v3 변경: customer_token에서 `unique=True` 제거. 같은 그룹의 line N개가 모두 동일한 token을
# 보유하므로 unique 제약이 살아 있으면 두 번째 line insert가 violation으로 실패한다.
# 일반 인덱스(index=True)는 R7.5 drop 전까지 유지 — get_by_customer_token이 호출되지는
# 않지만, 운영 디버깅이나 import 스크립트 호환을 위해 검색 인덱스만 남긴다.
customer_token: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
customer_name: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
customer_phone: Mapped[str | None] = mapped_column(String(30), index=True, nullable=True)
customer_address: Mapped[str | None] = mapped_column(Text, nullable=True)
source_channel: Mapped[str | None] = mapped_column(String(120), nullable=True)
customer_visible_payment: Mapped[bool | None] = mapped_column(Boolean, default=False, nullable=True)
```

> **주의 (v3):** `customer_token`의 `unique=True`는 v3에서 **반드시 제거**한다. 0001 마이그레이션이 column에 `unique=True`를 줬으므로 실제 DB에는 unique constraint가 살아 있다. Task 2 마이그레이션에서 이 constraint를 명시적으로 drop한다 (다음 step 참조).

- [ ] **Step 3: `__init__.py` export 추가**

```python
from app.models.order import Order  # noqa: F401
from app.models.order_group import OrderGroup  # noqa: F401  # 추가
```

- [ ] **Step 4: 컴파일 확인**

```powershell
python -m compileall backend/app/models
```

- [ ] **Step 5: 커밋**

```bash
git add backend/app/models/
git commit -m "feat(model): OrderGroup 신설 + Order에 group_id FK 추가"
```

---

## Task 2 — Alembic 마이그레이션 0008 (order_groups + 백필)

**Files:** Create `backend/alembic/versions/0008_order_groups.py`

**구현 의도 (D7):**
- 신규 테이블 `order_groups` 생성.
- 기존 `orders` 테이블에 `group_id` 컬럼 추가 (FK).
- 기존 6개 `customer_*` 컬럼을 nullable로 변경.
- **데이터 백필**: 기존 Order 1건마다 그룹 1개 생성 + `Order.group_id` 채움 + customer_* 데이터를 그룹으로 복사.

- [ ] **Step 1: 마이그레이션 파일 작성**

```python
"""Add order_groups + backfill 1:1 groups from existing orders.

Revision ID: 0008_order_groups
Revises: 0007_auto_publish_legacy_photos
Create Date: 2026-05-18
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_order_groups"
down_revision: str | None = "0007_auto_publish_legacy_photos"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) order_groups 테이블 생성
    op.create_table(
        "order_groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("customer_token", sa.String(80), nullable=False),
        sa.Column("customer_name", sa.String(80), nullable=False),
        sa.Column("customer_phone", sa.String(30), nullable=False),
        sa.Column("customer_address", sa.Text(), nullable=False),
        sa.Column("source_channel", sa.String(120), nullable=True),
        sa.Column("customer_visible_payment", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_order_groups_customer_token", "order_groups", ["customer_token"], unique=True)
    op.create_index("ix_order_groups_customer_name", "order_groups", ["customer_name"])
    op.create_index("ix_order_groups_customer_phone", "order_groups", ["customer_phone"])

    # 2) orders 테이블에 group_id 컬럼 추가 (FK 제약은 백필 후에 추가)
    op.add_column("orders", sa.Column("group_id", sa.String(36), nullable=True))

    # 3) 백필: v2 변경 — raw SQL 대신 Python loop + uuid.uuid4()로 처리.
    #    이유: v1의 `id || '-group'` 패턴은 (a) Postgres에서 36+6=42자가 String(36) 컬럼에
    #    안 들어가고 (b) `COALESCE(customer_visible_payment, 0)`이 Postgres boolean
    #    타입과 충돌한다. Python loop는 SQLite/Postgres 모두 안전하고 운영 데이터가
    #    100건 미만이라 성능 부담도 없다.
    bind = op.get_bind()
    existing_orders = bind.execute(
        sa.text(
            """
            SELECT id, customer_token, customer_name, customer_phone, customer_address,
                   source_channel, customer_visible_payment, created_at, updated_at
            FROM orders
            WHERE customer_token IS NOT NULL
            """
        )
    ).fetchall()

    for row in existing_orders:
        new_group_id = str(uuid.uuid4())
        bind.execute(
            sa.text(
                """
                INSERT INTO order_groups (
                    id, customer_token, customer_name, customer_phone, customer_address,
                    source_channel, customer_visible_payment, created_at, updated_at
                )
                VALUES (
                    :id, :token, :name, :phone, :address,
                    :source, :visible, :created, :updated
                )
                """
            ),
            {
                "id": new_group_id,
                "token": row.customer_token,
                "name": row.customer_name,
                "phone": row.customer_phone,
                "address": row.customer_address,
                "source": row.source_channel,
                "visible": bool(row.customer_visible_payment) if row.customer_visible_payment is not None else False,
                "created": row.created_at,
                "updated": row.updated_at,
            },
        )
        bind.execute(
            sa.text("UPDATE orders SET group_id = :gid WHERE id = :oid"),
            {"gid": new_group_id, "oid": row.id},
        )

    # 4) group_id를 NOT NULL + FK로 마무리. SQLite는 batch_alter_table 필요.
    #
    # v4 변경 (SQLite unique constraint reflection 문제 해소):
    # SQLite의 batch_alter_table은 기본적으로 ALTER 대상 테이블을 reflection으로 읽어
    # 새 테이블에 그대로 복사한다. 0001의 `Column("customer_token", ..., unique=True)`로
    # 만들어진 unnamed unique constraint도 그대로 복사되므로, 모델에서 `unique=True`를 빼는
    # 것만으로는 부족하다. `copy_from`에 명시적 Table 정의(unique=True 없는 v3 시점 스키마)를
    # 전달해 batch가 reflection을 건너뛰고 우리 정의대로 새 테이블을 만들게 한다.
    #
    # 이 Table 정의는 0008 적용 직후의 orders 스키마와 1:1 일치해야 한다. 다음 컬럼들은:
    #   - group_id: 이 마이그레이션 step 2~4에서 막 추가/NOT NULL 처리. nullable=False로 명시.
    #   - customer_*: v3에서 nullable로. customer_token은 unique=True 없음.
    #   - 나머지 컬럼: 0001 정의 그대로.
    orders_target = sa.Table(
        "orders",
        sa.MetaData(),
        sa.Column("id", sa.String(36), primary_key=True),
        # v5: group_id의 ForeignKey는 batch_op.create_foreign_key에서 명시적으로 만든다.
        # orders_target과 batch op 둘 다에 FK를 두면 SQLite/Postgres 충돌 가능.
        # 다른 FK(partner_id 등)는 Table 정의에만 두어 SQLite copy_from으로 새 테이블에 적용.
        sa.Column("group_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default=sa.literal("신규접수")),
        sa.Column("received_date", sa.Date(), nullable=False),
        sa.Column("scheduled_date", sa.Date()),
        sa.Column("requested_time", sa.String(80)),
        sa.Column("partner_id", sa.String(36), sa.ForeignKey("partners.id")),
        sa.Column("team_name", sa.String(120)),
        sa.Column("service_category_id", sa.String(36), sa.ForeignKey("service_categories.id")),
        sa.Column("service_item_id", sa.String(36), sa.ForeignKey("service_items.id")),
        sa.Column("service_name", sa.String(160), nullable=False),
        sa.Column("size_or_quantity", sa.String(80)),
        sa.Column("service_detail", sa.Text()),
        sa.Column("special_request", sa.Text()),
        sa.Column("source_channel", sa.String(120)),  # v3 nullable
        sa.Column("customer_name", sa.String(80)),    # v3 nullable
        sa.Column("customer_phone", sa.String(30)),   # v3 nullable
        sa.Column("customer_address", sa.Text()),     # v3 nullable
        sa.Column("total_amount", sa.Numeric(12, 2)),
        sa.Column("deposit_amount", sa.Numeric(12, 2)),
        sa.Column("balance_amount", sa.Numeric(12, 2)),
        sa.Column("onsite_extra_amount", sa.Numeric(12, 2)),
        sa.Column("vat_type", sa.String(20)),
        sa.Column("payment_status", sa.String(40)),
        sa.Column("payment_memo", sa.Text()),
        sa.Column("evidence_memo", sa.Text()),
        sa.Column("partner_payment_amount", sa.Numeric(12, 2)),
        sa.Column("partner_payment_status", sa.String(40)),
        # v3 변경: customer_token에서 unique=True 제거. 일반 인덱스만 유지(아래 sa.Index로).
        sa.Column("customer_token", sa.String(80)),
        sa.Column("customer_visible_payment", sa.Boolean(), server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        # v5 추가: 0001에서 만들어진 8개 인덱스 + R7 신규 group_id 인덱스를 명시적으로 정의.
        # SQLite copy_from은 reflection을 건너뛰므로 이들을 Table 정의에 포함시키지 않으면
        # 새 테이블에 인덱스가 사라진다. Postgres는 ALTER TABLE이라 이 정의는 무영향(reflection
        # 결과가 그대로 보존되므로).
        sa.Index("ix_orders_status", "status"),
        sa.Index("ix_orders_received_date", "received_date"),
        sa.Index("ix_orders_scheduled_date", "scheduled_date"),
        sa.Index("ix_orders_partner_id", "partner_id"),
        sa.Index("ix_orders_customer_name", "customer_name"),
        sa.Index("ix_orders_customer_phone", "customer_phone"),
        sa.Index("ix_orders_customer_token", "customer_token"),
        sa.Index("ix_orders_payment_status", "payment_status"),
        # v5: ix_orders_group_id는 batch_op.create_index에서 명시적으로 생성한다 (충돌 방지).
    )

    with op.batch_alter_table("orders", copy_from=orders_target) as batch_op:
        batch_op.alter_column("group_id", existing_type=sa.String(36), nullable=False)
        # v5: ix_orders_group_id 인덱스는 orders_target Table 정의에 sa.Index로 포함되어
        # SQLite copy_from으로 새 테이블에 자동 생성된다. Postgres는 ALTER TABLE이라
        # 기존 reflection으로 보존되지 않지만, group_id는 이 마이그레이션에서 새로 추가된
        # 컬럼이므로 reflection 보존이 무의미 — 그래서 batch_op.create_index로 명시 생성.
        batch_op.create_index("ix_orders_group_id", ["group_id"])
        # group_id FK는 양 dialect 모두 명시적으로 생성.
        # SQLite는 copy_from 새 테이블에 적용, Postgres는 ALTER TABLE로 추가.
        batch_op.create_foreign_key(
            "fk_orders_group_id_order_groups", "order_groups", ["group_id"], ["id"]
        )

        # 5) customer_* 컬럼을 nullable로 변경 (R7 deprecated, drop은 R7.5)
        batch_op.alter_column("customer_token", existing_type=sa.String(80), nullable=True)
        batch_op.alter_column("customer_name", existing_type=sa.String(80), nullable=True)
        batch_op.alter_column("customer_phone", existing_type=sa.String(30), nullable=True)
        batch_op.alter_column("customer_address", existing_type=sa.Text(), nullable=True)

    # 6) v3 추가: customer_token의 legacy unique 제약을 명시적으로 제거한다.
    #    0001_initial_schema에서 `sa.Column("customer_token", ..., unique=True)`로 만들었으므로
    #    DB마다 자동 명명된 unique constraint가 존재한다. SQLAlchemy `unique=True`만 모델에서
    #    빼는 것으로는 부족 — 마이그레이션이 실제 DB의 constraint를 drop해야 한다.
    #    같은 그룹의 line N개가 동일 customer_token을 공유하므로 unique violation을 방지.
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        # Postgres 자동 명명 패턴: `<table>_<column>_key`.
        bind.execute(sa.text("ALTER TABLE orders DROP CONSTRAINT IF EXISTS orders_customer_token_key"))
    elif dialect == "sqlite":
        # SQLite는 unnamed unique constraint를 별도 자동 unique index(`sqlite_autoindex_orders_<N>`)로
        # 만들고 직접 DROP할 수 없다. 그래서 v4에서는 위 batch_alter_table에 `copy_from=orders_target`
        # 으로 명시적 Table 정의(unique=True 없는 v3 스키마)를 전달했다. batch가 reflection을
        # 건너뛰고 우리 정의 기준으로 새 테이블을 만드므로 unique constraint가 자동 소실된다.
        # 따라서 이 분기에서는 추가 SQL이 필요 없다.
        pass
    else:
        # 다른 dialect (예: MySQL): 보통 인덱스 이름과 동일.
        # 운영 dialect가 Postgres/SQLite 외라면 별도 마이그레이션 작성 필요.
        pass

    # 7) v3 추가: 일반 인덱스 ix_orders_customer_token은 0001에서 별도로 만들었다 (line 124).
    #    검색 디버깅용으로 남기되, R6 consumer의 get_by_customer_token 호출은 더 이상 없으므로
    #    드롭해도 무방. R7에서는 명시적으로 두지 않고 batch의 reflect에 위임한다.
    #    필요 시 R7.5 cleanup에서 일괄 정리.


def downgrade() -> None:
    # 의도적으로 no-op: R7 데이터 모델 변경은 되돌리지 않는다.
    # 운영 롤백이 필요하면 R7 직전 커밋으로 git revert + DB는 별도 backup에서 복구.
    pass
```

- [ ] **Step 2: SQL 렌더 확인**

```powershell
cd backend; python -m alembic upgrade head --sql 2>&1 | Select-Object -Last 80
```

기대: order_groups CREATE TABLE + INSERT INTO order_groups + UPDATE orders + ALTER TABLE orders 모두 출력.

- [ ] **Step 3: dev DB에 적용 + 검증**

```powershell
cd backend; python -m alembic upgrade head
python -c "from app.db.session import SessionLocal; from sqlalchemy import text; s = SessionLocal(); print('groups:', s.execute(text('SELECT COUNT(*) FROM order_groups')).scalar()); print('orders w/o group:', s.execute(text('SELECT COUNT(*) FROM orders WHERE group_id IS NULL')).scalar())"
```

기대: groups 수 = 기존 orders 수, orders without group = 0.

- [ ] **Step 4: 커밋**

```bash
git add backend/alembic/versions/0008_order_groups.py
git commit -m "chore(db): order_groups 테이블 + 기존 Order 1:1 그룹 백필"
```

---

## Task 3 — 스키마 갱신 (`AdminOrderGroupRead`, `CustomerOrderGroupRead`, 기존 DTO 정리)

**Files:** Modify `backend/app/schemas/order.py`

**구현 의도:**
- `OrderGroupBase`: customer 정보 + source_channel + customer_visible_payment + notes
- `AdminOrderGroupRead`: 그룹 + 그 안 line 리스트(AdminOrderRead). 운영자가 그룹 단위 상세 확인용.
- `CustomerOrderGroupRead`: 고객 그룹 응답 — 고객 정보 + line 카드 리스트.
- 기존 `OrderBase`/`OrderCreate`/`OrderUpdate`에서 customer_*, source_channel, customer_visible_payment **제거** (그룹으로 이동).
- 기존 `AdminOrderRead`의 `customer_token` 제거 (그룹에 있음). `group_id` 추가.
- 신규 `OrderLineCreate`: 라인 1개 생성용 (group 정보 제외, line 운영 필드만).

- [ ] **Step 1: 신규/수정 클래스 정의**

`backend/app/schemas/order.py` 본문을 다음 구조로 재정렬한다 (예시 — 실제 구현에서는 기존 import/필드 보존하며 수정).

```python
from datetime import date, datetime

from pydantic import Field

from app.domain.constants import OrderStatus, PhotoType
from app.schemas.common import ApiModel, TimelineEventRead
from app.schemas.message import MessageLogRead
from app.schemas.photo import PartnerPhotoRead, PhotoRead


# --- OrderGroup ---

class OrderGroupBase(ApiModel):
    customer_name: str
    customer_phone: str
    customer_address: str
    source_channel: str | None = None
    customer_visible_payment: bool = False
    notes: str | None = None


class OrderGroupCreate(OrderGroupBase):
    lines: list["OrderLineCreate"] = Field(default_factory=list, min_length=1)


class OrderGroupUpdate(ApiModel):
    customer_name: str | None = None
    customer_phone: str | None = None
    customer_address: str | None = None
    source_channel: str | None = None
    customer_visible_payment: bool | None = None
    notes: str | None = None


class AdminOrderGroupRead(OrderGroupBase):
    id: str
    customer_token: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    lines: list["AdminOrderRead"] = Field(default_factory=list)


# --- Order (=line) ---

class OrderLineBase(ApiModel):
    """Group 정보 없이 line 운영 필드만 포함."""
    status: OrderStatus = OrderStatus.NEW
    received_date: date
    scheduled_date: date | None = None
    requested_time: str | None = None
    partner_id: str | None = None
    team_name: str | None = None
    service_category_id: str | None = None
    service_item_id: str | None = None
    service_name: str
    size_or_quantity: str | None = None
    service_detail: str | None = None
    special_request: str | None = None
    total_amount: float | None = Field(default=None, ge=0)
    deposit_amount: float | None = Field(default=None, ge=0)
    balance_amount: float | None = Field(default=None, ge=0)
    onsite_extra_amount: float | None = Field(default=None, ge=0)
    vat_type: str | None = None
    payment_status: str | None = None
    payment_memo: str | None = None
    evidence_memo: str | None = None
    partner_payment_amount: float | None = Field(default=None, ge=0)
    partner_payment_status: str | None = None


class OrderLineCreate(OrderLineBase):
    pass


class OrderUpdate(ApiModel):
    """기존 OrderUpdate에서 customer_*, source_channel, customer_visible_payment 제거."""
    status: OrderStatus | None = None
    received_date: date | None = None
    scheduled_date: date | None = None
    requested_time: str | None = None
    partner_id: str | None = None
    team_name: str | None = None
    service_category_id: str | None = None
    service_item_id: str | None = None
    service_name: str | None = None
    size_or_quantity: str | None = None
    service_detail: str | None = None
    special_request: str | None = None
    total_amount: float | None = Field(default=None, ge=0)
    deposit_amount: float | None = Field(default=None, ge=0)
    balance_amount: float | None = Field(default=None, ge=0)
    onsite_extra_amount: float | None = Field(default=None, ge=0)
    vat_type: str | None = None
    payment_status: str | None = None
    payment_memo: str | None = None
    evidence_memo: str | None = None
    partner_payment_amount: float | None = Field(default=None, ge=0)
    partner_payment_status: str | None = None


class AdminOrderRead(OrderLineBase):
    """라인 단일 응답. customer_token, customer_* 모두 그룹으로 이전."""
    id: str
    group_id: str
    customer_name: str  # 그룹에서 inherit. DTO 변환 함수가 채움.
    customer_phone: str
    customer_address: str
    source_channel: str | None = None
    customer_visible_payment: bool = False
    customer_token: str  # 그룹의 token을 표시 (운영 화면 표시용)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    timeline: list[TimelineEventRead] = Field(default_factory=list)


class AdminOrderDetailRead(AdminOrderRead):
    photos: list[PhotoRead] = Field(default_factory=list)
    message_logs: list[MessageLogRead] = Field(default_factory=list)
    sibling_lines: list["AdminOrderSiblingRead"] = Field(default_factory=list)


class AdminOrderSiblingRead(ApiModel):
    """그룹 내 형제 line의 요약. OrderDetailPage 우측 패널용."""
    id: str
    status: OrderStatus
    service_name: str
    partner_id: str | None = None
    team_name: str | None = None
    total_amount: float | None = None


# --- Partner DTO (D3: 변경 없음) ---

class PartnerJobRead(ApiModel):
    id: str
    status: OrderStatus
    scheduled_date: date | None
    requested_time: str | None
    service_name: str
    size_or_quantity: str | None = None
    service_detail: str | None = None
    special_request: str | None = None
    customer_name: str  # 그룹에서 inherit (DTO 변환 시 채움)
    customer_phone: str
    customer_address: str
    photos: list[PartnerPhotoRead] = Field(default_factory=list)


# --- Customer DTOs ---

class CustomerOrderLineRead(ApiModel):
    """그룹 내 line 1개의 고객용 표현."""
    id: str
    status: OrderStatus
    scheduled_date: date | None
    requested_time: str | None
    service_name: str
    size_or_quantity: str | None = None
    service_detail: str | None = None
    special_request: str | None = None
    total_amount: float | None = None
    deposit_amount: float | None = None
    balance_amount: float | None = None
    payment_status: str | None = None
    photos: list["CustomerPhotoRead"] = Field(default_factory=list)


class CustomerPhotoRead(ApiModel):
    id: str
    photo_type: PhotoType
    file_url: str
    file_name: str | None = None


class CustomerOrderGroupRead(ApiModel):
    """고객이 verify 후 보는 응답 — 그룹 + 그 안의 line N개."""
    id: str
    customer_name: str
    customer_phone: str
    customer_address: str
    customer_visible_payment: bool = False  # v2: Task 13의 결제 표시 분기에 필요
    lines: list[CustomerOrderLineRead] = Field(default_factory=list)


class CustomerVerifyRequest(ApiModel):
    phone_suffix: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")


# 기존 별칭 호환 (CustomerOrderRead → 새 이름으로 마이그레이션 중에는 alias 유지)
CustomerOrderRead = CustomerOrderGroupRead  # noqa: E305 (R7.5 cleanup에서 제거 예정)
```

> **호환성:** `CustomerOrderRead`를 `CustomerOrderGroupRead`의 alias로 일단 두는 이유는 customer route의 `response_model` 한 줄 변경으로 마이그레이션을 한 step에 끝낼 수 없기 때문. R7.5에서 alias 제거 + 호출처 일괄 갱신.

- [ ] **Step 2: forward reference 해석**

`OrderGroupCreate.lines`와 `AdminOrderGroupRead.lines`는 forward reference이므로 파일 끝에 `model_rebuild()` 호출.

```python
OrderGroupCreate.model_rebuild()
AdminOrderGroupRead.model_rebuild()
AdminOrderDetailRead.model_rebuild()
CustomerOrderLineRead.model_rebuild()
```

- [ ] **Step 3: 컴파일 + 커밋**

```powershell
python -m compileall backend/app/schemas/order.py
```

```bash
git add backend/app/schemas/order.py
git commit -m "feat(schemas): OrderGroup DTO 신설 + customer_* 컬럼을 그룹으로 이전"
```

---

## Task 4 — Repository 분리: `OrderGroupRepository` 신설 + `OrderRepository` 정리

**Files:**
- Create: `backend/app/repositories/order_groups.py`
- Modify: `backend/app/repositories/orders.py`

- [ ] **Step 1: `OrderGroupRepository` 신규**

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.order_group import OrderGroup
from app.repositories.base import Repository


class OrderGroupRepository(Repository[OrderGroup]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, OrderGroup)

    def get_by_customer_token(self, token: str) -> OrderGroup | None:
        stmt = select(OrderGroup).where(OrderGroup.customer_token == token)
        return self.db.scalar(stmt)

    def list_lines(self, group_id: str) -> list[Order]:
        stmt = (
            select(Order)
            .where(Order.group_id == group_id)
            .order_by(Order.created_at.asc(), Order.id.asc())
        )
        return list(self.db.scalars(stmt))
```

- [ ] **Step 2: `OrderRepository` 정리**

`get_by_customer_token` 제거 (그룹 레포로 이동). 신규 `list_by_group` 추가.

```python
# 제거:
# def get_by_customer_token(self, token: str) -> Order | None: ...

# 추가:
def list_by_group(self, group_id: str) -> list[Order]:
    stmt = select(Order).where(Order.group_id == group_id).order_by(Order.created_at.asc())
    return list(self.db.scalars(stmt))
```

> **확인:** `get_by_customer_token` 호출처는 `backend/app/api/routes/customer/orders.py:31` 1곳. Task 6에서 그룹 레포 호출로 갱신.

- [ ] **Step 3: 컴파일 + 커밋**

```bash
git add backend/app/repositories/
git commit -m "feat(repo): OrderGroupRepository 신설 + customer_token 조회 위치 이동"
```

---

## Task 5 — `OrderService.create_group` + `add_line_to_group` 신설, 기존 `create` deprecated

**Files:** Modify `backend/app/services/orders.py`

**구현 의도:**
- 신규 `OrderService.create_group(payload: OrderGroupCreate, *, actor_user_id) -> OrderGroup`:
  1. `OrderGroup` row 생성 (`customer_token = token_urlsafe(24)`, 정규화된 phone).
  2. `payload.lines` 각각에 대해 `_create_line_internal(group, line_payload, actor_user_id)` 호출 (Order row + timeline 이벤트 + 협력사 배정 시 partner_assigned 기록).
  3. 한 트랜잭션으로 commit.
- 신규 `OrderService.add_line_to_group(group_id, line_payload, actor_user_id) -> Order`:
  - 기존 그룹에 라인 1개 추가 (운영 중 라인 추가 시나리오).
- 기존 `OrderService.create`는 **deprecated** — 내부적으로 1-line 그룹을 만드는 호환 wrapper로 유지. 호출처(테스트·시드 등)는 점진 이전.
- 기존 `OrderService.update`는 변경 없음 (Order line 1개 수정).
- 신규 `OrderGroupService` 또는 `OrderService.update_group(group_id, payload)`: 그룹 정보 수정 (customer_*, source_channel 등).

- [ ] **Step 1: `_create_line_internal` 추출**

기존 `create` 내부의 Order 생성 로직을 재사용 가능하게 분리.

**v2 변경 (high finding 해소):** 신규 Order 생성 시 그룹의 customer_*/token/source_channel/customer_visible_payment 값을 **Order의 deprecated 컬럼에 함께 복사**한다. R7 동안 R6 consumer(`to_partner_job_dto`, `MessageService`, admin calendar, dashboard recent activity 등)가 여전히 `order.customer_*`/`order.customer_token`을 읽기 때문에 NULL이 들어가면 협력사 화면 500, 메시지 발송 실패, 운영 화면 검증 실패가 발생한다. R7.5 cleanup에서 호환 코드와 deprecated 컬럼을 동시 제거한다.

```python
def _create_line_internal(
    self,
    group: OrderGroup,
    payload: OrderLineCreate,
    *,
    actor_user_id: str | None,
) -> Order:
    values = payload.model_dump()
    self._apply_service_catalog(values)
    order = Order(
        id=str(uuid4()),
        group_id=group.id,
        # v2: R6 consumer 호환을 위해 group의 customer_* 를 deprecated 컬럼에 복사.
        # 이 코드는 R7.5에서 deprecated 컬럼 drop과 함께 제거된다.
        customer_token=group.customer_token,
        customer_name=group.customer_name,
        customer_phone=group.customer_phone,
        customer_address=group.customer_address,
        source_channel=group.source_channel,
        customer_visible_payment=group.customer_visible_payment,
        **values,
    )
    self.orders.add(order)
    self.timeline.record(
        order_id=order.id,
        actor_user_id=actor_user_id,
        event_type=TimelineEventType.CREATED,
        title="주문 생성",
    )
    if order.partner_id:
        self.timeline.record(
            order_id=order.id,
            actor_user_id=actor_user_id,
            event_type=TimelineEventType.PARTNER_ASSIGNED,
            title="협력사 배정",
            metadata={"partner_id": order.partner_id},
        )
    return order
```

> **`customer_token` unique 제약 (v3 정리)**: Task 1 Step 2에서 모델의 `unique=True`를 제거했고, Task 2 마이그레이션 step 6에서 0001의 실제 unique constraint를 dialect 분기로 drop한다. 같은 그룹 내 line이 같은 token을 공유해도 안전.

- [ ] **Step 2: `create_group` 신규**

```python
def create_group(
    self,
    payload: OrderGroupCreate,
    *,
    actor_user_id: str | None = None,
) -> OrderGroup:
    if not payload.lines:
        raise ValueError("at_least_one_line_required")
    group = OrderGroup(
        id=str(uuid4()),
        customer_token=token_urlsafe(24),
        customer_name=payload.customer_name,
        customer_phone=normalize_phone(payload.customer_phone),
        customer_address=payload.customer_address,
        source_channel=payload.source_channel,
        customer_visible_payment=payload.customer_visible_payment,
        notes=payload.notes,
    )
    self.db.add(group)
    self.db.flush()  # group.id 확정 후 라인 생성
    for line_payload in payload.lines:
        self._create_line_internal(group, line_payload, actor_user_id=actor_user_id)
    self.db.commit()
    self.db.refresh(group)
    return group
```

- [ ] **Step 3: `add_line_to_group` 신규**

```python
def add_line_to_group(
    self,
    group_id: str,
    payload: OrderLineCreate,
    *,
    actor_user_id: str | None = None,
) -> Order:
    group = self.db.get(OrderGroup, group_id)
    if group is None:
        raise ValueError("group_not_found")
    order = self._create_line_internal(group, payload, actor_user_id=actor_user_id)
    self.db.commit()
    self.db.refresh(order)
    return order
```

- [ ] **Step 4: 기존 `create` 호환 wrapper — 실제 1-line group 위임으로 구현**

**v2 변경 (medium finding 해소)**: v1은 `NotImplementedError`를 던졌으나, 기존 `POST /admin/orders` 라우트와 외부 호출처가 R7 직후에도 작동해야 한다 (기존 e2e, 외부 통합, import 스크립트). 따라서 wrapper를 실제로 동작하는 1-line group 위임으로 구현. R7.5에서 wrapper + 기존 라우트 동시 제거.

기존 `OrderCreate` 스키마도 호환을 위해 유지하되 위치만 deprecated 섹션으로 옮긴다.

```python
class OrderCreate(ApiModel):
    """Deprecated (R7): use OrderGroupCreate instead. 1-line 그룹 호환 wrapper용으로만 유지.
    R7.5 cleanup에서 제거.
    """
    # 기존 OrderBase의 모든 필드 그대로 (customer_*, source_channel, customer_visible_payment 포함).
    # 정의 본문은 기존 OrderBase + service line 필드 합본. 코드는 v1 시점 OrderBase의 model_dump 시그니처 그대로.
    ...
```

`OrderService.create` 본문:

```python
def create(self, payload: OrderCreate, *, actor_user_id: str | None = None) -> Order:
    """Deprecated (R7): 1-line OrderGroup으로 위임한다. R7.5에서 제거 예정."""
    # 그룹 1개 + line 1개로 분해.
    group_payload = OrderGroupCreate(
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        customer_address=payload.customer_address,
        source_channel=payload.source_channel,
        customer_visible_payment=payload.customer_visible_payment,
        notes=None,
        lines=[
            OrderLineCreate(
                status=payload.status,
                received_date=payload.received_date,
                scheduled_date=payload.scheduled_date,
                requested_time=payload.requested_time,
                partner_id=payload.partner_id,
                team_name=payload.team_name,
                service_category_id=payload.service_category_id,
                service_item_id=payload.service_item_id,
                service_name=payload.service_name,
                size_or_quantity=payload.size_or_quantity,
                service_detail=payload.service_detail,
                special_request=payload.special_request,
                total_amount=payload.total_amount,
                deposit_amount=payload.deposit_amount,
                balance_amount=payload.balance_amount,
                onsite_extra_amount=payload.onsite_extra_amount,
                vat_type=payload.vat_type,
                payment_status=payload.payment_status,
                payment_memo=payload.payment_memo,
                evidence_memo=payload.evidence_memo,
                partner_payment_amount=payload.partner_payment_amount,
                partner_payment_status=payload.partner_payment_status,
            )
        ],
    )
    group = self.create_group(group_payload, actor_user_id=actor_user_id)
    # 1-line이므로 첫 line을 반환.
    lines = OrderGroupRepository(self.db).list_lines(group.id)
    return lines[0]
```

> **기존 `POST /admin/orders` 라우트**: 변경 없이 유지. 내부적으로 `OrderService(db).create()` → `create_group` 위임 흐름. R7.5에서 라우트 + wrapper 동시 제거.
>
> **호출처 점검:**
>
> ```powershell
> Select-String -Path backend/ -Pattern "OrderService\(.+\)\.create\(" -Recurse
> Select-String -Path backend/ -Pattern "OrderCreate" -Recurse
> ```
>
> 출력에서 R7 신규 코드(`create_group`/`add_line_to_group`)와 wrapper(`create`) 외에 다른 호출처가 남아 있는지 확인. e2e helper `createAssignedOrder`는 R7에서 새 그룹 라우트로 갈아엎으므로 wrapper 의존도 점차 줄어든다.

- [ ] **Step 5: 컴파일 + 커밋**

```bash
git add backend/app/services/orders.py
git commit -m "feat(service): create_group + add_line_to_group 신설, create 호환 wrapper deprecated"
```

---

## Task 6 — Admin/Customer 라우터 갱신

**Files:**
- Modify: `backend/app/api/routes/admin/orders.py`
- Modify: `backend/app/api/routes/customer/orders.py`
- Modify: `backend/app/api/router.py` (`/admin/order-groups` prefix 등록 확인)

- [ ] **Step 1: Admin 그룹 엔드포인트 추가**

`backend/app/api/routes/admin/orders.py`에 새 그룹 라우트들 추가. 기존 `/orders` 라우트들은 line 단위로 유지.

```python
from app.repositories.order_groups import OrderGroupRepository
from app.schemas.order import (
    AdminOrderGroupRead,
    OrderGroupCreate,
    OrderGroupUpdate,
    OrderLineCreate,
)


@router.post("/groups", response_model=AdminOrderGroupRead, status_code=status.HTTP_201_CREATED)
def create_order_group(
    payload: OrderGroupCreate,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
):
    try:
        group = OrderService(db).create_group(payload, actor_user_id=user.id)
    except ValueError as exc:
        raise order_http_error(exc) from exc
    return to_admin_group_dto(group, lines=OrderGroupRepository(db).list_lines(group.id))


@router.get("/groups/{group_id}", response_model=AdminOrderGroupRead)
def get_order_group(
    group_id: str,
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
):
    group_repo = OrderGroupRepository(db)
    group = group_repo.get(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="group_not_found")
    return to_admin_group_dto(group, lines=group_repo.list_lines(group_id))


@router.post("/groups/{group_id}/lines", response_model=AdminOrderRead, status_code=status.HTTP_201_CREATED)
def add_line(
    group_id: str,
    payload: OrderLineCreate,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
):
    try:
        order = OrderService(db).add_line_to_group(group_id, payload, actor_user_id=user.id)
    except ValueError as exc:
        raise order_http_error(exc) from exc
    return to_admin_order_dto(order, group=OrderGroupRepository(db).get(group_id))


# v2 추가 (medium finding 해소): 그룹 메타데이터 수정.
# 관리자가 OrderDetailPage 또는 OrderFormPage 수정 모드에서 고객명/전화/주소/source_channel/
# customer_visible_payment를 변경하면 이 라우트가 호출된다. group 자체 + 모든 line의
# deprecated customer_* 컬럼을 함께 갱신해 R6 consumer 호환을 유지한다.
@router.patch("/groups/{group_id}", response_model=AdminOrderGroupRead)
def update_order_group(
    group_id: str,
    payload: OrderGroupUpdate,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
):
    try:
        group = OrderService(db).update_group(group_id, payload, actor_user_id=user.id)
    except ValueError as exc:
        raise order_http_error(exc) from exc
    return to_admin_group_dto(group, lines=OrderGroupRepository(db).list_lines(group.id))
```

> **`OrderService.update_group` 신설 명세 (v2)**: `backend/app/services/orders.py`에 추가.
>
> ```python
> def update_group(
>     self,
>     group_id: str,
>     payload: OrderGroupUpdate,
>     *,
>     actor_user_id: str | None = None,
> ) -> OrderGroup:
>     group = self.db.get(OrderGroup, group_id)
>     if group is None:
>         raise ValueError("group_not_found")
>
>     changes = payload.model_dump(exclude_unset=True)
>     if "customer_phone" in changes and changes["customer_phone"] is not None:
>         changes["customer_phone"] = normalize_phone(changes["customer_phone"])
>     for key, value in changes.items():
>         setattr(group, key, value)
>
>     # R6 consumer 호환: 그룹 customer_* 변경 시 모든 자식 line의 deprecated 컬럼도 갱신.
>     # R7.5에서 deprecated 컬럼 drop과 함께 이 sync 코드도 제거.
>     mirror_fields = {"customer_name", "customer_phone", "customer_address",
>                      "source_channel", "customer_visible_payment"}
>     mirror_changes = {k: changes[k] for k in mirror_fields if k in changes}
>     if mirror_changes:
>         lines = self.db.execute(
>             select(Order).where(Order.group_id == group_id)
>         ).scalars().all()
>         for line in lines:
>             for key, value in mirror_changes.items():
>                 setattr(line, key, value)
>
>     self.db.commit()
>     self.db.refresh(group)
>     return group
> ```

> **`to_admin_group_dto` 신설**: `backend/app/services/orders.py`에 추가. 그룹 + 그 안 line N개를 합쳐 `AdminOrderGroupRead` 형태로.
>
> **`to_admin_order_dto` 시그니처 변경**: 두 번째 인자 `group: OrderGroup | None = None` 추가. group에서 customer_*, source_channel, customer_visible_payment를 가져와 DTO에 inject. 호출처는 모두 group을 전달하도록 갱신.

- [ ] **Step 2: 기존 `/orders` 라우트의 DTO 변환 갱신**

```python
@router.get("", response_model=list[AdminOrderRead])
def list_orders(...):
    repo = OrderRepository(db)
    group_repo = OrderGroupRepository(db)
    return [
        to_admin_order_dto(order, group=group_repo.get(order.group_id))
        for order in repo.list_orders()
    ]
```

> N+1 쿼리 우려: 운영 데이터 100건 미만이라 R7에서는 허용. 성능 이슈 발생 시 `JOIN` 기반 `list_with_group` 추가 (R8 후보).

- [ ] **Step 3: Customer 라우트 — 그룹 응답**

`backend/app/api/routes/customer/orders.py`를 다음으로 갱신:

```python
from app.repositories.order_groups import OrderGroupRepository
from app.schemas.order import CustomerOrderGroupRead


@router.post("/{customer_token}/verify", response_model=CustomerOrderGroupRead)
def verify_customer_order(
    customer_token: str,
    payload: CustomerVerifyRequest,
    request: Request,
    db: Session = Depends(get_session),
) -> CustomerOrderGroupRead:
    rate_limit_key = _customer_verify_rate_limit_key(customer_token, request)
    _check_customer_verify_lockout(rate_limit_key)

    group_repo = OrderGroupRepository(db)
    group = group_repo.get_by_customer_token(customer_token)
    if group is None or not phone_suffix_matches(group.customer_phone, payload.phone_suffix):
        _record_customer_verify_failure(rate_limit_key)
        raise HTTPException(status_code=404, detail="order_not_found")
    _reset_customer_verify_failures(rate_limit_key)

    lines = group_repo.list_lines(group.id)
    photo_repo = PhotoRepository(db)
    lines_with_photos = [
        (line, photo_repo.list_for_order(line.id, customer_visible_only=True))
        for line in lines
    ]
    return to_customer_group_dto(group, lines_with_photos=lines_with_photos)
```

> **`to_customer_group_dto` 신설**: `backend/app/services/orders.py`에 추가. group 정보 + 각 line의 `CustomerOrderLineRead` 변환. 기존 `to_customer_order_dto`는 호환을 위해 alias로 잠시 유지 (R7.5에서 제거).
>
> **v2 추가 명세 (medium finding 해소)**: `to_customer_group_dto`는 `group.customer_visible_payment`가 `False`이면 각 line의 `total_amount` / `deposit_amount` / `balance_amount` / `payment_status`를 **모두 `None`으로 명시 처리**한다. 기존 `to_customer_order_dto`(R6)가 line의 `customer_visible_payment` 컬럼으로 분기했던 로직을 그룹 기준으로 옮긴 셈.
>
> ```python
> def to_customer_group_dto(
>     group: OrderGroup,
>     *,
>     lines_with_photos: list[tuple[Order, list[OrderPhoto]]],
> ) -> CustomerOrderGroupRead:
>     return CustomerOrderGroupRead(
>         id=group.id,
>         customer_name=group.customer_name,
>         customer_phone=group.customer_phone,
>         customer_address=group.customer_address,
>         customer_visible_payment=group.customer_visible_payment,
>         lines=[
>             _to_customer_line_dto(line, photos, payment_visible=group.customer_visible_payment)
>             for line, photos in lines_with_photos
>         ],
>     )
>
>
> def _to_customer_line_dto(
>     line: Order,
>     photos: list[OrderPhoto],
>     *,
>     payment_visible: bool,
> ) -> CustomerOrderLineRead:
>     return CustomerOrderLineRead(
>         id=line.id,
>         status=line.status,
>         scheduled_date=line.scheduled_date,
>         requested_time=line.requested_time,
>         service_name=line.service_name,
>         size_or_quantity=line.size_or_quantity,
>         service_detail=line.service_detail,
>         special_request=line.special_request,
>         total_amount=line.total_amount if payment_visible else None,
>         deposit_amount=line.deposit_amount if payment_visible else None,
>         balance_amount=line.balance_amount if payment_visible else None,
>         payment_status=line.payment_status if payment_visible else None,
>         photos=[to_customer_photo_dto(p) for p in photos if p.is_customer_visible],
>     )
> ```

- [ ] **Step 4: 컴파일 + 커밋**

```bash
git add backend/app/api/routes/admin/orders.py backend/app/api/routes/customer/orders.py backend/app/services/orders.py
git commit -m "feat(api): 관리자 그룹 엔드포인트 + 고객 token으로 그룹 응답"
```

---

## Task 7 — 시드 데이터 + dashboard 영향 검토

**Files:**
- Modify: `backend/app/db/seed.py`
- Verify (변경 없음): `backend/app/services/dashboard.py`

- [ ] **Step 1: seed_dev.py 갱신**

기존 `Order` 직접 생성을 `OrderGroup` + `Order` 1개로 분리. `DEV_CUSTOMER_TOKEN`은 그룹의 token으로 이전.

```python
def ensure_sample_order(db: Session) -> None:
    if db.get(Order, DEV_ORDER_ID) is not None:
        return
    group = OrderGroup(
        id=DEV_ORDER_GROUP_ID,
        customer_token=DEV_CUSTOMER_TOKEN,
        customer_name="박고객",
        customer_phone="010-9999-5432",
        customer_address="서울특별시 강남구 …",
        source_channel="seed",
        customer_visible_payment=False,
    )
    db.add(group)
    db.flush()

    order = Order(
        id=DEV_ORDER_ID,
        group_id=group.id,
        status=OrderStatus.SCHEDULE_CONFIRMED,
        received_date=date(2026, 5, 1),
        scheduled_date=date(2026, 5, 4),
        # ... 기존 필드들 그대로 ...
        # customer_token, customer_*, source_channel, customer_visible_payment 등은
        # 그룹에 있으므로 line에서는 제거.
    )
    db.add(order)
```

새 상수 `DEV_ORDER_GROUP_ID = "seed-order-group-2450"` 추가.

- [ ] **Step 2: dashboard 검토**

`backend/app/services/dashboard.py`는 status 카운트가 line(=Order) 단위 그대로. R7에서 변경 없음.

```powershell
python -m compileall backend/app/services/dashboard.py
```

- [ ] **Step 3: 커밋**

```bash
git add backend/app/db/seed.py
git commit -m "chore(seed): 시드 데이터를 OrderGroup + line 구조로 분리"
```

---

## Task 8 — 백엔드 테스트 갱신 + 신규 `test_order_groups.py`

**Files:**
- Modify: `backend/tests/test_auth_integration.py`, `test_photo_auto_visibility.py`, `test_photo_revoke.py`, `test_photo_race_guards.py` (핫픽스에서 추가됨)
- Create: `backend/tests/test_order_groups.py`

- [ ] **Step 1: 기존 테스트 갱신 — Order 직접 생성 → 그룹 + line**

다음 패턴을 찾아 갱신한다.

```powershell
Select-String -Path backend/tests/ -Pattern "Order\(.+customer_name|customer_token|OrderService\(.+\)\.create\(" -Recurse
```

- 매치되는 곳은 모두 `OrderGroup` 1개 + `Order` 1개로 분리. customer_* 인자는 OrderGroup으로.
- 시드 fixture(`seed_order_id`)는 변경 없음 (자동으로 새 seed.py 적용).

**주의:** `test_auth_integration.py:1011, 1072, 1086` 등 Order 직접 생성 라인은 모두 OrderGroup 백필이 필요하다. v8까지 R6 review에서 정리한 12개 line 단언이 customer_*에 접근하면 group을 통해 inherit되는지도 확인.

- [ ] **Step 2: `test_order_groups.py` 신규**

```python
from fastapi.testclient import TestClient

from app.domain.constants import OrderStatus


def test_create_group_with_multiple_lines(client: TestClient, seed_admin_token: str) -> None:
    """관리자가 라인 2개를 한 번에 생성. 각 line이 partner 따로 배정 + 결제 따로."""
    response = client.post(
        "/api/admin/orders/groups",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
        json={
            "customer_name": "박고객",
            "customer_phone": "010-1234-5678",
            "customer_address": "서울시 강남구",
            "source_channel": "test",
            "customer_visible_payment": False,
            "lines": [
                {
                    "status": "신규접수",
                    "received_date": "2026-05-18",
                    "scheduled_date": "2026-05-20",
                    "service_name": "사무실 청소",
                    "total_amount": 300000,
                    "partner_id": "seed-partner-01",
                },
                {
                    "status": "신규접수",
                    "received_date": "2026-05-18",
                    "scheduled_date": "2026-05-21",
                    "service_name": "화장실 청소",
                    "total_amount": 100000,
                    "partner_id": None,
                },
            ],
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert len(body["lines"]) == 2
    assert body["lines"][0]["service_name"] == "사무실 청소"
    assert body["lines"][0]["total_amount"] == 300000
    assert body["lines"][0]["partner_id"] == "seed-partner-01"
    assert body["lines"][1]["service_name"] == "화장실 청소"
    assert body["lines"][1]["partner_id"] is None
    # 두 line이 같은 group, 같은 customer_token 공유
    assert body["lines"][0]["group_id"] == body["lines"][1]["group_id"] == body["id"]
    assert body["lines"][0]["customer_token"] == body["customer_token"]


def test_customer_verify_returns_group_with_lines(client, seed_admin_token, seed_order_id) -> None:
    """customer_token으로 verify하면 그룹 + line 리스트가 반환된다."""
    # seed 데이터의 customer_token으로 검증.
    response = client.post(
        f"/api/customer/orders/ct2_seed-customer-token-2450/verify",
        json={"phone_suffix": "5432"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "lines" in body
    assert len(body["lines"]) >= 1
    assert all("photos" in line for line in body["lines"])
    # 그룹 정보 노출
    assert body["customer_name"]
    assert body["customer_phone"]


def test_partner_only_sees_own_line_in_group(
    client: TestClient, seed_admin_token: str, seed_partner_token: str
) -> None:
    """그룹에 line 2개 (다른 협력사 배정). 협력사 A는 자기 line만 본다 — D3."""
    # 그룹 생성: line A에 seed partner, line B에 다른 partner (또는 미배정)
    create = client.post(
        "/api/admin/orders/groups",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
        json={
            "customer_name": "박고객",
            "customer_phone": "010-7777-8888",
            "customer_address": "서울시 강남구",
            "lines": [
                {"status": "일정확정", "received_date": "2026-05-18",
                 "service_name": "line A", "partner_id": "seed-partner-01"},
                {"status": "일정확정", "received_date": "2026-05-18",
                 "service_name": "line B", "partner_id": None},
            ],
        },
    ).json()
    line_a_id = create["lines"][0]["id"]
    line_b_id = create["lines"][1]["id"]

    # 협력사가 본인 작업 목록 조회
    jobs = client.get(
        "/api/partner/jobs",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    ).json()
    job_ids = [job["id"] for job in jobs]
    assert line_a_id in job_ids
    assert line_b_id not in job_ids

    # B 직접 조회 시 404
    direct = client.get(
        f"/api/partner/jobs/{line_b_id}",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    )
    assert direct.status_code == 404


def test_partner_dto_does_not_leak_group_metadata(
    client: TestClient, seed_admin_token: str, seed_partner_token: str
) -> None:
    """협력사 응답에 group_id, source_channel, customer_visible_payment, customer_token, notes 가 없어야 한다 (D3 + AGENTS.md)."""
    jobs = client.get(
        "/api/partner/jobs",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    ).json()
    for job in jobs:
        for forbidden in ("group_id", "source_channel", "customer_visible_payment",
                          "customer_token", "notes", "partner_payment_amount",
                          "partner_payment_status", "total_amount", "evidence_memo"):
            assert forbidden not in job, f"partner DTO leak: {forbidden}"


def test_add_line_to_existing_group(client, seed_admin_token) -> None:
    """기존 그룹에 라인 1개 추가."""
    group = client.post(
        "/api/admin/orders/groups",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
        json={
            "customer_name": "박고객", "customer_phone": "010-3333-4444",
            "customer_address": "서울", "lines": [
                {"status": "신규접수", "received_date": "2026-05-18", "service_name": "line 1"}
            ],
        },
    ).json()

    add = client.post(
        f"/api/admin/orders/groups/{group['id']}/lines",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
        json={"status": "신규접수", "received_date": "2026-05-18", "service_name": "line 2"},
    )
    assert add.status_code == 201
    assert add.json()["group_id"] == group["id"]

    refreshed = client.get(
        f"/api/admin/orders/groups/{group['id']}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    ).json()
    assert len(refreshed["lines"]) == 2


def test_partial_cancel_does_not_cancel_other_lines(client, seed_admin_token) -> None:
    """D6: line A를 취소해도 line B는 진행."""
    group = client.post(
        "/api/admin/orders/groups",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
        json={
            "customer_name": "박", "customer_phone": "010-5555-6666",
            "customer_address": "서울", "lines": [
                {"status": "일정확정", "received_date": "2026-05-18", "service_name": "A"},
                {"status": "일정확정", "received_date": "2026-05-18", "service_name": "B"},
            ],
        },
    ).json()
    line_a_id, line_b_id = group["lines"][0]["id"], group["lines"][1]["id"]

    client.patch(
        f"/api/admin/orders/{line_a_id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
        json={"status": OrderStatus.CANCELLED.value},
    )

    refreshed = client.get(
        f"/api/admin/orders/groups/{group['id']}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    ).json()
    statuses = {line["id"]: line["status"] for line in refreshed["lines"]}
    assert statuses[line_a_id] == OrderStatus.CANCELLED.value
    assert statuses[line_b_id] == "일정확정"  # 영향 받지 않음
```

- [ ] **Step 3: 전체 테스트 실행**

```powershell
cd backend; python -m pytest -q
```

- [ ] **Step 4: 커밋**

```bash
git add backend/tests/
git commit -m "test(orders): 멀티라인 시나리오 + 기존 가정 갱신"
```

---

## Task 9 — 프론트 API 클라이언트 확장

**Files:** Modify `frontend/src/api/admin.ts`, `frontend/src/api/customer.ts`

- [ ] **Step 1: admin.ts에 그룹 함수 추가**

```typescript
export function createOrderGroup(input) {
  return apiRequest('/admin/orders/groups', {
    method: 'POST',
    body: input,
  });
}

export function getAdminOrderGroup(groupId) {
  return apiRequest(`/admin/orders/groups/${encodeURIComponent(groupId)}`);
}

export function addLineToGroup(groupId, input) {
  return apiRequest(`/admin/orders/groups/${encodeURIComponent(groupId)}/lines`, {
    method: 'POST',
    body: input,
  });
}

// v2 추가: 그룹 메타데이터 PATCH (edit 모드의 고객 정보·source_channel 변경 등).
export function updateAdminOrderGroup(groupId, input) {
  return apiRequest(`/admin/orders/groups/${encodeURIComponent(groupId)}`, {
    method: 'PATCH',
    body: input,
  });
}
```

> 기존 `createAdminOrder`는 R7에서 더 이상 호출되지 않아야 한다. OrderFormPage에서 호출 전환 (Task 10).

- [ ] **Step 2: customer.ts 응답 타입은 변경 불필요**

response가 group + lines 구조로 바뀌었지만 클라이언트는 그대로 받아 `setOrder(...)`만 하면 됨. UI 변경은 Task 13.

- [ ] **Step 3: 커밋**

```bash
git add frontend/src/api/admin.ts
git commit -m "feat(api-client): order group 함수 추가"
```

---

## Task 10 — OrderFormPage 대규모 갱신: 라인 리스트 편집

**Files:** Modify `frontend/src/features/admin/orders/OrderFormPage.tsx`

**구현 의도:**
- form state를 `{ group: {customer_*, source_channel, customer_visible_payment, notes}, lines: [{...line 필드...}] }` 구조로 재구성.
- "고객 정보" 섹션은 group 1번만 입력.
- "상품 / 일정" 섹션이 lines 리스트로. 각 line이 `<Section>` 카드.
- "+ 라인 추가" 버튼 → `lines` 배열에 빈 line 추가.
- 각 line별로 카테고리/상세상품 select (R6 R1), 협력사 select, 일정, 금액, 협력사 정산.
- 라인별 "이 라인 삭제" 버튼 (lines.length > 1일 때만 활성).
- 저장 시 `createOrderGroup({customer 정보, lines: [...]})` 호출.
- 수정 모드(`mode === 'edit'`)는 R7 v1 범위 밖 — 사용자가 "신규 주문 등록"만 명시. **수정 모드는 v1에서 동작 유지**(기존 single-order PATCH 그대로) 하되, 새 line 추가는 별도 액션으로.

- [ ] **Step 1: form state 재구성**

```javascript
function createEmptyGroupForm() {
  return {
    customer_name: '',
    customer_phone: '',
    customer_address: '',
    source_channel: '',
    customer_visible_payment: false,
    notes: '',
    lines: [createEmptyLineForm()],
  };
}

function createEmptyLineForm() {
  return {
    status: ORDER_STATUSES[0],
    received_date: todayString(),
    scheduled_date: '',
    requested_time: '',
    partner_id: '',
    team_name: '',
    service_category_id: '',
    service_item_id: '',
    service_name: '',
    size_or_quantity: '',
    service_detail: '',
    special_request: '',
    total_amount: '',
    deposit_amount: '',
    balance_amount: '',
    onsite_extra_amount: '',
    vat_type: '',
    payment_status: '',
    payment_memo: '',
    evidence_memo: '',
    partner_payment_amount: '',
    partner_payment_status: '',
  };
}
```

- [ ] **Step 2: handler 재정비**

```javascript
const setGroupField = (key, value) => {
  setForm((current) => ({ ...current, [key]: value }));
};

const setLineField = (lineIndex, key, value) => {
  setForm((current) => {
    const nextLines = current.lines.slice();
    nextLines[lineIndex] = { ...nextLines[lineIndex], [key]: value };
    return { ...current, lines: nextLines };
  });
};

const addLine = () => {
  setForm((current) => ({ ...current, lines: [...current.lines, createEmptyLineForm()] }));
};

const removeLine = (lineIndex) => {
  setForm((current) => {
    if (current.lines.length <= 1) return current;
    const nextLines = current.lines.filter((_, i) => i !== lineIndex);
    return { ...current, lines: nextLines };
  });
};
```

- [ ] **Step 3: 카테고리/상세상품/협력사/금액 line별로**

R6의 카테고리/상세상품 2단계 드롭다운(Task 7 R6)을 line별로 반복. 각 line block의 testid는 `order-line-{lineIndex}-service-category` 형태.

- [ ] **Step 4: handleSubmit 갱신 — createOrderGroup 호출**

**v2 변경 (medium finding 해소)**: edit 모드도 단순 line PATCH가 아니라 group 메타데이터 + line PATCH를 함께 처리한다. 그렇지 않으면 관리자가 수정 모드에서 고객명/전화/주소/source_channel을 바꿔도 그룹 source-of-truth에 반영되지 않는다. edit 모드에서는 `orderId`(=line id)로 진입했으니 먼저 그 line의 `group_id`를 받아두고, 변경된 그룹 필드가 있으면 `updateAdminOrderGroup(group_id, ...)`을, line 필드 변경이 있으면 `updateAdminOrder(orderId, ...)`을 호출.

```javascript
const handleSubmit = async (event) => {
  event.preventDefault();
  setError(null);
  if (!form.customer_name.trim() || !form.customer_phone.trim() || !form.customer_address.trim()) {
    setError('고객명, 연락처, 주소는 필수입니다.');
    return;
  }
  if (form.lines.some((line) => !line.service_name.trim())) {
    setError('모든 라인의 상품명은 필수입니다.');
    return;
  }
  setIsSaving(true);
  try {
    if (mode === 'edit' && orderId) {
      // v2: edit 모드 — 그룹 메타데이터 + 단일 line PATCH 함께 호출.
      // groupId는 useEffect에서 getAdminOrder 호출 시 응답의 group_id로 받아두었다고 가정.
      await updateAdminOrderGroup(form.group_id, toGroupMetadataPayload(form));
      const saved = await updateAdminOrder(orderId, toLinePayload(form.lines[0]));
      onSaved?.(saved);
    } else {
      const payload = toGroupCreatePayload(form);
      const saved = await createOrderGroup(payload);
      onSaved?.(saved);
    }
  } catch (requestError) {
    setError(requestError?.message || '주문을 저장하지 못했습니다.');
  } finally {
    setIsSaving(false);
  }
};
```

> **edit 모드 form state**: useEffect에서 `getAdminOrder(orderId)` 호출 후 응답의 `group_id`를 `form.group_id`에 저장. 응답의 customer_*도 그룹에서 inherit된 값으로 form 초기화. line 정보는 응답의 line 필드로 form.lines[0]에 채움.

- [ ] **Step 5: testid 명시**

- 그룹 정보 필드: 기존 `order-customer-name` 등 유지
- 라인별 필드: `order-line-{lineIndex}-service-category`, `order-line-{lineIndex}-service-item`, `order-line-{lineIndex}-service-name`, `order-line-{lineIndex}-partner`, `order-line-{lineIndex}-total-amount` 등
- "+ 라인 추가" 버튼: `order-add-line`
- "이 라인 삭제" 버튼: `order-remove-line-{lineIndex}`
- 저장 버튼은 기존 `order-save` 유지

- [ ] **Step 6: typecheck + lint + 커밋**

```powershell
cd frontend; npm run typecheck; npm run lint
```

```bash
git add frontend/src/features/admin/orders/OrderFormPage.tsx
git commit -m "feat(orders): 신규 주문 폼 라인 리스트 편집 UI"
```

---

## Task 11 — OrdersPage 그룹 시각 묶음

**Files:** Modify `frontend/src/features/admin/orders/OrdersPage.tsx`

**구현 의도:**
- 행은 그대로 line(=Order) 단위. 같은 group_id 끼리 시각적으로 묶음 표현.
- 정렬: group_id 기준으로 묶고 group 내부에서는 기존 정렬(방문일/접수일) 유지.
- 묶음 표현: 같은 group의 첫 행은 좌측 색띠, 두 번째 행부터는 들여쓰기 + "└" 같은 트리 아이콘.
- 같은 group의 모든 line이 `취소` 상태이면 group 묶음에 "취소됨" 배지 (D6 시각 표시).

- [ ] **Step 1: `toOrderRow`에 `groupId` 보존**

```javascript
function toOrderRow(order) {
  return {
    id: order.id,
    groupId: order.group_id || null,
    // ... 나머지 ...
  };
}
```

- [ ] **Step 2: filtered 결과를 그룹화**

```javascript
const groupedFiltered = React.useMemo(() => {
  // 같은 groupId끼리 인접하게 정렬한 뒤 각 행에 isGroupFirst, isGroupLast 메타 부여
  const sorted = [...filtered].sort((a, b) => {
    const aKey = `${a.groupId || a.id}|${a.scheduledDate || ''}|${a.id}`;
    const bKey = `${b.groupId || b.id}|${b.scheduledDate || ''}|${b.id}`;
    return aKey.localeCompare(bKey);
  });
  return sorted.map((row, idx) => {
    const isGroupFirst = idx === 0 || sorted[idx - 1].groupId !== row.groupId;
    const isGroupLast = idx === sorted.length - 1 || sorted[idx + 1].groupId !== row.groupId;
    return { ...row, isGroupFirst, isGroupLast };
  });
}, [filtered]);
```

- [ ] **Step 3: 테이블 row 렌더에 색띠 + 들여쓰기**

```jsx
<tr ...>
  <td style={{
    borderLeft: o.groupId && !o.isGroupFirst ? '3px solid var(--brand)' : '3px solid transparent',
    paddingLeft: o.groupId && !o.isGroupFirst ? 18 : 6,
  }}>
    {!o.isGroupFirst && <Icon name="cornerDownRight" size={11}/>}
    <input type="checkbox" ... />
  </td>
  ...
</tr>
```

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/features/admin/orders/OrdersPage.tsx
git commit -m "feat(orders): 같은 그룹의 line들을 시각적으로 묶어 표시"
```

---

## Task 12 — OrderDetailPage 그룹 다른 라인 패널

**Files:** Modify `frontend/src/features/admin/orders/OrderDetailPage.tsx`

**구현 의도:**
- 우측 패널에 "이 그룹의 다른 라인" 섹션 추가.
- backend `AdminOrderDetailRead.sibling_lines`에서 가져온 정보 표시 (service_name, status badge, partner, total_amount).
- 클릭하면 해당 line의 detail로 이동.

- [ ] **Step 1: API 응답에 sibling_lines 포함**

`backend/app/api/routes/admin/orders.py`의 `get_order` 핸들러에서 `AdminOrderDetailRead`로 변환할 때 `sibling_lines`를 채운다.

```python
group_repo = OrderGroupRepository(db)
all_lines = group_repo.list_lines(order.group_id)
siblings = [
    AdminOrderSiblingRead(
        id=l.id, status=l.status, service_name=l.service_name,
        partner_id=l.partner_id, team_name=l.team_name, total_amount=l.total_amount,
    )
    for l in all_lines if l.id != order.id
]
return to_admin_order_detail_dto(order, timeline=..., photos=..., message_logs=..., sibling_lines=siblings, group=group_repo.get(order.group_id))
```

- [ ] **Step 2: 프론트 패널 추가**

OrderDetailPage 우측 영역에 신규 섹션:

```jsx
{order.sibling_lines && order.sibling_lines.length > 0 && (
  <div className="card" style={{ padding: 14 }}>
    <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, marginBottom: 8 }}>
      이 그룹의 다른 라인
    </div>
    {order.sibling_lines.map((sibling) => (
      <button
        key={sibling.id}
        data-testid={`order-sibling-${sibling.id}`}
        onClick={() => onOpenOrder?.(sibling.id)}
        style={{ display: 'block', width: '100%', textAlign: 'left', padding: 8, ... }}
      >
        <div>{sibling.service_name}</div>
        <div>{sibling.status} · {sibling.team_name || '미배정'} · ₩{(sibling.total_amount || 0).toLocaleString()}</div>
      </button>
    ))}
  </div>
)}
```

- [ ] **Step 3: 커밋**

```bash
git add backend/app/api/routes/admin/orders.py backend/app/services/orders.py frontend/src/features/admin/orders/OrderDetailPage.tsx
git commit -m "feat(order-detail): 그룹 형제 라인 패널 + sibling_lines DTO 채움"
```

---

## Task 13 — CustomerReservation: line 카드 N개

**Files:** Modify `frontend/src/features/customer/CustomerReservation.tsx`

**구현 의도:**
- verify 응답이 `{customer_name, customer_phone, customer_address, lines: [...]}` 형태로 바뀜.
- 기존 `order.scheduled_date`, `order.service_name`, `order.photos` 사용 위치를 lines 배열로 분기.
- line 카드 N개를 세로로 표시. 각 카드: 일정 / 서비스명 / 사이즈 / 진행상황 배지 / 사진 N장 / 결제 (그룹의 customer_visible_payment=true일 때).
- "사진 준비 중" 상태는 line별로.

- [ ] **Step 1: ReservationContent 갱신**

```jsx
function ReservationContent({ order, onReset }) {
  return (
    <main ...>
      <ReservationHeader group={order} onReset={onReset} />
      {(order.lines || []).map((line) => (
        <ReservationLineCard key={line.id} line={line} customerVisiblePayment={order.customer_visible_payment} />
      ))}
      <TrustFooter />
    </main>
  );
}

function ReservationLineCard({ line, customerVisiblePayment }) {
  return (
    <section data-testid={`customer-line-${line.id}`} ...>
      <header>...{line.service_name} · {line.size_or_quantity}...</header>
      <VisitInfo scheduledDate={line.scheduled_date} requestedTime={line.requested_time}/>
      <CustomerPhotos photos={line.photos}/>
      {customerVisiblePayment && <PaymentSummary line={line}/>}
    </section>
  );
}
```

- [ ] **Step 2: 빈 lines 방어**

`order.lines`가 undefined/빈 배열일 때 "예약 정보가 없습니다" 표시. R7 마이그레이션 직후 잠시 발생 가능.

- [ ] **Step 3: 커밋**

```bash
git add frontend/src/features/customer/CustomerReservation.tsx
git commit -m "feat(customer): 그룹 응답에서 line N개를 카드로 표시"
```

---

## Task 14 — E2E 갱신

**Files:**
- Create: `frontend/e2e/admin-multi-line-e2e.spec.ts`
- Modify: `frontend/e2e/helpers.ts`, `partner-customer-e2e.spec.ts`, `admin-e2e.spec.ts`

- [ ] **Step 1: helpers.ts의 `createAssignedOrder` 갱신**

기존 `createAssignedOrder`는 line 1개만 만드는 헬퍼였다. R7에서는 그룹 + line 1개로 변경.

```typescript
export async function createAssignedOrder(request: APIRequestContext) {
  const adminSession = await loginViaApi(request, 'admin');
  const created = await checkedJson<{
    id: string;
    customer_token: string;
    lines: Array<{ id: string }>;
  }>(await request.post(`${backendUrl}/api/admin/orders/groups`, {
    headers: authHeaders(adminSession.access_token),
    data: {
      customer_name: 'R7 Test Customer',
      customer_phone: '010-8899-7766',
      customer_address: 'Seoul R7 E2E 1',
      source_channel: 'E2E',
      customer_visible_payment: false,
      lines: [
        {
          status: '일정확정',
          received_date: '2026-05-05',
          scheduled_date: '2026-05-14',
          requested_time: '09:30',
          partner_id: SEED_PARTNER_ID,
          team_name: 'R7 E2E Team',
          service_item_id: SEED_SERVICE_ITEM_ID,
          service_name: 'R7 E2E line',
          size_or_quantity: '32py',
          total_amount: 360000,
          payment_status: 'deposit_paid',
        },
      ],
    },
  }));
  return {
    orderId: created.lines[0].id,
    groupId: created.id,
    customerToken: created.customer_token,
    phoneSuffix: '7766',
  };
}

// v2 (low finding 해소): 실제 구현. createAssignedOrder와 동일 패턴이지만 lines 배열을 받는다.
export async function createMultiLineOrder(
  request: APIRequestContext,
  lines: Array<{
    service_name: string;
    partner_id?: string | null;
    total_amount?: number;
    scheduled_date?: string;
    requested_time?: string;
    size_or_quantity?: string;
  }>,
): Promise<{ groupId: string; lineIds: string[]; customerToken: string; phoneSuffix: string }> {
  const adminSession = await loginViaApi(request, 'admin');
  const created = await checkedJson<{
    id: string;
    customer_token: string;
    lines: Array<{ id: string }>;
  }>(await request.post(`${backendUrl}/api/admin/orders/groups`, {
    headers: authHeaders(adminSession.access_token),
    data: {
      customer_name: 'R7 Multi-line Customer',
      customer_phone: '010-2222-3333',
      customer_address: 'Seoul R7 Multi-line E2E',
      source_channel: 'E2E',
      customer_visible_payment: false,
      lines: lines.map((line) => ({
        status: '일정확정',
        received_date: '2026-05-05',
        scheduled_date: line.scheduled_date ?? '2026-05-14',
        requested_time: line.requested_time ?? '09:30',
        partner_id: line.partner_id ?? null,
        team_name: line.partner_id ? 'R7 Multi-line E2E Team' : null,
        service_item_id: SEED_SERVICE_ITEM_ID,
        service_name: line.service_name,
        size_or_quantity: line.size_or_quantity ?? '32py',
        total_amount: line.total_amount ?? 100000,
      })),
    },
  }));
  return {
    groupId: created.id,
    lineIds: created.lines.map((line) => line.id),
    customerToken: created.customer_token,
    phoneSuffix: '3333',
  };
}
```

- [ ] **Step 2: 기존 E2E의 호환**

`partner-customer-e2e.spec.ts`는 `createAssignedOrder` 호출만 하고 line 1개 흐름 그대로 — 변경 없이 동작해야 함.
`admin-photo-review-e2e.spec.ts`도 동일.
`admin-e2e.spec.ts`에서 신규 주문 폼을 사용하는 부분은 새 testid(`order-line-0-service-category` 등)로 갱신.

- [ ] **Step 3: 신규 `admin-multi-line-e2e.spec.ts`**

```typescript
import { expect, test } from '@playwright/test';
import { adminLogin, createMultiLineOrder } from './helpers';

test('관리자가 라인 2개 주문을 생성하고 같은 그룹에 묶여 표시된다', async ({ browser, page, request }) => {
  const flow = await createMultiLineOrder(request, [
    { service_name: 'line A', partner_id: 'seed-partner-01', total_amount: 200000 },
    { service_name: 'line B', partner_id: null, total_amount: 100000 },
  ]);

  await adminLogin(page);
  await page.getByTestId('admin-nav-orders').click();
  await page.getByTestId('admin-orders-page').waitFor();

  // 그룹의 두 line이 같은 색띠로 묶여 표시
  const lineARow = page.getByTestId(`admin-order-row-${flow.lineIds[0]}`);
  const lineBRow = page.getByTestId(`admin-order-row-${flow.lineIds[1]}`);
  await expect(lineARow).toBeVisible();
  await expect(lineBRow).toBeVisible();

  // line A 클릭 → 우측 패널에 line B가 sibling으로 노출
  await lineARow.click();
  await expect(page.getByTestId(`order-sibling-${flow.lineIds[1]}`)).toBeVisible();
});

test('고객이 같은 링크로 두 라인 카드를 모두 본다', async ({ browser, page, request }) => {
  const flow = await createMultiLineOrder(request, [
    { service_name: 'line A', partner_id: 'seed-partner-01', total_amount: 200000 },
    { service_name: 'line B', partner_id: null, total_amount: 100000 },
  ]);

  // 고객 페이지 진입
  await page.goto(`/c/${flow.customerToken}`);
  await page.getByPlaceholder(/연락처.*4자리/).fill(flow.phoneSuffix);
  await page.getByRole('button', { name: '확인' }).click();

  await expect(page.getByTestId(`customer-line-${flow.lineIds[0]}`)).toBeVisible();
  await expect(page.getByTestId(`customer-line-${flow.lineIds[1]}`)).toBeVisible();
});
```

- [ ] **Step 4: 실행 + 커밋**

```powershell
cd frontend; npm run e2e
```

```bash
git add frontend/e2e/
git commit -m "test(e2e): 멀티라인 주문 시나리오 + helpers 그룹 응답 대응"
```

---

## Task 15 — 검증 + 핸드오프

- [ ] **Step 1: 전체 검증**

```powershell
cd backend; python -m pytest -q
cd ../frontend; npm run typecheck; npm run lint; npm run build; npm run e2e
```

전부 통과해야 한다.

- [ ] **Step 2: 운영 runbook 작성**

`docs/runbooks/r7-multi-line-orders-migration.md` 신규 작성.

내용:
- 배포 전 체크 (백업 + 기존 Order 수 확인)
- 마이그레이션 실행 절차
- 검증 SQL (groups 수 = orders 수, orders w/o group = 0)
- 롤백: downgrade no-op이므로 git revert + DB backup 복구
- FAQ (운영자가 line 추가하는 절차, 그룹 안 1개 line만 취소하는 절차 등)

- [ ] **Step 3: `.master/next_session_plan.md` 갱신**

R7 마감 + R7.5(deprecated 컬럼 cleanup) / R8(체크리스트) 안내.

- [ ] **Step 4: 최종 커밋**

```bash
git add docs/runbooks/ .master/next_session_plan.md
git commit -m "docs(handoff): R7 마감 + R7.5/R8 안내"
```

---

## Self-Review 체크리스트 (모든 task 끝낸 뒤 본인이 확인)

### 권한/보안
- [ ] `POST /admin/orders/groups`, `GET /admin/orders/groups/{id}`, `POST /admin/orders/groups/{id}/lines` 모두 `require_admin`을 거치는가?
- [ ] `POST /customer/orders/{token}/verify`가 그룹 token + 전화번호 뒷자리 검증 + rate-limit 모두 유지하는가?
- [ ] PartnerJobRead DTO에 `group_id`, `source_channel`, `customer_visible_payment`, `customer_token`, `notes` 가 절대 노출되지 않는가? (테스트 `test_partner_dto_does_not_leak_group_metadata`)
- [ ] 협력사가 본인 partner_id가 아닌 다른 line(같은 그룹의 다른 line 포함)에 접근하면 404인가?

### DTO/스키마
- [ ] `AdminOrderRead`의 `customer_*`, `source_channel`, `customer_visible_payment`, `customer_token`은 그룹에서 inherit되는가? to_admin_order_dto가 group 인자를 받는가?
- [ ] `CustomerOrderGroupRead`에 `lines: list[CustomerOrderLineRead]`가 들어가고, 각 line의 photos는 `is_customer_visible=True`만 노출되는가?
- [ ] `OrderLineCreate`/`OrderUpdate`에서 `customer_*`, `source_channel`, `customer_visible_payment`가 모두 빠졌는가?

### 데이터/마이그레이션
- [ ] Alembic chain: 0008의 `down_revision = "0007_auto_publish_legacy_photos"` 정확한가?
- [ ] 백필 SQL이 기존 모든 Order에 대해 그룹을 만들고 group_id를 채우는가? (검증 쿼리: `SELECT COUNT(*) FROM orders WHERE group_id IS NULL` = 0)
- [ ] 기존 Order.customer_* 컬럼은 nullable로 변경됐고, R7에서 코드는 그룹에서 읽는가? (drop은 R7.5)
- [ ] 시드 데이터가 그룹 + line으로 분리되었고 `seed_order_id`/`seed_customer_token` fixture가 여전히 작동하는가?

### 상태/timeline
- [ ] line별 status 전이가 그룹과 무관하게 굴러가는가? (D1)
- [ ] timeline은 line의 order_id에 묶여 그룹 통합이 없는가? (D4)
- [ ] 부분 취소(D6): line 1개만 CANCELLED → 다른 line 영향 없음?
- [ ] R6의 자동공개 / revoke / customer_photo_ready 흐름이 변경 없이 동작하는가? (PhotoService.upload_for_partner, MessageService 모두 변경 없음 확인)

### 프론트
- [ ] OrderFormPage에 `order-add-line` 버튼이 있고 line N개 동적 추가 가능한가?
- [ ] 각 line 카드에 카테고리/상세상품 2단계 드롭다운(R6 R1)이 유지되는가?
- [ ] OrdersPage에서 같은 group의 line들이 시각적으로 묶여 보이는가? (색띠/들여쓰기)
- [ ] OrderDetailPage 우측 패널에 sibling_lines 노출되는가?
- [ ] CustomerReservation에서 `customer-line-{id}` testid로 line 카드 N개가 노출되는가?
- [ ] PartnerJobDetail은 변경 없는가? (협력사는 단일 line만 봄)

### 테스트
- [ ] `test_order_groups.py`에 6개 시나리오 모두 통과 (그룹 생성/customer verify/협력사 격리/partner DTO leak/라인 추가/부분 취소)
- [ ] 기존 backend 테스트의 Order 직접 생성 위치를 모두 그룹 + line으로 변환했는가?
- [ ] `admin-multi-line-e2e.spec.ts` 2개 테스트 모두 통과?
- [ ] `partner-customer-e2e.spec.ts`가 단일 line 흐름 그대로 통과? (회귀 없음)

### 운영 흐름
- [ ] 운영자가 같은 그룹의 다른 line을 OrderDetailPage에서 1클릭으로 이동할 수 있는가?
- [ ] 협력사가 본인에게 배정된 line만 보는 화면 흐름이 R6 그대로인가?
- [ ] 고객이 customer_token 1개로 들어가서 그룹 내 N개 line의 진행상황과 사진을 따로 확인할 수 있는가?
- [ ] 부분 취소된 line이 dashboard 카운터에서 적절히 빠지는가? (PHOTO_REVIEW_PENDING 0 유지 등)

### 운영/문서
- [ ] R7 runbook이 작성됐는가? (마이그레이션 절차/검증 SQL/롤백/FAQ)
- [ ] CLAUDE.md, AGENTS.md의 정책 문구가 그룹 모델과 충돌하지 않는가? (Photo flow invariant 등은 line=Order 단위 그대로라 변경 불필요)
