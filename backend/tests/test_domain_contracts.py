from app.domain.constants import ORDER_STATUSES, OrderStatus
from app.domain.phone import normalize_phone, phone_suffix_matches


def test_order_status_contract_has_required_statuses() -> None:
    assert ORDER_STATUSES == tuple(status.value for status in OrderStatus)
    assert "사진검수대기" in ORDER_STATUSES
    assert "서비스완료" in ORDER_STATUSES


def test_phone_suffix_verification_normalizes_phone() -> None:
    assert normalize_phone("010-1234-5678") == "01012345678"
    assert phone_suffix_matches("010-1234-5678", "5678")
    assert not phone_suffix_matches("010-1234-5678", "1234")
    assert not phone_suffix_matches("010-1234-5678", "78")
