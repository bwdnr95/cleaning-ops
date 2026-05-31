# R14 자가 리뷰 보고서

작성일: 2026-05-26  
대상: R14 Pricing / Settlement / Quote / Partner Work Order  
종합 판정: ✅ 머지 가능 — R14 핵심 요구사항과 회귀 검증은 통과했고, 로컬 환경에 `ruff`가 설치되어 있지 않은 점만 검증 제약으로 남았다.

## 1. 요청서 항목 충족 여부

### 1-A. 주문관리 메인 목록

- ✅ 주문번호 컬럼 제거 및 검색 placeholder 갱신: `frontend/src/features/admin/orders/OrdersPage.tsx:413`, `frontend/src/features/admin/orders/OrdersPage.tsx:685`
- ✅ 상품/품목 컬럼 분리, 소비자가/도급가 컬럼 추가, VAT 별도 보조 텍스트: `frontend/src/features/admin/orders/OrdersPage.tsx:685`, `frontend/src/features/admin/orders/OrdersPage.tsx:691`, `frontend/src/features/admin/orders/OrdersPage.tsx:773`

### 1-B. 주문관리 정렬/필터

- ✅ 기본 `visit_asc` 정렬과 방문일 토글: `frontend/src/features/admin/orders/OrdersPage.tsx:119`, `frontend/src/features/admin/orders/OrdersPage.tsx:478`
- ✅ 과거 비미납 숨김, 과거 미납 상단 유지, soft-delete 제외: `backend/app/repositories/orders.py:33`, `backend/app/repositories/orders.py:35`, `backend/app/repositories/orders.py:106`
- ✅ API `include_past_paid` 파라미터: `backend/app/api/routes/admin/orders.py:60`, `backend/app/repositories/orders.py:30`
- ✅ 백엔드 테스트: `backend/tests/test_r14_pricing_and_settlement.py:63`

### 1-C. 상품관리

- ✅ 상품 모델/API/화면에 `partner_base_price` 추가: `backend/app/models/service_item.py:27`, `backend/app/schemas/service_catalog.py:28`, `frontend/src/features/admin/products/ProductsPage.tsx:341`, `frontend/src/features/admin/products/ProductsPage.tsx:409`

### 1-D. 신규 주문 등록

- ✅ 고객 정보 / 상품·일정 / 결제·정산 구조 유지 및 견적 발송 버튼 추가: `frontend/src/features/admin/orders/OrderFormPage.tsx:267`, `frontend/src/features/admin/orders/OrderFormPage.tsx:280`
- ✅ 카탈로그 가격 기반 자동계산, 할인가 차감, 계약금/잔금 계산, 수동 입력 보호: `frontend/src/features/admin/orders/OrderFormPage.tsx:165`, `frontend/src/features/admin/orders/OrderFormPage.tsx:780`, `frontend/src/features/admin/orders/OrderFormPage.tsx:805`
- ✅ VAT select, 도급가 라벨/필드: `frontend/src/features/admin/orders/OrderFormPage.tsx:467`, `frontend/src/features/admin/orders/OrderFormPage.tsx:480`, `frontend/src/features/admin/orders/OrderFormPage.tsx:487`
- ✅ 견적 발송 시 도급가 미포함 테스트: `backend/tests/test_r14_pricing_and_settlement.py:194`, `frontend/e2e/r14-order-pricing.spec.ts:5`

### 1-E. 화면 폭 / 스크롤

- ✅ 공통 `.page-shell` 추가 및 주요 admin 페이지 적용: `frontend/src/styles/global.css:219`, `frontend/src/features/admin/dashboard/Dashboard.tsx:25`, `frontend/src/features/admin/orders/OrdersPage.tsx:361`, `frontend/src/features/admin/partners/PartnersPage.tsx:470`
- ✅ 넓은 주문/정산 표는 가로 스크롤 유지: `frontend/src/features/admin/orders/OrdersPage.tsx:681`, `frontend/src/features/admin/partners/PartnersPage.tsx:805`

### 1-F. 협력사 관리

