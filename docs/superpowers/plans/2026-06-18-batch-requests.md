# 도급사 누적 요청 9건 — 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (웨이브 단위 inline 실행 + 중간 확인). Steps use `- [ ]` checkbox.

**Goal:** 도급사 요청 9건(증빙자료/일괄변경/주문복제/담당자연락처/미정산버그/주소검색/줄바꿈/정산전체선택)을 4개 웨이브로 구현한다.

**Architecture:** 기존 FastAPI(레이어드)+React 구조를 그대로 따른다. 신규 enum/컬럼은 `domain/`+`models/`+마이그레이션, DTO는 Pydantic 클래스 구조(상속=노출, 별도클래스=차단)로 권한을 보장. 프론트는 `features/admin/*`에 기존 패턴(일괄변경 루프, 배지, 폼 prefill)으로 추가.

**Tech Stack:** Python 3.11/FastAPI/SQLAlchemy 2.0/Alembic/Pydantic, React 19/TS/plain CSS, pytest/Playwright.

**검증 명령:** 백엔드 `cd backend && python -m pytest && ruff check . && python -m compileall app`, 프론트 `cd frontend && npm run typecheck && npm run lint`.

**확인된 핵심 사실:**
- DTO 권한: `OrderLineBase` 상속 → `AdminOrderRead`/`OrderCreate`에 자동 포함. `OrderUpdate`는 별도 클래스(수동 추가 필요). `PartnerJobRead`/`CustomerOrderLineRead`는 별도 클래스 → 필드 안 넣으면 자동 차단.
- 최신 마이그레이션: `0012_user_phone_unique`.
- 프론트 `src/domain/*.ts`는 타입 없는 JS 스타일(`paymentStatus.ts` 참고) → 동일 스타일 유지.
- 일괄변경은 선택 주문을 for 루프로 개별 PATCH(`updateAdminOrder`) 호출하는 기존 패턴.

---

## 웨이브 0 — 가벼운 개선 3종 (위험 낮음)

### Task 0.1: 텍스트 줄바꿈 보존 (.multiline-text)

**Files:**
- Modify: `frontend/src/styles/global.css` (유틸 클래스 추가)
- Modify: `frontend/src/features/admin/orders/OrderDetailPage.tsx` (KVItem multiline 표시)
- Modify: `frontend/src/features/partner/PartnerJobDetail.tsx` (service_detail/special_request)
- Modify: `frontend/src/features/customer/CustomerReservation.tsx` (mutedLineStyle 표시부)

- [ ] **Step 1:** `global.css`에 유틸 클래스 추가(기존 유틸 클래스 인근):
```css
.multiline-text {
  white-space: pre-wrap;
  word-break: break-word;
}
```
- [ ] **Step 2:** `OrderDetailPage.tsx` `KVItem`에서 multiline 값 표시 `div`에 `className="multiline-text"` 부여(기존 `lineHeight:1.5` 유지). 정확 위치는 KVItem 함수(≈988~1001) 확인 후 적용.
- [ ] **Step 3:** `PartnerJobDetail.tsx` service_detail(≈198), special_request(≈217) 표시 `div`에 `className="multiline-text"` 부여.
- [ ] **Step 4:** `CustomerReservation.tsx` `mutedLineStyle` 사용 표시부(service_detail≈231, special_request≈235)에 `whiteSpace:'pre-wrap', wordBreak:'break-word'`를 스타일에 추가(클래스 미사용 패턴이면 인라인).
- [ ] **Step 5:** `npm run typecheck && npm run lint`.
- [ ] **Step 6:** 수동 확인 — 상세에서 줄바꿈 들어간 메모/특이사항이 개행 유지로 보이는지(실행 시 8002).
- [ ] **Step 7:** Commit `feat(ui): 상세 자유텍스트 줄바꿈 보존(.multiline-text)`.

### Task 0.2: 주문 주소 검색에 상세주소 포함

**Files:**
- Modify: `backend/app/services/order_page.py:306-331` (`_matches_query`)
- Test: `backend/tests/` (order_page 검색 테스트 파일; 없으면 신규)

