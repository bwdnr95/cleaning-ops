# 정기청소 — 서브시스템 A (정기계약 + 회차 자동생성) 설계

- 작성일: 2026-06-28
- 범위: **서브시스템 A만.** 정기계약 등록 → 도래한 회차 제안 → 일괄 승인 → 주문 라인 생성.
- 범위 밖: **서브시스템 B (월 합산 청구·정산 배치)** — 별도 spec→plan→구현 사이클. 본 설계는 B가 붙을 연결고리(`recurring_contract_id`, `billing_month`)만 데이터에 심어둔다.
- 전제 규칙: `AGENTS.md`(역할별 DTO 화이트리스트, 협력사/고객 민감필드 차단, 운영 변경의 타임라인 기록, soft-delete, 미정산/매출 정의) + `.claude/rules/backend.md`·`frontend.md` 준수.

---

## 0. 합의된 결정 (브레인스토밍 결과)

| # | 결정 | 값 |
|---|------|-----|
| D1 | 회차 생성 방식 | **자동 제안 + 일괄 승인 (하이브리드).** 도래분을 화면 열 때 계산해 `PENDING`으로 노출, 운영자가 승인 시 실제 주문 생성. **별도 스케줄러/크론 불필요.** |
| D2 | 주기 종류 | **월간(지정일) + 주간(N주 간격·요일).** 요일 다회/RRULE은 범위 밖. |
| D3 | 회차→주문 구조 | **계약당 공유 `OrderGroup` 1개에 회차마다 `Order` 라인 누적.** 고객은 한 링크로 전체 정기 이력 열람. |
| D4 | 정산 범위 | **A는 계약+자동생성에 집중.** 월 합산 청구/정산(B)은 다음 사이클. |
| D5 | 협력사 배정 | **기본 협력사는 선택 입력.** 있으면 자동 배정 + `일정확정`, 없으면 미배정 + `신규접수`. |
| D6 | 회차 추적 | **원장 테이블 `RecurringOccurrence`** (PENDING/GENERATED/SKIPPED). |
| D7 | 계약용 그룹 | **계약 생성 시 빈 그룹 선제 생성** (고객링크 즉시 준비). |
| D8 | 일시정지 처리 | **PAUSED는 기존 PENDING을 유지**하고 화면에 '일시정지됨' 배지. 새 PENDING은 제안 안 함. |

---

## 1. 데이터 모델

### 1.1 신규 enum (`backend/app/domain/constants.py`)

```python
class RecurrenceMode(StrEnum):
    MONTHLY = "monthly"   # 매월 지정일
    WEEKLY = "weekly"     # N주 간격, 지정 요일

class RecurringContractStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"

class RecurringOccurrenceStatus(StrEnum):
    PENDING = "pending"       # 도래했으나 미생성 (승인 대기)
    GENERATED = "generated"   # 승인되어 주문 라인 생성됨
    SKIPPED = "skipped"       # 운영자가 건너뜀
```

**컬럼 타입 결정**: 기존 `Order.status`가 `String(40)` + enum 값 저장 패턴이므로, **신규 status/mode 컬럼도 `SAEnum`이 아닌 `String` + enum 값 저장으로 통일**한다(예: `status: Mapped[str] = mapped_column(String(20), default=RecurringContractStatus.ACTIVE)`). 즉 이 컬럼들엔 `SAEnum`을 쓰지 않는다. (만약 다른 곳에서 `SAEnum`을 도입한다면 그때는 `values_callable=lambda x: [e.value for e in x]` 필수 — `.claude/rules/backend.md`.)

### 1.2 `RecurringContract` (신규, `backend/app/models/recurring_contract.py`)

"고정 고객링크(공유 그룹) + 스케줄 + 회차 템플릿".

