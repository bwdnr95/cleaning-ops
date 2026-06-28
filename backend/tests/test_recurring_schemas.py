from datetime import date

import pytest
from pydantic import ValidationError

from app.domain.constants import RecurrenceMode
from app.schemas.recurring import ApproveOccurrencesRequest, RecurringContractCreate


def test_contract_create_requires_service_and_schedule():
    payload = RecurringContractCreate(
        label="강남빌딩", customer_name="강남빌딩", customer_phone="01011112222",
        customer_address="서울 강남구 1", recurrence_mode=RecurrenceMode.MONTHLY, day_of_month=10,
        start_date=date(2026, 6, 10), service_name="사무실 정기청소", total_amount=150000,
    )
    assert payload.discount_amount == 0
    assert payload.default_partner_id is None


def test_approve_request_requires_at_least_one_item():
    with pytest.raises(ValidationError):
        ApproveOccurrencesRequest(items=[])
