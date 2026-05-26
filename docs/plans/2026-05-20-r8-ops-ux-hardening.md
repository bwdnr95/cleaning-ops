# R8 Ops UX Hardening Implementation Plan (260518 요청서 반영)

> **Codex 작업자에게**: task-by-task로 진행하라. 각 step의 코드/명령은 그대로 실행 가능해야 한다. 각 task 마지막은 git commit으로 끝낸다.

> **이력**
> - v1 (2026-05-20): 초안. PDF `docs/260518 클린잡 운영 시스템 수정 사항 요청서.pdf`의 4건 요청 반영.
> - v2 (2026-05-20): Codex CTO 리뷰 반영. blocking 5건 + should-fix 5건 + nit 3건 해소. 실제 코드(`OrderRepository.get`, `TimelineService.record`, `OrderStatus.NEW`, `app.models.timeline.OrderTimeline`, CSP `_build_csp_value`)와 정확히 정렬.

> **Codex 작업자에게**: 작업 전 반드시 `AGENTS.md` 전체와 `CLAUDE.md` § "Architecture / The three rules that drive everything"을 먼저 읽는다. 모든 작업은 한국어 커밋 메시지, TDD 순서 (실패 테스트 → 구현 → 통과 → 커밋)를 따른다. 권한·DTO·timeline 룰을 위반하면 review에서 반려된다.

**Goal:** 운영 일선의 4가지 마찰을 해소한다.
1. **주소 입력**: 단일 텍스트 입력 → 카카오 우편번호 검색(기본주소) + 상세주소 분리.
2. **자동 로그아웃 안정화**: idle 만료 원인 식별 + access TTL 연장 + 폼 draft 자동 저장 안전망.
3. **주문 목록 일괄 작업**: 전체선택/해제 토글 + 일괄 삭제 버튼.
4. **주문 상세 단건 삭제**: 헤더에 삭제 버튼 추가 (confirmation dialog).

**Architecture:**
- 삭제는 **soft-delete**다 (`orders.deleted_at`, `order_groups.deleted_at` nullable). AGENTS.md의 timeline 보존/운영 감사 원칙을 지키기 위함. 모든 조회 경로(list/detail/dashboard/calendar/customer)는 `deleted_at IS NULL` 필터를 추가한다. 복구 UI는 본 PR 범위 밖(R8.5+).
- 주소는 `OrderGroup`에 `customer_address_detail` 컬럼을 추가한다 (R7에서 customer 정보는 그룹으로 이전됨). `orders.customer_address` legacy mirror도 동기화 유지 (R7.5에서 일괄 정리).
- 자동 로그아웃은 (a) **현상 진단** (b) **access TTL 60분 연장** (c) **폼 draft localStorage 자동 저장** 3단계로 처리. 폼 draft는 운영 데이터(고객 PII)를 담으므로 30분 TTL 후 자동 만료, 저장 성공 시 즉시 삭제.
- 우편번호는 **`react-daum-postcode`** npm 패키지로 통합 (별도 API 키 불필요, 인스턴스 도메인 등록 불필요). E2E에서는 mock 컴포넌트로 stub.
- 모든 mutation은 기존 패턴대로 `order_timeline` 이벤트를 남긴다. 신규 이벤트 타입 `ORDER_DELETED` 1개를 추가한다.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 · Pydantic v2 · React 19 + TypeScript (no Tailwind) · Playwright · Alembic.

---

## CTO 결정 사항

- **D1. 주소 라이브러리**: **`react-daum-postcode@^3.1.3`** (npm) 채택. 대안 비교:
  - (a) 공식 카카오 Postcode script 직접 로드 (`https://t1.daumcdn.net/mapjsapi/bundle/postcode/prod/postcode.v2.js`) — TypeScript 타입 없음, 인스턴스 lifecycle 직접 관리. 의존성 X.
  - (b) **`react-daum-postcode`** — npm. React 컴포넌트 wrapper. TypeScript 타입 포함. 내부적으로 (a)와 동일한 외부 script를 로드. 약 12KB.
  - (c) `@actbase/react-daum-postcode` — RN 전용. 본 프로젝트는 웹이라 부적합.
  - 결정 근거: TypeScript 통합 편의 + 8년간 유지보수 안정 + 의존성 사이즈 무시 가능. 둘 다 동일한 카카오 외부 도메인을 사용하므로 **CSP 갱신은 필수**(Task 8.5). 검색 결과의 도로명 주소를 우선 사용 (`data.roadAddress || data.address || data.jibunAddress`).
- **D2. 주소 필수 여부**: 기본주소(`customer_address`) **필수**. 상세주소(`customer_address_detail`) **선택**. 비어 있어도 저장은 허용하되 폼에서 노란 안내("상세주소 미입력 — 동/호수까지 입력 권장")를 보여준다.
- **D3. Access token TTL**: 15분 → **60분**으로 연장 (`access_token_ttl_minutes`). Refresh token TTL(admin 3일/partner 7일)은 그대로 유지. 운영 단말 보안은 사무실 내부망 가정.
- **D4. 폼 draft 자동 저장**: 신규 주문 폼은 `customer_name` 또는 첫 line에 변경이 일어난 시점부터 1초 debounce로 localStorage에 저장한다. 키: `cleaning_ops_draft_order_form_v1`. 저장 성공 또는 명시적 취소 시 즉시 삭제. 다음 진입 시 draft가 있으면 "이전 입력값을 불러올까요?" prompt 1회. TTL 30분 경과 시 자동 폐기. **PII 최소화**: 결제 금액 필드(`total_amount`, `deposit_amount`, `balance_amount`, `onsite_extra_amount`, `partner_payment_amount`), 결제 메모(`payment_memo`), 증빙 메모(`evidence_memo`), 협력사 정산 상태(`partner_payment_status`)는 draft에서 제외한다. 로그아웃/세션 전환 시(`clearAuth` 호출) draft도 함께 clear한다.
- **D5. 단일 세션 강제 — 채택하지 않음**: 현재 single-session enforcement 없음. PDF의 "다른 사람 접속" 가설은 사실이 아님 (다중 디바이스 동시 로그인은 서로 영향 없음). 단, 운영팀에 명확히 설명하기 위해 본 PR에서 진단 로그를 강화한다 (Task 6 Step 3).
- **D6. 삭제 = soft-delete**: `orders.deleted_at`, `order_groups.deleted_at` nullable timestamp. 모든 list/detail 조회에 `deleted_at IS NULL` 필터. timeline은 그대로 보존되어 audit trail 유지. 운영자가 실수로 삭제해도 DB에는 흔적이 남는다.
- **D7. 삭제 단위**: 운영자 mental model은 "주문 = 라인"이므로 삭제는 `Order`(line) 단위. 그룹의 모든 line이 삭제되면 `OrderGroup`도 cascade soft-delete (Task 4의 service에서 처리). 그룹 내 일부 line만 삭제하면 그룹은 살아있다.
- **D8. 삭제 권한**: 모든 관리자 (admin role) 가능. 별도 sub-role 분리하지 않음. confirmation dialog와 timeline 기록으로 견제.
- **D9. Bulk delete API**: 단일 `DELETE /api/admin/orders/{order_id}` + bulk `POST /api/admin/orders/bulk-delete`. 둘 다 동일 service 함수 호출. **트랜잭션 정책**: bulk는 1개 트랜잭션으로 묶되, 개별 line의 `not_found`는 partial-success로 응답(`failed: [...]`)하고 나머지는 commit. DB 예외(IntegrityError 등)는 전체 rollback하고 500 응답. 응답 형식: `{succeeded: [...], failed: [{order_id, reason}]}`.

- **D10. CSP 갱신 (운영 배포 차단 방지)**: `backend/app/core/middleware.py`의 `_build_csp_value()`에 카카오 우편번호 도메인 allowlist를 추가. `script-src`에 `https://t1.daumcdn.net`, `frame-src`(신규)에 `https://postcode.map.kakao.com`, `connect-src`에 `https://postcode.map.kakao.com` 추가. CSP 없이는 운영 환경에서 우편번호 모달이 동작하지 않는다.

- **D11. Access TTL 60분의 보안 trade-off**: localStorage 토큰 구조에서 XSS 발생 시 노출 window가 길어진다. 운영팀 안내 runbook(Task 6)에 (a) 공용 PC 사용 금지 (b) 의심 시 즉시 로그아웃 (c) **장기 목표**: refresh token을 httpOnly cookie로 이전, access token도 httpOnly + Secure로 이전 (R9~R10 후보). 본 PR에서는 운영 편의를 우선하되 위험을 명시.

---

## File Map — 무엇을 어디서 바꾸는가