| 필드 | 타입 | 비고 |
|------|------|------|
| `id` | String(36) PK | uuid |
| `label` | String(160) | 계약명(목록 표시). 예: "강남빌딩 정기청소" |
| `order_group_id` | FK order_groups.id, index | 이 계약 전용 공유 그룹 (D7) |
| `recurrence_mode` | String(20) | MONTHLY \| WEEKLY |
| `day_of_month` | Integer, nullable | MONTHLY: 1~31 |
| `interval_weeks` | Integer, nullable | WEEKLY: 1=매주/2=격주/4=4주 |
| `weekday` | Integer, nullable | WEEKLY: 0=월 … 6=일 (`date.weekday()` 규약) |
| `start_date` | Date | 첫 회차 기준일 |
| `status` | String(20), index | ACTIVE \| PAUSED \| ENDED |
| `end_date` | Date, nullable | 종료 조건(택1). 둘 다 NULL=무기한 |
| `max_occurrences` | Integer, nullable | 종료 조건(택1) |
| `default_partner_id` | FK partners.id, nullable | (D5) |
| `team_name` | String(120), nullable | 템플릿 |
| `service_category_id` | FK service_categories.id, nullable | 템플릿 |
| `service_item_id` | FK service_items.id, nullable | 템플릿 |
| `service_name` | String(160) | 템플릿 |
| `size_or_quantity` | String(80), nullable | 템플릿 |
| `service_detail` | Text, nullable | 템플릿 |
| `special_request` | Text, nullable | 템플릿 |
| `requested_time` | String(80), nullable | 템플릿 |
| `total_amount` | Numeric(12,2), nullable | **1주기 고객 금액** |
| `discount_amount` | Numeric(12,2), default 0 | 템플릿 |
| `deposit_amount` | Numeric(12,2), nullable | 템플릿 |
| `balance_amount` | Numeric(12,2), nullable | 템플릿 |
| `vat_type` | String(20), nullable | 템플릿 |
| `partner_payment_amount` | Numeric(12,2), nullable | **협력사 1회 단가**(B 대비) |
| `deleted_at` | DateTime(tz), nullable, index | soft-delete |
| (TimestampMixin) | | created_at/updated_at |

고객정보(`customer_name/phone/address/address_detail`, `customer_visible_payment`, `notes`)는 **공유 `OrderGroup`에 보관**한다. 계약 폼이 이 값을 수집해 그룹을 생성/수정한다.

### 1.3 `RecurringOccurrence` (신규, `backend/app/models/recurring_occurrence.py`) — 회차 원장

| 필드 | 타입 | 비고 |
|------|------|------|
| `id` | String(36) PK | uuid |
| `contract_id` | FK recurring_contracts.id, index | |
| `sequence_no` | Integer | 계약 내 회차 순번(1,2,3…) |
| `due_date` | Date, index | 방문 예정일 |
| `billing_month` | String(7) | "YYYY-MM". **B 연결고리.** 기본 = due_date 기준월 |
| `status` | String(20), index | PENDING \| GENERATED \| SKIPPED |
| `generated_order_id` | FK orders.id, nullable | 승인 시 생성된 라인 |
| `generated_at` | DateTime(tz), nullable | |
| `skipped_reason` | String(200), nullable | |
| (TimestampMixin) | | |

**UNIQUE 제약 `(contract_id, due_date)`** — 멱등 upsert·중복생성 차단의 핵심.

### 1.4 `Order` 변경 (`backend/app/models/order.py`)

- `recurring_contract_id: Mapped[str | None] = mapped_column(ForeignKey("recurring_contracts.id"), index=True, nullable=True)` 추가.
- 용도: '정기' 배지·계약 역참조·B 집계. 기존 일회성 주문은 NULL.

### 1.5 마이그레이션 `0015_recurring_contracts`