- [ ] **Step 1 (failing test):** 상세주소만 매칭되는 검색 테스트 작성. 같은 그룹에 `customer_address="서울시 강남구"`, `customer_address_detail="101동 202호"`인 주문을 만들고, `q="202호"`로 `list_page` 호출 시 결과 포함을 기대. 기존 order_page 테스트 파일 패턴을 따른다(없으면 `tests/test_order_page_search.py` 신설, 기존 fixture 재사용).
- [ ] **Step 2:** 테스트 실행 → FAIL(상세주소 미매칭).
- [ ] **Step 3:** `_matches_query`에서 상세주소 추출 후 candidates에 추가:
```python
customer_address_detail = (group.customer_address_detail if group else None) or ""
...
candidates = [
    status_label,
    order.status,  # rawStatus
    order.service_name,
    format_quantity(order.size_or_quantity),
    customer_address,
    customer_address_detail,
    f"{customer_address} {customer_address_detail}".strip(),
    customer_name,
    format_phone(customer_phone),
    order.team_name or "미배정",
]
```
- [ ] **Step 4:** 테스트 실행 → PASS.
- [ ] **Step 5:** `python -m pytest tests/test_order_page_search.py -v && ruff check .`.
- [ ] **Step 6:** Commit `feat(search): 주문 검색에 상세주소 포함`.

### Task 0.3: 협력사 정산 리스트 전체선택 체크박스

**Files:**
- Modify: `frontend/src/features/admin/partners/PartnersPage.tsx` (정산 그리드 헤더 811~812, 선택 핸들러 412~418)

- [ ] **Step 1:** 전체선택 핸들러 추가(toggleSettlementSelection 인근):
```tsx
const allSettlementIds = settlements ? settlements.items.map((job) => job.order_id) : [];
const allSettlementsSelected = allSettlementIds.length > 0 && allSettlementIds.every((id) => settlementSelection.has(id));
const toggleAllSettlements = () => {
  setSettlementSelection((current) =>
    allSettlementsSelected ? new Set() : new Set(allSettlementIds),
  );
};
```
- [ ] **Step 2:** 헤더 렌더링(812)에서 첫 칸을 체크박스로 교체. 기존 `['', ...].map(...)`을, 첫 GridHead는 체크박스로 분리 렌더:
```tsx
<GridHead><input data-testid="partner-settlement-select-all" type="checkbox" checked={allSettlementsSelected} onChange={toggleAllSettlements} /></GridHead>
{['방문일', '상태', '작업', '고객', '소비자가', '도급가(VAT 포함)', '정산상태', '액션'].map((header) => <GridHead key={header}>{header}</GridHead>)}
```
- [ ] **Step 3:** 필터/기간 변경 시 선택 초기화는 기존 effect(405~410)가 `setSettlementSelection(new Set())`로 이미 처리함 — 확인만.
- [ ] **Step 4:** `npm run typecheck && npm run lint`.
- [ ] **Step 5:** 수동 확인 — 전체선택 시 모든 행 체크 + 하단 "선택 N건 정산" 활성.
- [ ] **Step 6:** Commit `feat(partners): 정산 리스트 전체선택 체크박스`.

### ✋ 체크포인트 W0 — 사용자 확인 후 W1 진행

---

## 웨이브 1 — 🌟 증빙자료 (최우선)

### Task 1.1: 백엔드 enum + 모델 + 마이그레이션

**Files:**
- Modify: `backend/app/domain/constants.py` (enum 2종)
- Modify: `backend/app/models/order.py` (컬럼 2개)
- Modify: `backend/app/domain/payment_status.py` (PAYMENT_TRACKED_FIELDS)
- Create: `backend/alembic/versions/0013_receipt_fields.py`