| 영역 | 파일 | 종류 |
|---|---|---|
| 정책 | `AGENTS.md` | 수정 (Data Access Rules + 신규 § Delete Policy) |
| 정책 | `CLAUDE.md` | 수정 (§ "The three rules" 인근에 삭제 정책 1줄 + § "Working Style" 인근에 세션 정책 1줄) |
| 보안 | `backend/app/core/middleware.py` | 수정 (`_build_csp_value()`에 카카오 도메인 allowlist) |
| DB 마이그레이션 | `backend/alembic/versions/0009_address_detail_and_soft_delete.py` | 신규 |
| 백엔드 도메인 | `backend/app/domain/constants.py` | 수정 (`TimelineEventType.ORDER_DELETED` 추가) |
| 백엔드 설정 | `backend/app/core/config.py` | 수정 (`access_token_ttl_minutes: 60`) |
| 백엔드 모델 | `backend/app/models/order_group.py` | 수정 (`customer_address_detail`, `deleted_at`) |
| 백엔드 모델 | `backend/app/models/order.py` | 수정 (`deleted_at`) |
| 백엔드 스키마 | `backend/app/schemas/order.py` | 수정 (group/order/admin/partner/customer DTO 모두에 `customer_address_detail`) |
| 백엔드 레포 | `backend/app/repositories/orders.py` | 수정 (`get()` override + 모든 query에 `deleted_at IS NULL`) |
| 백엔드 레포 | `backend/app/repositories/order_groups.py` | 수정 (`get()` override + 모든 query에 `deleted_at IS NULL`) |
| 백엔드 서비스 | `backend/app/services/orders.py` | 수정 (`delete_order`, `bulk_delete_orders` + 4개 DTO 변환 함수에 `customer_address_detail`) |
| 백엔드 서비스 | `backend/app/services/dashboard.py` | 수정 (count/recent 조회에 `deleted_at IS NULL`) |
| 백엔드 서비스 | `backend/app/services/photos.py` | 수정 (partner upload용 `Order` 조회에 `deleted_at IS NULL`) |
| 백엔드 서비스 | `backend/app/services/messages.py` | 수정 (메시지 발송 대상 `Order`/group 조회에 `deleted_at IS NULL`) |
| 백엔드 라우터 | `backend/app/api/routes/admin/orders.py` | 수정 (`@router.delete("/{order_id}")`, `@router.post("/bulk-delete")`) |
| 백엔드 라우터 | `backend/app/api/routes/partner/jobs.py` | 수정 (협력사 detail/mutation/upload route 가드) |
| 백엔드 라우터 | `backend/app/api/routes/customer/orders.py` | 수정 (customer verify/get group에 가드) |
| 백엔드 테스트 | `backend/tests/test_order_delete.py` | 신규 |
| 백엔드 테스트 | `backend/tests/test_auth_integration.py` | 수정 (access TTL 60분 가정으로 expiration 테스트 정정) |
| 프론트 의존성 | `frontend/package.json` | 수정 (`react-daum-postcode` 추가) |
| 프론트 컴포넌트 | `frontend/src/components/AddressInput.tsx` | 신규 |
| 프론트 신규폼 | `frontend/src/features/admin/orders/OrderFormPage.tsx` | 수정 (`AddressInput` 적용 + draft 자동 저장) |
| 프론트 폼 draft | `frontend/src/features/admin/orders/useOrderFormDraft.ts` | 신규 |
| 프론트 주문목록 | `frontend/src/features/admin/orders/OrdersPage.tsx` | 수정 (전체선택 헤더, 일괄 삭제 버튼) |
| 프론트 주문상세 | `frontend/src/features/admin/orders/OrderDetailPage.tsx` | 수정 (삭제 버튼 + confirm dialog) |
| 프론트 API | `frontend/src/api/admin.ts` | 수정 (`deleteAdminOrder`, `bulkDeleteAdminOrders`) |
| 프론트 E2E | `frontend/e2e/admin-order-delete-e2e.spec.ts` | 신규 |
| 프론트 E2E | `frontend/e2e/admin-address-input-e2e.spec.ts` | 신규 (mock postcode) |
| 핸드오프 | `.master/next_session_plan.md` | 수정 (R8 마감 후) |
| 운영 문서 | `docs/runbooks/r8-session-policy.md` | 신규 (자동 로그아웃 원인 + 운영팀 안내) |

---

## Task 1 — 정책 문서 갱신: AGENTS.md + CLAUDE.md

**Files:**
- Modify: `AGENTS.md` (§ "Data Access Rules" 다음에 신규 § "Delete Policy" 삽입)
- Modify: `CLAUDE.md` (§ "The three rules that drive everything" 마지막에 1줄 추가)

정책 문서를 코드보다 먼저 갱신해야 후속 task에서 가정이 정렬된다.

- [ ] **Step 1: AGENTS.md에 § "Delete Policy" 추가**

`## Data Access Rules` 블록(line 93~) 다음에 아래를 통째로 삽입한다.

```markdown
## Delete Policy

- 주문/그룹 삭제는 **soft-delete**다. 모델의 `deleted_at` 컬럼을 채우고 hard-delete는 사용하지 않는다.
- 모든 list/detail/dashboard/calendar/customer 조회 경로는 `deleted_at IS NULL` 필터를 포함한다.
- 삭제 시 `order_timeline`에 `order_deleted` 이벤트를 기록한다 (actor=관리자 user_id). photos, message_logs, timeline은 그대로 보존되어 audit trail을 유지한다.
- 그룹 내 모든 line이 삭제되면 service 단에서 `OrderGroup.deleted_at`도 함께 채운다. 일부만 삭제되면 그룹은 살아있다.
- 협력사/고객 API는 삭제된 주문에 접근할 수 없다 (`deleted_at IS NULL` 가드 + 404 응답).
- 복구 기능은 본 정책 범위 밖이다. DB에 직접 접근하여 `deleted_at`을 NULL로 되돌리는 운영 절차로만 처리한다.
```

- [ ] **Step 2: CLAUDE.md § "The three rules" 마지막에 4번 룰 추가**

`### The three rules that drive everything` 블록의 3번 항목 다음에 아래를 삽입한다.

```markdown
4. **Soft-delete는 timeline 보존을 위한 합의다.** 주문/그룹 삭제는 `deleted_at` 컬럼을 채우고, 모든 조회 경로는 `deleted_at IS NULL` 필터를 강제한다. 자세한 내용은 `AGENTS.md` § "Delete Policy"를 본다.
```

- [ ] **Step 3: 커밋**

```bash
git add AGENTS.md CLAUDE.md
git commit -m "docs(policy): R8 삭제 정책 및 세션 안전망 명시"
```

---

## Task 2 — DB 마이그레이션: 주소 상세 컬럼 + soft-delete 컬럼

**Files:**
- Create: `backend/alembic/versions/0009_address_detail_and_soft_delete.py`

기존 마이그레이션 번호는 `0008`까지 차 있다 (R7 multi-line). 다음 번호는 `0009`.

- [ ] **Step 1: revision 파일 작성**

```python
"""R8 address detail + soft delete

Revision ID: 0009_address_detail_and_soft_delete
Revises: 0008_order_groups
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_address_detail_and_soft_delete"
down_revision = "0008_order_groups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "order_groups",
        sa.Column("customer_address_detail", sa.Text(), nullable=True),
    )
    op.add_column(
        "order_groups",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_orders_deleted_at", "orders", ["deleted_at"]
    )
    op.create_index(
        "ix_order_groups_deleted_at", "order_groups", ["deleted_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_order_groups_deleted_at", table_name="order_groups")
    op.drop_index("ix_orders_deleted_at", table_name="orders")
    op.drop_column("orders", "deleted_at")
    op.drop_column("order_groups", "deleted_at")
    op.drop_column("order_groups", "customer_address_detail")
```

- [ ] **Step 2: 마이그레이션 SQL 미리보기 (검증, 적용 X)**

Run: `cd backend && python -m alembic upgrade head --sql`
Expected: `ALTER TABLE order_groups ADD COLUMN customer_address_detail TEXT`, `ALTER TABLE order_groups ADD COLUMN deleted_at TIMESTAMP`, `ALTER TABLE orders ADD COLUMN deleted_at TIMESTAMP`, 2개 인덱스 생성 DDL이 나오면 OK.

- [ ] **Step 3: 마이그레이션 실제 적용**

Run: `cd backend && python -m alembic upgrade head`
Expected: `INFO  [alembic.runtime.migration] Running upgrade 0008_order_groups -> 0009_address_detail_and_soft_delete`

- [ ] **Step 4: 커밋**

```bash
git add backend/alembic/versions/0009_address_detail_and_soft_delete.py
git commit -m "feat(db): R8 주소 상세 + soft-delete 컬럼 추가"
```

---

## Task 3 — 백엔드 모델/스키마: customer_address_detail + deleted_at

**Files:**
- Modify: `backend/app/models/order_group.py`
- Modify: `backend/app/models/order.py`
- Modify: `backend/app/schemas/order.py`
- Modify: `backend/app/domain/constants.py`

- [ ] **Step 1: `OrderGroup` 모델에 컬럼 2개 추가**

`backend/app/models/order_group.py`의 `OrderGroup` 클래스에서 `customer_address` 줄 바로 다음에 추가하고, 클래스 끝부분에 `deleted_at`도 추가한다.

```python
customer_address: Mapped[str] = mapped_column(Text, nullable=False, default="")
customer_address_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
# ... (기존 필드 유지)
deleted_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True, index=True
)
```

`datetime`/`DateTime` import가 없다면 file 상단에:
```python
from datetime import datetime
from sqlalchemy import DateTime, Text
```
이 이미 있는지 먼저 확인하고 없으면 추가.

- [ ] **Step 2: `Order` 모델에 `deleted_at` 추가**

`backend/app/models/order.py`의 `Order` 클래스 끝에:

```python
deleted_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True, index=True
)
```

- [ ] **Step 3: 스키마 갱신**

`backend/app/schemas/order.py`의 `OrderGroupBase`, `OrderGroupUpdate`, `AdminOrderRead`, `CustomerOrderGroupRead`에 `customer_address_detail` 필드 추가.

```python
class OrderGroupBase(BaseModel):
    customer_name: str
    customer_phone: str
    customer_address: str
    customer_address_detail: str | None = None
    source_channel: str | None = None
    customer_visible_payment: bool = False
    notes: str | None = None


class OrderGroupUpdate(BaseModel):
    customer_name: str | None = None
    customer_phone: str | None = None
    customer_address: str | None = None
    customer_address_detail: str | None = None
    source_channel: str | None = None
    customer_visible_payment: bool | None = None
    notes: str | None = None
```

`AdminOrderRead`, `AdminOrderGroupRead`, `CustomerOrderGroupRead`, `PartnerJobRead` 모두에 `customer_address_detail: str | None = None` 추가. CustomerOrderLineRead는 group 레벨이 아닌 line 레벨이므로 추가하지 않는다.

- [ ] **Step 4: `TimelineEventType.ORDER_DELETED` enum 추가**

`backend/app/domain/constants.py`의 `TimelineEventType` enum에:

```python
class TimelineEventType(str, Enum):
    # ... 기존 값 유지
    ORDER_DELETED = "order_deleted"
```

- [ ] **Step 5: DTO 변환 함수 4종에 `customer_address_detail` 명시 추가**

`backend/app/services/orders.py`의 변환 함수 4개를 갱신한다. 각 함수가 명시적 whitelist 변환이므로 새 필드는 직접 추가해야 한다.

