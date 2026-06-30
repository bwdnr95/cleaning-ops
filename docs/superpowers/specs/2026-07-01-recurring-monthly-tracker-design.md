# 정기청소 '월 트래커' 재설계 (#4) 설계

- 작성일: 2026-07-01
- 범위: 정기청소를 **회차 주문 생성 → 월별 상태 트래커**로 전환. 계약×월 단위로 **세금계산서 발급여부 + 잔금입금여부**만 토글 관리.
- 전제: `main`(정기청소 A+B+partner+다중요일+260629/260630). 작업 브랜치 `feature/recurring-monthly-tracker`(main 분기). 규칙 `AGENTS.md`·`.claude/rules/*`.

---

## 0. 합의된 결정
- **월별 2토글**(세금계산서 발급 / 잔금입금) + **월 금액 표시**(계약의 `total_amount` 참조, 스냅샷 없음). '잔금입금'=그 달 입금 완료 Y/N(계약금/잔금 분리 없음).
- **회차 주문 생성·승인 + B(주문 집계) 제거**, B의 '월 정산' 화면을 **월 트래커**로 전환.
- **`RecurringOccurrence` 테이블은 비활성 유지**(drop 마이그 안 함, 데이터 없음). 생성/승인 코드·UI만 제거.
- 유지: `RecurringContract`(고객·스케줄=주기/다음청소일 표시용·월 금액), 계약 CRUD/라이프사이클/목록/폼/상세.

---

## 1. 새 모델 — 월별 상태
`backend/app/models/recurring_monthly_status.py`:

| 필드 | 타입 | 비고 |
|------|------|------|
| `id` | String(36) PK | uuid |
| `contract_id` | FK recurring_contracts.id, index | |
| `billing_month` | String(7) | "YYYY-MM" |
| `tax_invoice_issued` | Boolean, default False | 세금계산서 발급 여부 |
| `balance_paid` | Boolean, default False | 잔금(그 달 금액) 입금 여부 |
| (TimestampMixin) | | |

**UNIQUE `(contract_id, billing_month)`**. 마이그 **`0018_recurring_monthly_status`**(`down_revision="0017_recurring_weekdays"`). 실 Postgres(5434) 적용.

> 금액은 모델에 저장하지 않고 계약 `total_amount`를 표시 시 참조(단순).

---

## 2. 서비스 — `RecurringMonthlyService` (`backend/app/services/recurring_monthly.py`)
- `list_month(month: str) -> list[RecurringMonthlyRowRead]`:
  - 그 달에 **활성인 계약** 선정: `deleted_at IS NULL` AND `status == ACTIVE` AND `start_date <= 그 달 말일` AND (`end_date IS NULL` OR `end_date >= 그 달 1일`).
  - 각 계약에 대해 `(contract_id, month)` status 행을 **lazy upsert**(없으면 생성, 둘 다 False) — A의 sync 멱등 패턴.
  - 행 = 계약명/고객명/주기(schedule_text)/월 금액(total_amount)/tax_invoice_issued/balance_paid. (계약·그룹 메타는 기존 리포 재사용.)
  - 변경분 있으면 단일 commit.
- `set_status(contract_id, month, *, tax_invoice_issued=None, balance_paid=None, actor_user_id) -> RecurringMonthlyRowRead`:
  - `(contract_id, month)` 행 upsert 후 전달된 필드만 설정. 계약 없으면 ValueError("recurring_contract_not_found").
- 리포지토리 `RecurringMonthlyStatusRepository`(get_by_contract_and_month / list_by_month / add) — `.claude/rules/backend.md` 준수(`__init__(self, db)`·commit 금지).
- 월 경계 계산은 Python(KST `business_today` 기준 '이번 달' 기본), 활성 판정은 `calendar.monthrange`로 말일.

---

## 3. 라우트 (`backend/app/api/routes/admin/`)
**신규** (`recurring_monthly.py`, prefix `/admin/recurring/monthly`, 전부 `require_admin`):
- `GET /admin/recurring/monthly?month=YYYY-MM` → `list_month`(upsert+반환).
- `POST /admin/recurring/monthly/set` (body `{contract_id, month, tax_invoice_issued?, balance_paid?}`) → `set_status`. `_not_found`→404.

**제거**:
- `app/api/routes/admin/recurring.py`의 **occurrences 라우트**(`/occurrences/sync`·`/pending`·`/approve`·`/skip`). 계약 CRUD/pause/resume/end/delete는 유지.
- `app/api/routes/admin/recurring_billing.py`(B) 전체 + `router.py`의 `recurring_billing` 등록 제거.

---

