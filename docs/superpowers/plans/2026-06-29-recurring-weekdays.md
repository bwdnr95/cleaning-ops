# 정기청소 다중 요일 주기 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 주간 정기청소에서 한 주에 여러 요일(예: 매주 월·수·금)을 선택할 수 있게 한다(기존 매주/격주/4주 간격과 조합).

**Architecture:** WEEKLY에 요일 집합을 추가한다. 저장은 `recurring_contracts.weekdays`(CSV) 신설 + 레거시 단일 `weekday` 폴백. 스케줄 생성은 현재 단일요일 로직의 일반화(활성 주마다 선택된 각 요일 생성). 검증 변경 없음(요일 미선택 시 `start_date.weekday()`로 폴백). B(월 정산)는 무변경.

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy 2.0 / Alembic / Pydantic / pytest, Vite + React 19 + TS.

**설계 출처:** `docs/superpowers/specs/2026-06-29-recurring-weekdays-design.md`. 브랜치 `feature/recurring-weekdays`(main에서 분기). 규칙 `AGENTS.md`·`.claude/rules/*`.

---

## File Structure
- Modify: `backend/app/domain/recurrence.py`(helpers + ScheduleSpec + iter_due_dates), `backend/app/models/recurring_contract.py`(컬럼), `backend/app/schemas/recurring.py`(weekdays), `backend/app/services/recurring.py`(직렬화·_spec·_schedule_text·to_contract_read)
- Create: `backend/alembic/versions/0017_recurring_weekdays.py`
- Frontend Modify: `frontend/src/api/recurring.ts`, `frontend/src/domain/recurrence.ts`, `frontend/src/features/admin/recurring/RecurringContractForm.tsx`
- Tests: `backend/tests/test_recurrence_weekdays.py`, 기존 `test_recurring_service.py` 확장

---

## Task 1: 스케줄 도메인 — 다중요일 (helpers + ScheduleSpec + iter_due_dates)

**Files:**
- Modify: `backend/app/domain/recurrence.py`
- Test: `backend/tests/test_recurrence_weekdays.py`

- [ ] **Step 1: 실패 테스트** — `backend/tests/test_recurrence_weekdays.py`