**`to_admin_group_dto`** (line 384~):
```python
def to_admin_group_dto(group: OrderGroup, *, lines: list[Order] | None = None) -> AdminOrderGroupRead:
    return AdminOrderGroupRead(
        id=group.id,
        customer_token=group.customer_token,
        customer_name=group.customer_name,
        customer_phone=group.customer_phone,
        customer_address=group.customer_address,
        customer_address_detail=group.customer_address_detail,  # 신규
        source_channel=group.source_channel,
        customer_visible_payment=group.customer_visible_payment,
        notes=group.notes,
        created_at=group.created_at,
        updated_at=group.updated_at,
        lines=[to_admin_order_dto(line, group=group) for line in lines or []],
    )
```

**`to_admin_order_dto`** (line 400~): 본문 상단에 매핑 추가, return 객체에도 추가.
```python
def to_admin_order_dto(
    order: Order,
    *,
    group: OrderGroup | None = None,
    timeline: list | None = None,
) -> AdminOrderRead:
    customer_name = group.customer_name if group else order.customer_name
    customer_phone = group.customer_phone if group else order.customer_phone
    customer_address = group.customer_address if group else order.customer_address
    customer_address_detail = group.customer_address_detail if group else None  # 신규
    source_channel = group.source_channel if group else order.source_channel
    # ... 기존 로직 유지
    return AdminOrderRead(
        # ... 기존 필드 유지
        customer_address=customer_address or "",
        customer_address_detail=customer_address_detail,  # 신규
        # ... 나머지 유지
    )
```

**`to_partner_job_dto`** (line 485~): 협력사도 현장 작업 시 상세주소가 필요하다. 시그니처에 `group` 인자를 추가하고, 모든 호출처도 갱신한다.

```python
def to_partner_job_dto(
    order: Order,
    *,
    group: OrderGroup | None = None,
    photos: list[OrderPhoto] | None = None,
) -> PartnerJobRead:
    customer_address = group.customer_address if group else order.customer_address
    customer_address_detail = group.customer_address_detail if group else None
    return PartnerJobRead(
        id=order.id,
        status=order.status,
        scheduled_date=order.scheduled_date,
        requested_time=order.requested_time,
        service_name=order.service_name,
        size_or_quantity=order.size_or_quantity,
        service_detail=order.service_detail,
        special_request=order.special_request,
        customer_name=group.customer_name if group else order.customer_name,
        customer_phone=group.customer_phone if group else order.customer_phone,
        customer_address=customer_address or "",
        customer_address_detail=customer_address_detail,
        photos=[to_partner_photo_dto(photo) for photo in photos or []],
    )
```

`to_partner_job_dto` 호출처는 `backend/app/api/routes/partner/`에서 사용된다. Grep으로 `to_partner_job_dto(` 패턴을 찾아 `group=group_repo.get(order.group_id)` 인자를 추가한다.

**`to_customer_group_dto`** (line 515~):
```python
def to_customer_group_dto(
    group: OrderGroup,
    *,
    lines_with_photos: list[tuple[Order, list[OrderPhoto]]],
) -> CustomerOrderGroupRead:
    return CustomerOrderGroupRead(
        id=group.id,
        customer_name=group.customer_name,
        customer_phone=group.customer_phone,
        customer_address=group.customer_address,
        customer_address_detail=group.customer_address_detail,  # 신규
        customer_visible_payment=group.customer_visible_payment,
        lines=[
            _to_customer_line_dto(
                line,
                photos,
                payment_visible=group.customer_visible_payment,
            )
            for line, photos in lines_with_photos
        ],
    )
```

- [ ] **Step 6: 빠른 syntax 검증**

Run: `cd backend && python -m compileall app`
Expected: 에러 없음.

- [ ] **Step 7: 커밋**

```bash
git add backend/app/models/order_group.py backend/app/models/order.py backend/app/schemas/order.py backend/app/domain/constants.py backend/app/services/orders.py backend/app/api/routes/partner/jobs.py
git commit -m "feat(model): R8 customer_address_detail + deleted_at + ORDER_DELETED 이벤트 + 4개 DTO 변환 갱신"
```

---

## Task 4 — 백엔드 서비스: delete_order / bulk_delete_orders

**Files:**
- Modify: `backend/app/services/orders.py`
- Test: `backend/tests/test_order_delete.py` (신규)

- [ ] **Step 1: 실패 테스트 작성 — 단건 삭제 + timeline 기록**

`backend/tests/test_order_delete.py` 신규 작성. 기존 `conftest.py`의 `db_session`/`seed_admin_user`/`make_test_client` fixture를 재사용한다.

```python
import pytest
from sqlalchemy import select

from app.domain.constants import OrderStatus, TimelineEventType
from app.models.order import Order
from app.models.order_group import OrderGroup
from app.models.timeline import OrderTimeline
from app.services.orders import OrderService


def test_delete_order_marks_deleted_at_and_records_timeline(db_session, seed_admin_user, seed_order):
    service = OrderService(db_session)

    service.delete_order(order_id=seed_order.id, actor_user_id=seed_admin_user.id)

    db_session.commit()
    db_session.refresh(seed_order)
    assert seed_order.deleted_at is not None

    events = db_session.execute(
        select(OrderTimeline).where(
            OrderTimeline.order_id == seed_order.id,
            OrderTimeline.event_type == TimelineEventType.ORDER_DELETED,
        )
    ).scalars().all()
    assert len(events) == 1
    assert events[0].actor_user_id == seed_admin_user.id


def test_delete_order_is_idempotent_404_on_already_deleted(db_session, seed_admin_user, seed_order):
    service = OrderService(db_session)
    service.delete_order(order_id=seed_order.id, actor_user_id=seed_admin_user.id)
    db_session.commit()

    with pytest.raises(LookupError):
        service.delete_order(order_id=seed_order.id, actor_user_id=seed_admin_user.id)


def test_delete_last_line_in_group_cascades_group_soft_delete(db_session, seed_admin_user, seed_order):
    service = OrderService(db_session)
    service.delete_order(order_id=seed_order.id, actor_user_id=seed_admin_user.id)
    db_session.commit()

    group = db_session.get(OrderGroup, seed_order.group_id)
    assert group.deleted_at is not None


def test_delete_partial_lines_keeps_group_alive(db_session, seed_admin_user, seed_order, make_extra_line):
    extra = make_extra_line(seed_order.group_id)
    service = OrderService(db_session)

    service.delete_order(order_id=extra.id, actor_user_id=seed_admin_user.id)
    db_session.commit()

    group = db_session.get(OrderGroup, seed_order.group_id)
    assert group.deleted_at is None
    db_session.refresh(seed_order)
    assert seed_order.deleted_at is None


def test_bulk_delete_orders_returns_succeeded_and_failed(db_session, seed_admin_user, seed_order):
    service = OrderService(db_session)
    result = service.bulk_delete_orders(
        order_ids=[seed_order.id, "non-existent-id"],
        actor_user_id=seed_admin_user.id,
    )
    db_session.commit()

    assert result.succeeded == [seed_order.id]
    assert len(result.failed) == 1
    assert result.failed[0].order_id == "non-existent-id"
    assert result.failed[0].reason == "not_found"
```

`conftest.py`에 `seed_order` / `make_extra_line` / `seed_admin_token` / `seed_partner_token` fixture가 없으면 추가한다. 기존 R6 계획서(`2026-05-18-modification-requests.md` Task 7 인근)에서 도입한 fixture 패턴을 그대로 따른다.

`seed_order` fixture 명세:
- 기존 `seed_admin_user`와 같은 scope (`function`).
- `OrderGroup` 1개를 `customer_name="테스트"`, `customer_phone="010-1234-5678"`, `customer_address="서울특별시 강남구 테스트로 1"`, `customer_address_detail=None`으로 생성.
- 그 group에 `Order` 1개(`status=OrderStatus.NEW`, `received_date=date.today()`)를 생성.
- `db_session.flush()` 후 `Order` ORM 객체 반환.

`make_extra_line` fixture 명세:
- callable factory fixture (`pytest.fixture` + factory pattern).
- `def make_extra_line(group_id: str) -> Order`: 해당 group에 line 1개를 추가 생성한 뒤 반환.

`seed_admin_token` / `seed_partner_token` fixture는 기존 `make_test_client` 또는 login flow를 호출해 access token 문자열을 반환한다.

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && python -m pytest tests/test_order_delete.py -v`
Expected: `AttributeError: 'OrderService' object has no attribute 'delete_order'` 또는 import error.

- [ ] **Step 3: 서비스 함수 구현**

`backend/app/services/orders.py`에 추가 (파일 끝 또는 클래스 내 적절한 위치):

```python
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class BulkDeleteFailure:
    order_id: str
    reason: str  # "not_found" | "already_deleted"


@dataclass(frozen=True)
class BulkDeleteResult:
    succeeded: list[str]
    failed: list[BulkDeleteFailure]


class OrderService:
    # ... 기존 메서드 유지

    def delete_order(self, *, order_id: str, actor_user_id: str) -> None:
        """주문 1건 soft-delete. 그룹의 마지막 살아있는 line이면 그룹도 함께 soft-delete.

        Raises:
            LookupError: 해당 id의 주문이 없거나 이미 삭제됨.
        """
        order = self.db.execute(
            select(Order).where(
                Order.id == order_id,
                Order.deleted_at.is_(None),
            )
        ).scalar_one_or_none()
        if order is None:
            raise LookupError(f"order not found or already deleted: {order_id}")

        now = datetime.now(UTC)
        order.deleted_at = now

        TimelineService(self.db).record(
            order_id=order.id,
            event_type=TimelineEventType.ORDER_DELETED,
            actor_user_id=actor_user_id,
            title="주문 삭제",
            description="관리자가 주문 내역을 삭제했습니다.",
        )

        remaining = self.db.execute(
            select(func.count(Order.id)).where(
                Order.group_id == order.group_id,
                Order.deleted_at.is_(None),
            )
        ).scalar_one()
        if remaining == 0:
            group = self.db.get(OrderGroup, order.group_id)
            if group is not None and group.deleted_at is None:
                group.deleted_at = now

        self.db.flush()

    def bulk_delete_orders(
        self, *, order_ids: list[str], actor_user_id: str
    ) -> BulkDeleteResult:
        succeeded: list[str] = []
        failed: list[BulkDeleteFailure] = []

        for order_id in order_ids:
            try:
                self.delete_order(order_id=order_id, actor_user_id=actor_user_id)
            except LookupError:
                failed.append(BulkDeleteFailure(order_id=order_id, reason="not_found"))
            else:
                succeeded.append(order_id)

        return BulkDeleteResult(succeeded=succeeded, failed=failed)
