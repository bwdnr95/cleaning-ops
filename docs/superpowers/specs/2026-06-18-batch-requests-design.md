# 도급사 누적 요청 9건 — 설계 문서

- 작성일: 2026-06-18
- 범위: 도급사가 누적 전달한 요청 10건 중 **9건**. (정기청소 관리 메뉴는 별도 프로젝트로 분리 — 본 문서 범위 밖, 마지막 §11 참고)
- 진행 방식: **단계별 웨이브 + 중간 확인**. 각 웨이브가 끝날 때마다 화면으로 검증 후 다음 진행.
- 전제 규칙: `AGENTS.md`(역할별 DTO 화이트리스트, 협력사/고객 민감필드 차단, 모든 운영 변경의 타임라인 기록, soft-delete) + `.claude/rules/*` 준수.

---

## 0. 요청 → 작업 매핑 요약

| # | 요청 | 그룹 | 웨이브 | 규모 |
|---|------|------|--------|------|
| 1·9 | 증빙자료(현금영수증/세금계산서) 상태 — 리스트 컬럼 + 상세 1차/2차 | 증빙 | **W1** | 중 |
| 10 | 상품/일정 상세 단락 줄바꿈 보존 | 텍스트 | W0 | 소 |
| 4 | 주문 주소 검색에 상세주소 포함 | 검색 | W0 | 소 |
| 6 | 협력사 정산 리스트 전체선택 체크박스 | 협력사 | W0 | 소 |
| 3 | 결제상태 일괄변경 + 일정 일괄변경 | 리스트 | **W2** | 중 |
| 8 | 주문 복제(고객정보만 복사) | 복제 | **W2** | 중 |
| 5 | 협력사 담당자 연락처 추가 | 협력사 | **W3** | 중 |
| 7 | 협력사 미정산/미지급 미표시 버그 | 협력사 | **W3** | 중(버그) |
| 2 | 정기청소 관리 메뉴 | — | 별건 | 대 |

---

## 1. 웨이브 구성

- **W0 (가벼운 개선 3종)**: 텍스트 줄바꿈 · 상세주소 검색 · 협력사 정산 전체선택. 위험 낮음, 한 번에.
- **W1 (증빙자료 ★★★★★)**: 데이터 모델 + 마이그레이션 + 상세 1차/2차 + 리스트 배지. 최우선.
- **W2 (리스트 일괄변경 + 주문 복제)**: 결제상태/일정 일괄변경, 주문 복제.
- **W3 (협력사관리)**: 담당자 연락처 + 미정산 버그 수정(실데이터 재현 선행).

각 웨이브 종료 시 중간 확인.

---

## 2. [W1] 증빙자료 — 현금영수증/세금계산서 (요청 #1·#9, 최우선)

### 2.1 목표
- 리스트에서 고객별 증빙(현금영수증/세금계산서) 발급 유무를 **한눈에** 확인.
- 상세 '결제/정산'의 '결제 상태' **밑에** 2단계 선택:
  - 1차(유형): 현금영수증 / 세금계산서 / 발급X
  - 2차(상태): 발급완료 / 미발급 / 해당없음
- **발급X 선택 시 2차는 '해당없음'으로 자동 고정·비활성.**

### 2.2 데이터 모델
- `backend/app/domain/constants.py` (또는 `domain/receipt.py`)에 enum 2종 신설:
  - `ReceiptType`: `CASH_RECEIPT="cash_receipt"`, `TAX_INVOICE="tax_invoice"`, `NONE="none"`
  - `ReceiptStatus`: `ISSUED="issued"`, `PENDING="pending"`, `NOT_APPLICABLE="not_applicable"`
- `backend/app/models/order.py`(Order=라인 단위, payment_status와 동일 레벨): 컬럼 2개 추가
  - `receipt_type: Mapped[str | None] = mapped_column(String(20))`
  - `receipt_status: Mapped[str | None] = mapped_column(String(30))`
- 마이그레이션 **`0013_receipt_fields`** (`down_revision="0012_user_phone_unique"`), 두 컬럼 nullable 추가. 기존 행은 NULL.
- `backend/app/domain/payment_status.py`의 `PAYMENT_TRACKED_FIELDS`에 `receipt_type`, `receipt_status` 추가 → 기존 `payment_updated` 타임라인 흐름이 증빙 변경도 자동 추적.