## 4. 서비스/스키마 정리 (백엔드)
- `services/recurring.py`: **제거** `sync_due_occurrences`·`list_pending`·`list_pending_views`·`approve_occurrences`·`skip_occurrences`(+ 관련 import). **유지** 계약 CRUD·라이프사이클·`to_contract_read`·`list_contract_summaries`·`_spec`·`_next_due`·`_schedule_text`(주기/다음청소일 표시). `list_contract_summaries`에서 `pending_count`/`this_month_count`/`this_month_amount`는 의미 없어짐 → 제거하거나 0 유지(요약 DTO 정리).
- `schemas/recurring.py`: occurrence/approve/skip 관련 DTO(`PendingOccurrenceRead`·`ApproveItem`·`ApproveOccurrencesRequest/Result`·`SkipItem`·`SkipOccurrencesRequest/Result`·`RecurringOccurrenceRead`) **제거**. 신규 `schemas/recurring_monthly.py`(`RecurringMonthlyRowRead`·`SetMonthlyStatusRequest`).
- `services/recurring_billing.py`·`schemas/recurring_billing.py`·`domain/recurring_billing.py`·관련 테스트 **제거**(B 주문 집계).
- `repositories/recurring.py`의 `RecurringOccurrenceRepository`·`repositories/orders.py`의 `list_recurring_billing_orders`·`list_recurring_orders_in_month`는 **사용처 제거 후 미사용** → 제거 또는 유지(미사용). 권장: 미사용 메서드 제거(깔끔).
- `RecurringOccurrence` 모델/테이블: **유지(비활성)** — drop 안 함.

> 제거 시 import·테스트 동반 정리. 기존 recurring/billing 테스트 중 generation/aggregation 의존 테스트는 삭제, 계약 CRUD/스케줄 테스트는 유지.

---

## 5. 프론트엔드
- `features/admin/recurring/RecurringContractsPage.tsx`: **'승인 대기 회차' 패널 제거**. 진입 시 `sync` 호출 제거. 계약 목록 유지(요약에서 pending/이번달 집계 표기는 제거). 탭(계약 / 월 정산)은 **계약 / 월 트래커**로.
- `features/admin/recurring/RecurringBillingView.tsx` → **월 트래커로 전환**(파일 재사용 또는 `RecurringMonthlyTracker.tsx` 신규): 월 피커 + 계약별 행(계약명/고객/주기/월 금액/**세금계산서 토글**/**잔금입금 토글**). 토글 클릭 → `POST /monthly/set` 후 재조회. 일괄 입금/정산·CSV(B) 제거.
- `api/recurring.ts`(또는 `recurringMonthly.ts`): `getRecurringMonthly(month)`·`setRecurringMonthlyStatus(contractId, month, {tax_invoice_issued?, balance_paid?})`. 기존 `api/recurringBilling.ts`(B) 및 occurrences(sync/pending/approve/skip) 호출 제거.
- 주문 상세/목록의 '정기' 배지·역링크: 정기 주문이 더는 생성되지 않으므로 신규로는 안 뜸. 코드는 유지(기존 주문 보호) — 제거 불필요.

---

## 6. 테스트
1. 월 status **멱등 upsert**(두 번 호출 중복 없음, `(contract,month)` 유니크).
2. `set_status` 토글(세금계산서/잔금 각각), 계약 없으면 404.
3. 활성 계약 선정: start_date 이전 달 제외, end_date 이후 제외, PAUSED/ENDED/deleted 제외.
4. DTO admin 전용(협력사/고객 경로 미노출).
5. (회귀) 계약 CRUD/라이프사이클/스케줄 텍스트(다중요일 포함) 테스트 유지·그린.
6. 제거된 occurrences/billing 엔드포인트가 404(또는 라우트 부재).
7. 프론트 typecheck/lint/build + (선택) e2e(월 트래커 진입·토글).

---

## 7. 마이그/검증
- `0018_recurring_monthly_status` 작성 → 실 Postgres(5434) `alembic upgrade head` 적용(완료 기준).
- 백엔드 `pytest`+`compileall`, 프론트 `typecheck/lint/build`.

---

## 8. 미해결/리뷰 확인 포인트
1. 활성 월 범위: 그 달에 계약이 활성이면 행 생성(start~end 사이). 미래 달도 조회 가능(빈 토글) — 운영자가 미리 발급/입금 체크 가능.
2. 월 금액은 계약 `total_amount` 참조(스냅샷 없음) — 계약 금액 변경 시 과거 달 표시도 바뀜. 단순성 우선(요청대로).
3. `RecurringOccurrence`·미사용 리포 메서드: 제거 vs 유지 — 구현 시 "사용처 없는 코드는 제거, 테이블은 유지" 기준.
4. 기존에 승인된 정기 주문은 없음(확인). 있으면 주문관리 보존.
