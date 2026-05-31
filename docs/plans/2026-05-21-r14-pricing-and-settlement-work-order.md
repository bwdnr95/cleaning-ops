# R14 작업 지시서 — 가격 체계 분리 · 정산 운영 강화 · 견적 발송

> 출처 요청서: `.claude/260521_2 클린잡 운영 시스템 수정 사항 요청서.pdf`
> 작성일: 2026-05-26 (CTO/기술 자문)
> 수신: Codex (구현)
> 후속 지시서: `2026-05-21-r14-codex-review-checklist.md` (구현 후 자가 리뷰)
> 마일스톤 코드: **R14**

---

## 0. 작업 전 필독

다음 문서를 **반드시** 먼저 읽고 그 안의 규칙을 준수한다. 본 지시서는 이들 규칙을 전제로 작성된다.

1. `AGENTS.md` — 보안/DTO/사진/메시지/테스트/리뷰 규칙. 특히 **§Delete Policy, §DTO Whitelist, §Timeline Mutation Rule**.
2. `CLAUDE.md` — 3대 아키텍처 룰 (역할 분리, 화이트리스트 DTO, timeline 기록).
3. `.claude/rules/backend.md` — Repository 패턴, SQLAlchemy 2.0 스타일, KST 시간 등.
4. `.claude/rules/frontend.md` — 데스크탑/모바일 768px 분기, 로딩/에러/빈 상태 3종, raw fetch 금지.
5. `.master/first_demo_code_status_2026-05-06.md` — 파일별 구현 맵.
6. `docs/plans/2026-05-25-r13-operational-reporting.md` — 직전 마일스톤 컨텍스트.

### 작업 언어 / 컨벤션
- 코드 주석 / 커밋 메시지 / PR 본문: **한국어 우선** (코드 식별자는 영문).
- 커밋 메시지 prefix: `feat(...)`, `fix(...)`, `refactor(...)`, `test(...)`, `docs(...)` — 기존 히스토리 참조.
- 마이그레이션 번호: **0010부터 순차** (현재 최신 `0009_address_detail_and_soft_delete.py`).
- DB는 dev 기본 SQLite. SQLAlchemy 2.0 `select()` 스타일만 사용.
- 모든 가격 필드는 `Numeric(12, 2)`로 통일하고 **부가세 포함 전제**. (별도 표기 시 UI 라벨로 안내)
- 모든 운영 mutation은 `services/timeline.py`를 통해 timeline 이벤트를 남긴다.

### 금지 사항
- `npm run dev` / `uvicorn` 단독 기동 금지. 검증은 `npm run typecheck`, `python -m pytest`, `npm run e2e`(playwright가 8003/5176로 자체 기동)로 한다.
- 디자인 prototype(`/.master/design_handoff_prototype/*`) 복붙 금지.
- AGENTS.md에 명시된 partner/customer DTO 금지 필드를 새로 노출하지 말 것.
- 기존 마이그레이션 수정 금지 → 항상 새 revision 추가.

---

## 1. 큰 그림 (Why)

이번 마일스톤의 핵심은 **두 가지 가격 체계 (소비자가 / 도급가)** 를 데이터 모델·운영 화면·정산 흐름 전반에 정착시키는 것이다. 동시에 다음과 같은 운영 불편을 해결한다.

- 주문 목록이 단순 정렬이라 오늘/미납 작업을 즉시 식별하지 못한다.
- 신규 주문 등록 시 수동 계산이 많아 운영 부담이 크다.
- 협력사 정산을 시스템에서 직접 처리하지 못해 외부 시트에 의존한다.
- 견적서 발송이 자동화되어 있지 않다.

요청서의 모든 항목은 **운영 흐름**을 한 단계 끊김 없이 만들기 위한 것이며, 이 흐름을 깨면 안 된다.

---

## 2. 현황 진단 요약 (Implementation State Map)