- `down_revision="0014_partner_manager_phone"`.
- **테이블/컬럼 생성 순서(FK 의존성)**: ① `recurring_contracts`(order_groups·partners·service_* 는 기존) → ② `orders.recurring_contract_id` 컬럼 추가(→ recurring_contracts) → ③ `recurring_occurrences`(→ recurring_contracts·orders). 순환 FK가 아니므로 위 순서면 안전.
- ⚠️ **SQLite는 FK를 강제하지 않아 테스트로 FK 순서 버그를 못 잡는다**(메모 `sqlite-fk-not-enforced-gap`). **실 Postgres(앱 DB `cleaning_ops`, 포트 8002 / 5434)에서 `alembic upgrade head` 적용 확인을 완료 기준에 포함**한다(메모 `local-run-environments`).
- `.claude/rules/backend.md`: 코드 수정 전에 마이그레이션 작성 후 `alembic upgrade head` 먼저 실행.

---

## 2. 스케줄 계산 (순수 함수, `backend/app/domain/recurrence.py`)

스케줄 로직은 DB·서비스와 분리된 순수 헬퍼로 둔다(단위 테스트 용이).

### 2.1 due_date 열거: `iter_due_dates(contract, *, until: date) -> Iterator[tuple[int, date]]`

`start_date`부터 `until`까지의 `(sequence_no, due_date)`를 순서대로 산출.

- **MONTHLY**: `start_date`의 월부터 매월, 그 달의 `due_day = min(day_of_month, 그_달의_말일)`로 클램프(예: `day_of_month=31` → 2월은 28/29일). `start_date`의 첫 달은 due_day가 `start_date` 이상일 때만 포함(이전이면 다음 달부터).
- **WEEKLY**: `anchor = start_date` 기준, `due = anchor + k*interval_weeks*7` (k=0,1,2…). `start_date`는 `weekday`에 맞춰 폼에서 보정(또는 첫 due를 `start_date` 이후 첫 해당 요일로 정규화)한다.
- `max_occurrences`가 설정되면 `sequence_no > max_occurrences`에서 중단. `end_date`가 설정되면 `due_date > end_date`에서 중단.

### 2.2 KST

"오늘"·"이번 달"은 `datetime.now(KST).date()` 사용(`date.today()` 금지, `.claude/rules/backend.md`).

---

## 3. 회차 제안 → 승인 → 생성 플로우

### 3.1 동기화(제안) — `RecurringService.sync_due_occurrences()`

운영자가 정기청소 화면을 열 때 호출(`POST /admin/recurring/occurrences/sync`, side-effect 명시적). 스케줄러 대체.

1. `deleted_at IS NULL AND status == ACTIVE` 계약을 순회.
2. 각 계약에 대해 `iter_due_dates(contract, until = 오늘 + HORIZON_DAYS)` 계산. `HORIZON_DAYS` 기본 **14**(전역 상수).
3. 각 due_date가 원장에 없으면(`(contract_id, due_date)` 부재) `PENDING` 행 upsert(`billing_month` 채움). 이미 GENERATED/SKIPPED/PENDING이면 건드리지 않음 → **멱등**.
4. **과거 미생성분 노출**: due_date < 오늘이라도 미생성이면 PENDING으로 표시. 단 폭주 방지를 위해 `due_date >= 오늘 - OVERDUE_GRACE_DAYS`(기본 **30**)로 하한. (start_date가 먼 과거인 계약 보호 — ▶튜너블)
5. PAUSED/ENDED 계약은 신규 PENDING을 만들지 않음(D8). **기존 PENDING은 유지**.
6. 스케줄이 변경된 계약(2.x 수정)으로 인해 더 이상 유효하지 않은 **PENDING은 정리(삭제)**한다(GENERATED/SKIPPED는 보존).

### 3.2 승인 대기 조회 — `GET /admin/recurring/occurrences/pending`

PENDING 회차를 계약별로 묶어, 각 회차의 **생성될 주문 미리보기**(due_date, service_name, total_amount, default_partner)와 함께 반환. (sync 후 호출하거나, sync 응답에 동일 목록 포함)

### 3.3 승인(생성) — `POST /admin/recurring/occurrences/approve`

