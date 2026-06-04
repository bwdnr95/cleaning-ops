from datetime import UTC, datetime

from app.core.time import business_today, to_business_time
from app.domain.constants import ORDER_STATUSES, OrderStatus
from app.domain.phone import normalize_phone, phone_suffix_matches
from app.domain.service_catalog import SERVICE_UNITS, ServiceUnit


def test_order_status_contract_has_required_statuses() -> None:
    assert ORDER_STATUSES == tuple(status.value for status in OrderStatus)
    assert "사진검수대기" in ORDER_STATUSES
    assert "서비스완료" in ORDER_STATUSES


def test_service_units_include_kan_for_service_catalog() -> None:
    assert ServiceUnit.KAN.value == "칸"
    assert "칸" in SERVICE_UNITS


def test_phone_suffix_verification_normalizes_phone() -> None:
    assert normalize_phone("010-1234-5678") == "01012345678"
    assert phone_suffix_matches("010-1234-5678", "5678")
    assert not phone_suffix_matches("010-1234-5678", "1234")
    assert not phone_suffix_matches("010-1234-5678", "78")


def test_business_time_uses_korea_timezone() -> None:
    utc_value = datetime(2026, 5, 5, 15, 30, tzinfo=UTC)

    assert to_business_time(utc_value).strftime("%Y-%m-%d %H:%M") == "2026-05-06 00:30"
    assert business_today(utc_value).isoformat() == "2026-05-06"