```

import 누락 확인: `from sqlalchemy import select, func`, `from app.models.order import Order`, `from app.models.order_group import OrderGroup`, `from app.domain.constants import TimelineEventType`, `from app.services.timeline import TimelineService`. 이미 있는 것은 중복 추가하지 않는다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && python -m pytest tests/test_order_delete.py -v`
Expected: 5 passed.

- [ ] **Step 5: Repository `get()` override + 모든 list 쿼리에 `deleted_at IS NULL` 필터**

`backend/app/repositories/base.py`의 `Repository.get()`은 `self.db.get(self.model, id_)`를 그대로 반환한다 — soft-delete 가드가 없다. 두 레포에서 `get()`을 명시적으로 override 한다.

**`backend/app/repositories/orders.py`**:
```python
class OrderRepository(Repository[Order]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Order)

    def get(self, id_: str, *, include_deleted: bool = False) -> Order | None:
        obj = self.db.get(Order, id_)
        if obj is None:
            return None
        if obj.deleted_at is not None and not include_deleted:
            return None
        return obj

    def list_orders(self, *, limit: int | None = None, offset: int = 0) -> list[Order]:
        stmt = (
            select(Order)
            .where(Order.deleted_at.is_(None))
            .order_by(Order.scheduled_date.asc().nulls_last(), Order.id.asc())
        )
        if limit is not None:
            stmt = stmt.limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def list_scheduled_between(
        self,
        start_date: date,
        end_date: date,
        *,
        partner_id: str | None = None,
    ) -> list[Order]:
        stmt = (
            select(Order)
            .where(
                Order.deleted_at.is_(None),
                Order.scheduled_date >= start_date,
                Order.scheduled_date <= end_date,
            )
            .order_by(Order.scheduled_date.asc(), Order.requested_time.asc().nulls_last(), Order.id.asc())
        )
        if partner_id:
            stmt = stmt.where(Order.partner_id == partner_id)
        return list(self.db.scalars(stmt))

    def list_for_partner(self, partner_id: str) -> list[Order]:
        stmt = (
            select(Order)
            .where(Order.deleted_at.is_(None), Order.partner_id == partner_id)
            .order_by(Order.scheduled_date.asc())
        )
        return list(self.db.scalars(stmt))

    def list_by_group(self, group_id: str) -> list[Order]:
        stmt = (
            select(Order)
            .where(Order.deleted_at.is_(None), Order.group_id == group_id)
            .order_by(Order.created_at.asc(), Order.id.asc())
        )
        return list(self.db.scalars(stmt))

    def count_scheduled_on(self, target: date) -> int:
        stmt = (
            select(func.count(Order.id))
            .where(Order.deleted_at.is_(None), Order.scheduled_date == target)
        )
        return self.db.scalar(stmt) or 0
```

`from sqlalchemy import select, func` import 확인.

**`backend/app/repositories/order_groups.py`**: 같은 패턴. `get()` override + 모든 `select(OrderGroup)` 쿼리에 `.where(OrderGroup.deleted_at.is_(None))` 추가. `get_by_customer_token()`이 있다면 동일하게 가드.

- [ ] **Step 5.5: 서비스 layer에서 raw `db.get(Order, ...)` / `db.get(OrderGroup, ...)` 호출처 가드**

레포 `get()` override만으로는 부족하다. 서비스에서 `self.db.get(Order, ...)` / `self.db.get(OrderGroup, ...)`를 직접 부르는 경로가 있다. Grep으로 확인:

```
Grep: pattern="db\.get\(Order|db\.get\(OrderGroup" path="backend/app"
```

각 호출처에서 반환된 객체의 `deleted_at`를 즉시 체크하고, soft-delete 된 경우 `None` 처럼 취급하거나 404를 발생시킨다. 본 plan에서 명시적으로 가드해야 할 파일:

- `backend/app/services/orders.py` — 자체 `db.get(Order, ...)` / `db.get(OrderGroup, ...)` 호출처. `delete_order` 내부의 cascade group lookup은 **soft-delete된 group도 OK**(자기 자신 group을 찾는 경우라 예외).
- `backend/app/services/dashboard.py` — count/recent activity 조회. `deleted_at IS NULL`을 통한 필터링 보강.
- `backend/app/services/photos.py` — partner upload 시 `Order` lookup. `OrderRepository(db).get(order_id)` 로 통일.
- `backend/app/services/messages.py` — 메시지 발송 대상 `Order` lookup. 동일 패턴.
- `backend/app/api/routes/partner/jobs.py` / `backend/app/api/routes/partner/photos.py` — 협력사 detail/upload route. 동일 패턴.
- `backend/app/api/routes/customer/orders.py` — customer verify 후 group 조회. `get_by_customer_token` 호출 시 `deleted_at IS NULL` 가드.

각 file에서 raw `db.get(...)`을 `OrderRepository(db).get(...)`/`OrderGroupRepository(db).get(...)`로 치환하면 자동으로 가드가 적용된다.

- [ ] **Step 5.6: 격리 테스트 추가**

`backend/tests/test_order_delete.py`에 추가:

```python
def test_deleted_order_not_in_admin_list(client, seed_admin_token, seed_order):
    client.delete(
        f"/api/admin/orders/{seed_order.id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    response = client.get(
        "/api/admin/orders",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    ids = [o["id"] for o in response.json()]
    assert seed_order.id not in ids


def test_deleted_order_not_visible_to_partner(client, seed_admin_token, seed_partner_token, seed_order_assigned_to_partner):
    order = seed_order_assigned_to_partner
    client.delete(
        f"/api/admin/orders/{order.id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    response = client.get(
        "/api/partner/jobs",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    )
    ids = [j["id"] for j in response.json()]
    assert order.id not in ids


def test_deleted_group_not_visible_to_customer(client, seed_admin_token, seed_order_with_customer_token):
    order, group = seed_order_with_customer_token
    client.delete(
        f"/api/admin/orders/{order.id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    response = client.post(
        f"/api/customer/orders/{group.customer_token}/verify",
        json={"phone_suffix": group.customer_phone[-4:]},
    )
    assert response.status_code == 404
```

추가 fixture (`seed_order_assigned_to_partner`, `seed_order_with_customer_token`)는 `conftest.py`에 추가한다.

- [ ] **Step 6: 기존 테스트가 깨지지 않는지 확인**

Run: `cd backend && python -m pytest -q`
Expected: R7까지 통과한 104개 + 신규 5개 + 격리 3개 = 112+ passed.

- [ ] **Step 7: 커밋**

```bash
git add backend/app/services/orders.py backend/app/repositories/orders.py backend/app/repositories/order_groups.py backend/tests/test_order_delete.py backend/tests/conftest.py
git commit -m "feat(orders): R8 soft-delete 서비스 + bulk-delete + deleted_at 조회 필터"
```

---

## Task 5 — 백엔드 API: DELETE + bulk-delete 엔드포인트

**Files:**
- Modify: `backend/app/api/routes/admin/orders.py`
- Test: `backend/tests/test_order_delete.py` (Task 4의 같은 파일에 API 레벨 테스트 추가)

- [ ] **Step 1: 실패 테스트 작성 — API 레벨**

`backend/tests/test_order_delete.py`에 추가:

```python
def test_delete_order_api_204(client, seed_admin_token, seed_order):
    response = client.delete(
        f"/api/admin/orders/{seed_order.id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    assert response.status_code == 204

    # 다시 조회하면 404
    response = client.get(
        f"/api/admin/orders/{seed_order.id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    assert response.status_code == 404


def test_delete_order_api_404_for_already_deleted(client, seed_admin_token, seed_order):
    client.delete(
        f"/api/admin/orders/{seed_order.id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    response = client.delete(
        f"/api/admin/orders/{seed_order.id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    assert response.status_code == 404


def test_delete_order_api_requires_admin(client, seed_partner_token, seed_order):
    response = client.delete(
        f"/api/admin/orders/{seed_order.id}",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    )
    assert response.status_code in {401, 403}


def test_bulk_delete_orders_api(client, seed_admin_token, seed_order):
    response = client.post(
        "/api/admin/orders/bulk-delete",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
        json={"order_ids": [seed_order.id, "non-existent-id"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["succeeded"] == [seed_order.id]
    assert len(body["failed"]) == 1
    assert body["failed"][0]["order_id"] == "non-existent-id"
    assert body["failed"][0]["reason"] == "not_found"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && python -m pytest tests/test_order_delete.py::test_delete_order_api_204 -v`
Expected: 404 또는 405 (라우트 없음).

- [ ] **Step 3: 라우트 구현**

`backend/app/api/routes/admin/orders.py`에 추가:

```python
from pydantic import BaseModel


class BulkDeleteRequest(BaseModel):
    order_ids: list[str]  # 빈 배열 허용 — succeeded=[], failed=[]로 응답


class BulkDeleteFailureItem(BaseModel):
    order_id: str
    reason: str  # "not_found" 등


class BulkDeleteResponse(BaseModel):
    succeeded: list[str]
    failed: list[BulkDeleteFailureItem]


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin_order(
    order_id: str,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
) -> Response:
    service = OrderService(db)
    try:
        service.delete_order(order_id=order_id, actor_user_id=user.id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="order_not_found") from exc

    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/bulk-delete", response_model=BulkDeleteResponse)
def bulk_delete_admin_orders(
    payload: BulkDeleteRequest,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
) -> BulkDeleteResponse:
    service = OrderService(db)
    result = service.bulk_delete_orders(
        order_ids=payload.order_ids,
        actor_user_id=user.id,
    )
    db.commit()

    return BulkDeleteResponse(
        succeeded=result.succeeded,
        failed=[BulkDeleteFailureItem(order_id=f.order_id, reason=f.reason) for f in result.failed],
    )
```