요청 바디: 승인할 회차 목록 + **회차별 보정값**.

```jsonc
{ "items": [
  { "occurrence_id": "...", "partner_id": "...", "scheduled_date": "2026-07-10",
    "total_amount": 150000, "team_name": "...", /* 그 외 라인 오버라이드 */ }
]}
```

처리(회차당, **한 트랜잭션**):
1. 회차 로드 후 `status == PENDING` 가드(아니면 스킵/409).
2. 계약 템플릿 + 회차 보정값을 머지해 `OrderLineCreate` 구성.
3. **초기 상태(D5)**:
   - 협력사(보정 우선, 없으면 `default_partner_id`) 있음 → `partner_id` 채움, `status=일정확정(SCHEDULE_CONFIRMED)`, `scheduled_date=due_date`.
   - 없음 → `partner_id=None`, `status=신규접수(NEW)`, `scheduled_date=due_date`.
   - 공통: `received_date = 오늘(KST)`.
4. 계약 그룹에 라인 생성(아래 3.5 참고) + `recurring_contract_id` 스탬프.
5. 타임라인: `CREATED`("주문 생성") + 협력사 있으면 `PARTNER_ASSIGNED`. (기존 `_create_line_internal` 동작과 동일)
6. 회차 → `GENERATED`, `generated_order_id`, `generated_at` 기록.

### 3.4 건너뛰기 — `POST /admin/recurring/occurrences/skip`

`{ "items": [ { "occurrence_id": "...", "reason": "고객 휴무" } ] }` → 회차 `SKIPPED` + `skipped_reason`. PENDING만 허용.

### 3.5 라인 생성의 트랜잭션 경계 (구현 주의)

기존 `OrderService.add_line_to_group`는 **내부에서 `commit()`** 한다. 그러나 승인은 "라인 생성 + 회차 GENERATED 갱신"을 **한 트랜잭션**으로 묶어야 한다. 따라서:
- `OrderService._create_line_internal`(commit 안 함)을 재사용하되, `recurring_contract_id`를 받을 수 있게 확장하거나, `RecurringService`가 `_create_line_internal` 호출 → 반환 Order에 `recurring_contract_id` 설정 → 회차 갱신 → **`RecurringService`가 단일 `commit()` 소유**.
- 리포지토리는 commit 금지(`.claude/rules/backend.md`), 트랜잭션은 서비스(caller)가 관리.

---

## 4. 계약 라이프사이클

- **생성**(`POST /admin/recurring/contracts`): 빈 `OrderGroup` 선제 생성(D7) + `RecurringContract` 생성. → **`OrderService`에 "라인 0개 그룹 생성" 경로 추가** 필요(현재 `create_group`은 `at_least_one_line_required` 가드, `orders.py:144`). 신규 메서드 `create_empty_group(payload)` 또는 `create_group(..., allow_empty=True)`.
- **수정**(`PATCH /admin/recurring/contracts/{id}`): **미래 회차 계산·미래 생성 라인에만 영향.** 이미 생성된 주문은 불변. ⚠️ **고객정보 수정은 공유 그룹을 통해 전 회차 라인에 영향**(D3 공유 구조의 본질) — 폼/안내문에 명시. 스케줄 변경 시 무효 PENDING 정리(3.1.6).
- **일시정지/재개/종료**: `POST .../{id}/pause|resume|end` (또는 PATCH status). PAUSED→제안 중단·기존 PENDING 유지(D8). end_date 경과/ max_occurrences 도달은 sync 시 자동 ENDED 전환.
- **소프트삭제**(`DELETE /admin/recurring/contracts/{id}`): 계약 `deleted_at` 채움. **이미 생성된 주문은 주문관리에 그대로 보존**(삭제 안 함). 모든 계약 조회는 `deleted_at IS NULL`(`AGENTS.md` Delete Policy 준수).

---

## 5. 백엔드 — 레이어·스키마·라우트

