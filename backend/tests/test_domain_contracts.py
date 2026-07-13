from datetime import UTC, datetime

from app.core.time import business_today, to_business_time, to_utc
from app.domain.constants import ORDER_STATUSES, OrderStatus, PhotoType
from app.domain.customer_token import CUSTOMER_TOKEN_PREFIX, generate_customer_token
from app.domain.phone import normalize_phone, phone_suffix_matches
from app.domain.service_catalog import SERVICE_UNITS, ServiceUnit
from app.models.photo import OrderPhoto
from app.services.orders import to_partner_photo_dto


def test_order_status_contract_has_required_statuses() -> None:
    assert ORDER_STATUSES == tuple(status.value for status in OrderStatus)
    assert "사진검수대기" in ORDER_STATUSES
    assert "서비스완료" in ORDER_STATUSES


def test_customer_tokens_use_current_random_version() -> None:
    tokens = {generate_customer_token() for _ in range(100)}

    assert len(tokens) == 100
    assert all(token.startswith(CUSTOMER_TOKEN_PREFIX) for token in tokens)
    assert all(len(token) <= 80 for token in tokens)


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


def test_to_utc_normalizes_sqlite_naive_datetimes() -> None:
    naive_value = datetime(2026, 5, 5, 15, 30)
    assert to_utc(naive_value) == datetime(2026, 5, 5, 15, 30, tzinfo=UTC)


def test_partner_photo_dto_serializes_sqlite_naive_datetime_as_utc() -> None:
    photo = OrderPhoto(
        id="photo-utc-contract",
        order_id="order-utc-contract",
        uploaded_by_user_id="partner-user",
        photo_type=PhotoType.BEFORE,
        file_url="/uploads/photo.png",
        is_customer_visible=True,
        created_at=datetime(2026, 5, 5, 15, 30),
    )

    dto = to_partner_photo_dto(photo)

    assert dto.created_at == datetime(2026, 5, 5, 15, 30, tzinfo=UTC)
    assert '"created_at":"2026-05-05T15:30:00Z"' in dto.model_dump_json()