| # | 요청 항목 | 현재 구현 상태 | 핵심 파일 |
|---|---|---|---|
| 1 | 주문 목록 '주문번호' 칼럼 제거 | ❌ 컬럼 존재 | `frontend/src/features/admin/orders/OrdersPage.tsx:683` |
| 2 | 상품/품목 컬럼 분리 표시 | ⚠ DTO에 `service_name`+`size_or_quantity` 존재, UI는 한 셀에 통합 표기 (`OrdersPage.tsx:1036`) | `OrdersPage.tsx` |
| 3 | '금액' → '소비자가' 명칭 변경 | ❌ | `OrdersPage.tsx` |
| 4 | 소비자가 옆 '도급가' 컬럼 추가 | ❌ | `OrdersPage.tsx`, DTO |
| 5 | 부가세 포함 가격 표시 일관화 | ⚠ Order.vat_type만 있고 UI 정책 없음 | 전반 |
| 6 | 목록 정렬: 오늘부터 / 미납 우선 / 차순 토글 | ⚠ `scheduled_date asc` 단순 정렬 (`backend/app/repositories/orders.py:26`) | 백엔드 정렬 + UI 토글 |
| 7 | 목록에 결제 상태 컬럼 + 미납 강조 | ⚠ PaidPill 컴포넌트 (`OrdersPage.tsx:59-77`) 존재, 정렬·필터 미연동 | UI + 백엔드 |
| 8 | 상품관리 '도급가' 컬럼 추가 | ❌ ServiceItem 모델에 partner_base_price 없음 | `backend/app/models/service_item.py`, `frontend/src/features/admin/products/ProductsPage.tsx` |
| 9 | 신규주문등록: 섹션 재구성 (상품/일정 ↔ 상품/결제) | ⚠ 1개 폼에 혼재 | `OrderFormPage.tsx` |
| 10 | '협력사 지급액' → '도급가' 명칭 변경 | ❌ 라벨/필드명 모두 협력사 지급액 | `OrderFormPage.tsx:422`, 백엔드 DTO 라벨 |
| 11 | 수량/규격 × 기준가 = 총 금액 자동계산 | ⚠ 기준가만 채우고 곱셈 없음 (`OrderFormPage.tsx:151-171`) | 프론트 로직 |
| 12 | 총 금액 → 계약금 30% 자동 | ❌ | 프론트 |
| 13 | 할인가 칸 + 총 금액 차감 | ❌ 필드 자체 없음 | 백엔드 모델 + 프론트 |
| 14 | 잔금 자동계산 | ✅ (`OrderFormPage.tsx:679`) — 식만 검토 |  |
| 15 | 'VAT' 포함/별도 선택지 | ⚠ 자유 텍스트 (`OrderFormPage.tsx:419`) | 프론트 enum화 |
| 16 | 완료 버튼 → 견적서 카카오 발송 | ❌ 메시지 타입 없음 | 백엔드 메시지 + 카카오 템플릿 + 프론트 버튼 |
| 17 | 가로 스크롤바 일관 적용 | ⚠ 페이지별 max-width 상이 | `global.css`, 각 페이지 |
| 18 | 화면 꽉 채우기 (잘림 방지) | ⚠ `OrderFormPage` 1260px, `ProductsPage` 1240px, `PartnersPage` 1280px 등 상이 | 레이아웃 정리 |
| 19 | 협력사 배정 작업 일자 캘린더 필터 | ❌ | `frontend/src/features/admin/partners/PartnersPage.tsx` |
| 20 | 협력사 클릭 시 미정산 도급가 합계 표시 | ❌ | 백엔드 집계 + 프론트 |
| 21 | 협력사 정산 버튼 (일괄 paid) | ❌ Order.partner_payment_status enum은 존재 | 백엔드 API + 프론트 |
| 22 | 배정 작업 목록에 소비자가/도급가 동시 표시 | ❌ | 프론트 |
| 23 | 배정 작업별 정산 완료 여부 표시 + 체크박스 | ❌ | 프론트 |
| 24 | 미입금 고객 정보를 협력사에 전송 버튼 | ❌ 메시지 타입 없음 | 백엔드 메시지 + 프론트 |
| 25 | 사이드바 '신규주문등록' 바로가기 | ❌ (주문관리 페이지 내부에만 있음) | `frontend/src/components/layout/AdminShell.tsx` |
| 26 | 결제선생 연동 가능 여부 | ❓ 외부 정보 부족 | 별도 조사 |

✅ 구현됨 / ⚠ 부분 구현 / ❌ 미구현 / ❓ 정보 부족

---

## 3. 작업 항목 (Tasks)