라우터 prefix는 `app/api/router.py`에서 `/api/admin/orders`로 마운트되어 있다. 즉 위 경로는 최종적으로 `DELETE /api/admin/orders/{order_id}` / `POST /api/admin/orders/bulk-delete`가 된다.

import 누락 확인: `from fastapi import Response, HTTPException, status` (status는 이미 import). `from pydantic import BaseModel` 신규 추가. `get_session`, `require_admin`, `CurrentUser`는 이미 file 상단에 있음.

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && python -m pytest tests/test_order_delete.py -v`
Expected: 9 passed (Task 4의 5개 + 본 task의 4개).

- [ ] **Step 5: 전체 backend 회귀 확인**

Run: `cd backend && python -m pytest -q`
Expected: 모두 통과.

- [ ] **Step 6: 커밋**

```bash
git add backend/app/api/routes/admin/orders.py backend/tests/test_order_delete.py
git commit -m "feat(api): R8 DELETE /admin/orders/{id} + bulk-delete 엔드포인트"
```

---

## Task 6 — Access TTL 60분 연장 + 진단 로그

**Files:**
- Modify: `backend/app/core/config.py` (line 18)
- Modify: `backend/tests/test_auth_integration.py` (access TTL 가정 변경)
- Create: `docs/runbooks/r8-session-policy.md`

자동 로그아웃 원인 분석:
- 운영팀 보고: "오랫동안 화면 켜두고 저장 누르면 로그인 화면이 뜬다."
- 코드 분석 결과:
  - access token TTL 15분 → idle 15분이면 무조건 `401`
  - 그러나 `apiRequest`가 refresh 자동 재시도 → refresh token이 3일 이내면 자동 복구되어야 함
  - 따라서 로그인 화면이 뜨는 경우는 **refresh token도 만료**(3일 미접속) 혹은 refresh API 자체가 실패하는 경로
  - "다른 사람 접속" 가설은 사실이 아님 — single-session enforcement 없음 (다중 디바이스 동시 로그인 가능, 서로 영향 없음)

조치:
1. Access TTL을 15분 → **60분**으로 연장 (사무실 운영 시나리오 가정).
2. Refresh API 실패 시 frontend 콘솔/Sentry에 명시적 로그 (Task 9 Step 3에서 처리).
3. 폼 draft 자동 저장 (Task 8) — 만에 하나 logout이 일어나도 입력 데이터 보존.
4. 운영팀 안내 문서 작성.

- [ ] **Step 1: config 변경**

`backend/app/core/config.py` line 18:

```python
access_token_ttl_minutes: int = 60
```

- [ ] **Step 2: 의존 테스트 정정**

기존 `test_auth_integration.py`에서 access TTL 15분 가정으로 작성된 expiration 테스트가 있는지 확인:

Run: Grep으로 `access_token_ttl_minutes`, `timedelta(minutes=15)`, `15분` 패턴 검색.

발견되면 60분 가정으로 정정한다. 만약 expiration boundary를 fixture로 주입하는 패턴이라면 수정 불필요.

- [ ] **Step 3: 운영팀 안내 문서 작성**

`docs/runbooks/r8-session-policy.md`:

```markdown
# R8 자동 로그아웃 정책 (운영팀 안내)

## 요약

- 운영 시스템은 1시간 동안 활동이 없으면 다음 요청 시 자동 갱신을 시도하고, 갱신에 실패하면 로그인 화면으로 이동한다.
- 입력 중이던 신규 주문 폼은 자동으로 임시 저장된다 (브라우저별 30분 유지). 재로그인 후 폼에 들어가면 "이전 입력값을 불러올까요?" 안내가 나온다.
- 다른 컴퓨터/탭에서 같은 계정으로 로그인해도 현재 세션은 풀리지 않는다. 즉, **동시 접속이 로그아웃 원인이 아니다**.

## 원리

| 구성 요소 | TTL | 갱신 방법 |
|---|---|---|
| Access token | 60분 | 만료 시 다음 API 호출에서 자동 재발급 시도 |
| Refresh token (관리자) | 3일 | 로그인 후 3일 이내에 한 번이라도 화면을 조작하면 갱신됨 |
| Refresh token (협력사) | 7일 | 동일 |

3일 이상 화면을 켜두기만 하고 아무 동작도 하지 않으면 refresh token도 만료되어 로그인이 필요하다.

## "갑자기 풀렸는데 동시 접속 때문인가요?" 답변

아니다. 동일 계정으로 다른 단말에서 로그인해도 기존 세션은 끊기지 않는다. 단말별로 별도 refresh token이 발급되어 독립 운영된다.

자주 로그아웃되는 패턴은 (1) 3일 이상 신규 동작이 없거나 (2) 사내망 차단/네트워크 일시 장애로 refresh API 호출이 실패하는 경우다.

## 폼 임시 저장 동작

- 신규 주문 폼에서 1초 이상 입력 후 멈추면 자동으로 브라우저에 저장된다.
- 저장 성공 또는 명시적 취소 시 즉시 삭제된다.
- 30분 후 자동 폐기된다 (보안 정책상 PII 장기 보관 X).

## 만약 여전히 풀리면

브라우저 콘솔(F12 → Console) 화면을 캡처해 운영팀에 전달한다. `refresh_failed`, `401` 로그가 보이면 refresh API 호출이 실패한 경우다.

## 보안 trade-off (운영팀 인지 사항)

- Access token TTL 연장(15분→60분) + localStorage 저장 구조는 **XSS 발생 시 노출 시간**이 길어진다. 공용 PC에서 사용 금지, 의심 시 즉시 로그아웃을 권장한다.
- 장기 개선 목표 (R9~R10 후보): refresh/access token을 httpOnly + Secure cookie로 이전. 그렇게 하면 XSS 공격으로 토큰 탈취 불가. 본 R8에서는 운영 편의를 우선했다.

## 수동 검증 항목 (배포 후 1회)

- 주문 신규 등록 → 주소 검색 클릭 → 카카오 우편번호 모달이 정상적으로 뜨고, 결과를 선택하면 기본주소 입력란에 채워지는지 확인. 콘솔에 `Refused to load the script ...` CSP 에러가 없어야 한다.
```

- [ ] **Step 4: 커밋**

```bash
git add backend/app/core/config.py backend/tests/test_auth_integration.py docs/runbooks/r8-session-policy.md
git commit -m "feat(auth): R8 access token TTL 60분 연장 + 운영팀 세션 정책 안내"
```

---

## Task 7 — 프론트엔드: react-daum-postcode 의존성 + CSP allowlist

**Files:**
- Modify: `frontend/package.json`, `frontend/package-lock.json`
- Modify: `backend/app/core/middleware.py`

`react-daum-postcode`는 내부적으로 카카오 외부 도메인의 script와 iframe을 로드한다. 현재 CSP가 `script-src 'self'`로 닫혀 있어 외부 배포 시 우편번호 모달이 차단된다. **반드시 CSP를 함께 갱신해야** 운영에서 동작한다.

- [ ] **Step 1: 패키지 설치**

Run:
```powershell
cd frontend
npm install react-daum-postcode@^3.1.3
```

Expected: `package.json`의 `dependencies`에 `"react-daum-postcode": "^3.1.3"` 추가됨. 4.x도 가능하나 v3 API와 호환되는지 별도 확인 필요 — 일단 안정 버전 3.1.x로 고정.

- [ ] **Step 2: typecheck로 즉시 검증**

Run: `cd frontend && npm run typecheck`
Expected: 통과 (아직 import 한 곳 없음).

- [ ] **Step 3: CSP에 카카오 도메인 allowlist 추가**

`backend/app/core/middleware.py`의 `_build_csp_value()` 함수를 다음으로 치환한다 (line 49~79).

```python
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
```

- [ ] **Step 4: CSP 검증 테스트 추가**

`backend/tests/test_middleware.py` (또는 기존 middleware 테스트 file)에 추가:

```python
def test_csp_includes_kakao_postcode_domains(client):
    response = client.get("/api/health")
    csp = response.headers.get("content-security-policy", "")
    assert "https://t1.daumcdn.net" in csp
    assert "https://postcode.map.kakao.com" in csp
    assert "script-src" in csp
    assert "frame-src" in csp
```

Run: `cd backend && python -m pytest tests/test_middleware.py -v`
Expected: 통과.

- [ ] **Step 5: 운영 수동 검증 항목 기록**

배포 후 다음을 확인해야 한다 (`docs/runbooks/r8-session-policy.md`에 한 줄 추가):
- "주문 신규 등록 → 주소 검색 클릭 → 우편번호 모달이 정상적으로 로드되고 결과 선택 시 입력란에 채워지는지" 수동 확인.
- 브라우저 콘솔에 `Refused to load the script ...` CSP 에러가 없는지 확인.

- [ ] **Step 6: 커밋**

```bash
git add frontend/package.json frontend/package-lock.json backend/app/core/middleware.py backend/tests/test_middleware.py docs/runbooks/r8-session-policy.md
git commit -m "chore(deps): R8 react-daum-postcode 추가 + CSP 카카오 도메인 allowlist"
```

---

## Task 8 — `AddressInput` 컴포넌트 + 신규 주문 폼 통합

**Files:**
- Create: `frontend/src/components/AddressInput.tsx`
- Modify: `frontend/src/features/admin/orders/OrderFormPage.tsx`

- [ ] **Step 1: `AddressInput` 컴포넌트 신규 작성**

`frontend/src/components/AddressInput.tsx`:

```tsx
import React from 'react';
import DaumPostcode from 'react-daum-postcode';