```python
from datetime import date

from app.domain.constants import RecurrenceMode
from app.domain.recurrence import (
    ScheduleSpec,
    format_weekdays_csv,
    iter_due_dates,
    parse_weekdays_csv,
)


def _dates(spec, until):
    return [d for _, d in iter_due_dates(spec, until=until)]


def test_csv_helpers_roundtrip_and_normalize():
    assert parse_weekdays_csv("0,2,4") == (0, 2, 4)
    assert parse_weekdays_csv("4,0,2,2") == (0, 2, 4)  # 정렬+중복제거
    assert parse_weekdays_csv("") == ()
    assert parse_weekdays_csv(None) == ()
    assert format_weekdays_csv([4, 0, 2]) == "0,2,4"
    assert format_weekdays_csv([]) is None
    assert format_weekdays_csv(None) is None


def test_weekly_multi_weekday_every_week():
    # 2026-06-01 = 월요일. 매주 월(0)·수(2)·금(4).
    spec = ScheduleSpec(
        mode=RecurrenceMode.WEEKLY, start_date=date(2026, 6, 1), interval_weeks=1, weekdays=(0, 2, 4)
    )
    out = _dates(spec, until=date(2026, 6, 14))
    assert out == [
        date(2026, 6, 1), date(2026, 6, 3), date(2026, 6, 5),   # 1주차 월수금
        date(2026, 6, 8), date(2026, 6, 10), date(2026, 6, 12),  # 2주차 월수금
    ]


def test_weekly_first_week_skips_days_before_start():
    # start=수(2026-06-03). 매주 월·수·금 → 첫 주는 수·금만(월은 start 이전).
    spec = ScheduleSpec(
        mode=RecurrenceMode.WEEKLY, start_date=date(2026, 6, 3), interval_weeks=1, weekdays=(0, 2, 4)
    )
    out = _dates(spec, until=date(2026, 6, 10))
    assert out == [date(2026, 6, 3), date(2026, 6, 5), date(2026, 6, 8), date(2026, 6, 10)]


def test_weekly_biweekly_multi_weekday():
    # 2026-06-01=월. 격주 월·금.
    spec = ScheduleSpec(
        mode=RecurrenceMode.WEEKLY, start_date=date(2026, 6, 1), interval_weeks=2, weekdays=(0, 4)
    )
    out = _dates(spec, until=date(2026, 6, 30))
    assert out == [
        date(2026, 6, 1), date(2026, 6, 5),    # 1주차
        date(2026, 6, 15), date(2026, 6, 19),  # 3주차(격주)
        date(2026, 6, 29),                      # 5주차 월(금=7/3은 until 초과)
    ]


def test_weekly_falls_back_to_weekday_then_start_weekday():
    # weekdays 없으면 weekday, 그것도 없으면 start_date.weekday()
    spec_wd = ScheduleSpec(
        mode=RecurrenceMode.WEEKLY, start_date=date(2026, 6, 1), interval_weeks=1, weekday=2
    )  # 수
    assert _dates(spec_wd, until=date(2026, 6, 11)) == [date(2026, 6, 3), date(2026, 6, 10)]
    spec_none = ScheduleSpec(
        mode=RecurrenceMode.WEEKLY, start_date=date(2026, 6, 1), interval_weeks=1
    )  # 월(=start 요일)
    assert _dates(spec_none, until=date(2026, 6, 9)) == [date(2026, 6, 1), date(2026, 6, 8)]


def test_weekly_multi_weekday_respects_end_and_max():
    spec = ScheduleSpec(
        mode=RecurrenceMode.WEEKLY, start_date=date(2026, 6, 1), interval_weeks=1,
        weekdays=(0, 2, 4), max_occurrences=2,
    )
    assert _dates(spec, until=date(2026, 12, 1)) == [date(2026, 6, 1), date(2026, 6, 3)]
    spec2 = ScheduleSpec(
        mode=RecurrenceMode.WEEKLY, start_date=date(2026, 6, 1), interval_weeks=1,
        weekdays=(0, 2, 4), end_date=date(2026, 6, 3),
    )
    assert _dates(spec2, until=date(2026, 12, 1)) == [date(2026, 6, 1), date(2026, 6, 3)]
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python -m pytest tests/test_recurrence_weekdays.py -q`
Expected: FAIL — `ImportError: cannot import name 'parse_weekdays_csv'`.

- [ ] **Step 3: 구현** — `backend/app/domain/recurrence.py`

(a) `ScheduleSpec`에 필드 추가(기존 dataclass의 `weekday` 아래):
```python
    weekdays: tuple[int, ...] | None = None
```

(b) 파일에 helper 2개 추가(`billing_month_of` 근처):
```python
def parse_weekdays_csv(value: str | None) -> tuple[int, ...]:
    """CSV "0,2,4" → (0,2,4). 정렬·중복제거. 빈 값/None → ()."""
    if not value:
        return ()
    return tuple(sorted({int(p) for p in value.split(",") if p.strip() != ""}))


def format_weekdays_csv(weekdays) -> str | None:
    """[4,0,2] → "0,2,4". 빈 값/None → None(미선택)."""
    if not weekdays:
        return None
    return ",".join(str(w) for w in sorted({int(x) for x in weekdays}))
```

(c) `iter_due_dates`의 **WEEKLY 분기를 통째로 교체**:
```python
    elif spec.mode == RecurrenceMode.WEEKLY:
        if not spec.interval_weeks:
            raise ValueError("interval_weeks_required_for_weekly")
        # 폴백 체인: weekdays → weekday → start_date 요일
        wds = spec.weekdays or (
            (spec.weekday,) if spec.weekday is not None else (spec.start_date.weekday(),)
        )
        wds = tuple(sorted(set(wds)))
        anchor_monday = spec.start_date - timedelta(days=spec.start_date.weekday())
        step = timedelta(weeks=spec.interval_weeks)
        week_monday = anchor_monday
        while True:
            if week_monday > until:
                return
            for w in wds:
                due = week_monday + timedelta(days=w)
                if due < spec.start_date:
                    continue
                if due > until:
                    break  # 이 주의 나머지 요일도 초과 → 다음 주
                if spec.end_date is not None and due > spec.end_date:
                    return
                seq += 1
                if spec.max_occurrences is not None and seq > spec.max_occurrences:
                    return
                yield seq, due
            week_monday = week_monday + step
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && python -m pytest tests/test_recurrence_weekdays.py tests/test_recurrence_schedule.py -q`
Expected: PASS (신규 + 기존 단일요일 회귀 그린).