> 각 Task는 독립적으로 PR 가능하도록 분리되어 있다. 실제 작업 순서는 **T1 → T2 → T3 → T4 → T5 → T6** 순으로 진행하여 마이그레이션·DTO 변경의 후행 충돌을 막는다. T7(결제선생) 은 마지막에 조사 보고서로 처리한다.

---

### T1. 데이터 모델: 가격 체계 정비

#### T1-1. ServiceItem에 `partner_base_price` 추가
- 파일: `backend/app/models/service_item.py`
- 추가 컬럼: `partner_base_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")`
- 기존 `base_price` 옆에 배치. 의미: **상품 단위 기본 도급가 (부가세 포함)**.

#### T1-2. Order에 `discount_amount` 추가
- 파일: `backend/app/models/order.py`
- 추가 컬럼: `discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")`
- 의미: 신규 등록 시 입력하는 **할인가**. `total_amount` 은 할인 이후 최종 소비자가로 유지(이중 계산 방지). UI에서 사용자가 할인가를 입력하면 `total_amount`은 자동 감소한다 (T3-2 참고).

#### T1-3. Order.vat_type을 enum화
- 파일: `backend/app/domain/constants.py`에 `VatType` enum 신설.
  - 값: `included` (포함), `excluded` (별도). DB는 문자열 그대로.
- 기존 자유 텍스트 호환을 위해 마이그레이션 시 `vat_type IN ('포함','included') → 'included'`, `('별도','excluded') → 'excluded'`, 그 외 NULL/빈 값은 `included` 기본값으로 백필.
- `backend/app/schemas/admin/orders.py` (또는 해당 위치) 입력 스키마에서 enum 검증.

#### T1-4. Alembic 마이그레이션 추가
- 새 파일: `backend/alembic/versions/0010_pricing_partner_base_and_discount.py`
- 내용:
  - `service_items.partner_base_price` (`Numeric(12,2)`, NOT NULL, default 0)
  - `orders.discount_amount` (`Numeric(12,2)`, NOT NULL, default 0)
  - `orders.vat_type` 백필 (UPDATE 문) + 컬럼 제약 그대로 유지(varchar(32) 등).
- downgrade는 컬럼 drop. SQLite 환경에서 컬럼 drop은 batch mode 사용.
- `python -m alembic upgrade head --sql` 로 SQL 검증 후 실 적용.

#### T1-5. 시드/픽스처 보정
- `backend/app/db/seed.py` — 기존 ServiceItem 시드에 `partner_base_price`를 `base_price` 의 70% 정도로 채워 dev 데모 정상화.
- 기존 테스트 픽스처도 동일 보정.

---

### T2. 백엔드: 주문 목록 정렬 / DTO / 정산 API

#### T2-1. 주문 목록 정렬 규칙 변경
- 파일: `backend/app/repositories/orders.py` `list_orders()`
- 규칙(필수 순서):
  1. **미납 우선 그룹**: 작업일자가 오늘 이전이고 `payment_status` 가 미납(`unpaid`, `pending`, `balance_pending`, `deposit_paid` 중 잔금 미납 케이스)인 항목이 최상단.
  2. **오늘부터 미래순**: `scheduled_date >= today` 인 항목을 오름차순으로.
  3. **오늘 이전 완료/취소 항목**: 마지막에 배치하되 작업일 내림차순.
- 신규 쿼리 파라미터:
  - `sort=visit_asc | visit_desc` (기본 `visit_asc`)
  - `include_past_paid=true|false` (기본 `false` — 작업일 지난 결제완료 건은 기본 숨김. "전체" 보기/협력사별 보기에서만 true)
- 정렬 보조 키: `id` 로 안정 정렬 보장.
- `today` 는 KST(`datetime.now(KST).date()`) 사용 — `.claude/rules/backend.md` 준수.

#### T2-2. 관리자 주문 DTO 확장
- 파일: `backend/app/services/orders.py` `to_admin_order_dto`
- 추가 필드:
  - `consumer_price` = `total_amount` (의미 명확화용 별칭, 기존 `total_amount`도 그대로 유지 — 호환).
  - `partner_price` (각 주문 라인의 협력사 도급가). 데이터 소스: `Order.partner_payment_amount`.
  - `discount_amount`
  - `vat_type` (enum 값)
  - `service_name` / `size_or_quantity` (이미 존재한다면 명확히 노출 보장)