- [ ] **Step 1:** `constants.py`에 enum 추가(VatType 아래):
```python
class ReceiptType(StrEnum):
    CASH_RECEIPT = "cash_receipt"
    TAX_INVOICE = "tax_invoice"
    NONE = "none"


class ReceiptStatus(StrEnum):
    ISSUED = "issued"
    PENDING = "pending"
    NOT_APPLICABLE = "not_applicable"
```
- [ ] **Step 2:** `models/order.py`에서 `evidence_memo` 아래에 컬럼 추가:
```python
receipt_type: Mapped[str | None] = mapped_column(String(20))
receipt_status: Mapped[str | None] = mapped_column(String(30))
```
- [ ] **Step 3:** `payment_status.py` `PAYMENT_TRACKED_FIELDS`에 두 필드 추가(`evidence_memo` 다음 줄):
```python
    "receipt_type",
    "receipt_status",
```
- [ ] **Step 4:** 마이그레이션 작성. 기존 0012 파일 헤더/스타일을 먼저 읽어 동일 포맷 사용. revision id `0013_receipt_fields`, down_revision `0012_user_phone_unique`. upgrade:
```python
def upgrade() -> None:
    op.add_column("orders", sa.Column("receipt_type", sa.String(length=20), nullable=True))
    op.add_column("orders", sa.Column("receipt_status", sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "receipt_status")
    op.drop_column("orders", "receipt_type")
```
- [ ] **Step 5:** 마이그레이션 적용 먼저(규칙: 코드 수정 전 upgrade) — 실제론 모델 수정 후이므로 여기서 실행: `cd backend && python -m alembic upgrade head`. SQLite dev DB 기준. 오류 없으면 OK.
- [ ] **Step 6:** `python -m compileall app && ruff check .`.
- [ ] **Step 7:** Commit `feat(order): 증빙자료 receipt_type/receipt_status 컬럼+마이그레이션`.

### Task 1.2: 백엔드 DTO + 정규화 + 테스트

**Files:**
- Modify: `backend/app/schemas/order.py` (`OrderLineBase`, `OrderUpdate`)
- Modify: `backend/app/services/orders.py` (정규화 NONE→NOT_APPLICABLE; to_admin_order_dto 통과 확인)
- Test: `backend/tests/test_orders_receipt.py` (신규)

- [ ] **Step 1:** `schemas/order.py` import에 `ReceiptType, ReceiptStatus` 추가. `OrderLineBase`의 `evidence_memo` 아래:
```python
receipt_type: ReceiptType | None = None
receipt_status: ReceiptStatus | None = None
```
- [ ] **Step 2:** `OrderUpdate`에도 동일 2줄 추가(`evidence_memo` 아래).
- [ ] **Step 3 (failing test):** `test_orders_receipt.py` — (a) 주문 생성/수정 시 `receipt_type='none'`이면 저장 결과 `receipt_status='not_applicable'`로 정규화, (b) 관리자 DTO에 두 필드 노출, (c) `PartnerJobRead`/`CustomerOrderLineRead`에 미노출. 기존 orders 테스트 fixture/헬퍼 재사용.
- [ ] **Step 4:** 테스트 실행 → FAIL.
- [ ] **Step 5:** `services/orders.py`에서 라인 생성/수정 경로에 정규화 헬퍼 적용:
```python
def _normalize_receipt(receipt_type, receipt_status):
    if receipt_type == ReceiptType.NONE:
        return receipt_type, ReceiptStatus.NOT_APPLICABLE
    return receipt_type, receipt_status
```
생성(create_group/add_line)·수정(update) 시 payload에서 두 값을 정규화해 모델에 반영. 정확 위치는 기존 결제필드(payment_status 등) 매핑부를 읽고 동일 패턴으로.
- [ ] **Step 6:** `to_admin_order_dto`가 ORM→DTO를 `model_validate`/from_attributes로 처리하면 자동 통과 — 확인. 명시 매핑이면 두 필드 추가.
- [ ] **Step 7:** 테스트 실행 → PASS. `python -m pytest tests/test_orders_receipt.py -v && ruff check .`.
- [ ] **Step 8:** Commit `feat(order): 증빙자료 DTO+정규화(발급X→해당없음), 협력사/고객 비노출`.

### Task 1.3: 프론트 도메인 상수 + 상세 1차/2차 UI

**Files:**
- Create: `frontend/src/domain/receiptType.ts`
- Modify: `frontend/src/api/admin.ts` (타입에 receipt 필드)
- Modify: `frontend/src/features/admin/orders/OrderDetailPage.tsx` (state + 결제/정산 카드 UI + 저장)

