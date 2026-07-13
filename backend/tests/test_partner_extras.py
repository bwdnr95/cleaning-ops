"""협력사(Partner) 현장 메모 + 협력사용 메시지 조회 API 검증.

기존 test_auth_integration 의 픽스처/헬퍼(make_test_client, login)와
시드 데이터(seed-order-2450, 시드 협력사)를 그대로 재사용한다.
"""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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


def _partner_headers(client: TestClient) -> dict[str, str]:
    session = login(client, "/api/auth/partner/login", DEV_PARTNER_PHONE, DEV_PARTNER_PASSWORD)
    return {"Authorization": f"Bearer {session['access_token']}"}


def _admin_headers(client: TestClient) -> dict[str, str]:
    session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    return {"Authorization": f"Bearer {session['access_token']}"}


_PARTNER_B_ID = "reassign-partner-b"
_PARTNER_B_USER_ID = "reassign-user-b"
_PARTNER_B_PHONE = "01055554444"


def _seed_partner_b(db: Session) -> None:
    """재배정 격리 테스트용 협력사 B(+ 로그인 계정)."""
    db.add(
        Partner(
            id=_PARTNER_B_ID,
            name="Reassign Partner B",
            manager_name="B Manager",
            phone=_PARTNER_B_PHONE,
            service_areas="Seoul",
            available_services="Cleaning",
            memo=None,
            is_active=True,
        )
    )
    db.add(
        User(
            id=_PARTNER_B_USER_ID,
            role=UserRole.PARTNER,
            name="Reassign User B",
            email=None,
            phone=_PARTNER_B_PHONE,
            password_hash=hash_password("PartnerB123!"),
            partner_id=_PARTNER_B_ID,
            is_active=True,
        )
    )


def _partner_b_headers() -> dict[str, str]:
    token = create_access_token(
        user_id=_PARTNER_B_USER_ID,
        role=UserRole.PARTNER,
        partner_id=_PARTNER_B_ID,
    )
    return {"Authorization": f"Bearer {token}"}


def test_partner_login_includes_partner_company_name() -> None:
    """협력사 로그인 응답에 회사명(partner_name)이 포함된다(앱바 노출용)."""
    client = make_test_client()
    session = login(client, "/api/auth/partner/login", DEV_PARTNER_PHONE, DEV_PARTNER_PASSWORD)
    user = session["user"]
    assert user["role"] == "partner"
    partner_name = user["partner_name"]
    assert isinstance(partner_name, str)
    assert partner_name.strip()


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
    partner_headers = _partner_headers(client)

    status_response = client.patch(
        "/api/admin/orders/seed-order-2450",
        headers=admin_headers,
        json={"status": OrderStatus.PARTNER_CONFIRMING},
    )
    assert status_response.status_code == 200, status_response.text

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
        "/api/partner/jobs/seed-order-2450/confirm",
        headers=partner_headers,
    )
    assert customer_response.status_code == 200, customer_response.text

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


def test_partner_memo_rejects_whitespace_only_text() -> None:
    client = make_test_client()
    headers = _partner_headers(client)

    response = client.post(
        "/api/partner/jobs/seed-order-2450/memo",
        headers=headers,
        json={"text": "   "},
    )

    assert response.status_code == 422


def test_partner_memo_and_messages_blocked_on_soft_deleted_order() -> None:
    """soft-delete된 주문에는 신규 메모/메시지 엔드포인트도 접근 불가(404)."""
    client = make_test_client()
    partner_headers = _partner_headers(client)
    admin_headers = _admin_headers(client)

    delete_response = client.delete("/api/admin/orders/seed-order-2450", headers=admin_headers)
    assert delete_response.status_code == 204, delete_response.text

    memo_response = client.post(
        "/api/partner/jobs/seed-order-2450/memo",
        headers=partner_headers,
        json={"text": "삭제된 주문 메모"},
    )
    assert memo_response.status_code == 404
    messages_response = client.get("/api/partner/jobs/seed-order-2450/messages", headers=partner_headers)
    assert messages_response.status_code == 404