- [ ] **Step 5: 커밋**

```bash
git add backend/app/domain/recurrence.py backend/tests/test_recurrence_weekdays.py
git commit -m "feat(recurring): WEEKLY 다중요일 생성 + CSV helper(단일요일 일반화)"
```

---

## Task 2: 모델 컬럼 + 마이그레이션 0017

**Files:**
- Modify: `backend/app/models/recurring_contract.py`
- Create: `backend/alembic/versions/0017_recurring_weekdays.py`
- Test: `backend/tests/test_recurring_weekdays_model.py`

- [ ] **Step 1: 실패 테스트** — `backend/tests/test_recurring_weekdays_model.py`

```python
from datetime import date
from uuid import uuid4

from app.domain.constants import RecurrenceMode, RecurringContractStatus
from app.models.order_group import OrderGroup
from app.models.recurring_contract import RecurringContract


def test_contract_persists_weekdays_csv(db_session):
    group = OrderGroup(
        id=str(uuid4()), customer_token=f"t-{uuid4()}", customer_name="C",
        customer_phone="01000000000", customer_address="A", customer_visible_payment=False,
    )
    db_session.add(group)
    db_session.flush()
    c = RecurringContract(
        id=str(uuid4()), label="L", order_group_id=group.id, recurrence_mode=RecurrenceMode.WEEKLY,
        interval_weeks=1, weekdays="0,2,4", start_date=date(2026, 6, 1),
        status=RecurringContractStatus.ACTIVE, service_name="S",
    )
    db_session.add(c)
    db_session.flush()
    assert c.weekdays == "0,2,4"
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python -m pytest tests/test_recurring_weekdays_model.py -q`
Expected: FAIL — `TypeError: 'weekdays' is an invalid keyword argument for RecurringContract`.

- [ ] **Step 3: 모델 컬럼 추가** — `backend/app/models/recurring_contract.py`의 `weekday` 컬럼 아래에 추가:

```python
    weekdays: Mapped[str | None] = mapped_column(String(20))  # CSV "0,2,4" (다중요일). 레거시 weekday와 병행.
```

- [ ] **Step 4: 마이그레이션** — `backend/alembic/versions/0017_recurring_weekdays.py`

```python
"""정기청소 다중요일 — recurring_contracts.weekdays

Revision ID: 0017_recurring_weekdays
Revises: 0016_message_recipient_partner_id
Create Date: 2026-06-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0017_recurring_weekdays"
down_revision = "0016_message_recipient_partner_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("recurring_contracts", sa.Column("weekdays", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("recurring_contracts", "weekdays")
```

- [ ] **Step 5: 통과 + 렌더 확인**

Run: `cd backend && python -m pytest tests/test_recurring_weekdays_model.py -q && python -m alembic upgrade 0016_message_recipient_partner_id:0017_recurring_weekdays --sql 2>&1 | tail -5`
Expected: 테스트 PASS + `ALTER TABLE recurring_contracts ADD COLUMN weekdays` 렌더.

- [ ] **Step 6: 커밋**

```bash
git add backend/app/models/recurring_contract.py backend/alembic/versions/0017_recurring_weekdays.py backend/tests/test_recurring_weekdays_model.py
git commit -m "feat(recurring): recurring_contracts.weekdays 컬럼 + 마이그 0017"
```

---

## Task 3: 스키마 + 서비스 (직렬화·_spec·schedule_text·read)

**Files:**
- Modify: `backend/app/schemas/recurring.py`, `backend/app/services/recurring.py`
- Test: `backend/tests/test_recurring_service.py`(확장)

- [ ] **Step 1: 실패 테스트 추가** — `backend/tests/test_recurring_service.py` 끝에 추가