- [ ] **Step 1:** `receiptType.ts` 작성(paymentStatus.ts 스타일):
```js
export const RECEIPT_TYPES = [
  { value: 'cash_receipt', label: '현금영수증' },
  { value: 'tax_invoice', label: '세금계산서' },
  { value: 'none', label: '발급X' },
];

export const RECEIPT_STATUSES = [
  { value: 'issued', label: '발급완료' },
  { value: 'pending', label: '미발급' },
  { value: 'not_applicable', label: '해당없음' },
];

export function receiptTypeLabel(value) {
  return RECEIPT_TYPES.find((item) => item.value === value)?.label || '';
}
export function receiptStatusLabel(value) {
  return RECEIPT_STATUSES.find((item) => item.value === value)?.label || '';
}
// 리스트 배지용: { text, tone } (tone: 'ok' | 'warn' | 'muted')
export function receiptBadge(type, status) {
  if (!type) return { text: '-', tone: 'muted' };
  if (type === 'none') return { text: '발급X', tone: 'muted' };
  const t = receiptTypeLabel(type);
  const s = receiptStatusLabel(status);
  const tone = status === 'issued' ? 'ok' : status === 'pending' ? 'warn' : 'muted';
  return { text: s ? `${t}·${s}` : t, tone };
}
```
- [ ] **Step 2:** `admin.ts`의 `AdminOrderRead`, `AdminOrderLineInput`, `UpdateOrderInput`에 `receipt_type?: string | null; receipt_status?: string | null;` 추가.
- [ ] **Step 3:** `OrderDetailPage.tsx` state 추가(selectedReceiptType/Status, 초기값 order에서). 결제/정산 카드(585~627) '고객 결제 상태' 드롭다운 아래에 1차/2차 select 추가:
  - 1차 select: RECEIPT_TYPES. onChange 시 값이 'none'이면 selectedReceiptStatus를 'not_applicable'로 강제.
  - 2차 select: RECEIPT_STATUSES. `disabled={selectedReceiptType === 'none'}`.
- [ ] **Step 4:** `handlePaymentUpdate`(171~188) 페이로드에 `receipt_type`, `receipt_status` 포함. `isPaymentDirty`(316~318)에 두 state 비교 추가.
- [ ] **Step 5:** `npm run typecheck && npm run lint`.
- [ ] **Step 6:** Commit `feat(order-detail): 증빙자료 1차/2차 선택 UI(발급X시 2차 비활성)`.

### Task 1.4: 리스트 증빙자료 배지 컬럼

**Files:**
- Modify: `frontend/src/features/admin/orders/OrdersPage.tsx` (컬럼 정의 200~212, 헤더 898~907, 바디 셀, toOrderRow 1352~1384)

- [ ] **Step 1:** `ORDER_TABLE_COLUMNS`에 `{ key: 'evidence', label: '증빙자료', width: ... }` 추가(payment 인근). 너비 저장/복원 로직이 key 기반이면 자동 반영.
- [ ] **Step 2:** `toOrderRow`에서 `receiptType: order.receipt_type, receiptStatus: order.receipt_status` 포함.
- [ ] **Step 3:** 테이블 헤더에 '증빙자료' 헤더 셀 추가(payment 헤더 옆).
- [ ] **Step 4:** 바디 행에 배지 셀 추가. `receiptBadge(row.receiptType, row.receiptStatus)`로 `{text,tone}` 받아 기존 배지/뱃지 스타일(StatusBadge나 pill 패턴)로 렌더. tone→색상 매핑.
- [ ] **Step 5:** `npm run typecheck && npm run lint`.
- [ ] **Step 6:** 수동 확인 — 리스트에 증빙자료 배지 표시, 상세에서 변경 시 리스트 반영.
- [ ] **Step 7:** Commit `feat(orders): 리스트 증빙자료 배지 컬럼`.

### ✋ 체크포인트 W1 — 사용자 확인 후 W2 진행

---

## 웨이브 2 — 일괄변경 + 주문 복제

> 실행 시 먼저 읽기: `OrdersPage.tsx`(일괄변경 패널 1151~1219, 핸들러 430~448, 선택바 834~836), `OrderFormPage.tsx`(toForm/createEmpty/payload 635~728), `App.tsx`(주문 라우팅), `OrderDetailPage.tsx`(상단 버튼영역).

### Task 2.1: 결제상태 일괄변경

**Files:** Modify `frontend/src/features/admin/orders/OrdersPage.tsx`

