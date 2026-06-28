from __future__ import annotations

from calendar import monthrange
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta

from app.domain.constants import RecurrenceMode

# 화면 열 때 "오늘 + HORIZON_DAYS"까지의 도래분을 제안한다.
HORIZON_DAYS = 14
# 과거 미생성분은 "오늘 - OVERDUE_GRACE_DAYS"까지만 노출(먼 과거 start_date 폭주 방지).
OVERDUE_GRACE_DAYS = 30


@dataclass(frozen=True)
class ScheduleSpec:
    mode: str
    start_date: date
    day_of_month: int | None = None
    interval_weeks: int | None = None
    weekday: int | None = None
    end_date: date | None = None
    max_occurrences: int | None = None


def validate_recurrence_fields(
    mode: str, day_of_month: int | None, interval_weeks: int | None
) -> None:
    """스케줄 모드와 짝 필드의 정합성 검증. 불일치 시 ValueError.

    MONTHLY는 day_of_month, WEEKLY는 interval_weeks가 반드시 있어야 한다.
    잘못된 짝(예: weekly↔monthly 전환 시 짝 필드 누락)이 저장되면 이후
    iter_due_dates가 ValueError를 던져 조회/sync 경로가 연쇄 고장하므로
    유입 단계(스키마 검증/계약 수정)에서 막는다.
    """
    if mode == RecurrenceMode.MONTHLY and day_of_month is None:
        raise ValueError("invalid_recurrence_fields")
    if mode == RecurrenceMode.WEEKLY and interval_weeks is None:
        raise ValueError("invalid_recurrence_fields")


def billing_month_of(due: date) -> str:
    return f"{due.year:04d}-{due.month:02d}"


def _clamp_day(year: int, month: int, day: int) -> date:
    last_day = monthrange(year, month)[1]
    return date(year, month, min(day, last_day))


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def iter_due_dates(spec: ScheduleSpec, *, until: date) -> Iterator[tuple[int, date]]:
    """start_date부터 until(포함)까지의 (sequence_no, due_date)를 오름차순 산출.

    sequence_no는 계약 내 회차 순번(1부터). end_date/max_occurrences는 종료 조건.

    WEEKLY는 `start_date`를 요일 앵커로 사용한다(모든 회차가 start_date.weekday()).
    `spec.weekday`는 표시/검증용 메타이며 계산에 쓰이지 않으므로, 폼에서 start_date와
    동기화되어 있어야 한다(설계 §10.1).
    """
    seq = 0
    if spec.mode == RecurrenceMode.MONTHLY:
        if spec.day_of_month is None:
            raise ValueError("day_of_month_required_for_monthly")
        year, month = spec.start_date.year, spec.start_date.month
        while True:
            due = _clamp_day(year, month, spec.day_of_month)
            if due >= spec.start_date:
                if due > until:
                    return
                if spec.end_date is not None and due > spec.end_date:
                    return
                seq += 1
                if spec.max_occurrences is not None and seq > spec.max_occurrences:
                    return
                yield seq, due
            year, month = _next_month(year, month)
    elif spec.mode == RecurrenceMode.WEEKLY:
        if not spec.interval_weeks:
            raise ValueError("interval_weeks_required_for_weekly")
        step = timedelta(weeks=spec.interval_weeks)
        due = spec.start_date
        while True:
            if due > until:
                return
            if spec.end_date is not None and due > spec.end_date:
                return
            seq += 1
            if spec.max_occurrences is not None and seq > spec.max_occurrences:
                return
            yield seq, due
            due = due + step
    else:
        raise ValueError(f"unknown_recurrence_mode:{spec.mode}")