```python
def test_create_weekly_contract_with_weekdays_generates_multiple_per_week(db_session):
    from app.schemas.recurring import ApproveItem, RecurringContractCreate
    from app.services.recurring import RecurringService
    svc = RecurringService(db_session)
    c = svc.create_contract(
        RecurringContractCreate(
            label="다중요일", customer_name="강남", customer_phone="01011112222", customer_address="A",
            recurrence_mode="weekly", interval_weeks=1, weekdays=[0, 2, 4],
            start_date=date(2026, 6, 1), service_name="청소", total_amount=100000,
        ),
        actor_user_id=None,
    )
    assert svc.get_contract(c.id).weekdays == "0,2,4"  # CSV로 저장
    read = svc.to_contract_read(c)
    assert read.weekdays == [0, 2, 4]                  # list로 복원
    # 2026-06-01~07 한 주에 월·수·금 3건 도래
    n = svc.sync_due_occurrences(today=date(2026, 6, 7))
    dues = sorted(o.due_date for o in svc.occurrences.list_by_contract(c.id))
    assert dues == [date(2026, 6, 1), date(2026, 6, 3), date(2026, 6, 5)]


def test_schedule_text_weekly_multiple(db_session):
    from app.schemas.recurring import RecurringContractCreate
    from app.services.recurring import RecurringService
    svc = RecurringService(db_session)
    c = svc.create_contract(
        RecurringContractCreate(
            label="x", customer_name="c", customer_phone="01000000000", customer_address="A",
            recurrence_mode="weekly", interval_weeks=1, weekdays=[0, 2, 4],
            start_date=date(2026, 6, 1), service_name="청소",
        ),
        actor_user_id=None,
    )
    assert svc.list_contract_summaries()[0].schedule_text in ("매주 월·수·금",)
```

> 참고: `sync_due_occurrences(today=...)`의 호라이즌은 HORIZON_DAYS(14)·grace(30). today=2026-06-07이면 6/1·6/3·6/5(과거 grace 내) + 6/8·6/10·6/12(미래 14일 내)도 잡힐 수 있다. 위 단언이 6/1·6/3·6/5만 기대하면 깨질 수 있으니, **today를 6/5로 두거나** 단언을 "6/1·6/3·6/5 ⊆ dues"로 완화하라(구현 시 실제 horizon에 맞춰 조정). 핵심은 한 주에 3건이 생성되는 것.

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python -m pytest tests/test_recurring_service.py -k "weekdays or schedule_text_weekly_multiple" -q`
Expected: FAIL (weekdays 필드 없음 / CSV 미저장).

- [ ] **Step 3: 스키마** — `backend/app/schemas/recurring.py`

`RecurringContractBase`의 `weekday` 아래에 추가:
```python
    weekdays: list[int] | None = None
```
`RecurringContractUpdate`에도 동일 추가:
```python
    weekdays: list[int] | None = None
```
(`RecurringContractRead`는 Base 상속이라 자동 포함. 값 검증은 도메인 폴백이 흡수하므로 별도 제약 없음 — 0~6 범위는 폼에서 보장.)

- [ ] **Step 4: 서비스** — `backend/app/services/recurring.py`

상단 import에 helper 추가:
```python
from app.domain.recurrence import (
    HORIZON_DAYS,
    OVERDUE_GRACE_DAYS,
    ScheduleSpec,
    billing_month_of,
    format_weekdays_csv,
    iter_due_dates,
    parse_weekdays_csv,
    validate_recurrence_fields,
)
```

`create_contract`: `data = payload.model_dump()` 직후, 그룹필드 제거 루프 **앞 또는 뒤**에 weekdays 직렬화 추가:
```python
        if data.get("weekdays") is not None:
            data["weekdays"] = format_weekdays_csv(data["weekdays"])
```
(이러면 `RecurringContract(**data)`에 CSV 문자열/None이 들어간다.)

`update_contract`: changes 적용 루프 **앞**에 추가:
```python
        if "weekdays" in changes:
            changes["weekdays"] = format_weekdays_csv(changes["weekdays"])
```

`_spec`: `ScheduleSpec(...)`에 weekdays 추가:
```python
            weekdays=parse_weekdays_csv(contract.weekdays) or None,