- **partner/customer DTO에는 절대 도급가/discount 노출 금지.** AGENTS.md DTO 화이트리스트 따른다.

#### T2-3. 협력사 정산 API
- 신규 라우트: `backend/app/api/routes/admin/partner_settlements.py`
- 엔드포인트:
  - `GET /api/admin/partners/{partner_id}/settlements?status=unpaid|paid|all&from=YYYY-MM-DD&to=YYYY-MM-DD`
    - 응답: 주문 라인별 `{order_id, scheduled_date, service_name, customer_name, address_short, consumer_price, partner_price, partner_payment_status, settled_at}` 배열 + 합계.
  - `POST /api/admin/partners/{partner_id}/settlements/settle`
    - body: `{ order_ids: UUID[], memo?: string }`
    - 동작: 각 Order의 `partner_payment_status` 를 `paid` 로 업데이트, `Order.partner_settled_at`(신규 컬럼) 기록, **각 주문 timeline에 `partner_settled` 이벤트 기록**.
  - `POST /api/admin/partners/{partner_id}/settlements/revert`
    - body: `{ order_ids: UUID[] }` — 잘못된 정산 되돌리기. 동일하게 timeline `partner_settlement_reverted`.
- 마이그레이션 추가: `orders.partner_settled_at TIMESTAMP NULL` 을 0010에 함께 포함.
- 권한: `require_admin` 의존성.
- 새 timeline 이벤트 타입은 `backend/app/domain/constants.py`에 추가.

#### T2-4. 협력사 상세 페이지용 집계
- `GET /api/admin/partners/{partner_id}` 응답에 다음 집계 필드 추가:
  - `unpaid_partner_amount_total` (미정산 도급가 합계, 소프트삭제 제외)
  - `unpaid_partner_order_count`
- `services/partners.py` 등 적절한 service 레이어에서 계산. raw SQL 금지, repository 경유.

#### T2-5. 견적서 / 협력사용 고객정보 전송 메시지 타입 추가
- 파일: `backend/app/domain/constants.py`
  - `MessageType.CUSTOMER_QUOTE` (고객 견적서)
  - `MessageType.PARTNER_CUSTOMER_INFO` (협력사에 미입금 고객 정보 전달)
- 템플릿: `backend/app/domain/message_templates.py`
  - 카카오 알림톡 템플릿 ID 키 추가 (config에서 비워두면 Mock 발송):
    - `solapi_kakao_template_customer_quote`
    - `solapi_kakao_template_partner_customer_info`
  - 변수: `CUSTOMER_QUOTE` → `{고객명, 서비스명, 수량, 소비자가, 할인가, 총금액, 계약금, 잔금, VAT_표기, 방문예정일, 회사명}`. **도급가 변수는 절대 포함 금지.**
  - `PARTNER_CUSTOMER_INFO` → `{협력사담당자, 고객명, 연락처마스킹, 방문일, 주소, 미수금, 비고}` — 연락처는 `***-****-####` 형태로 백엔드에서 마스킹 후 발송 가능 여부 정책 확정 후 채움 (기본은 마스킹 OFF, 발송 시 운영자 confirm). **AGENTS.md customer-data-exposure 규칙 재확인 후 진행.**
- 발송 라우트:
  - `POST /api/admin/orders/{order_id}/quote/send` — 견적서 발송. body: `{ channel: "kakao"|"sms" }` (기본 kakao). timeline `quote_sent`.
  - `POST /api/admin/orders/{order_id}/notify-partner-unpaid` — 협력사에 미입금 고객 정보 전송. timeline `partner_unpaid_notice_sent`.
- 두 신규 timeline 이벤트도 constants에 추가.

#### T2-6. 응답 캐싱·페이지네이션·정렬 회귀 점검
- 기존 R13 reports API 호출이 깨지지 않도록 정렬 변경 후 단위/통합 테스트로 회귀 확인.

---

### T3. 프론트엔드: 주문 화면 정비