interface AddressInputProps {
  baseAddress: string;
  detailAddress: string;
  onChange: (next: { baseAddress: string; detailAddress: string }) => void;
  required?: boolean;
  testIdPrefix?: string;
}

export function AddressInput({
  baseAddress,
  detailAddress,
  onChange,
  required = false,
  testIdPrefix = 'order-customer-address',
}: AddressInputProps) {
  const [isSearchOpen, setSearchOpen] = React.useState(false);

  const handleComplete = (data: { roadAddress?: string; address: string; jibunAddress?: string; zonecode: string }) => {
    const chosen = data.roadAddress || data.address || data.jibunAddress || '';
    const formatted = data.zonecode ? `(${data.zonecode}) ${chosen}` : chosen;
    onChange({ baseAddress: formatted, detailAddress });
    setSearchOpen(false);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-tertiary)' }}>
        주소{required ? ' *' : ''}
      </label>

      <div style={{ display: 'flex', gap: 6 }}>
        <input
          data-testid={`${testIdPrefix}-base`}
          className="input"
          style={{ flex: 1 }}
          value={baseAddress}
          placeholder="검색 버튼을 눌러 우편번호 / 도로명을 선택하세요"
          readOnly
        />
        <button
          type="button"
          data-testid={`${testIdPrefix}-search`}
          className="btn btn--secondary btn--sm"
          onClick={() => setSearchOpen(true)}
        >
          주소 검색
        </button>
      </div>

      <input
        data-testid={`${testIdPrefix}-detail`}
        className="input"
        value={detailAddress}
        placeholder="상세주소 (동/호수 등) — 권장"
        onChange={(event) => onChange({ baseAddress, detailAddress: event.target.value })}
      />

      {baseAddress && !detailAddress && (
        <div style={{ fontSize: 11, color: 'var(--warning-fg)' }}>
          상세주소 미입력 — 동/호수까지 입력하면 협력사가 헤매지 않습니다.
        </div>
      )}

      {isSearchOpen && (
        <div
          data-testid={`${testIdPrefix}-modal`}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
          onClick={() => setSearchOpen(false)}
        >
          <div
            style={{ background: 'var(--surface)', padding: 12, borderRadius: 8, width: 480, maxWidth: '90vw' }}
            onClick={(event) => event.stopPropagation()}
          >
            <DaumPostcode onComplete={handleComplete} autoClose={false} style={{ height: 480 }} />
            <div style={{ marginTop: 8, textAlign: 'right' }}>
              <button
                type="button"
                data-testid={`${testIdPrefix}-modal-close`}
                className="btn btn--ghost btn--sm"
                onClick={() => setSearchOpen(false)}
              >
                닫기
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: `OrderFormPage`에 `AddressInput` 적용**

`frontend/src/features/admin/orders/OrderFormPage.tsx`:

1. 상단 import에 추가:
```tsx
import { AddressInput } from '../../../components/AddressInput';
```

2. `createEmptyGroupForm` (line 471–481)에 `customer_address_detail: ''` 추가:
```tsx
function createEmptyGroupForm() {
  return {
    group_id: '',
    customer_name: '',
    customer_phone: '',
    customer_address: '',
    customer_address_detail: '',
    source_channel: '',
    customer_visible_payment: false,
    notes: '',
    lines: [createEmptyLineForm()],
  };
}
```

3. `<Section title="고객 정보">` 블록(line 211–218)에서 주소 `TextField` 줄을 아래로 치환:
```tsx
<Section title="고객 정보">
  <FieldGrid>
    <TextField testId="order-customer-name" label="고객명" required value={form.customer_name} onChange={(value) => setGroupField('customer_name', value)} />
    <TextField testId="order-customer-phone" label="연락처" required value={form.customer_phone} onChange={(value) => setGroupField('customer_phone', value)} placeholder="010-0000-0000" />
    <TextField label="유입 경로" value={form.source_channel} onChange={(value) => setGroupField('source_channel', value)} />
    <div style={{ gridColumn: 'span 2' }}>
      <AddressInput
        baseAddress={form.customer_address}
        detailAddress={form.customer_address_detail}
        required
        onChange={({ baseAddress, detailAddress }) => {
          setGroupField('customer_address', baseAddress);
          setGroupField('customer_address_detail', detailAddress);
        }}
      />
    </div>
  </FieldGrid>
</Section>
```

4. 폼 수정(edit) 모드 진입 시 group을 fetch 해서 form state로 매핑하는 위치를 찾는다 — `OrderFormPage.tsx`에서 `Grep`으로 `customer_address:` 또는 `customer_name:` 매핑 라인을 찾아 그 다음에 `customer_address_detail: group.customer_address_detail ?? '',` 라인을 추가한다.

5. submit payload 매핑 — `OrderFormPage.tsx`에서 `Grep`으로 `createAdminOrderGroup` 또는 `updateAdminOrderGroup` 호출부를 찾는다. payload 객체에 `customer_address` 다음 줄로 `customer_address_detail: form.customer_address_detail,`를 추가한다 (spread 패턴이면 자동 포함되므로 확인만).

6. `frontend/src/api/admin.ts`의 `OrderGroupCreatePayload` / `OrderGroupUpdatePayload` TypeScript interface에도 `customer_address_detail?: string | null;` 필드를 추가한다.

- [ ] **Step 3: typecheck + lint**

Run: `cd frontend && npm run typecheck && npm run lint`
Expected: 통과.

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/components/AddressInput.tsx frontend/src/features/admin/orders/OrderFormPage.tsx
git commit -m "feat(orders): R8 카카오 우편번호 + 상세주소 분리 입력"
```

---

## Task 9 — 폼 draft 자동 저장 (자동 로그아웃 안전망)

**Files:**
- Create: `frontend/src/features/admin/orders/useOrderFormDraft.ts`
- Modify: `frontend/src/features/admin/orders/OrderFormPage.tsx`

- [ ] **Step 1: `useOrderFormDraft` hook 작성**

`frontend/src/features/admin/orders/useOrderFormDraft.ts`:

```ts
import React from 'react';

const STORAGE_KEY = 'cleaning_ops_draft_order_form_v1';
const TTL_MS = 30 * 60 * 1000; // 30분
const DEBOUNCE_MS = 1000;

// PII/결제 정보는 draft에서 제외한다. 결제 메모/금액/협력사 정산은
// 30분 잔존 위험 대비 가치가 낮다.
const EXCLUDED_FORM_FIELDS = [
  'payment_memo',
  'evidence_memo',
] as const;
const EXCLUDED_LINE_FIELDS = [
  'total_amount',
  'deposit_amount',
  'balance_amount',
  'onsite_extra_amount',
  'partner_payment_amount',
  'partner_payment_status',
  'payment_memo',
  'evidence_memo',
] as const;

function sanitize<T extends Record<string, unknown>>(form: T): T {
  const cloned = { ...form } as Record<string, unknown>;
  for (const key of EXCLUDED_FORM_FIELDS) {
    if (key in cloned) delete cloned[key];
  }
  if (Array.isArray(cloned.lines)) {
    cloned.lines = (cloned.lines as Record<string, unknown>[]).map((line) => {
      const lineCopy = { ...line };
      for (const key of EXCLUDED_LINE_FIELDS) {
        if (key in lineCopy) delete lineCopy[key];
      }
      return lineCopy;
    });
  }
  return cloned as T;
}

interface DraftEnvelope<T> {
  saved_at: number;
  payload: T;
}

export function useOrderFormDraft<T>(form: T, options: { enabled: boolean }) {
  const { enabled } = options;
  const timer = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  React.useEffect(() => {
    if (!enabled) return;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      try {
        const sanitized = sanitize(form as unknown as Record<string, unknown>) as T;
        const envelope: DraftEnvelope<T> = { saved_at: Date.now(), payload: sanitized };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(envelope));
      } catch {
        // localStorage quota exceeded — silently drop draft
      }
    }, DEBOUNCE_MS);

    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [form, enabled]);

  return {
    loadDraft: (): T | null => {
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return null;
        const envelope = JSON.parse(raw) as DraftEnvelope<T>;
        if (Date.now() - envelope.saved_at > TTL_MS) {
          localStorage.removeItem(STORAGE_KEY);
          return null;
        }
        return envelope.payload;
      } catch {
        return null;
      }
    },
    clearDraft: () => {
      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch {
        // ignore
      }
    },
  };
}
```

- [ ] **Step 2: `OrderFormPage`에 draft 통합**

`OrderFormPage.tsx` 컴포넌트 상단(state 선언 다음)에 추가:

```tsx
const draft = useOrderFormDraft(form, { enabled: mode === 'create' });