- [ ] **Step 1:** `bulkAction` 유니온/상태에 `'payment'` 추가.
- [ ] **Step 2:** `handleBulkPaymentStatusChange(value)` 추가 — 기존 `handleBulkStatusChange`(430) 패턴 복제, 선택 주문 루프 `updateAdminOrder(id, { payment_status: value })`, 성공 후 목록 reload + 선택 해제.
- [ ] **Step 3:** `BulkActionPanel`(1151~1219)에 `payment` 케이스 — `PAYMENT_STATUSES` select.
- [ ] **Step 4:** 선택 바(834)에 "결제상태 변경" 버튼 추가(기존 상태/협력사/메시지 버튼 옆).
- [ ] **Step 5:** `npm run typecheck && npm run lint`. 수동 확인.
- [ ] **Step 6:** Commit `feat(orders): 결제상태 일괄변경`.

### Task 2.2: 일정(방문일) 일괄변경

**Files:** Modify `frontend/src/features/admin/orders/OrdersPage.tsx`; 확인 `backend/app/services/orders.py`(update의 일정 타임라인)

- [ ] **Step 1:** `OrderService.update()`에서 `scheduled_date` 변경 시 타임라인 기록 경로 확인. 미기록이면 status_changed/별도 이벤트로 기록 보강(STATUS_CHANGED 또는 메모성 기록 — 기존 일정 변경 처리 방식을 따른다).
- [ ] **Step 2:** `bulkAction`에 `'schedule'` 추가, `handleBulkScheduleChange(date)` — 루프 `updateAdminOrder(id, { scheduled_date: date })`.
- [ ] **Step 3:** `BulkActionPanel`에 `schedule` 케이스 — DatePicker.
- [ ] **Step 4:** 선택 바에 "일정 변경" 버튼.
- [ ] **Step 5:** `npm run typecheck && npm run lint`. 수동 확인.
- [ ] **Step 6:** Commit `feat(orders): 일정 일괄변경`.

### Task 2.3: 주문 복제 (고객정보만 복사)

**Files:** Modify `OrderDetailPage.tsx`(복제 버튼), `App.tsx`(복제 라우팅), `OrderFormPage.tsx`(prefill 모드)

- [ ] **Step 1:** `OrderFormPage.tsx`에 복제 진입 지원. 방식: `duplicateFromOrderId` prop. 존재 시 `getAdminOrder`로 로드 → `createEmptyGroupForm()`에 고객정보(customer_name/phone/address/address_detail, source_channel)만 채우고 라인은 빈 라인 1개. 헤더 "주문 복제", 안내문 "고객정보만 복사됨 — 서비스/일정/협력사 입력 필요".
- [ ] **Step 2:** `App.tsx`에 복제 라우트/상태(`duplicateOrderId`) 추가. 주문 상세→복제 시 OrderFormPage를 create+duplicateFromOrderId로 진입.
- [ ] **Step 3:** `OrderDetailPage.tsx` 상단 버튼영역에 "주문 복제" 버튼 → `onDuplicate(orderId)`.
- [ ] **Step 4:** 저장은 기존 create 경로 그대로(새 customer_token/CREATED 타임라인 자동). soft-delete 주문은 상세 접근 불가라 진입 차단 자동.
- [ ] **Step 5:** `npm run typecheck && npm run lint`. 수동 확인 — 복제 후 고객정보 채워지고 라인 공란, 저장 시 새 주문 생성.
- [ ] **Step 6:** Commit `feat(orders): 주문 복제(고객정보만 복사)`.

### ✋ 체크포인트 W2 — 사용자 확인 후 W3 진행

---

## 웨이브 3 — 협력사관리

> 실행 시 먼저 읽기: `backend/app/services/messages.py`(_resolve_recipient 1107~1121), `backend/app/services/partners.py`(create/update 120~177, to_admin_dto), `frontend/.../PartnersPage.tsx`(폼 664~714, defaultPartnerForm/toPartnerForm/toPartnerPayload 1193~1208), `OrderDetailPage.tsx:436`(협력사 정산 라벨), `backend/app/services/reports.py`(settlements 176~205).

### Task 3.1: 협력사 담당자 연락처(manager_phone)

**Files:** `models/partner.py`, `alembic/versions/0014_partner_manager_phone.py`, `schemas/partner.py`, `services/partners.py`, `services/messages.py`, `PartnersPage.tsx`; Test `tests/`