### 2.3 백엔드
- `backend/app/schemas/order.py`: `OrderLineBase`에 `receipt_type: ReceiptType | None = None`, `receipt_status: ReceiptStatus | None = None` 추가(→ Create/Update/Read 상속).
- `services/orders.py`:
  - `to_admin_order_dto`에 두 필드 포함.
  - **`to_partner_job_dto` / `to_customer_order_dto`에는 미포함** (증빙은 내부 정산 정보 — `evidence_memo`가 이미 양쪽 금지필드인 것과 동일 정책).
  - 정규화 규칙: 저장 시 `receipt_type == NONE`이면 `receipt_status = NOT_APPLICABLE`로 강제(서버 단). 빈 입력 허용(둘 다 NULL).
- 결제상태(PaymentStatus 6종) 자체는 **변경 없음**.

### 2.4 프론트엔드
- `frontend/src/domain/receiptType.ts` 신설: 옵션 배열 + 라벨 + 배지 색상.
- 상세 `OrderDetailPage.tsx` (결제/정산 카드 `585~627`):
  - state `selectedReceiptType`, `selectedReceiptStatus`.
  - '고객 결제 상태' 드롭다운 아래에 1차/2차 드롭다운 세로 배치.
  - **1차=발급X → 2차 disabled + '해당없음' 고정.**
  - `handlePaymentUpdate`에 두 필드 포함, `isPaymentDirty` 계산에 반영.
- 리스트 `OrdersPage.tsx`:
  - `ORDER_TABLE_COLUMNS`에 `'evidence'` 컬럼 추가(헤더 '증빙자료').
  - `toOrderRow`에서 `receipt_type/receipt_status` 추출.
  - 셀: **배지** 표시(예: `세금계산서·발급완료`). 미발급은 주의 색, 미설정은 흐린 '-'.
- `frontend/src/api/admin.ts`: `AdminOrderRead`, `AdminOrderLineInput`, `UpdateOrderInput`에 두 필드 추가.

### 2.5 기존 `evidence_memo` 처리
- **보존.** 구조화 필드와 별개로 자유 텍스트 증빙메모는 그대로 둠(특이사항 기록용). 컬럼 제거 없음(데이터 손실 방지). → 스펙 리뷰에서 "메모 제거하고 일원화" 원하면 변경.

### 2.6 테스트
- enum 정규화(NONE→NOT_APPLICABLE) 단위 테스트.
- 증빙 변경 시 `payment_updated` 타임라인 기록 확인(통합).
- 협력사/고객 DTO에 `receipt_type/status` 미노출 확인(기존 DTO 비노출 테스트 패턴 확장).

---

## 3. [W0] 상품/일정 상세 — 단락 줄바꿈 보존 (요청 #10)

### 3.1 원인
- 입력은 textarea로 개행(`\n`)이 저장되지만, 읽기 표시부에 `white-space: pre-wrap`이 없어 개행이 뭉개짐. (메시지 미리보기 모달만 `<pre>`로 올바르게 표시 중.)

### 3.2 작업
- `frontend/src/styles/global.css`에 재사용 클래스 추가:
  ```css
  .multiline-text { white-space: pre-wrap; word-break: break-word; }
  ```
- 적용 대상(읽기 표시부):
  - 관리자 `OrderDetailPage.tsx` `KVItem`(multiline 값) — service_detail, special_request, payment_memo, evidence_memo, notes.
  - 협력사 `PartnerJobDetail.tsx` — service_detail, special_request.
  - 고객 `CustomerReservation.tsx` — `mutedLineStyle` 사용부.
- 방식: CSS `pre-wrap` (마크업 변경 없는 최소 침습). 모바일(360px)에서 `word-break: break-word` 동반.

---

## 4. [W0] 주문 주소 검색에 상세주소 포함 (요청 #4)

### 4.1 원인
- `backend/app/services/order_page.py` `_matches_query`(`306~331`)의 검색 후보에 `customer_address`만 있고 `customer_address_detail` 누락.

### 4.2 작업
- 검색 후보 리스트에 `customer_address_detail`(OrderGroup) 추가. 주소+상세를 합친 문자열로도 매칭되도록 후보에 둘 다 포함.
- 정렬/필터 로직은 변경 없음.

### 4.3 테스트
- 상세주소 토큰으로 검색 시 해당 주문이 매칭되는지 단위 테스트.

---

## 5. [W0] 협력사 정산 리스트 — 전체선택 체크박스 (요청 #6)

### 5.1 현황
- 행 체크박스(`PartnersPage.tsx:818`)와 일괄 정산/되돌리기 액션(`handleSettle:420`, `handleRevertSettlement:439`)은 이미 동작. **헤더 전체선택만 없음.**

