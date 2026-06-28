# 정기청소 — 서브시스템 B (월 합산 청구·정산) 설계

- 작성일: 2026-06-28
- 범위: **서브시스템 B만.** A(정기계약+회차 자동생성)가 만든 정기 주문을 (계약, 월) 단위로 집계해 고객 청구 + 협력사 정산을 조회·일괄처리·내보내기.
- 전제: A는 완료되어 `main`에 있음(`recurring_contract_id` 연결고리, `RecurringOccurrence.billing_month`). 작업 브랜치 `feature/recurring-billing`(main에서 분기 — 동시 진행 중인 partner 작업과 격리).
- 전제 규칙: `AGENTS.md`(매출 정의·미정산 정의·정산 가드·집계는 Python/Decimal·역할 DTO 화이트리스트·타임라인) + `.claude/rules/*` 준수.

---

## 0. 합의된 결정 (브레인스토밍 결과)

| # | 결정 | 값 |
|---|------|-----|
| D1 | 표현 방식 | **파생 집계.** 새 테이블/상태머신 없음. (계약,월)별로 주문을 집계만 하고, 상태는 기존 주문별 `payment_status`/`partner_payment_status`에서 파생. |
| D2 | 범위 | **고객 청구 + 협력사 정산 둘 다.** |
| D3 | 집계 단위 | **계약×월 = 한 행** (협력사 여럿이면 정산은 협력사별 소계). |
| D4 | 액션 | **조회 + 일괄 입금/정산 마킹 + CSV 내보내기.** (메시지 발송은 범위 밖.) |
| D5 | 위치 | **정기청소 영역의 '월 정산' 뷰** (A1). |
| D6 | 월 기준 날짜 | **`Order.scheduled_date`의 월** (A의 `list_recurring_orders_in_month`와 동일). |
| D7 | 청구액 표기 | **전체 생성주문 합 + '확정 매출'(매출 정의) 별도 표기.** |
| D8 | 내보내기 | **CSV** (기존 `order_export` 패턴). |

---

## 1. 데이터 흐름 — 새 테이블 없음

(계약, 월)별로 **정기 주문을 집계**한다. 대상 주문 집합:
- `Order.recurring_contract_id == contract.id`
- `Order.deleted_at IS NULL`
- `Order.scheduled_date`의 `YYYY-MM == month` (D6)
- `Order.status != 취소(CANCELLED)` (취소 제외)

이 집합에서 고객/협력사 두 면을 집계한다. **집계는 Python(`itertools.groupby` + `Decimal`)** — DB 방언 함수 금지(`AGENTS.md`). 마이그레이션 없음.

---

## 2. 무엇을 보여주나 (정의는 AGENTS.md와 1:1)

계약×월 한 행(`RecurringBillingRowRead`):
- 계약: `contract_id`, `label`, `customer_name`, `month`, `visit_count`(주문 수).
- **고객 청구**:
  - `billed_total` = 대상 주문의 소비자가 합(`order_consumer_total` 사용 — 할인/부가세 반영, 기존 매출 계산과 동일).
  - `confirmed_revenue` = 그중 `status∈(CUSTOMER_DELIVERY_DONE, COMPLETED)` 합 (**대시보드 매출 정의와 동일**, `DashboardService.monthly_revenue`와 일관).
  - `payment_breakdown` = `payment_status`별 건수/금액(입금완료/미입금/대기/환불 등).
  - `unpaid_customer_count` = 입금 미완(`PAYMENT_CHECK_STATUSES` 등) 건수.
- **협력사 정산**:
  - `partner_total` = 대상 주문의 `partner_payment_amount` 합.
  - `unpaid_partner_total`/`unpaid_partner_count` = 공통 `unpaid_partner_condition`(`partner_payment_status∈(unpaid,ready)` 또는 `COMPLETED+NULL`) 해당분.
  - `partner_subtotals` = 협력사별 소계 리스트(D3: 한 계약에 협력사 여럿일 때) — `partner_id/name`, 정산합, 미정산합, 정산 가능 건수.