```

`to_contract_read`: 병합 dict에서 weekdays를 list로 덮어쓰기(컬럼 값은 CSV이므로). `data = {...}` 구성 후 `model_validate` 전에:
```python
        data["weekdays"] = list(parse_weekdays_csv(contract.weekdays)) or None
```

`_schedule_text`: WEEKLY 분기를 다중요일로 교체:
```python
    def _schedule_text(self, contract: RecurringContract) -> str:
        if contract.recurrence_mode == RecurrenceMode.MONTHLY:
            return f"매월 {contract.day_of_month}일"
        weekday_ko = ["월", "화", "수", "목", "금", "토", "일"]
        every = {1: "매주", 2: "격주"}.get(contract.interval_weeks, f"{contract.interval_weeks}주마다")
        wds = parse_weekdays_csv(contract.weekdays)
        if not wds:
            wds = (contract.weekday,) if contract.weekday is not None else (contract.start_date.weekday(),)
        days = "·".join(weekday_ko[w] for w in sorted(set(wds)))
        return f"{every} {days}"
```

> `validate_recurrence_fields`는 **변경하지 않는다**(WEEKLY는 interval_weeks만 필수, 요일은 폴백으로 항상 ≥1).

- [ ] **Step 5: 통과 확인 + 회귀**

Run: `cd backend && python -m pytest tests/test_recurring_service.py tests/test_recurring_api.py -q`
Expected: PASS(신규 + 기존 그린).

- [ ] **Step 6: 커밋**

```bash
git add backend/app/schemas/recurring.py backend/app/services/recurring.py backend/tests/test_recurring_service.py
git commit -m "feat(recurring): weekdays 스키마/서비스 직렬화·스케줄텍스트·read"
```

---

## Task 4: 백엔드 전체 검증 + Postgres 0017 적용

- [ ] **Step 1: 전체 테스트** — Run: `cd backend && python -m pytest -q` → 전부 PASS(회귀 0).
- [ ] **Step 2: 컴파일** — Run: `cd backend && python -m compileall app tests` → exit 0.
- [ ] **Step 3: 실 Postgres 적용** — Run:
  `cd backend && DATABASE_URL="postgresql+psycopg2://cleanops:cleanops_local_dev@localhost:5434/cleaning_ops" python -m alembic upgrade head`
  그 후 같은 DATABASE_URL로 `python -m alembic current` → `0017_recurring_weekdays (head)` 확인.
- [ ] **Step 4:** 코드 변경 없으면 커밋 없음.

---

## Task 5: 프론트엔드 (API 타입 + 스케줄 텍스트 + 폼 다중요일)

**Files:**
- Modify: `frontend/src/api/recurring.ts`, `frontend/src/domain/recurrence.ts`, `frontend/src/features/admin/recurring/RecurringContractForm.tsx`

- [ ] **Step 1: API 타입** — `frontend/src/api/recurring.ts`

`RecurringContractInput`과 `RecurringContract`에 추가:
```ts
  weekdays?: number[] | null;
```

- [ ] **Step 2: 스케줄 텍스트(있으면)** — `frontend/src/domain/recurrence.ts`에 `WEEKDAY_LABEL`이 있으면 재사용. 목록/상세는 백엔드 `schedule_text`를 그대로 쓰므로 추가 작업 불필요. (없으면 표시용으로 `WEEKDAY_LABEL = ['월','화','수','목','금','토','일']` export.)

- [ ] **Step 3: 폼 다중요일 토글** — `frontend/src/features/admin/recurring/RecurringContractForm.tsx`

(a) state: 기존 weekday 자동동기화(`set('weekday', ...)`) useEffect를 **제거**하고 weekdays 배열을 관리. 폼 초기값(EMPTY)에 영향 없음(weekdays 미설정=undefined).

(b) weekly 분기 UI(간격 select 아래)에 요일 토글 추가:
```jsx
{form.recurrence_mode === 'weekly' && (
  <label>요일 선택
    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
      {['월','화','수','목','금','토','일'].map((lbl, idx) => {
        const on = (form.weekdays ?? []).includes(idx);
        return (
          <button type="button" key={idx} data-testid={`rc-weekday-${idx}`}
            onClick={() => set('weekdays',
              on ? (form.weekdays ?? []).filter((w) => w !== idx)
                 : [...(form.weekdays ?? []), idx].sort((a, b) => a - b))}
            style={{
              minWidth: 40, height: 36, borderRadius: 6, fontSize: 14,
              border: '1px solid var(--border)',
              background: on ? 'var(--brand-bg)' : 'var(--surface)',
              color: on ? 'var(--brand)' : 'var(--text-secondary)', fontWeight: on ? 700 : 400,
            }}>{lbl}</button>
        );
      })}
    </div>
  </label>
)}
```

(c) submit payload: weekly면 `weekdays`(배열, 최소 1개) 포함, monthly면 `weekdays: null`. 저장 검증: weekly인데 `(form.weekdays ?? []).length === 0`이면 저장 비활성/경고(`rc-submit` disabled 또는 alert). 기존 `day_of_month`/`interval_weeks` 정리 로직 옆에:
```jsx
        weekdays: form.recurrence_mode === 'weekly' ? (form.weekdays ?? []) : null,