### 5.2 작업
- 정산 그리드 `GridHead` 첫 칸(현재 빈 문자열, `812`)에 전체선택 체크박스.
- `toggleAllSettlements()`: 현재 표시된 `settlements.items` 전체의 `order_id`를 일괄 선택/해제.
- 헤더 체크박스 `checked` = 표시 항목 전부 선택됨 여부(부분선택 표현).
- **필터(날짜/정산상태) 변경 시 선택 초기화.**
- 일괄 액션 API는 이미 배열 처리 → 백엔드 변경 없음.

---

## 6. [W2] 결제상태 일괄변경 + 일정 일괄변경 (요청 #3)

### 6.1 현황
- 현재 일괄변경은 상태/협력사/메시지 3종(`OrdersPage.tsx:834`). `handleBulkStatusChange`(`430`)는 선택 주문을 **for 루프로 개별 PATCH**(`updateAdminOrder`) 호출.

### 6.2 작업 (기존 루프 패턴 그대로 따름)
- **결제상태 일괄변경**(★ 명시 요청):
  - `bulkAction`에 `'payment'` 추가, `BulkActionPanel`에 결제상태 select(`PAYMENT_STATUSES`).
  - `handleBulkPaymentStatusChange` → 선택 주문 루프 `updateAdminOrder(id, { payment_status })`.
  - 선택 바에 버튼 추가.
- **일정 일괄변경**("혹시 가능?" → 함께 적용):
  - `bulkAction`에 `'schedule'` 추가, 날짜 피커 UI.
  - `handleBulkScheduleChange` → 루프 `updateAdminOrder(id, { scheduled_date })`.
  - 일정 변경은 기존 `OrderService.update()`가 일정 변경 감지 시 타임라인 기록하는 경로를 그대로 탐(확인 필요 — 미기록이면 보강).

### 6.3 참고
- 기존에 `POST /bulk-delete`(벌크 엔드포인트) 선례는 있으나, 상태 일괄변경이 루프 방식이라 **일관성 위해 루프 유지**. 건수 많아 성능 이슈 확인되면 후속으로 `POST /bulk-update` 신설 검토(범위 밖).

### 6.4 테스트
- 결제상태/일정 일괄변경 후 각 주문 타임라인 기록 확인.

---

## 7. [W2] 주문 복제 — 고객정보만 복사 (요청 #8)

### 7.1 결정
- **새 주문으로 복제, 고객정보(이름/연락처/주소/상세주소)만 복사.** 서비스/일정/협력사/금액/결제/증빙은 비움. (확정된 방향)

### 7.2 작업 (프론트 중심, 백엔드 신규 엔드포인트 불필요)
- 진입점: `OrderDetailPage.tsx` 상단 버튼영역에 **'주문 복제'** 버튼 → `onDuplicate(orderId)` 콜백.
- `App.tsx`: 복제 시 `OrderFormPage`를 `mode='create'` + `prefill`(고객정보만) 로 진입.
- `OrderFormPage.tsx`:
  - 신규: `prefillCustomer` prop 또는 `duplicateFromOrderId`. 후자면 `getAdminOrder`로 로드 후 그룹 고객필드만 채우고 라인 필드 초기화.
  - 헤더 '주문 복제', 안내문 "고객정보만 복사됨 — 서비스/일정/협력사를 입력하세요".
  - 저장은 기존 create 경로(`POST /admin/orders` 또는 `/groups`) → 새 `customer_token` 자동 생성, `CREATED` 타임라인.
- soft-delete된 주문은 복제 진입 차단(`deleted_at IS NULL`).

### 7.3 테스트
- 복제 후 저장 시 새 그룹/토큰 생성 + 고객정보 일치 + 라인 필드 공란 확인(E2E 또는 폼 단위).

---

## 8. [W3] 협력사 담당자 연락처 추가 (요청 #5)

### 8.1 목표
- 협력사 정보에 '대표 연락처'(`phone`)만 있음. **'담당자 연락처'(`manager_phone`) 추가** → 정산 안내가 담당자에게 가도록.