- 회차 상태 요약(생성/예정/완료 건수)는 선택 표기.

> 금액 헬퍼: 소비자가는 `app/domain/order_pricing.py`의 `order_consumer_total`, 협력사가는 `partner_payment_amount`(또는 `partner_vat`가 관여하면 기존 정산 탭과 동일 계산). 기존 `reports.settlements`/`partner_settlements`의 계산과 정확히 일치시킨다.

---

## 3. 일괄 액션 (기존 경로 재사용 — 새 상태머신 없음)

각 액션은 (contract_id, month)를 받아 백엔드가 **대상 주문을 재선정**해 처리(화면 표시 시점과 실제 처리 시점의 불일치 방지). 처리 건수를 반환.

### 3.1 이 달 입금완료 일괄 — `POST /admin/recurring/billing/mark-paid`
- 대상: 그 (계약,월) 주문 중 **입금 미완**(`payment_status NOT IN (PAID, REFUNDED)`).
- 처리: 각 주문 `OrderService.update`로 `payment_status → PAID` — **기존 결제상태 일괄변경과 동일한 루프-개별 방식**(각 주문 결제 타임라인 자동 기록). 처리/스킵 건수 반환.

### 3.2 이 달 협력사 정산완료 일괄 — `POST /admin/recurring/billing/settle`
- 대상: 그 (계약,월) 주문 중 **정산 가능분만** = `is_unpaid_partner_order`(= `COMPLETED` + 미정산). 미완료 주문은 정산 불가(`AGENTS.md` 가드 — 미완료를 지급완료로 못 찍게).
- 처리: **기존 `PartnerSettlementService`의 정산 실행 경로 재사용**(`partner_payment_status → PAID` + `partner_settled_at` + `PARTNER_SETTLED` 타임라인). 이미 배열 처리 지원.
- 선택: `partner_id`로 협력사별 소계 단위 정산도 허용(D3). 미지정 시 그 달 전체 정산 가능분.
- 처리/스킵(미완료라 제외) 건수 반환.

### 3.3 UI 가드
두 액션 모두 **확인 모달 + 영향 건수**(예: "이 달 입금완료 N건 처리") 표시 후 실행.

---

## 4. 내보내기 — `GET /admin/recurring/billing/export?month=YYYY-MM`

- 그 달 **정기 주문 상세 CSV**(계약/고객/방문일/서비스/소비자가/매출확정여부/입금상태/협력사/협력사가/정산상태). 기존 `app/services/order_export.py` 컬럼/패턴 재사용 + 정기/정산 컬럼 보강.
- (선택) `contract_id` 쿼리로 단일 계약만.
- 응답: `text/csv`, 파일명 `recurring-billing-YYYY-MM.csv`. 프론트는 기존 `downloadBlob`(`api/client.ts`) 사용.

---

## 5. 백엔드 (strict 레이어 준수)

- `services/recurring_billing.py` — `RecurringBillingService(db)`:
  - `month_summary(month) -> list[RecurringBillingRowRead]` (ACTIVE/전체 계약 중 그 달 주문 있는 계약, soft-delete 제외).
  - `mark_month_paid(contract_id, month, *, actor_user_id) -> {updated, skipped}`.
  - `settle_month(contract_id, month, partner_id=None, *, actor_user_id) -> {settled, skipped}` (PartnerSettlementService 위임).
  - `export_csv(month, contract_id=None) -> bytes/str`.
  - 협업: `OrderRepository`(대상 주문 조회), `OrderService`(결제 update), `PartnerSettlementService`(정산), `RecurringContractRepository`(계약 메타).