#### T3-1. 주문 목록 (OrdersPage.tsx) 리팩터
- '주문번호' 컬럼 제거 (`OrdersPage.tsx:683` 및 데이터 셀).
- 검색 placeholder의 '주문번호' 문구 제거 → "고객/주소/연락처 검색" 로 변경 (`OrdersPage.tsx:413`).
- '상품' 컬럼 1개를 → **'상품' / '품목'** 두 컬럼으로 분리. `service_name` / `size_or_quantity` 사용.
- '금액' 컬럼 라벨 → **'소비자가'**, 그 옆에 **'도급가'** 컬럼 신규 추가 (도급가는 admin DTO 새 필드 사용).
- 결제 상태 표시: 기존 PaidPill 사용. 미납(`isUnpaid`)은 빨간색, 완납은 회색.
- 정렬 토글:
  - 상단 필터바에 "방문일 ↑↓" 토글 버튼. state `sortBy: 'visit_asc' | 'visit_desc'`.
  - 기본 진입 시 **오늘 작업** 위주 표시(백엔드 `include_past_paid=false`), "전체" 탭 클릭 시 `include_past_paid=true`.
- 회색(완료) / 빨강(미납) 시각 규칙은 `global.css` 토큰 사용 — 새로 색 하드코딩 금지.

#### T3-2. 신규/수정 주문 등록 (OrderFormPage.tsx) 리팩터
- 폼 섹션을 3개 카드로 명확 분리:
  1. **고객 정보** (기존 유지)
  2. **상품 / 일정** (수량·일정·팀명·상품 상세·요청사항)
  3. **결제 / 정산** (총 금액·할인가·계약금·잔금·현장추가·VAT·결제 상태·결제 메모·증빙 메모·도급가·정산 상태)
- 자동계산 로직 강화 (`LineEditor`):
  - 상세상품 선택 시 `selected.base_price * 수량 = total_amount` 자동 채움. 수량 변경 시도 즉시 재계산.
  - 동시에 `selected.partner_base_price * 수량 = partner_payment_amount` 자동 채움.
  - `discount_amount` 입력 시 `total_amount = base_price*qty - discount_amount` 재계산 (음수 방지, `Math.max(0, …)`).
  - `total_amount` 변경 시 **계약금이 비어 있으면** 30% 자동 채움(`round(total*0.3)`). 사용자가 직접 입력한 값은 덮어쓰지 않음(상태 플래그 `depositTouched`로 관리).
  - 잔금 = max(0, total - deposit).
- 라벨 변경: '협력사 지급액' → **'도급가'**. 필드명(`partner_payment_amount`)은 그대로 유지.
- '할인가' 입력 칸 신규 추가 (`discount_amount`).
- VAT: 자유 텍스트 → `<select>` 옵션 `포함(included)` / `별도(excluded)`.
- **모든 금액 칸은 자동계산되더라도 직접 수정 가능해야 한다.** 사용자가 수정한 칸은 자동 재계산 대상에서 제외(터치 플래그). 사용자가 칸을 비우면 자동계산 재개.
- 하단에 두 버튼:
  - **저장** (기존 유지)
  - **견적서 발송 (카카오톡)** — 신규. 저장이 안 된 폼이면 먼저 저장 후 발송. 발송 결과 토스트 + 발송이력으로 이동 링크. **도급가 변수는 카카오 템플릿에 포함되지 않는다는 점을 텍스트로 안내.**
- 폼 검증: 도급가가 총 금액(=소비자가)을 초과하면 경고 배너(차단은 아님).

#### T3-3. 상품관리 (ProductsPage.tsx)
- 상품 편집 폼 `기준가` 입력칸 옆에 **'도급가'** 입력칸을 동일한 형식으로 추가.
- 테이블(목록 뷰)에 '도급가' 컬럼 추가.

#### T3-4. 사이드바 (AdminShell.tsx) 신규주문등록 바로가기
- 메뉴 목록 하단(또는 '주문관리' 바로 아래)에 별도 강조 버튼:
  - 라벨: "+ 신규 주문 등록"
  - 동작: 어떤 페이지에 있든 `OrderFormPage` 신규 모드로 전환. 라우팅 state 또는 zustand store 사용.
- 모바일(≤768px)에서는 FAB 형태로 우하단 고정 (디자인 토큰 따름).

