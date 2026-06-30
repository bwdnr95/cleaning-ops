from datetime import date

import pytest
from pydantic import ValidationError

from app.domain.constants import RecurrenceMode
from app.schemas.recurring import RecurringContractCreate


def test_contract_create_requires_service_and_schedule():
    payload = RecurringContractCreate(
        label="강남빌딩", customer_name="강남빌딩", customer_phone="01011112222",
        customer_address="서울 강남구 1", recurrence_mode=RecurrenceMode.MONTHLY, day_of_month=10,
        start_date=date(2026, 6, 10), service_name="사무실 정기청소", total_amount=150000,
    )
    assert payload.discount_amount == 0
    assert payload.default_partner_id is None


def _create_kwargs(**over):
    base = dict(
        label="강남빌딩", customer_name="강남빌딩", customer_phone="01011112222",
        customer_address="서울 강남구 1", recurrence_mode=RecurrenceMode.MONTHLY, day_of_month=10,
        start_date=date(2026, 6, 10), service_name="사무실 정기청소", total_amount=150000,
    )
    base.update(over)
    return base


def test_contract_create_monthly_requires_day_of_month():
    with pytest.raises(ValidationError):
        RecurringContractCreate(**_create_kwargs(recurrence_mode=RecurrenceMode.MONTHLY, day_of_month=None))


def test_contract_create_weekly_requires_interval_weeks():
    with pytest.raises(ValidationError):
        RecurringContractCreate(
            **_create_kwargs(recurrence_mode=RecurrenceMode.WEEKLY, day_of_month=None, interval_weeks=None)
        )


def test_contract_create_weekly_with_interval_weeks_ok():
    payload = RecurringContractCreate(
        **_create_kwargs(recurrence_mode=RecurrenceMode.WEEKLY, day_of_month=None, interval_weeks=2)
    )
    assert payload.interval_weeks == 2


def test_contract_create_rejects_invalid_vat_type():
    with pytest.raises(ValidationError):
        RecurringContractCreate(**_create_kwargs(vat_type="bogus"))


def test_contract_create_rejects_out_of_range_weekday():
    # weekdays 요소는 0~6만 허용(범위 밖이면 _schedule_text IndexError로 목록 API 500 유발).
    with pytest.raises(ValidationError):
        RecurringContractCreate(
            **_create_kwargs(
                recurrence_mode=RecurrenceMode.WEEKLY, day_of_month=None, interval_weeks=1, weekdays=[9]
            )
        )


def test_contract_create_accepts_valid_weekdays():
    payload = RecurringContractCreate(
        **_create_kwargs(
            recurrence_mode=RecurrenceMode.WEEKLY, day_of_month=None, interval_weeks=1, weekdays=[0, 2, 4]
        )
    )
    assert payload.weekdays == [0, 2, 4]