### 5.1 레이어 (기존 strict 레이어링 준수)
- `models/recurring_contract.py`, `models/recurring_occurrence.py`
- `repositories/recurring.py` — `RecurringContractRepository`, `RecurringOccurrenceRepository`. 생성자 `def __init__(self, db: Session): self.db = db`, **commit 금지(flush만)**, SQLAlchemy 2.0 `select()+where()`, PK 파라미터 `contract_id`·`occurrence_id`.
- `services/recurring.py` — `RecurringService`(계약 CRUD, sync_due_occurrences, approve, skip, lifecycle). `OrderService`/`TimelineService` 협업. 트랜잭션 소유.
- `domain/recurrence.py` — 순수 스케줄 계산.
- `schemas/recurring.py` — 역할별 DTO(아래).
- `api/routes/admin/recurring.py` — `require_admin` 가드. `router.py`에 `prefix="/admin/recurring"`로 등록.

### 5.2 DTO (화이트리스트, `AGENTS.md`)
- 신규 스키마: `AdminRecurringContractCreate/Update/Read`, `RecurringContractSummaryRead`(목록+이번달 회차수/합계), `RecurringOccurrenceRead`, `PendingOccurrenceRead`(미리보기 포함), `ApproveOccurrencesRequest`, `SkipOccurrencesRequest`.
- **`Order.recurring_contract_id`는 `to_admin_order_dto`에만 추가.** `to_partner_job_dto`·`to_customer_order_dto`에는 **미포함**(내부 운영 메타 — 기존 `partner_payment_*`/`evidence_memo` 차단 정책과 동일). 계약/회차 엔티티 전체가 admin 전용.

### 5.3 엔드포인트 요약 (모두 `require_admin`)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/admin/recurring/contracts` | 계약 목록(+요약) |
| POST | `/admin/recurring/contracts` | 계약 생성(빈 그룹+계약) |
| GET | `/admin/recurring/contracts/{id}` | 상세(+회차 목록+이번달 요약) |
| PATCH | `/admin/recurring/contracts/{id}` | 수정(미래만 반영) |
| POST | `/admin/recurring/contracts/{id}/pause` `…/resume` `…/end` | 라이프사이클 |
| DELETE | `/admin/recurring/contracts/{id}` | 소프트삭제 |
| POST | `/admin/recurring/occurrences/sync` | 도래분 계산·upsert·반환 (화면 열 때) |
| GET | `/admin/recurring/occurrences/pending` | PENDING 목록(+미리보기) |
| POST | `/admin/recurring/occurrences/approve` | 일괄 승인→주문 생성 |
| POST | `/admin/recurring/occurrences/skip` | 일괄 건너뛰기 |

---

## 6. 프론트엔드

- `components/layout/AdminShell.tsx`의 `NAV` 배열에 `{ key: 'recurring', label: '정기청소', icon: <기존 아이콘 중 택1> }` 추가(아이콘은 `common/ui`의 `Icon` 지원 목록에서 선택; 미지원이면 추가). `App.tsx`에 페이지 라우팅 연결.
- `api/recurring.ts` — `apiGet/apiPost`(raw fetch 금지, `.claude/rules/frontend.md`).
- `domain/recurrence.ts` — mode/status 라벨·배지 색상, 스케줄 사람이 읽는 문자열("매월 10일", "격주 화요일") 포맷.
- 화면(`features/admin/recurring/`):
  - `RecurringContractsPage.tsx` — 계약 목록(계약명/고객·주기·다음 회차일·상태·이번달 회차수/합계) + **승인 대기 패널**(PENDING 일괄 승인/건너뛰기; 전체선택은 협력사 정산 그리드 패턴 재사용). 화면 진입 시 `sync` 호출.
  - `RecurringContractForm.tsx` — 생성/수정(고객정보 + 스케줄 + 템플릿 + 기본 협력사 + 라이프사이클). `OrderFormPage` 패턴 차용.
  - `RecurringContractDetail.tsx` — 상세 + 회차 원장 + 이번달 요약 + 라이프사이클 액션.