#### T3-5. 가로 스크롤 / 화면 폭 정리
- `global.css`에 공통 클래스 `.page-shell { max-width: 1440px; margin: 0 auto; width: 100%; }` 추가.
- 모든 admin 페이지(`OrdersPage`, `OrderFormPage`, `ProductsPage`, `PartnersPage`, `ReportsPage`, `PhotosPage`, `SendsPage` 등) 상위 컨테이너에 `.page-shell` 적용해 폭 통일.
- 데이터 테이블이 폭 부족할 경우 부모 `overflow-x: auto`로 항상 가로 스크롤 가능하게. 테이블별 `minWidth` 인라인 스타일은 그대로 유지하되, 큰 테이블은 헤더 sticky(`position: sticky; top: 0`) 적용을 권장.
- 모바일 분기는 기존 768px 분기 유지.

---

### T4. 프론트엔드: 협력사 관리 강화 (PartnersPage.tsx)

#### T4-1. 협력사 상세 패널 — 미정산 합계 & 정산 버튼
- 상세 카드에 다음 정보 표시:
  - 미정산 도급가 합계 `₩{unpaid_partner_amount_total}`
  - 미정산 건수 `{unpaid_partner_order_count}건`
- 합계 옆에 **'정산'** 액션 버튼:
  - 클릭 시 모달 → "선택한 N건을 정산 완료로 처리합니까?" 확인 → `POST /partners/{id}/settlements/settle`.
  - 정산할 항목 선택은 T4-2의 체크박스에서 모은다.

#### T4-2. 최근 배정 작업 영역
- 컬럼 구성을 다음과 같이 변경:
  - 체크박스 / 방문일 / 상태 / 작업(상품·품목·주소) / 고객 / 소비자가 / 도급가 / 정산상태 / 액션
- 정산상태:
  - 미정산: 빨간 pill ("정산 대기")
  - 정산완료: 회색 pill ("정산 완료") + `settled_at` 표시
- 액션 컬럼:
  - 미정산 건: "정산" (단건 처리) 버튼
  - 정산완료 건: "되돌리기" 버튼(권한 admin)
- 상단에 **일자 필터**: 시작일~종료일 (DatePicker, 은행 앱과 같이 캘린더 팝업). 기본 최근 30일.
- 상태 필터: 전체 / 미정산 / 정산완료.
- 일괄 정산: 체크박스로 다중 선택 후 상단 "선택 N건 정산" 버튼.

#### T4-3. 미입금 고객 정보 협력사 전송
- 협력사 상세에서 미정산 건 또는 잔금 미납건을 행 단위로 표시할 때, 행 우측 액션 메뉴(...)에 **'협력사에 고객정보 전송'** 항목 추가.
- 클릭 시 모달:
  - 발송 채널 (kakao 기본)
  - 발송 내용 미리보기 (고객명/연락처/주소/미수금/방문일)
  - 운영자가 확인 후 "전송" 클릭 → `POST /api/admin/orders/{order_id}/notify-partner-unpaid`
- 운영 메모 입력 옵션.
- 발송 직후 토스트 + 발송이력으로 링크.

#### T4-4. 협력사 목록 — '담당자 미정산 합계' 컬럼
- 협력사 목록 테이블에 '미정산 합계' 컬럼 추가. 0원은 회색 빈 표시, 0원 초과는 강조.

---

### T5. 시각/UX 정리

- 모든 가격 표시는 천 단위 콤마, 우측 정렬. 부가세 정책 표기를 표 헤더 또는 행 우측에 `(VAT 포함)` / `(VAT 별도)` 작게 표시.
- 결제 상태 색상 토큰을 `global.css`에 정의(`--paid-fg`, `--unpaid-fg`, `--deposit-fg`)하고 컴포넌트는 이를 참조.
- 정산 상태 색상 토큰도 동일 패턴으로 추가.
- 토스트/배너 메시지는 한국어 일관 표현 유지 ("저장되었습니다", "발송 요청을 보냈습니다").

---

### T6. 테스트

