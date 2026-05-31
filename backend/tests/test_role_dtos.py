from datetime import date

from app.domain.constants import OrderStatus
from app.models.order import Order
from app.services.orders import (
    to_admin_order_dto,
    to_customer_order_dto,
    to_partner_job_dto,
)


def make_order(*, customer_visible_payment: bool = False) -> Order:
    return Order(
        id="order-1",
        group_id="group-1",
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
        discount_amount=20000,
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
    assert "discount_amount" not in payload
    assert "consumer_price" not in payload
    assert "partner_price" not in payload
    assert "partner_payment_amount" not in payload


def test_customer_order_dto_hides_internal_fields_and_payment_by_default() -> None:
    dto = to_customer_order_dto(make_order(customer_visible_payment=False))
    payload = dto.model_dump()

    assert payload["customer_name"] == "이서연"
    assert payload["customer_phone"] == "01012345678"
    line = payload["lines"][0]
    assert line["total_amount"] is None
    assert line["deposit_amount"] is None
    assert line["balance_amount"] is None
    assert line["payment_status"] is None
    assert "discount_amount" not in line
    assert "consumer_price" not in line
    assert "partner_price" not in line
    assert "source_channel" not in payload
    assert "payment_memo" not in payload
    assert "evidence_memo" not in payload
    assert "partner_payment_amount" not in payload


def test_admin_order_dto_allows_negative_onsite_adjustment() -> None:
    # 현장 추가는 부호 있는 현장 조정값이다. 엑셀 임포트/프론트는 음수(현장 차감)를
    # 허용하므로 조회 DTO도 음수를 그대로 직렬화해야 한다.
    order = make_order()
    order.onsite_extra_amount = -45000
    order.vat_type = "included"

    dto = to_admin_order_dto(order)

    assert dto.onsite_extra_amount == -45000


def test_customer_order_dto_can_show_payment_when_admin_allows_it() -> None:
    dto = to_customer_order_dto(make_order(customer_visible_payment=True))
    payload = dto.model_dump()
    line = payload["lines"][0]

    assert line["total_amount"] == 320000
    assert line["deposit_amount"] == 100000
    assert line["balance_amount"] == 220000
    assert line["payment_status"] == "계약금"
