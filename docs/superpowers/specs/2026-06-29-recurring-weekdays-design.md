# 정기청소 — 다중 요일 주기 (WEEKLY 여러 요일) 설계

- 작성일: 2026-06-29
- 범위: 주간 정기청소에서 **한 주에 여러 요일** 선택(예: 매주 월·수·금). 기존 간격(매주/격주/4주)과 **조합**.
- 전제: A(정기계약+회차생성)·B(월 청구·정산) 완료(`main`). `domain/recurrence.py`·`RecurringContract`·계약 폼만 수정. 마이그 신규 1개.
- 규칙: `AGENTS.md` + `.claude/rules/*` 준수.
- 작업 브랜치: `feature/recurring-weekdays`(main에서 분기).

---

## 0. 합의된 결정
- **간격 유지 + 다중 요일 추가**: WEEKLY = `interval_weeks`(매주/격주/4주) + 요일 **집합**. 예: 매주 월·수·금, 격주 화·목.
- **저장**: `weekdays` CSV 컬럼 신설 + 레거시 `weekday`(단일) 보존·폴백(데이터 마이그/타입변경 회피).
- **생성**: 현재 단일요일 로직의 **엄밀한 일반화**(단일요일 계약은 동일 결과).
- **MONTHLY 변경 없음**(단일 지정일 유지).

---

## 1. 데이터 모델
- `backend/app/models/recurring_contract.py`: 컬럼 추가
  - `weekdays: Mapped[str | None] = mapped_column(String(20))` — CSV `"0,2,4"`(0=월 … 6=일, `date.weekday()` 규약).
- 기존 `weekday: int | None`(단일)은 **보존**(레거시). 신규 WEEKLY는 `weekdays`를 채운다.
- 마이그레이션 **`0017_recurring_weekdays`**(`down_revision="0016_message_recipient_partner_id"`): `recurring_contracts.weekdays VARCHAR(20)` nullable 추가. 기존 행은 NULL.
- 실 Postgres(5434) 적용(완료 기준 — SQLite 테스트는 FK/제약 한계, [[sqlite-fk-not-enforced-gap]]).

---

## 2. 스케줄 계산 (`backend/app/domain/recurrence.py`)
- `ScheduleSpec`에 `weekdays: tuple[int, ...] | None = None` 추가.
- WEEKLY 선택요일 결정(폴백): `wds = spec.weekdays or ((spec.weekday,) if spec.weekday is not None else (spec.start_date.weekday(),))`. 빈 튜플이면 ValueError.
- `iter_due_dates` WEEKLY 분기 **일반화**(아래 알고리즘). 활성 주(=start_date 주에서 `interval_weeks`마다)마다, 선택된 각 요일의 그 주 날짜를 시간순 생성.

```python
elif spec.mode == RecurrenceMode.WEEKLY:
    if not spec.interval_weeks:
        raise ValueError("interval_weeks_required_for_weekly")
    wds = spec.weekdays or (
        (spec.weekday,) if spec.weekday is not None else (spec.start_date.weekday(),)
    )
    wds = tuple(sorted(set(wds)))
    if not wds:
        raise ValueError("weekday_required_for_weekly")
    anchor_monday = spec.start_date - timedelta(days=spec.start_date.weekday())  # start 주의 월요일
    step = timedelta(weeks=spec.interval_weeks)
    week_monday = anchor_monday
    while True:
        if week_monday > until:            # 그 주 월요일이 호라이즌 초과 → 종료(단조 증가)
            return
        for w in wds:                      # 오름차순 요일
            due = week_monday + timedelta(days=w)
            if due < spec.start_date:      # 첫 주의 start 이전 요일은 건너뜀(seq 미소비)
                continue
            if due > until:                # 이 주의 나머지 요일도 초과 → 다음 주로
                break
            if spec.end_date is not None and due > spec.end_date:
                return
            seq += 1
            if spec.max_occurrences is not None and seq > spec.max_occurrences:
                return
            yield seq, due
        week_monday = week_monday + step
```

- **불변식**: 주 단위 전진 + 주 안에서 요일 오름차순 → 전체 시간순. `until` 유한 → 종료 보장. 단일요일(`wds=(start.weekday(),)`, 매주)이면 기존과 동일 결과(첫 회차=start_date, 이후 +interval주).
- 예: start=수, weekdays=월·수·금, 매주 → 1주차 수·금(월 skip), 이후 월·수·금. 격주면 활성 주만.