#### T6-1. 백엔드 단위/통합 테스트 (필수)
- `backend/tests/test_admin_orders_sort.py` (신규): 미납 우선·오늘 우선·오름차순/내림차순·`include_past_paid` 동작.
- `backend/tests/test_partner_settlement.py` (신규): 정산 처리/되돌리기, timeline 이벤트 발생, 권한 거부 케이스, soft-delete 주문 제외.
- `backend/tests/test_quote_message.py` (신규): 견적서 메시지 발송 — Mock provider 경유 호출, **도급가 변수 미포함** assertion.
- `backend/tests/test_pricing_dtos.py` (신규): partner/customer DTO에 `partner_price`, `discount_amount` 가 포함되지 않음 확인.
- 기존 테스트 회귀 통과(`python -m pytest`).

#### T6-2. 프론트엔드 typecheck/lint
- `npm run typecheck`, `npm run lint` 무경고.
- 신규주문 자동계산 로직은 순수 함수로 추출하여 `frontend/src/features/admin/orders/__tests__/pricing.test.ts` 작성 (vitest 이미 들어와 있다면 활용, 없으면 단순 export로 두고 e2e에서 검증).

#### T6-3. Playwright E2E (필수)
- `tests/e2e/r14-order-pricing.spec.ts`:
  - 신규 주문 등록 → 카테고리/상세상품 선택 → 수량 30 입력 → 총 금액·도급가·계약금 자동 채움 확인.
  - 할인가 입력 → 총 금액 차감 확인.
  - VAT 셀렉트 선택 확인.
  - 저장 후 목록에서 소비자가/도급가 두 컬럼 노출 확인.
- `tests/e2e/r14-partner-settlement.spec.ts`:
  - 협력사 상세 진입 → 미정산 도급가 합계 노출 → 다중 선택 → 일괄 정산 → 상태 변경 확인.
- 기존 `tests/e2e/r13-reports.spec.ts` 회귀 통과.

---

### T7. 외부 연동 조사 (코드 변경 없음, 보고서로 처리)

#### T7-1. 결제선생(payself) 연동 가능성 보고
- 결제선생 사업자 페이지/공개 API 문서/타사 연동 사례를 web 검색하여 다음 항목을 정리해 PR 본문 또는 별도 `docs/research/2026-05-21-payself-integration-feasibility.md`에 첨부:
  - 제공 API/Webhook 종류 (REST, OAuth, IP 화이트리스트 등)
  - 인증 방식 / 발급 키 종류
  - 결제 상태 자동 동기화 방식(폴링 vs 푸시)
  - 도입 시 본 프로젝트에 추가될 모듈/마이그레이션 예상
  - 위험 / 비용 / 우선순위 의견 (1~2단락)
- 실제 코드 작성 금지 — **조사 결과만** 정리한다.

---

## 4. PR 분할 권장안

| PR# | 범위 | 의존 |
|-----|------|------|
| PR-R14-A | T1 (모델/마이그/시드) | — |
| PR-R14-B | T2-1, T2-2, T2-3, T2-4 (백엔드 정렬/DTO/정산 API/집계) | PR-A |
| PR-R14-C | T2-5 (견적/협력사 알림 메시지) | PR-A |
| PR-R14-D | T3 (주문/상품/사이드바/레이아웃 프론트) | PR-A, PR-B |
| PR-R14-E | T4 (협력사 관리 프론트) | PR-B, PR-C |
| PR-R14-F | T5, T6 (UX 정리 + 테스트 보강) | 모두 |
| PR-R14-G | T7 보고서 (별도, 코드 변경 없음) | — |

각 PR은 한국어 본문으로 작성하며 다음을 반드시 포함:
- 변경 요약
- 영향 받는 화면/엔드포인트
- 마이그레이션 적용 순서
- 자가 검증 결과 (테스트 출력 요약)
- 스크린샷(주요 화면)

---

## 5. 자가 검증 체크리스트 (작업자가 PR 제출 직전 실행)

각 항목을 PR 본문에 ✅/❌로 표기하여 첨부한다.

