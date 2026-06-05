from datetime import timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.time import business_today
from app.db.seed import (
    DEV_ADMIN_EMAIL,
    DEV_ADMIN_PASSWORD,
    DEV_ORDER_ID,
    DEV_PARTNER_ID,
    DEV_SERVICE_ITEM_ID,
)
from app.domain.constants import OrderStatus
from app.domain.payment_status import PaymentStatus, PartnerPaymentStatus
from app.models import Order
from tests.test_auth_integration import add_order_group, login, make_test_client


def admin_headers(client) -> dict[str, str]:
    session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    return {"Authorization": f"Bearer {session['access_token']}"}


def test_service_item_pricing_auto_fills_order_consumer_and_partner_prices() -> None:
    client = make_test_client()
    headers = admin_headers(client)

    response = client.post(
        "/api/admin/orders/groups",
        headers=headers,
        json={
            "customer_name": "R14 견적 고객",
            "customer_phone": "010-5555-1414",
            "customer_address": "서울시 R14 테스트로 1",
            "source_channel": "테스트",
            "customer_visible_payment": False,
            "lines": [
                {
                    "status": OrderStatus.NEW,
                    "received_date": "2026-05-21",
                    "service_item_id": DEV_SERVICE_ITEM_ID,
                    "service_name": "직접입력 값은 카탈로그명으로 대체",
                    "size_or_quantity": "1",
                    "discount_amount": 25000,
                    "vat_type": "excluded",
                }
            ],
        },
    )

    assert response.status_code == 201, response.text
    line = response.json()["lines"][0]
    assert line["service_name"] == "입주청소"
    assert line["total_amount"] == 280000
    assert line["discount_amount"] == 25000
    assert line["consumer_price"] == 280000
    assert line["partner_payment_amount"] == 196000
    assert line["partner_price"] == 196000
    assert line["vat_type"] == "excluded"


