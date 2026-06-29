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