- [ ] **Step 1:** `models/partner.py`에 `manager_phone: Mapped[str | None] = mapped_column(String(30))`(manager_name 인근).
- [ ] **Step 2:** 마이그레이션 `0014_partner_manager_phone`(down_revision `0013_receipt_fields`): `op.add_column("partners", sa.Column("manager_phone", sa.String(length=30), nullable=True))` / downgrade drop. `python -m alembic upgrade head`.
- [ ] **Step 3:** `schemas/partner.py` `PartnerBase`에 `manager_phone: str | None = None`(Create/Update/Read 상속 확인). Read DTO에도 노출.
- [ ] **Step 4 (failing test):** `tests/test_partners_manager_phone.py` — (a) 생성/수정 시 manager_phone 정규화 저장, (b) 정산성 메시지 수신처가 manager_phone(있을 때)/phone(없을 때 폴백)인지.
- [ ] **Step 5:** `services/partners.py` create/update에 manager_phone normalize. `to_admin_dto`에 포함.
- [ ] **Step 6:** `services/messages.py` `_resolve_recipient` — 정산/고객정보 안내(PARTNER_CUSTOMER_INFO 등) 수신번호를 `partner.manager_phone or partner.phone`로. PARTNER_ASSIGNMENT는 기존 phone 유지.
- [ ] **Step 7:** 테스트 → PASS. `python -m pytest tests/test_partners_manager_phone.py -v && ruff check .`.
- [ ] **Step 8:** 프론트 `PartnersPage.tsx` 등록/수정 폼에 '담당자 연락처' 필드 + form 직렬화. `npm run typecheck && npm run lint`.
- [ ] **Step 9:** Commit `feat(partners): 담당자 연락처(manager_phone)+정산안내 수신처`.

### Task 3.2: 미정산/미지급 표시 버그 수정

**Files:** `frontend/src/domain/paymentStatus.ts`, `OrderDetailPage.tsx`, (조사 결과 따라) `backend/app/services/reports.py`/`partner_settlements.py`; Test `tests/`

- [ ] **Step 1 (재현):** 실데이터(8002/Postgres 5434)로 "고객정보에서 협력사 정산 미지급" / "협력사관리 미정산 내역"이 비는 정확한 지점 특정. `mcp__postgres__query`로 `partner_payment_status` 분포 확인(NULL/unpaid/ready/paid). 증상·원인을 기록.
- [ ] **Step 2:** 원인이 "NULL을 '-'로 표시"이면: `paymentStatus.ts`에서 협력사 정산 표시용 라벨이 NULL→'미지급'이 되도록 처리(예: OrderDetail 표시부에서 `partner_payment_status ?? 'unpaid'` 라벨링, 또는 전용 헬퍼 `partnerSettlementLabel`). 단, 의미상 NULL=미정산임을 명확히.
- [ ] **Step 3:** 필터 일관성 — `partner_settlements._list_orders`(NULL 포함)와 `reports.settlements`의 NULL/상태 포함 정책을 동일하게. 불일치 발견 시 정렬하고 테스트로 고정.
- [ ] **Step 4 (test):** NULL/unpaid/ready가 미정산 목록·집계에 일관 포함되는지 통합 테스트. OrderDetail 표시 라벨 단위 테스트(프론트는 도메인 함수 단위로).
- [ ] **Step 5:** 검증 명령 + 실데이터로 미정산 정상 표시 확인.
- [ ] **Step 6:** Commit `fix(settlement): 협력사 미정산(NULL 포함) 표시/집계 일관화`.

### ✋ 체크포인트 W3 — 최종 확인 + 전체 검증/리뷰

---

## 최종 단계
- [ ] 전체 검증: 백엔드 `python -m pytest && ruff check .`, 프론트 `npm run typecheck && npm run lint && npm run build`.
- [ ] (선택) E2E 핵심 플로우 `npm run e2e` 영향 없음 확인.
- [ ] `.master/next_session_plan.md`에 마일스톤 갱신(사용자 승인 시).
- [ ] PR 생성(사용자 요청 시).

## 스펙 대비 커버리지 자가점검
- 증빙자료(#1·#9): Task 1.1~1.4 ✅
- 줄바꿈(#10): 0.1 ✅ / 상세주소(#4): 0.2 ✅ / 정산 전체선택(#6): 0.3 ✅
- 결제상태+일정 일괄변경(#3): 2.1·2.2 ✅ / 주문 복제(#8): 2.3 ✅
- 담당자 연락처(#5): 3.1 ✅ / 미정산 버그(#7): 3.2 ✅
- 정기청소(#2): 범위 밖(별도) ✅