- 주문 상세/목록: `recurring_contract_id` 있으면 **'정기' 배지** + 계약으로 역링크.
- 공통: 데스크탑+모바일 768px 분기, 로딩/에러/빈 3종 처리, iOS input 16px(`.claude/rules/frontend.md`).

---

## 7. B(월 합산 청구·정산) 연결고리 — 지금 심어두는 것만

- `Order.recurring_contract_id`, `RecurringOccurrence.billing_month`(YYYY-MM), 계약/회차 FK.
- B는 추후 `(contract_id, billing_month)`로 회차·주문을 **집계만** 하면 됨. **B의 배치·화면·청구 상태머신은 본 범위 밖.**

---

## 8. 테스트 (`backend/tests/`, `pytest`)

1. **스케줄 계산**(`domain/recurrence.py` 순수 단위): 월간 일반/말일 클램프(31일→2월), 월간 첫 달 경계, 주간 매주/격주/4주, `end_date`/`max_occurrences` 종료.
2. **멱등 sync**: 두 번 호출해도 PENDING 중복 생성 없음(`(contract_id, due_date)` 유니크). PAUSED/ENDED 미제안. 과거 미생성분 노출(+OVERDUE_GRACE 하한). 스케줄 변경 시 무효 PENDING 정리.
3. **승인**: 협력사 있음→라인 `일정확정`+`partner_id`+`PARTNER_ASSIGNED`+`CREATED` 타임라인; 없음→`신규접수`. `recurring_contract_id` 스탬프. 회차 `GENERATED`+`generated_order_id`. 라인+회차 **원자성**(중간 실패 시 롤백). 이미 GENERATED 회차 재승인 차단.
4. **건너뛰기**: PENDING→SKIPPED, 사유 저장.
5. **라이프사이클**: 빈 그룹 선제 생성, 수정은 미래만 반영(기존 주문 불변), 고객정보 수정이 공유 그룹 전 라인에 반영, 소프트삭제 후 계약 조회 제외 + **생성 주문은 보존**.
6. **DTO 화이트리스트**: `recurring_contract_id`·계약/회차 필드가 **협력사/고객 DTO에 미노출**(기존 비노출 테스트 패턴 확장).
7. (선택) E2E: 계약 생성 → sync → 승인 → 주문관리에 라인 등장 → '정기' 배지.

---

## 9. 검증 명령
- 백엔드: `python -m pytest` + `ruff check .` + `python -m compileall app tests`.
- 마이그레이션: `python -m alembic upgrade head --sql`(렌더) → 실 Postgres `alembic upgrade head`(8002/5434) 적용 확인.
- 프론트: `npm run typecheck` + `npm run lint` + `npm run build`.

---

## 10. 미해결/스펙 리뷰 확인 포인트
1. **WEEKLY `weekday` 정규화**: `start_date`가 `weekday`와 다를 때 — 폼에서 강제 일치 vs 첫 due를 `start_date` 이후 첫 해당 요일로 자동 보정. → 기본: **폼에서 `start_date` 선택 시 weekday 자동 동기화**(둘 중 단순).
2. **HORIZON_DAYS=14 / OVERDUE_GRACE_DAYS=30** 기본값 — 운영 감각에 맞는지(추후 설정화 가능).
3. **계약 라이프사이클 로그**: 별도 contract 타임라인 테이블은 v1 미도입(주문 타임라인만). 필요 시 `audit_log` 또는 후속.
4. **메시지 연동**: 회차 생성 시 협력사 배정/고객 일정확정 안내 메시지를 **자동 발송할지**는 v1 범위 밖(운영자가 기존 주문 화면에서 수동 발송). 후속 검토.
5. **데모 시드**: QA용 정기계약 1건 시드 추가는 선택(권장).
