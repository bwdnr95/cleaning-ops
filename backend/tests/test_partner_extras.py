"""협력사(Partner) 현장 메모 + 협력사용 메시지 조회 API 검증.

기존 test_auth_integration 의 픽스처/헬퍼(make_test_client, login)와
시드 데이터(seed-order-2450, 시드 협력사)를 그대로 재사용한다.
"""

from datetime import date

from app.core.security import create_access_token, hash_password
from app.db.seed import (
    DEV_ADMIN_EMAIL,
    DEV_ADMIN_PASSWORD,
    DEV_PARTNER_PASSWORD,
    DEV_PARTNER_PHONE,
)
from app.domain.constants import OrderStatus, UserRole
from app.models import Order, Partner, User
from app.services.orders import to_partner_job_dto

from tests.test_auth_integration import login, make_test_client


def _partner_headers(client) -> dict:
    session = login(client, "/api/auth/partner/login", DEV_PARTNER_PHONE, DEV_PARTNER_PASSWORD)
    return {"Authorization": f"Bearer {session['access_token']}"}


def _admin_headers(client) -> dict:
    session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    return {"Authorization": f"Bearer {session['access_token']}"}


def test_partner_can_add_memo_and_read_it_back() -> None:
    client = make_test_client()
    headers = _partner_headers(client)

    memo_text = "현장 도착, 베란다 곰팡이 심함 사진 추가 예정"
    create_response = client.post(
        "/api/partner/jobs/seed-order-2450/memo",
        headers=headers,
        json={"text": memo_text},
    )

    assert create_response.status_code == 200, create_response.text
    body = create_response.json()
    assert [memo["text"] for memo in body["memos"]] == [memo_text]
    assert body["memos"][0]["id"]

    # 새로 조회한 상세에도 메모가 남아있어야 한다.
    detail_response = client.get("/api/partner/jobs/seed-order-2450", headers=headers)
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert memo_text in [memo["text"] for memo in detail["memos"]]

    # 민감 필드가 협력사 DTO 로 새지 않는지 재확인.
    assert "total_amount" not in detail
    assert "payment_memo" not in detail

    # 관리자 타임라인에 author_role=partner 의 memo_added 이벤트가 기록되어야 한다.
    admin_headers = _admin_headers(client)
    admin_detail = client.get("/api/admin/orders/seed-order-2450", headers=admin_headers)
    assert admin_detail.status_code == 200
    memo_events = [
        event
        for event in admin_detail.json()["timeline"]
        if event["event_type"] == "memo_added" and event["title"] == "협력사 메모"
    ]
    assert len(memo_events) == 1
    assert memo_events[0]["description"] == memo_text
    assert memo_events[0]["event_metadata"]["author_role"] == "partner"


def test_partner_memo_rejects_empty_text() -> None:
    client = make_test_client()
    headers = _partner_headers(client)

    response = client.post(
        "/api/partner/jobs/seed-order-2450/memo",
        headers=headers,
        json={"text": ""},
    )

    assert response.status_code == 422