```
그리고 저장 버튼 disabled 조건에 `|| (form.recurrence_mode === 'weekly' && (form.weekdays ?? []).length === 0)` 추가.

- [ ] **Step 4: 검증** — Run: `cd frontend && npm run typecheck && npm run lint && npm run build` → 통과.

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/api/recurring.ts frontend/src/domain/recurrence.ts frontend/src/features/admin/recurring/RecurringContractForm.tsx
git commit -m "feat(recurring): 계약 폼 요일 다중선택(weekly)"
```

---

## Task 6: 최종 검증

- [ ] **Step 1: 백엔드** — Run: `cd backend && python -m pytest -q` → 전부 PASS.
- [ ] **Step 2: 프론트** — Run: `cd frontend && npm run typecheck && npm run lint && npm run build` → green.
- [ ] **Step 3: (선택) e2e** — 기존 `recurring.spec.ts`가 그린인지(`npm run e2e -- recurring.spec.ts`). 다중요일 단언 추가는 선택. e2e 인프라 불안정하면 루프 말고 보고.
- [ ] **Step 4:** 변경 없으면 커밋 없음.

---

## Self-Review (작성자 체크리스트 결과)

**1. Spec coverage:** §1 모델/마이그→T2, §2 스케줄 계산→T1, §3 검증(폴백으로 충족·무변경)→T1·T3 명시, §4 스키마/서비스→T3, §5 프론트→T5, §6 B 무변경→해당없음, §7 테스트→T1·T3·T6, §8 마이그/검증→T4. ✅
- 스펙 §3은 "WEEKLY는 interval+요일 필요"였으나, 폴백(start_date.weekday())으로 항상 ≥1요일이 보장되어 **validate_recurrence_fields 변경 불필요**로 단순화(스펙 의도 충족). T3 Step4에 명시.

**2. Placeholder scan:** 실제 코드 포함. T3 Step1의 sync 단언 horizon 주의는 구현자에게 명확한 조정 지시(공백 아님).

**3. Type consistency:** `parse_weekdays_csv`(str→tuple)·`format_weekdays_csv`(list→str|None)(T1) = 서비스가 사용(T3) ✅. `ScheduleSpec.weekdays: tuple[int]|None`(T1) = `_spec`이 채움(T3) ✅. 스키마 `weekdays: list[int]|None`(T3) = 모델 CSV str(T2) — 서비스가 경계에서 변환 ✅. 프론트 `weekdays?: number[]`(T5) = 백엔드 list ✅.

**알려진 실행 주의:**
- T3 sync 테스트의 today/horizon은 실제 HORIZON_DAYS(14)·grace(30)에 맞춰 단언 조정(한 주 3건 생성이 핵심).
- `to_contract_read`는 컬럼값(CSV)을 list로 덮어써야 함(빠뜨리면 Read DTO 검증 실패).
- 폼: 기존 weekday 자동동기화 useEffect 제거 후 weekly 저장은 weekdays≥1 요구.
- main에서 분기한 `feature/recurring-weekdays`에서 작업. 완료 후 사용자 지시대로 main 머지.
