from datetime import date

from app.domain.constants import OrderStatus
from app.models.order import Order
from app.services.orders import to_customer_order_dto, to_partner_job_dto


def make_order(*, customer_visible_payment: bool = False) -> Order:
    return Order(
        id="order-1",
        status=OrderStatus.SCHEDULE_CONFIRMED,
        received_date=date(2026, 5, 1),
        scheduled_date=date(2026, 5, 2),
        requested_time="오후 2-5",
        partner_id="partner-1",
        team_name="클린파트너스",
        service_name="에어컨 분해세척",
        size_or_quantity="4대",
        service_detail="벽걸이 2대 + 스탠드 2대",
        special_request="베란다 곰팡이 심함",
        source_channel="네이버 검색",
        customer_name="이서연",
        customer_phone="01012345678",
        customer_address="서울 마포구 와우산로 88",
        total_amount=320000,
        deposit_amount=100000,
        balance_amount=220000,
        onsite_extra_amount=0,
        vat_type="포함",
        payment_status="계약금",
        payment_memo="국민은행 입금 확인",
        evidence_memo="세금계산서 요청",
        partner_payment_amount=180000,
        partner_payment_status="미정",
        customer_token="customer-token",
        customer_visible_payment=customer_visible_payment,
    )


def test_partner_job_dto_does_not_expose_money_or_internal_fields() -> None:
    dto = to_partner_job_dto(make_order())
    payload = dto.model_dump()

    assert payload["customer_address"] == "서울 마포구 와우산로 88"
    assert "total_amount" not in payload
    assert "deposit_amount" not in payload
    assert "balance_amount" not in payload
    assert "payment_memo" not in payload
    assert "source_channel" not in payload
    assert "partner_payment_amount" not in payload


def test_customer_order_dto_hides_internal_fields_and_payment_by_default() -> None:
    dto = to_customer_order_dto(make_order(customer_visible_payment=False))
    payload = dto.model_dump()

    assert payload["customer_name"] == "이서연"
    assert payload["total_amount"] is None
    assert payload["deposit_amount"] is None
    assert payload["balance_amount"] is None
    assert payload["payment_status"] is None
    assert "customer_phone" not in payload
    assert "source_channel" not in payload
    assert "payment_memo" not in payload
    assert "evidence_memo" not in payload
    assert "partner_payment_amount" not in payload


def test_customer_order_dto_can_show_payment_when_admin_allows_it() -> None:
    dto = to_customer_order_dto(make_order(customer_visible_payment=True))
    payload = dto.model_dump()

    assert payload["total_amount"] == 320000
    assert payload["deposit_amount"] == 100000
    assert payload["balance_amount"] == 220000
    assert payload["payment_status"] == "계약금"