- [ ] `python -m alembic upgrade head` 무오류, downgrade 1회 후 재상승 무오류
- [ ] `python -m pytest` 전체 통과
- [ ] `ruff check backend` 통과
- [ ] `npm run typecheck` 통과
- [ ] `npm run lint` 통과
- [ ] `npm run build` 통과
- [ ] `npm run e2e` (R13 + R14 신규 스펙) 통과
- [ ] AGENTS.md DTO 화이트리스트 재검토 — `partner_price`, `discount_amount`, `partner_settled_at`가 partner/customer DTO에 노출되지 않는지 grep 확인
- [ ] 모든 운영 mutation(정산, 견적 발송, 협력사 알림)이 timeline 이벤트를 남기는지 확인
- [ ] 소프트 삭제된 주문이 정산/목록/집계에 포함되지 않는지 확인
- [ ] KST 기준 '오늘' 비교 사용 (`datetime.now(KST).date()`)
- [ ] 신규 가격 컬럼은 모두 `Numeric(12,2)` 통일
- [ ] 카카오 견적 템플릿에 도급가 변수 없음 (테스트로 보장)

---

## 6. 작업자에게 (Codex)

- 변경이 광범위하므로, **각 Task 시작 전에** 해당 파일을 직접 읽어 현재 코드와 위 진단을 대조한 뒤 작업을 시작한다. 진단이 틀렸다고 판단되면 **수정하지 말고 PR 본문에 "진단 수정 필요" 섹션을 만들어 명시**한다.
- 불확실한 정책(특히 협력사에 전송될 고객 연락처 마스킹 여부, 견적서 카카오 템플릿 사전 등록 여부, 결제선생 연동 우선순위)은 **임의 결정하지 말고** 작업 메모에 질문을 남긴 뒤 보수적 기본값을 적용한다.
- 모든 작업은 위에서 정한 Task 단위로 commit/PR을 분리한다. 한 PR이 1000라인 넘는 변경이면 추가 분할을 검토한다.
- 작업 완료 후 별도 첨부된 리뷰 체크리스트(`2026-05-21-r14-codex-review-checklist.md`)에 따라 **자가 리뷰 보고서**를 작성하여 동일 PR 또는 후속 PR에 첨부한다.

---

## 7. 종료 조건 (Definition of Done)

다음을 모두 만족할 때 본 마일스톤 종료:

1. 위 모든 Task의 자가 검증 체크리스트 100% 통과.
2. R13 회귀 테스트 그린.
3. 자가 리뷰 보고서 첨부 (체크리스트 참조).
4. `docs/plans/2026-05-21-r14-pricing-and-settlement-work-order.md` 마지막에 "구현 완료 회신" 섹션을 추가하여 PR 번호 / 커밋 해시 / 테스트 결과 요약을 기록.
5. `.master/next_session_plan.md` 의 "next recommended task" 갱신.

— 끝 —

---

## 구현 완료 회신

작성일: 2026-05-26

- PR 번호: 미생성 (로컬 Codex 작업)
- 커밋 해시: 미생성
- 구현 범위:
  - R14-A: `0010_pricing_partner_base_and_discount` 마이그레이션, `partner_base_price`, `discount_amount`, `partner_settled_at` 모델/시드/스키마 반영
  - R14-B: 주문 기본 정렬/과거 완료 숨김, 관리자 가격 DTO, 협력사 정산 조회/완료/되돌리기 API
  - R14-C: 고객 견적 알림톡, 협력사 고객정보 전송 메시지와 timeline 이벤트
  - R14-D/E: 주문 목록/폼/상세, 상품관리, 협력사 정산 UI, 신규 주문 사이드바/FAB, 공통 `page-shell`
  - R14-F: 백엔드/프론트/E2E 테스트 보강 및 role route API 토큰 레이스 수정
  - R14-G: `docs/research/2026-05-21-payself-integration-feasibility.md`
- 검증 결과:
  - `python -m compileall app` 통과
  - 임시 SQLite DB 기준 `python -m alembic upgrade head` → `python -m alembic downgrade -1` → `python -m alembic upgrade head` 통과
  - `pytest -q` → `151 passed`
  - `npm run typecheck` 통과
  - `npm run lint` 통과
  - `npm run build` 통과 (Vite chunk size warning만 출력)
  - `npm run e2e` → `33 passed`
- 검증 제약:
  - 현재 로컬 Python 환경에 `ruff`가 없어 `ruff check .` / `python -m ruff check .`는 실행 불가.
  - `python -m alembic upgrade head --sql` offline 출력은 기존 `0006_default_partner_categories.py`의 offline 비호환 data migration 때문에 실패. R14 online migration은 임시 DB에서 검증 완료.
- 자가 리뷰 보고서: `docs/plans/2026-05-21-r14-review-report.md`