React.useEffect(() => {
  if (mode !== 'create') return;
  const restored = draft.loadDraft();
  if (!restored) return;
  // 사용자가 빈 폼인지 확인 후 prompt — 폼이 비어있을 때만 prompt
  if (form.customer_name === '' && form.customer_phone === '' && form.lines.every((l) => !l.scheduled_date)) {
    if (window.confirm('이전 작성 중이던 신규 주문 임시 저장 데이터가 있습니다. 불러올까요?')) {
      setForm(restored);
    } else {
      draft.clearDraft();
    }
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, [mode]);
```

저장 성공 핸들러(`onSubmit` 성공 분기 + 명시적 취소)에 추가:
```tsx
draft.clearDraft();
```

import 추가:
```tsx
import { useOrderFormDraft } from './useOrderFormDraft';
```

- [ ] **Step 2.5: 로그아웃/세션 클리어 시 draft 삭제**

`frontend/src/store/authStore.tsx`의 `clearAuth` 콜백(line 44~57)에 draft 삭제를 함께 처리한다.

`clearAuth` 함수 본문 최상단(setState 호출 전)에 추가:

```tsx
const clearAuth = React.useCallback((role = undefined) => {
  try {
    localStorage.removeItem('cleaning_ops_draft_order_form_v1');
  } catch {
    // ignore
  }
  setState((current) => {
    // ... 기존 로직 유지
  });
}, []);
```

세션이 만료되거나 명시적 logout이 발생하면 draft도 함께 사라진다 — XSS/공용 PC 잔존 위험 최소화.

- [ ] **Step 3: api/client.ts에 refresh 실패 진단 로그 추가**

`frontend/src/api/client.ts`의 line 56–59 (refresh catch 블록):

```ts
} catch (error) {
  console.warn('[auth] refresh_failed — session will be cleared', error);
  authHandlers.onUnauthorized();
  throw error;
}
```

retryResponse 401 분기(line 63–64):
```ts
if (retryResponse.status === 401) {
  console.warn('[auth] retry_still_unauthorized — clearing session');
  authHandlers.onUnauthorized();
}
```

- [ ] **Step 4: typecheck + lint**

Run: `cd frontend && npm run typecheck && npm run lint`
Expected: 통과.

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/features/admin/orders/useOrderFormDraft.ts frontend/src/features/admin/orders/OrderFormPage.tsx frontend/src/api/client.ts
git commit -m "feat(orders): R8 폼 draft 자동 저장 + 세션 만료 진단 로그"
```

---

## Task 10 — 주문 목록: 전체선택 + 일괄 삭제

**Files:**
- Modify: `frontend/src/features/admin/orders/OrdersPage.tsx`
- Modify: `frontend/src/api/admin.ts`

- [ ] **Step 1: API client에 `bulkDeleteAdminOrders` 추가**

`frontend/src/api/admin.ts`에:

```ts
export interface BulkDeleteFailure {
  order_id: string;
  reason: string;
}

export interface BulkDeleteResponse {
  succeeded: string[];
  failed: BulkDeleteFailure[];
}

export function bulkDeleteAdminOrders(orderIds: string[]): Promise<BulkDeleteResponse> {
  return apiRequest('/admin/orders/bulk-delete', {
    method: 'POST',
    body: { order_ids: orderIds },
  });
}

export function deleteAdminOrder(orderId: string): Promise<void> {
  return apiRequest(`/admin/orders/${orderId}`, { method: 'DELETE' });
}
```

- [ ] **Step 2: `OrdersPage`에 전체선택 토글 + 일괄 삭제 버튼**

테이블 헤더 row에 전체선택 checkbox (현재 OrdersPage의 테이블 헤더 구조를 따라 추가). 정확한 라인은 OrdersPage의 `<thead>` 또는 row template 위치 (Grep으로 `<thead>` 검색).

선택 바(line 562–577)에 "삭제" 버튼 추가:

```tsx
<button data-testid="orders-bulk-status-open" style={bulkActionButton(bulkAction === 'status')} onClick={() => setBulkAction(bulkAction === 'status' ? null : 'status')}>상태 변경</button>
<button data-testid="orders-bulk-message-open" style={bulkActionButton(bulkAction === 'message')} onClick={() => setBulkAction(bulkAction === 'message' ? null : 'message')}>메시지</button>
<button data-testid="orders-bulk-partner-open" style={bulkActionButton(bulkAction === 'partner')} onClick={() => setBulkAction(bulkAction === 'partner' ? null : 'partner')}>협력사 배정</button>
<button data-testid="orders-bulk-delete" style={{ ...bulkActionButton(false), color: 'var(--danger-fg)' }} onClick={handleBulkDelete}>삭제</button>
```

전체선택/해제 토글은 테이블 헤더의 모든 row checkbox 자리에 다음을 넣는다 (현재 OrdersPage의 헤더 구조에 맞게 적절한 `<th>` 또는 `<th className="checkbox">`를 찾아 교체):

```tsx
<input
  data-testid="orders-select-all"
  type="checkbox"
  checked={visibleOrders.length > 0 && visibleOrders.every((o) => selected.has(o.id))}
  onChange={(event) => {
    if (event.target.checked) {
      setSelected(new Set(visibleOrders.map((o) => o.id)));
    } else {
      setSelected(new Set());
    }
  }}
/>
```

(주의: `visibleOrders`는 현재 OrdersPage가 filter/sort 적용 후 화면에 보이는 주문 배열의 변수명. 실제 변수명에 맞게 치환한다. Grep으로 `.map((order` 패턴을 보고 변수명 확인.)

`handleBulkDelete` 핸들러:

```tsx
const [isDeleting, setIsDeleting] = React.useState(false);

const handleBulkDelete = async () => {
  if (selected.size === 0) return;
  if (!window.confirm(`선택한 ${selected.size}건의 주문을 삭제하시겠습니까? 삭제된 주문은 목록에서 사라지지만 운영 기록(타임라인)은 보존됩니다.`)) return;

  setIsDeleting(true);
  try {
    const result = await bulkDeleteAdminOrders(Array.from(selected));
    setSelected(new Set());
    setBulkAction(null);
    if (result.failed.length > 0) {
      window.alert(`${result.succeeded.length}건 삭제 완료, ${result.failed.length}건 실패: ${result.failed.map((f) => f.order_id).join(', ')}`);
    }
    await ordersResource.reload();
  } catch (error) {
    window.alert(`삭제 실패: ${error instanceof Error ? error.message : String(error)}`);
  } finally {
    setIsDeleting(false);
  }
};
```

import 추가:
```tsx
import { bulkDeleteAdminOrders } from '../../../api/admin';
```

- [ ] **Step 3: typecheck + lint**

Run: `cd frontend && npm run typecheck && npm run lint`
Expected: 통과.

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/features/admin/orders/OrdersPage.tsx frontend/src/api/admin.ts
git commit -m "feat(orders): R8 전체 선택 + 일괄 삭제 버튼"
```

---

## Task 11 — 주문 상세: 단건 삭제 버튼 + 상세주소 표시

**Files:**
- Modify: `frontend/src/features/admin/orders/OrderDetailPage.tsx`
- Modify: `frontend/src/features/customer/CustomerReservation.tsx`

- [ ] **Step 1: 헤더에 삭제 버튼 추가**

`OrderDetailPage.tsx` line 242~252 (toolbar 영역)에 "일정표" 버튼 다음에 삭제 버튼 추가:

```tsx
<button className="btn btn--ghost btn--sm" onClick={() => onNav?.('calendar')}>
  <Icon name="calendar" size={12}/> 일정표
</button>
<button
  data-testid="order-detail-delete"
  className="btn btn--ghost btn--sm"
  style={{ color: 'var(--danger-fg)' }}
  onClick={handleDelete}
  disabled={isDeleting}
>
  <Icon name="trash" size={12}/> {isDeleting ? '삭제 중' : '삭제'}
</button>
```

handler:

```tsx
const [isDeleting, setIsDeleting] = React.useState(false);

const handleDelete = async () => {
  const ok = window.confirm(
    `이 주문(${order.id})을 삭제하시겠습니까?\n\n` +
    '운영 기록(타임라인, 메시지 로그, 사진)은 보존되지만 목록에서는 사라집니다.'
  );
  if (!ok) return;

  setIsDeleting(true);
  try {
    await deleteAdminOrder(order.id);
    onBack(); // 목록으로 복귀
  } catch (error) {
    window.alert(`삭제 실패: ${error instanceof Error ? error.message : String(error)}`);
  } finally {
    setIsDeleting(false);
  }
};
```

import:
```tsx
import { deleteAdminOrder } from '../../../api/admin';
```

`Icon name="trash"`이 존재하지 않으면 가장 가까운 위험 액션 아이콘으로 대체 (또는 "✕" 텍스트 + 빨간색). Icon 컴포넌트 정의를 먼저 확인.

- [ ] **Step 1.5: OrderDetailPage 고객 정보에 상세주소 표시 추가**

같은 파일 line 257~265 (`<Section title="고객 정보">` 블록)에서 `<KVItem label="주소" value={order.customer_address} span={2}/>` 라인을 다음으로 치환:

```tsx
<KVItem
  label="주소"
  value={[order.customer_address, order.customer_address_detail].filter(Boolean).join(' ')}
  span={2}
/>
```

`AdminOrderRead` DTO TypeScript 정의(`frontend/src/api/admin.ts` 또는 `types`)에도 `customer_address_detail?: string | null;` 필드를 추가한다.

- [ ] **Step 1.6: 고객 페이지에도 상세주소 표시**

`frontend/src/features/customer/CustomerReservation.tsx`에서 `customer_address`를 표시하는 위치를 `Grep`으로 찾아(`customer_address` 패턴) 동일 패턴으로 치환:

```tsx
{[group.customer_address, group.customer_address_detail].filter(Boolean).join(' ')}
```

`CustomerOrderGroupRead` TypeScript 정의에도 `customer_address_detail?: string | null;` 추가.

- [ ] **Step 2: typecheck + lint**

Run: `cd frontend && npm run typecheck && npm run lint`
Expected: 통과.

- [ ] **Step 3: 커밋**

```bash
git add frontend/src/features/admin/orders/OrderDetailPage.tsx frontend/src/features/customer/CustomerReservation.tsx frontend/src/api/admin.ts
git commit -m "feat(orders): R8 주문 상세 단건 삭제 버튼 + 상세주소 표시"
```

---

## Task 12 — E2E: 주문 삭제 시나리오

**Files:**
- Create: `frontend/e2e/admin-order-delete-e2e.spec.ts`

- [ ] **Step 1: spec 작성**

```ts
import { expect, test } from '@playwright/test';
import { adminLogin, createAssignedOrder } from './helpers';

test('admin can delete a single order from detail page', async ({ browser, request }) => {
  const orderId = await createAssignedOrder(request);
  const context = await browser.newContext();
  const page = await context.newPage();
  await adminLogin(page);

  await page.getByTestId('admin-nav-orders').click();
  await expect(page.getByTestId('admin-orders-page')).toBeVisible();
  await page.getByText(orderId).first().click();

  await expect(page.getByTestId('admin-order-detail-page')).toBeVisible();

  page.on('dialog', (dialog) => dialog.accept());
  await page.getByTestId('order-detail-delete').click();

  await expect(page.getByTestId('admin-orders-page')).toBeVisible();
  await expect(page.getByText(orderId)).toHaveCount(0);

  await context.close();
});

test('admin can bulk-delete selected orders from list page', async ({ browser, request }) => {
  const orderId1 = await createAssignedOrder(request);
  const orderId2 = await createAssignedOrder(request);
  const context = await browser.newContext();
  const page = await context.newPage();
  await adminLogin(page);

  await page.getByTestId('admin-nav-orders').click();
  await expect(page.getByTestId('admin-orders-page')).toBeVisible();

  // 개별 체크박스 선택 — 기존 testid `admin-order-row-${id}` (OrdersPage.tsx:649) 사용
  await page.locator(`[data-testid="admin-order-row-${orderId1}"] input[type="checkbox"]`).check();
  await page.locator(`[data-testid="admin-order-row-${orderId2}"] input[type="checkbox"]`).check();

  await expect(page.getByText('2건 선택')).toBeVisible();
  page.on('dialog', (dialog) => dialog.accept());
  await page.getByTestId('orders-bulk-delete').click();

  await expect(page.getByText(orderId1)).toHaveCount(0);
  await expect(page.getByText(orderId2)).toHaveCount(0);

  await context.close();
});
```

helpers.ts에 `adminLogin`/`createAssignedOrder`가 이미 있으면 그대로 사용 (R6/R7 plan에서 도입). 행 testid는 기존 `admin-order-row-${id}`를 사용.

- [ ] **Step 2: 실행**

Run: `cd frontend && npm run e2e -- admin-order-delete-e2e`
Expected: 2 passed.

- [ ] **Step 3: 커밋**

```bash
git add frontend/e2e/admin-order-delete-e2e.spec.ts frontend/e2e/helpers.ts
git commit -m "test(e2e): R8 주문 단건/일괄 삭제 시나리오"
```

---

## Task 13 — E2E: 주소 검색 입력 (mock)

**Files:**
- Create: `frontend/e2e/admin-address-input-e2e.spec.ts`

`react-daum-postcode`는 외부 iframe을 불러온다. E2E에서는 실제 우편번호 검색을 호출하지 않고, mock 입력으로 우회한다.

- [ ] **Step 1: spec 작성**

```ts
import { expect, test } from '@playwright/test';
import { adminLogin } from './helpers';

test('admin can open address search modal and edit detail address', async ({ browser }) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  await adminLogin(page);

  await page.getByTestId('admin-nav-orders').click();
  // 기존 testid `admin-orders-create` (OrdersPage.tsx:355) 사용 — 새 testid 추가 X
  await page.getByTestId('admin-orders-create').click();

  await expect(page.getByTestId('order-customer-address-search')).toBeVisible();
  await page.getByTestId('order-customer-address-search').click();
  await expect(page.getByTestId('order-customer-address-modal')).toBeVisible();
  await page.getByTestId('order-customer-address-modal-close').click();
  await expect(page.getByTestId('order-customer-address-modal')).toHaveCount(0);

  await page.getByTestId('order-customer-address-detail').fill('101동 1001호');
  await expect(page.getByTestId('order-customer-address-detail')).toHaveValue('101동 1001호');

  await context.close();
});
```

(우편번호 검색 자체의 iframe 동작은 본 spec에서 검증하지 않는다 — 외부 서비스 의존성. 추후 mock 컴포넌트로 분리하는 작업은 R8.5+.)

신규 testid는 추가하지 않는다 — `admin-orders-create`(OrdersPage.tsx:355), `admin-order-row-${id}`(:649)가 이미 존재.

- [ ] **Step 2: 실행**

Run: `cd frontend && npm run e2e -- admin-address-input-e2e`
Expected: 1 passed.

- [ ] **Step 3: 커밋**

```bash
git add frontend/e2e/admin-address-input-e2e.spec.ts
git commit -m "test(e2e): R8 주소 검색 모달 + 상세주소 입력"
```

---

## Task 14 — 전체 회귀 + 핸드오프 갱신

**Files:**
- Modify: `.master/next_session_plan.md`

- [ ] **Step 1: backend 전체 회귀**

Run: `cd backend && python -m pytest -q`
Expected: 모두 통과.

- [ ] **Step 2: frontend 전체 회귀**

Run:
```powershell
cd frontend
npm run typecheck
npm run lint
npm run build
npm run e2e
```
Expected: 모두 통과.

- [ ] **Step 3: `next_session_plan.md` 갱신**

`.master/next_session_plan.md` 상단 "최신 업데이트" 블록에 R8 항목을 추가하고, "## 3. 다음 세션 추천 작업"을 다음 세션용으로 갱신한다.

```markdown
최신 업데이트:

- `R6 Photo Auto Publish + Revoke` 완료 후 race-condition hotfix까지 반영됐다.
- `R7 Multi-line Orders` 완료.
- `R8 Ops UX Hardening` 완료.
  - 카카오 우편번호 + 상세주소 분리 입력
  - Access token TTL 60분 + 폼 draft 자동 저장 (자동 로그아웃 안전망)
  - 주문 목록 전체선택 + 일괄 삭제
  - 주문 상세 단건 삭제
  - 삭제는 soft-delete, timeline은 보존
```

세션 정책 안내 문서 위치를 § "1. 기준 문서"에 추가:
```markdown
- `docs/runbooks/r8-session-policy.md`
```

- [ ] **Step 4: 커밋**

```bash
git add .master/next_session_plan.md
git commit -m "docs(handoff): R8 마감 + 다음 세션 진입점 갱신"
```

---

## Self-Review (작성자가 직접 확인)

**1. Spec coverage:**

| PDF 요청 | Task 매핑 |
|---|---|
| 주소 입력 API (우편번호 검색 + 상세주소 분리) | Task 2 (DB) + Task 3 (모델/스키마/DTO 변환 4종) + Task 7 (의존성 + CSP) + Task 8 (컴포넌트/폼) + Task 13 (E2E) |
| 자동 로그아웃 개선 + 원인 진단 | Task 6 (TTL 60분 + 운영 안내 + 보안 trade-off) + Task 9 (폼 draft + 진단 로그 + clearAuth 연동) |
| 주문관리 전체선택/일괄 삭제 | Task 2 (DB) + Task 3 (timeline enum) + Task 4 (서비스 + soft-delete 가드 전방위) + Task 5 (API) + Task 10 (UI) + Task 12 (E2E bulk) |
| 주문 상세 단건 삭제 | Task 5 (API) + Task 11 (UI) + Task 12 (E2E single) |
| 정책/문서/보안 | Task 1 (AGENTS/CLAUDE) + Task 7 (CSP) + Task 14 (핸드오프) |

모든 요청 항목이 task에 매핑됨.

**v2 Codex review 반영 사항 (5 blocking + 5 should-fix + 3 nit):**

| Codex finding | 반영 위치 |
|---|---|
| B1: 라우트 경로 `/{order_id}`/`bulk-delete` + `get_session`/`CurrentUser` | Task 5 Step 3 |
| B2: `TimelineService.record`(record_event X), `OrderStatus.NEW`(NEW_ORDER X), `app.models.timeline.OrderTimeline` | Task 3 + Task 4 Step 1, 3 |
| B3: DTO 변환 함수 4종에 `customer_address_detail` 명시 + Partner DTO도 group 인자 받음 | Task 3 Step 5 |
| B4: Repository `get()` override + 모든 서비스/route의 raw `db.get()` 가드 + 격리 테스트 | Task 4 Step 5, 5.5, 5.6 |
| B5: CSP `script-src/frame-src/connect-src` 카카오 도메인 추가 + 검증 테스트 | Task 7 Step 3, 4 |
| S1: react-daum-postcode v3.1.3 고정 + 대안 비교 (공식 SDK vs npm) | D1 |
| S2: testid `admin-order-row-${id}` / `admin-orders-create` 통일 | Task 12, 13 |
| S3: draft에서 결제/메모 필드 제외 + clearAuth 시 삭제 | D4 + Task 9 Step 1, 2.5 |
| S4: bulk 트랜잭션 정책 (not_found = partial commit, DB exception = rollback) | D9 |
| S5: 60분 TTL 보안 trade-off 명시 + httpOnly 장기 목표 | D11 + Task 6 runbook |
| N1: superpowers:* 서브-스킬 헤더 제거 | 헤더 갱신 |
| N2: `python -m grep` 제거 | Task 4 Step 5 |
| N3: `data.roadAddress || data.address || data.jibunAddress` | Task 8 Step 1 |

**2. Placeholder scan:** 없음. 각 step에 실행 가능한 코드/명령/예상 결과 제공.

**3. Type consistency:**
- 백엔드 클래스명: `BulkDeleteResult` / `BulkDeleteFailure` (서비스 dataclass, Task 4) → `BulkDeleteResponse` / `BulkDeleteFailureItem` (Pydantic, Task 5). 클래스명은 다르지만 JSON 응답 키는 `succeeded` / `failed` / `order_id` / `reason`으로 일관. Frontend interface `BulkDeleteResponse` / `BulkDeleteFailure` (Task 10)는 JSON에만 의존하므로 OK.
- `delete_order(order_id, actor_user_id)` signature: Task 4의 서비스, Task 5의 라우터에서 동일하게 호출.
- `customer_address_detail`: 모델·스키마·form state·API payload 모두 동일 snake_case 유지.
- timeline event type: `TimelineEventType.ORDER_DELETED = "order_deleted"` Task 3에서 정의, Task 4에서 사용.
- `useOrderFormDraft` hook의 `loadDraft` / `clearDraft` 메서드명: Task 9에서 정의, 같은 task에서 호출 — 일치.

---

## Execution Handoff

이 plan은 codex가 task-by-task로 진행하며, 각 task 완료 후 사용자(나)에게 review를 요청한다. 권장 흐름:

1. Codex가 Task 1부터 순서대로 진행. 각 task의 step 완료 시점에 git status / diff를 보고한다.
2. 각 task 완료 시 사용자가 코드 리뷰 후 다음 task 진행 승인.
3. 만약 Task 진행 중 spec 충돌이 생기면 즉시 멈추고 사용자에게 결정 요청 (CTO 결정 사항 D1~D9 외의 항목).
4. 마지막 Task 14 완료 후 전체 PR 리뷰 → main 브랜치 머지.