- ✅ 미정산 합계/건수 표시: `backend/app/services/partners.py:300`, `frontend/src/features/admin/partners/PartnersPage.tsx:741`
- ✅ 정산 목록/필터/정산/되돌리기/고객정보 전송 UI: `frontend/src/features/admin/partners/PartnersPage.tsx:789`, `frontend/src/features/admin/partners/PartnersPage.tsx:827`, `frontend/src/features/admin/partners/PartnersPage.tsx:832`
- ✅ 정산/되돌리기 API 및 timeline 이벤트: `backend/app/api/routes/admin/partner_settlements.py:37`, `backend/app/services/partner_settlements.py:64`, `backend/app/services/partner_settlements.py:91`
- ✅ 협력사 고객정보 전송 timeline: `backend/app/services/messages.py:1000`, `backend/tests/test_r14_pricing_and_settlement.py:215`

### 1-G. 사이드바

- ✅ 데스크톱 신규 주문 버튼과 모바일 FAB: `frontend/src/components/layout/AdminShell.tsx:79`, `frontend/src/components/layout/AdminShell.tsx:106`
- ✅ 역할 전환 레이스 방지: `frontend/src/app/App.tsx:84`, `frontend/src/app/App.tsx:229`

### 1-H. Payself / 셀프페이 조사

- ✅ 조사 보고서 작성: `docs/research/2026-05-21-payself-integration-feasibility.md:1`
- ✅ 공개 정보상 상세 API 스펙은 비공개/계약 기반으로 판단하고 provider 인터페이스 후속 설계를 제안: `docs/research/2026-05-21-payself-integration-feasibility.md:8`, `docs/research/2026-05-21-payself-integration-feasibility.md:31`

## 2. 아키텍처 / 데이터 모델

- ✅ 신규 컬럼 `Numeric(12,2)` 및 server default: `backend/app/models/order.py:34`, `backend/app/models/service_item.py:27`, `backend/alembic/versions/0010_pricing_partner_base_and_discount.py:21`
- ✅ 마이그레이션 번호 `0010_*`, downgrade 포함: `backend/alembic/versions/0010_pricing_partner_base_and_discount.py:3`, `backend/alembic/versions/0010_pricing_partner_base_and_discount.py:54`
- ⚠ `python -m alembic upgrade head --sql`은 기존 `0006_default_partner_categories.py`가 offline SQL 모드에서 `op.get_bind()` 결과를 실행 가능한 connection으로 가정해 실패한다. R14 migration 자체는 임시 SQLite DB에서 `upgrade head -> downgrade -1 -> upgrade head` 통과.
- ✅ Admin DTO에만 `consumer_price`, `partner_price`, `partner_settled_at` 추가: `backend/app/schemas/order.py:115`, `backend/app/services/orders.py:538`
- ✅ Partner/Customer DTO 민감 필드 비노출 테스트: `backend/tests/test_role_dtos.py:52`, `backend/tests/test_role_dtos.py:69`
- ✅ 신규 정산/정렬 쿼리 soft-delete 가드: `backend/app/repositories/orders.py:33`, `backend/app/services/partner_settlements.py:119`, `backend/app/services/partners.py:307`
- ✅ SQLAlchemy 2.0 `select().where()` 스타일 사용: `backend/app/repositories/orders.py:33`, `backend/app/services/partner_settlements.py:118`
- ✅ KST today helper 사용: `backend/app/repositories/orders.py:6`, `backend/app/repositories/orders.py:32`

## 3. 보안 / 권한

- ✅ 정산 라우트 모두 `require_admin`: `backend/app/api/routes/admin/partner_settlements.py:24`, `backend/app/api/routes/admin/partner_settlements.py:42`, `backend/app/api/routes/admin/partner_settlements.py:60`
- ✅ 견적/협력사 고객정보 전송 라우트 admin 전용: `backend/app/api/routes/admin/orders.py:207`, `backend/app/api/routes/admin/orders.py:228`
- ✅ DTO 변환은 명시 필드 구성: `backend/app/services/orders.py:582`, `backend/app/services/orders.py:668`
- ✅ 협력사 고객 연락처는 메시지 템플릿에서 마지막 4자리만 남김: `backend/app/services/messages.py:1110`, `backend/app/services/messages.py:1211`
- ✅ 협력사 고객정보 전송 모달의 memo는 메시지 비고에 반영: `backend/app/api/routes/admin/orders.py:242`, `backend/app/services/messages.py:1219`
- ✅ 카카오 견적 템플릿 변수에 도급가 없음: `backend/app/domain/message_templates.py:63`, `backend/tests/test_r14_pricing_and_settlement.py:206`

## 4. 프론트엔드 품질