### 8.2 작업
- `backend/app/models/partner.py`: `manager_phone: Mapped[str | None] = mapped_column(String(30))`.
- 마이그레이션 **`0014_partner_manager_phone`** (`down_revision="0013_receipt_fields"`).
- `schemas/partner.py`: `PartnerBase`에 `manager_phone: str | None = None`(Create/Update/Read 상속).
- `services/partners.py`: create/update 시 `manager_phone` 정규화(전화번호 normalize), `to_admin_dto` 포함.
- **메시지 수신처 정책**(`services/messages.py` `_resolve_recipient` `1107~1121`):
  - 정산/고객정보 안내(`PARTNER_CUSTOMER_INFO` 등 정산 성격) → `manager_phone` 우선, 없으면 `phone` 폴백.
  - 배정 안내(`PARTNER_ASSIGNMENT`) → 기존 `phone` 유지.
- 프론트 `PartnersPage.tsx`: 등록/수정 폼에 '담당자 연락처' 필드(`defaultPartnerForm`/`toPartnerForm`/`toPartnerPayload` 반영). 목록/상세 표시.

### 8.3 결정 사항(기본값)
- `manager_phone`은 **선택**(필수 아님). 비면 대표 연락처로 폴백.
- 협력사 로그인용 `users.phone`과는 독립 필드.

### 8.4 테스트
- `manager_phone` 정규화 + 폴백 수신처 단위 테스트.

---

## 9. [W3] 협력사 미정산/미지급 미표시 버그 (요청 #7)

### 9.1 증상(가설)
- 주문 상세에서 `partner_payment_status = NULL`을 `partnerPaymentStatusLabel`이 **'-'로 표시**(`OrderDetailPage.tsx:436`). AGENTS.md 정의상 NULL = 정산 대기(미정산)인데 화면엔 '미정산'으로 안 보임.
- 정산 탭 조회(`partner_settlements._list_orders`)는 NULL을 포함하나, Backlog 리포트(`reports.settlements`)의 표시/필터 일관성 점검 필요.

### 9.2 작업 (재현 선행)
- **먼저 실데이터(포트 8002 / Postgres 5434)로 재현** — "고객정보에서 협력사 정산 미지급" / "협력사관리 미정산 내역"이 정확히 어느 화면·어느 데이터에서 비는지 특정.
- 확인된 원인에 따라:
  - 라벨: `partner_payment_status` NULL → **'미정산'**(또는 '미지급')으로 표시(현재 '-' 대신). 프론트 `paymentStatus.ts` 라벨 + 표시부 보강.
  - 필터 일관성: `_list_orders`와 `reports.settlements`의 NULL 포함 정책을 동일하게 정렬. 필요 시 `PARTNER_SETTLEMENT_PENDING_STATUSES` 주변 로직 명시화.
  - (선택) Backlog 리포트에 `partner_payment_status` 컬럼 노출.

### 9.3 테스트
- NULL/unpaid/ready가 미정산 목록·집계에 일관되게 잡히는지 통합 테스트.

---

## 10. 공통 고려사항

- **마이그레이션 순서**: `0013_receipt_fields` → `0014_partner_manager_phone`. 코드 수정 전 `alembic upgrade head` 먼저(.claude/rules/backend.md).
- **타임라인**: 증빙 변경=`payment_updated` 재사용. 복제=`CREATED`. 일괄변경/정산=기존 경로 유지.
- **DTO 화이트리스트**: 신규 필드(receipt_*, manager_phone) 모두 명시 추가. 협력사/고객 노출 금지 준수.
- **검증 명령**: 백엔드 `python -m pytest` + `ruff check .` + `python -m compileall`, 프론트 `npm run typecheck` + `npm run lint` + `npm run build`.

---

## 11. 범위 밖 — 정기청소 관리 메뉴 (요청 #2)

별도 프로젝트로 분리. 본 9건 완료 후 독립 설계 사이클(spec→plan→구현)로 진행. 개략 규모(참고용, 본 문서에서 구현하지 않음):
- 신규 모델: 정기계약(RecurringContract) / 자동생성이력 / 월 정산배치.
- 자동 일정생성(스케줄러) + 월 정산배치 + 신규 네비 탭 + 페이지군.
- 미해결 핵심 질문: 주기 종류, 자동 vs 수동 정산, 휴무일 처리, 협력사 자동배정 여부, 결제 게이트웨이 연동 등.

---

## 12. 미해결/스펙 리뷰 확인 포인트
- (W1) `evidence_memo`를 보존할지, 구조화 필드로 일원화(제거)할지 — 현재 **보존**으로 설계.
- (W2) 일정 일괄변경 시 `OrderService.update()`의 일정 변경 타임라인 기록 경로 존재 확인(미기록이면 보강).
- (W3) 미정산 버그의 정확한 재현 지점 — 구현 착수 시 실데이터로 특정.