def test_admin_schedule_memo_added_excluded_from_partner_detail() -> None:
    """관리자 일정/결제 변경의 memo_added는 협력사 상세 memos에 절대 보이지 않는다."""
    client = make_test_client()
    partner_headers = _partner_headers(client)
    admin_headers = _admin_headers(client)

    own_memo = "협력사 본인 현장 메모"
    assert (
        client.post(
            "/api/partner/jobs/seed-order-2450/memo",
            headers=partner_headers,
            json={"text": own_memo},
        ).status_code
        == 200
    )

    # 관리자가 방문일을 변경 → memo_added('방문 일정 변경') 이벤트 기록
    patch_response = client.patch(
        "/api/admin/orders/seed-order-2450",
        headers=admin_headers,
        json={"scheduled_date": "2026-07-15"},
    )
    assert patch_response.status_code == 200, patch_response.text

    # 관리자 타임라인엔 일정변경 memo_added가 실제로 기록되어 있어야(테스트 의미 확보)
    admin_detail = client.get("/api/admin/orders/seed-order-2450", headers=admin_headers).json()
    schedule_memos = [
        event
        for event in admin_detail["timeline"]
        if event["event_type"] == "memo_added" and event["title"] == "방문 일정 변경"
    ]
    assert len(schedule_memos) >= 1

    # 그러나 협력사 상세 memos에는 본인 메모만 보인다.
    partner_detail = client.get("/api/partner/jobs/seed-order-2450", headers=partner_headers).json()
    assert [memo["text"] for memo in partner_detail["memos"]] == [own_memo]


def test_partner_messages_exclude_previous_partner_after_reassignment() -> None:
    """재배정(A→B) 시 B는 이전 협력사 A에게 간 메시지를 보면 안 된다."""
    client = make_test_client(_seed_partner_b)
    admin_headers = _admin_headers(client)

    # 현재 배정 협력사 A(시드)에게 배정 안내 발송
    assert (
        client.post(
            "/api/admin/messages/send",
            headers=admin_headers,
            json={
                "order_id": "seed-order-2450",
                "message_type": "partner_assignment",
                "recipient_type": "partner",
                "channel": "sms",
            },
        ).status_code
        == 200
    )

    # B로 재배정
    reassign = client.patch(
        "/api/admin/orders/seed-order-2450",
        headers=admin_headers,
        json={"partner_id": _PARTNER_B_ID},
    )
    assert reassign.status_code == 200, reassign.text
    assert client.post(
        "/api/admin/messages/send",
        headers=admin_headers,
        json={
            "order_id": "seed-order-2450",
            "message_type": "partner_assignment",
            "recipient_type": "partner",
            "channel": "sms",
        },
    ).status_code == 200

    b_headers = _partner_b_headers()
    before = client.get("/api/partner/jobs/seed-order-2450/messages", headers=b_headers)
    assert before.status_code == 200
    before_messages = before.json()
    assert len(before_messages) == 1
    assert "Reassign Partner B" in before_messages[0]["content"]

    assert (
        client.post(
            "/api/admin/messages/send",
            headers=admin_headers,
            json={
                "order_id": "seed-order-2450",
                "message_type": "partner_assignment",
                "recipient_type": "partner",
                "channel": "sms",
            },
        ).status_code
        == 200
    )
    after = client.get("/api/partner/jobs/seed-order-2450/messages", headers=b_headers).json()
    assert len(after) == 2
    assert all(message["message_type"] == "partner_assignment" for message in after)
    assert all("Reassign Partner B" in message["content"] for message in after)