---

## 3. 검증 (`validate_recurrence_fields`)
- WEEKLY: `interval_weeks` 필수 **그리고** (`weekdays` 비어있지 않음 **또는** 레거시 `weekday` 존재). 둘 다 없으면 `ValueError("weekday_required_for_weekly")`.
- 신규 입력(스키마)에서 `weekdays` 각 값 0~6 범위.
- `RecurringContractCreate` model_validator + `RecurringService.update_contract` 재검증(기존 A 패턴 확장).

---

## 4. 스키마 / 서비스 (`schemas/recurring.py`, `services/recurring.py`)
- `RecurringContractBase`/`RecurringContractUpdate`/`Read`에 `weekdays: list[int] | None`(각 0~6) 추가. 프론트는 **배열**로 송수신.
- 저장 경계: 서비스 create/update에서 `weekdays: list[int]` → CSV(`",".join(map(str, sorted(set(v))))`) 직렬화 저장. Read DTO 구성 시 CSV → `list[int]` 역직렬화.
- `RecurringService._spec()`: `contract.weekdays`(CSV) → `tuple[int]` 파싱해 `ScheduleSpec.weekdays`에 전달.
- `_schedule_text()`: WEEKLY → `f"{매주|격주|N주마다} {요일목록}"`(예: "매주 월·수·금"). 요일 라벨 = `["월","화","수","목","금","토","일"]`.

> 정규화 헬퍼(`parse_weekdays_csv`/`format_weekdays_csv`)를 `domain/recurrence.py`에 두고 서비스가 재사용(DRY).

---

## 5. 프론트엔드 (`RecurringContractForm.tsx`, `domain/recurrence.ts`, `api/recurring.ts`)
- `RecurringContractInput`/`RecurringContract`에 `weekdays?: number[] | null` 추가.
- 폼 주간 모드: 간격 select(매주/격주/4주) + **요일 다중 선택 토글(월~일 7개 버튼)**. `weekdays` state(`number[]`). 기존 `weekday` 자동동기화 로직 **제거/대체**. `start_date`는 첫 회차 기준일.
  - 저장 시 monthly면 `weekdays=null`, weekly면 `weekdays=선택배열`(최소 1개 — 0개면 저장 버튼 비활성/검증).
- `domain/recurrence.ts`: `WEEKDAY_LABEL`(기존 재사용) + `formatScheduleText`가 weekdays 배열을 "월·수·금"으로 표시.
- 상세/목록의 주기 표시도 다중요일 반영(`schedule_text`는 백엔드가 이미 포맷 → 그대로 사용).

---

## 6. B (월 청구·정산) — 변경 없음
주문 단위 집계라 주당 회차가 늘어도 그대로 동작. (다중요일 → 더 많은 주문 → B가 자연 집계.)

---

## 7. 테스트
1. **생성**(`domain/recurrence.py` 순수): 매주 월·수·금(첫 주 mid-week skip), 격주 다중요일, 4주, `end_date`/`max_occurrences` 경계, `until` 호라이즌, 요일 정렬·중복 제거.
2. **레거시 폴백**: `weekdays=None`+`weekday` 단일 → 기존과 동일 결과(회귀 가드).
3. **검증**: WEEKLY 요일 0개 거부, 범위 밖 거부.
4. **직렬화 왕복**: list ↔ CSV(서비스/스키마).
5. **schedule_text** 포맷.
6. (통합) 다중요일 계약 sync → 한 주에 회차 여러 건 PENDING 생성, 승인 시 주문 다건.
7. 검증 명령: `pytest` + `compileall`(+ruff 가능 시), 프론트 `typecheck/lint/build`.

---

## 8. 마이그레이션·검증
- `0017_recurring_weekdays` 작성 후 렌더 확인, 실 Postgres(5434) `alembic upgrade head` 적용(완료 기준).
- 전체 백엔드 pytest + 프론트 빌드 그린.

---

## 9. 미해결/스펙 리뷰 확인 포인트
1. 레거시 단일 `weekday` 컬럼 **제거는 범위 밖**(보존·폴백). 추후 일원화 원하면 별도.
2. `start_date`가 선택 요일 중 하나가 아니어도 OK — 첫 회차는 `start_date` 이후 첫 해당 요일(알고리즘이 자연 처리).
3. MONTHLY 다중 지정일(예: 매월 1·15일)은 이번 범위 밖(요청은 주간 다중요일).