def test_other_partner_cannot_add_memo_to_seed_job() -> None:
    def seed_other_partner_user(db) -> None:
        db.add(
            Partner(
                id="memo-other-partner",
                name="Memo Other Partner",
                manager_name="Other Manager",
                phone="01098765432",
                service_areas="Seoul",
                available_services="Cleaning",
                memo=None,
                is_active=True,
            )
        )
        db.add(
            User(
                id="memo-other-user",
                role=UserRole.PARTNER,
                name="Memo Other User",
                email=None,
                phone="01098765432",
                password_hash=hash_password("OtherPartner123!"),
                partner_id="memo-other-partner",
                is_active=True,
            )
        )

    client = make_test_client(seed_other_partner_user)
    token = create_access_token(
        user_id="memo-other-user",
        role=UserRole.PARTNER,
        partner_id="memo-other-partner",
    )
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/partner/jobs/seed-order-2450/memo",
        headers=headers,
        json={"text": "남의 주문에 메모"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "order_not_found"


def test_seeded_one_off_job_is_not_recurring() -> None:
    client = make_test_client()
    headers = _partner_headers(client)

    detail_response = client.get("/api/partner/jobs/seed-order-2450", headers=headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["is_recurring"] is False


def test_to_partner_job_dto_marks_recurring_order() -> None:
    """recurring_contract_id 가 채워진 주문은 DTO 에서 is_recurring=True."""
    order = Order(
        id="recurring-dto-unit",
        group_id="recurring-dto-group",
        status=OrderStatus.SCHEDULE_CONFIRMED,
        received_date=date(2026, 6, 1),
        scheduled_date=date(2026, 6, 10),
        requested_time="10:00",
        service_name="정기청소",
        customer_name="정기고객",
        customer_phone="01000000000",
        customer_address="서울시 강남구",
        customer_token="recurring-dto-token",
        customer_visible_payment=False,
        recurring_contract_id="recurring-contract-1",
    )

    dto = to_partner_job_dto(order)

    assert dto.is_recurring is True
    assert dto.memos == []


def test_partner_messages_endpoint_returns_partner_recipient_only() -> None:
    client = make_test_client()
    admin_headers = _admin_headers(client)

    assignment_response = client.post(
        "/api/admin/messages/send",
        headers=admin_headers,
        json={
            "order_id": "seed-order-2450",
            "message_type": "partner_assignment",
            "recipient_type": "partner",
            "channel": "sms",
        },
    )
    assert assignment_response.status_code == 200, assignment_response.text

    customer_response = client.post(
        "/api/admin/messages/send",
        headers=admin_headers,
        json={
            "order_id": "seed-order-2450",
            "message_type": "customer_schedule_confirmed",
            "recipient_type": "customer",
            "channel": "sms",
        },
    )
    assert customer_response.status_code == 200, customer_response.text

    partner_headers = _partner_headers(client)
    messages_response = client.get(
        "/api/partner/jobs/seed-order-2450/messages",
        headers=partner_headers,
    )

    assert messages_response.status_code == 200, messages_response.text
    messages = messages_response.json()
    # 협력사 수신 메시지 1건만, 고객 수신 메시지는 제외.
    assert len(messages) == 1
    assert messages[0]["message_type"] == "partner_assignment"
    assert "신규 작업이 배정되었습니다" in messages[0]["content"]

    # 슬림 DTO: provider/error 내부 필드가 노출되지 않아야 한다.
    raw = messages_response.text
    for forbidden in (
        "provider_response",
        "error_message",
        "recipient_phone",
        "recipient_name",
        "provider_message_id",
    ):
        assert forbidden not in raw
    leaked = set(messages[0].keys()) - {
        "id",
        "message_type",
        "channel",
        "content",
        "status",
        "sent_at",
        "created_at",
    }
    assert leaked == set()


def test_partner_messages_endpoint_blocks_other_partner() -> None:
    def seed_other_partner_user(db) -> None:
        db.add(
            Partner(
                id="msg-other-partner",
                name="Msg Other Partner",
                manager_name="Other Manager",
                phone="01099998888",
                service_areas="Seoul",
                available_services="Cleaning",
                memo=None,
                is_active=True,
            )
        )
        db.add(
            User(
                id="msg-other-user",
                role=UserRole.PARTNER,
                name="Msg Other User",
                email=None,
                phone="01099998888",
                password_hash=hash_password("OtherPartner123!"),
                partner_id="msg-other-partner",
                is_active=True,
            )
        )

    client = make_test_client(seed_other_partner_user)
    token = create_access_token(
        user_id="msg-other-user",
        role=UserRole.PARTNER,
        partner_id="msg-other-partner",
    )
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/partner/jobs/seed-order-2450/messages", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "order_not_found"