- ✅ `apiRequest` 래퍼로 신규 API 호출: `frontend/src/api/admin.ts:73`, `frontend/src/api/admin.ts:169`
- ✅ 로딩/에러/빈 상태 유지: `frontend/src/features/admin/partners/PartnersPage.tsx:797`, `frontend/src/features/admin/orders/OrderFormPage.tsx:332`
- ✅ 천 단위 금액 표기: `frontend/src/features/admin/partners/PartnersPage.tsx:1284`, `frontend/src/features/admin/orders/OrderFormPage.tsx:822`
- ✅ 모바일 FAB CSS: `frontend/src/styles/global.css:227`
- ✅ 세션 role 전환 시 잘못된 토큰으로 API를 먼저 호출하는 레이스 수정: `frontend/src/app/App.tsx:84`, `frontend/src/app/App.tsx:235`

## 5. 테스트 커버리지

- ✅ 가격 자동 채움/정렬/정산/메시지 스코프: `backend/tests/test_r14_pricing_and_settlement.py:25`, `backend/tests/test_r14_pricing_and_settlement.py:63`, `backend/tests/test_r14_pricing_and_settlement.py:140`, `backend/tests/test_r14_pricing_and_settlement.py:194`
- ✅ DTO 민감 필드 회귀: `backend/tests/test_role_dtos.py:43`, `backend/tests/test_role_dtos.py:59`
- ✅ 기존 메시지 설정 테스트가 신규 템플릿 포함: `backend/tests/test_auth_integration.py:1884`, `backend/tests/test_auth_integration.py:1912`
- ✅ 신규 Playwright E2E: `frontend/e2e/r14-order-pricing.spec.ts:5`, `frontend/e2e/r14-partner-settlement.spec.ts:5`
- ⚠ 체크리스트가 제안한 파일명(`test_admin_orders_sort.py`, `test_partner_settlement.py` 등) 그대로 분리하지 않고 `test_r14_pricing_and_settlement.py`에 통합했다. 커버리지는 충족하나 파일명은 지시서 권장안과 다르다.

## 6. 검증 로그

- ✅ `python -m compileall app` 통과
- ✅ 임시 DB 마이그레이션: `python -m alembic upgrade head`, `python -m alembic downgrade -1`, `python -m alembic upgrade head` 통과
- ✅ `pytest -q` → `151 passed in 101.03s`
- ⚠ `ruff check .` / `python -m ruff check .` → 현재 Python 환경에 `ruff` 미설치
- ✅ `npm run typecheck` 통과
- ✅ `npm run lint` 통과
- ✅ `npm run build` 통과, Vite chunk size warning만 기존처럼 출력
- ✅ `npm run e2e` → `33 passed`

## 7. 회귀 위험 점검

- ✅ R7 다중 라인 회귀: `frontend/e2e/admin-multi-line-e2e.spec.ts`가 전체 E2E에서 통과
- ✅ R8 사진 자동 공개/되돌리기 회귀: `frontend/e2e/admin-photo-review-e2e.spec.ts`, `frontend/e2e/partner-customer-e2e.spec.ts` 통과
- ✅ R10 인증/세션 회귀: 기존 role route E2E 실패를 수정 후 전체 E2E 통과
- ✅ R13 보고서/정산 회귀: `frontend/e2e/admin-reports-e2e.spec.ts`와 `backend/tests/test_reports.py`가 전체 테스트에서 통과

## 8. 운영 워크스루

- ✅ 시나리오 A(신규 주문 → 가격 자동계산 → 견적 발송)는 `frontend/e2e/r14-order-pricing.spec.ts:5`로 자동화.
- ✅ 시나리오 B(협력사 고객정보 전송)는 `frontend/e2e/r14-partner-settlement.spec.ts:5`와 `backend/tests/test_r14_pricing_and_settlement.py:194`로 자동화.
- ✅ 시나리오 C(정렬/필터)는 `backend/tests/test_r14_pricing_and_settlement.py:63`와 기존 주문 목록 E2E로 자동화.

## 9. 발견 이슈 / 후속

- ⚠ 로컬 backend dev dependency에 `ruff`가 없어 lint 검증을 실행하지 못했다. 다음 세션에서 dev dependency 설치 방식(`pip install -e ".[dev]"`, uv/pipx 등)을 정리하는 것이 좋다.
- ⚠ Alembic offline SQL 출력은 R14가 아니라 기존 0006 data migration의 offline 호환성 문제로 실패한다. 실제 online upgrade/downgrade는 임시 DB에서 통과했다.

최종 결론: ✅ 머지 가능.
