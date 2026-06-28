from datetime import date

from app.domain.constants import RecurrenceMode
from app.domain.recurrence import ScheduleSpec, billing_month_of, iter_due_dates


def _dates(spec, until):
    return [d for _, d in iter_due_dates(spec, until=until)]


def test_monthly_basic_lists_each_month_on_day():
    spec = ScheduleSpec(mode=RecurrenceMode.MONTHLY, start_date=date(2026, 6, 10), day_of_month=10)
    assert _dates(spec, until=date(2026, 8, 31)) == [date(2026, 6, 10), date(2026, 7, 10), date(2026, 8, 10)]


def test_monthly_clamps_day_to_month_end():
    spec = ScheduleSpec(mode=RecurrenceMode.MONTHLY, start_date=date(2026, 1, 31), day_of_month=31)
    assert _dates(spec, until=date(2026, 3, 31)) == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)]


def test_monthly_skips_first_month_when_day_already_passed():
    spec = ScheduleSpec(mode=RecurrenceMode.MONTHLY, start_date=date(2026, 6, 20), day_of_month=10)
    assert _dates(spec, until=date(2026, 8, 31)) == [date(2026, 7, 10), date(2026, 8, 10)]


def test_weekly_biweekly_steps_from_start_keeping_weekday():
    spec = ScheduleSpec(mode=RecurrenceMode.WEEKLY, start_date=date(2026, 6, 2), interval_weeks=2, weekday=1)
    out = _dates(spec, until=date(2026, 7, 1))
    assert out == [date(2026, 6, 2), date(2026, 6, 16), date(2026, 6, 30)]
    assert all(d.weekday() == 1 for d in out)


def test_max_occurrences_stops_enumeration():
    spec = ScheduleSpec(
        mode=RecurrenceMode.MONTHLY, start_date=date(2026, 6, 10), day_of_month=10, max_occurrences=2
    )
    assert _dates(spec, until=date(2027, 1, 1)) == [date(2026, 6, 10), date(2026, 7, 10)]


def test_end_date_stops_enumeration():
    spec = ScheduleSpec(
        mode=RecurrenceMode.MONTHLY, start_date=date(2026, 6, 10), day_of_month=10, end_date=date(2026, 7, 31)
    )
    assert _dates(spec, until=date(2027, 1, 1)) == [date(2026, 6, 10), date(2026, 7, 10)]


def test_until_horizon_excludes_future_beyond():
    spec = ScheduleSpec(mode=RecurrenceMode.MONTHLY, start_date=date(2026, 6, 10), day_of_month=10)
    assert _dates(spec, until=date(2026, 6, 30)) == [date(2026, 6, 10)]


def test_billing_month_of_formats_year_month():
    assert billing_month_of(date(2026, 6, 10)) == "2026-06"