def test_partner_memos_exclude_previous_partner_after_reassignment() -> None:
    """재배정(A→B) 시 B는 이전 협력사 A가 남긴 현장 메모를 보면 안 된다."""
    client = make_test_client(_seed_partner_b)
    a_headers = _partner_headers(client)  # 시드 협력사 A
    admin_headers = _admin_headers(client)

    assert (
        client.post(
            "/api/partner/jobs/seed-order-2450/memo",
            headers=a_headers,
            json={"text": "A의 출입 비번 메모"},
        ).status_code
        == 200
    )

    reassign = client.patch(
        "/api/admin/orders/seed-order-2450",
        headers=admin_headers,
        json={"partner_id": _PARTNER_B_ID},
    )
    assert reassign.status_code == 200, reassign.text

    b_headers = _partner_b_headers()
    detail = client.get("/api/partner/jobs/seed-order-2450", headers=b_headers)
    assert detail.status_code == 200
    assert detail.json()["memos"] == []

    # B 자신의 메모는 정상적으로 보인다.
    assert (
        client.post(
            "/api/partner/jobs/seed-order-2450/memo",
            headers=b_headers,
            json={"text": "B의 메모"},
        ).status_code
        == 200
    )
    detail2 = client.get("/api/partner/jobs/seed-order-2450", headers=b_headers).json()
    assert [memo["text"] for memo in detail2["memos"]] == ["B의 메모"]


def test_partner_messages_isolated_when_partners_share_phone() -> None:
    """전화번호가 같아도 recipient_partner_id로 협력사 간 메시지가 격리된다.

    (전화번호 기반 스코프였다면 A에게 간 메시지가 B에게 샜을 시나리오 — Codex 재리뷰 지적.)
    """
    shared_phone = "01088880000"

    def seed_shared(db) -> None:
        seed_a = db.get(Partner, "seed-partner-01")
        if seed_a is not None:
            seed_a.phone = shared_phone  # A 대표번호를 공유번호로 바꾼다
        db.add(
            Partner(
                id="shared-partner-b",
                name="Shared Phone B",
                manager_name="Shared Manager",
                phone=shared_phone,  # B도 같은 대표번호(Partner.phone엔 유니크 제약 없음)
                service_areas="Seoul",
                available_services="Cleaning",
                memo=None,
                is_active=True,
            )
        )
        db.add(
            User(
                id="shared-user-b",
                role=UserRole.PARTNER,
                name="Shared User B",
                email=None,
                phone="01066660000",  # 로그인 번호(users.phone)는 유니크라 별도값
                password_hash=hash_password("SharedB123!"),
                partner_id="shared-partner-b",
                is_active=True,
            )
        )

    client = make_test_client(seed_shared)
    admin_headers = _admin_headers(client)

    # 현재 배정 협력사 A(공유번호)에게 배정 안내 발송 → recipient_partner_id=A
    assert (
        client.post(
            "/api/admin/messages/send",
            headers=admin_headers,
            json={
                "order_id": "seed-order-2450",
                "message_type": "partner_assignment",
                "recipient_type": "partner",
                "channel": "sms",
            },
        ).status_code
        == 200
    )

    # B로 재배정 (B는 A와 동일한 대표 전화번호)
    assert (
        client.patch(
            "/api/admin/orders/seed-order-2450",
            headers=admin_headers,
            json={"partner_id": "shared-partner-b"},
        ).status_code
        == 200
    )
    assert client.post(
        "/api/admin/messages/send",
        headers=admin_headers,
        json={
            "order_id": "seed-order-2450",
            "message_type": "partner_assignment",
            "recipient_type": "partner",
            "channel": "sms",
        },
    ).status_code == 200

    b_token = create_access_token(
        user_id="shared-user-b",
        role=UserRole.PARTNER,
        partner_id="shared-partner-b",
    )
    b_headers = {"Authorization": f"Bearer {b_token}"}

    messages = client.get("/api/partner/jobs/seed-order-2450/messages", headers=b_headers)
    assert messages.status_code == 200
    own_messages = messages.json()
    assert len(own_messages) == 1
    assert "Shared Phone B" in own_messages[0]["content"]