def test_admin_order_list_prioritizes_upcoming_then_overdue_unpaid_and_hides_past_paid() -> None:
    today = business_today()

    def seed_sort_orders(db: Session) -> None:
        add_order_group(
            db,
            group_id="r14-sort-group",
            customer_token="r14-sort-token",
            customer_name="R14 정렬 고객",
            customer_phone="01011112222",
            customer_address="서울 R14 정렬로 1",
            source_channel="테스트",
        )
        db.add_all(
            [
                Order(
                    id="r14-overdue-unpaid",
                    group_id="r14-sort-group",
                    status=OrderStatus.CONSULTING,
                    received_date=today - timedelta(days=70),
                    scheduled_date=today - timedelta(days=60),
                    service_name="미수 과거 작업",
                    customer_token="r14-sort-token",
                    customer_name="R14 정렬 고객",
                    customer_phone="01011112222",
                    customer_address="서울 R14 정렬로 1",
                    total_amount=Decimal("100000"),
                    payment_status=PaymentStatus.BALANCE_PENDING,
                ),
                Order(
                    id="r14-overdue-paid",
                    group_id="r14-sort-group",
                    status=OrderStatus.COMPLETED,
                    received_date=today - timedelta(days=70),
                    scheduled_date=today - timedelta(days=59),
                    service_name="완납 과거 작업",
                    customer_token="r14-sort-token",
                    customer_name="R14 정렬 고객",
                    customer_phone="01011112222",
                    customer_address="서울 R14 정렬로 1",
                    total_amount=Decimal("90000"),
                    payment_status=PaymentStatus.PAID,
                ),
                Order(
                    id="r14-today-paid",
                    group_id="r14-sort-group",
                    status=OrderStatus.SCHEDULED,
                    received_date=today,
                    scheduled_date=today,
                    service_name="오늘 작업",
                    customer_token="r14-sort-token",
                    customer_name="R14 정렬 고객",
                    customer_phone="01011112222",
                    customer_address="서울 R14 정렬로 1",
                    total_amount=Decimal("110000"),
                    payment_status=PaymentStatus.PAID,
                ),
                Order(
                    id="r14-future-paid",
                    group_id="r14-sort-group",
                    status=OrderStatus.SCHEDULE_CONFIRMED,
                    received_date=today,
                    scheduled_date=today + timedelta(days=3),
                    service_name="미래 작업",
                    customer_token="r14-sort-token",
                    customer_name="R14 정렬 고객",
                    customer_phone="01011112222",
                    customer_address="서울 R14 정렬로 1",
                    total_amount=Decimal("120000"),
                    payment_status=PaymentStatus.PAID,
                ),
                Order(
                    id="r14-unscheduled",
                    group_id="r14-sort-group",
                    status=OrderStatus.NEW,
                    received_date=today - timedelta(days=1),
                    scheduled_date=None,
                    service_name="일정 미정 신규접수",
                    customer_token="r14-sort-token",
                    customer_name="R14 정렬 고객",
                    customer_phone="01011112222",
                    customer_address="서울 R14 정렬로 1",
                    total_amount=Decimal("130000"),
                    payment_status=PaymentStatus.PENDING,
                ),
            ]
        )

    client = make_test_client(seed_sort_orders)
    headers = admin_headers(client)

    response = client.get("/api/admin/orders?sort=visit_asc", headers=headers)

    assert response.status_code == 200, response.text
    ids = [item["id"] for item in response.json()]
    assert "r14-overdue-unpaid" in ids
    assert "r14-today-paid" in ids
    assert "r14-future-paid" in ids
    assert "r14-unscheduled" in ids
    assert "r14-overdue-paid" not in ids
    # 오늘·미래 → 미정(신규접수) → 과거 잔금 미완납 순.
    assert ids.index("r14-today-paid") < ids.index("r14-future-paid")
    assert ids.index("r14-future-paid") < ids.index("r14-unscheduled")
    assert ids.index("r14-unscheduled") < ids.index("r14-overdue-unpaid")

    with_past_response = client.get(
        "/api/admin/orders?sort=visit_asc&include_past_paid=true",
        headers=headers,
    )
    assert with_past_response.status_code == 200
    with_past_ids = [item["id"] for item in with_past_response.json()]
    assert "r14-overdue-paid" in with_past_ids
    assert with_past_ids.index("r14-overdue-unpaid") < with_past_ids.index("r14-overdue-paid")

    received_response = client.get(
        "/api/admin/orders?sort=received_desc&include_past_paid=true",
        headers=headers,
    )
    assert received_response.status_code == 200, received_response.text
    received_ids = [item["id"] for item in received_response.json()]
    assert received_ids.index("r14-future-paid") < received_ids.index("r14-overdue-unpaid")