- `repositories/orders.py` — `list_recurring_orders_in_month` 확장/신설: `(contract_id, month)` 또는 `(month)` 전체, 취소·삭제 제외, partner/contract 관계 로딩(N+1 완화). 기존 메서드는 A 요약이 쓰므로 **시그니처 보존하고 별도 메서드 추가** 권장.
- `api/routes/admin/recurring.py`에 billing 서브라우트 추가(또는 `admin/recurring_billing.py` 신설 후 `/admin/recurring/billing` prefix). 전부 `require_admin`.
- `schemas/recurring_billing.py` — `RecurringBillingRowRead`, `PartnerSubtotalRead`, `PaymentBreakdownRead`, `MarkPaidRequest{contract_id, month}`, `SettleRequest{contract_id, month, partner_id?}`, 결과 DTO. **모두 admin 전용**(협력사/고객 DTO에 미노출 — 계약/정산 내부정보).

---

## 6. 프론트엔드

- 정기청소 영역에 **'월 정산' 뷰**(정기청소 페이지 상단 탭: `계약` / `월 정산`, 또는 사이드 보조 진입). 기존 `RecurringContractsPage`와 형제.
- 월 피커(기본 이번 달, 이전/다음 달 이동). 계약×월 테이블: 계약·고객·방문수·청구합(+확정매출)·입금상태·정산합·미정산·정산상태. 행 펼치면 그 달 주문 목록(주문 상세로 링크).
- 행별 **[이 달 입금완료]** / **[이 달 정산완료]** 버튼 → 확인 모달(영향 건수) → 실행 후 재조회. **[CSV 내보내기]**.
- `api/recurring.ts`(또는 `recurringBilling.ts`)에 호출 추가. `.claude/rules/frontend.md`: 768px·로딩/에러/빈 3종·`apiRequest`/`downloadBlob`.

---

## 7. 테스트 (`pytest`)

1. **집계 정확성**: 소비자가 합·확정매출(매출 정의)·`payment_status` 분해·협력사 정산합·미정산(`unpaid_partner_condition`)·협력사별 소계 — `Decimal` 정확. 취소/삭제 주문 제외. 월 경계(`scheduled_date` 기준).
2. **mark-paid**: 미완분만 PAID, 이미 PAID/REFUNDED 스킵, 결제 타임라인 기록, 처리 건수.
3. **settle**: **완료 주문만**(미완료 스킵 — 가드), `PARTNER_SETTLED` 타임라인·`partner_settled_at`, 협력사별 정산.
4. **export**: CSV 헤더/행, 그 달·계약 필터.
5. **DTO 화이트리스트**: billing DTO가 협력사/고객 경로에 미노출.
6. **정의 일관성**: 같은 데이터에서 B의 확정매출 합 == 대시보드 매출 정의(회귀 가드).

---

## 8. 검증 명령
- 백엔드: `python -m pytest` + `ruff check .`(가능 시) + `python -m compileall app tests`.
- 프론트: `npm run typecheck` + `npm run lint` + `npm run build`(+ e2e 선택).
- 마이그레이션 없음(파생 집계).

---

## 9. 미해결/스펙 리뷰 확인 포인트
1. **mark-paid 대상 상태**: 모든 미완(`pending/balance_pending/unpaid/deposit_paid`)을 PAID로 — `deposit_paid`(계약금만 입금)도 PAID로 덮을지. → 기본: **PAID로 통일**(운영자가 "이 달 입금완료"를 누른 의미). 세분이 필요하면 후속.
2. **partner_vat 반영**: 협력사 정산합에 `partner_vat`(부가세 포함분)을 기존 정산 탭과 동일하게 계산할지 — **기존 `partner_settlements`/`reports.settlements` 계산과 일치**시킨다(구현 시 그 코드 참조).
3. **'월 정산' 진입**: 정기청소 페이지 내 상단 탭 vs 별도 네비. → 기본: **정기청소 페이지 내 탭**(계약/월 정산).
4. 전역 "모든 계약 이 달 일괄"은 v1 제외(계약 행 단위만). 필요 시 후속.