def test_partner_settlement_marks_paid_reverts_and_records_timeline() -> None:
    def mark_seed_completed(db: Session) -> None:
        order = db.get(Order, DEV_ORDER_ID)
        assert order is not None
        order.status = OrderStatus.COMPLETED

    client = make_test_client(mark_seed_completed)
    headers = admin_headers(client)

    unpaid_response = client.get(
        f"/api/admin/partners/{DEV_PARTNER_ID}/settlements",
        params={"status": "unpaid", "from": "2026-01-01", "to": "2026-12-31"},
        headers=headers,
    )
    assert unpaid_response.status_code == 200, unpaid_response.text
    unpaid_items = unpaid_response.json()["items"]
    seed_item = next(item for item in unpaid_items if item["order_id"] == DEV_ORDER_ID)
    assert seed_item["consumer_price"] == 280000
    assert seed_item["partner_price"] == 180000
    assert seed_item["partner_payment_status"] == PartnerPaymentStatus.UNPAID

    settle_response = client.post(
        f"/api/admin/partners/{DEV_PARTNER_ID}/settlements/settle",
        headers=headers,
        json={"order_ids": [DEV_ORDER_ID], "memo": "R14 정산 테스트"},
    )
    assert settle_response.status_code == 200, settle_response.text
    assert settle_response.json()["updated_order_ids"] == [DEV_ORDER_ID]

    detail_after_settle = client.get(f"/api/admin/orders/{DEV_ORDER_ID}", headers=headers).json()
    assert detail_after_settle["partner_payment_status"] == PartnerPaymentStatus.PAID
    assert detail_after_settle["partner_settled_at"] is not None
    assert "partner_settled" in {event["event_type"] for event in detail_after_settle["timeline"]}

    paid_response = client.get(
        f"/api/admin/partners/{DEV_PARTNER_ID}/settlements",
        params={"status": "paid", "from": "2026-01-01", "to": "2026-12-31"},
        headers=headers,
    )
    assert paid_response.status_code == 200
    assert DEV_ORDER_ID in {item["order_id"] for item in paid_response.json()["items"]}

    revert_response = client.post(
        f"/api/admin/partners/{DEV_PARTNER_ID}/settlements/revert",
        headers=headers,
        json={"order_ids": [DEV_ORDER_ID]},
    )
    assert revert_response.status_code == 200, revert_response.text

    detail_after_revert = client.get(f"/api/admin/orders/{DEV_ORDER_ID}", headers=headers).json()
    assert detail_after_revert["partner_payment_status"] == PartnerPaymentStatus.UNPAID
    assert detail_after_revert["partner_settled_at"] is None
    timeline_types = {event["event_type"] for event in detail_after_revert["timeline"]}
    assert "partner_settlement_reverted" in timeline_types


def test_partner_settlement_rejects_uncompleted_orders() -> None:
    client = make_test_client()
    headers = admin_headers(client)

    settle_response = client.post(
        f"/api/admin/partners/{DEV_PARTNER_ID}/settlements/settle",
        headers=headers,
        json={"order_ids": [DEV_ORDER_ID]},
    )

    assert settle_response.status_code == 422, settle_response.text
    assert settle_response.json()["detail"] == "invalid_settlement_order"

    detail = client.get(f"/api/admin/orders/{DEV_ORDER_ID}", headers=headers).json()
    assert detail["partner_payment_status"] == PartnerPaymentStatus.UNPAID
    assert "partner_settled" not in {event["event_type"] for event in detail["timeline"]}


def test_quote_and_partner_customer_info_messages_are_scoped_to_allowed_fields() -> None:
    client = make_test_client()
    headers = admin_headers(client)

    quote_response = client.post(
        f"/api/admin/orders/{DEV_ORDER_ID}/quote/send",
        headers=headers,
        json={"channel": "kakao"},
    )

    assert quote_response.status_code == 200, quote_response.text
    quote = quote_response.json()
    assert quote["message_type"] == "customer_quote"
    assert quote["channel"] == "alimtalk"
    assert quote["status"] == "sent"
    assert "280,000원" in quote["content"]
    assert "180,000원" not in quote["content"]

    partner_response = client.post(
        f"/api/admin/orders/{DEV_ORDER_ID}/notify-partner-unpaid",
        headers=headers,
        json={"channel": "kakao", "memo": "R14 고객정보 전송"},
    )

    assert partner_response.status_code == 200, partner_response.text
    partner_log = partner_response.json()
    assert partner_log["message_type"] == "partner_customer_info"
    assert partner_log["recipient_type"] == "partner"
    assert "***-****-5432" in partner_log["content"]
    assert "R14 고객정보 전송" not in partner_log["content"]
    assert "01098765432" not in partner_log["content"]
    assert "180,000원" not in partner_log["content"]
    assert "230,000원" not in partner_log["content"]
    assert "미수금" not in partner_log["content"]
    assert "비고" not in partner_log["content"]

    detail = client.get(f"/api/admin/orders/{DEV_ORDER_ID}", headers=headers).json()
    timeline_types = {event["event_type"] for event in detail["timeline"]}
    assert "quote_sent" in timeline_types
    assert "partner_unpaid_notice_sent" in timeline_types
