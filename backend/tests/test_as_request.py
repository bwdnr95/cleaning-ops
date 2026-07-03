"""AS(사후관리) 요청 전송 테스트 (배치3 항목5).

운영에서 주문에 AS 요청을 전송하면 (1) 주문에 AS 플래그+메모가 남고, (2) AS_REQUESTED
타임라인과 협력사 안내 메시지가 기록되며, (3) 협력사 링크(잡 상세)에도 AS 요청/메모가 노출된다.
"""

from __future__ import annotations

from app.db.seed import DEV_ORDER_ID
from app.domain.constants import MessageType, TimelineEventType


def test_as_request_sets_flags_notifies_and_shows_on_partner_link(
    client, seed_admin_token, seed_partner_token
):
    admin_h = {"Authorization": f"Bearer {seed_admin_token}"}
    res = client.post(
        f"/api/admin/orders/{DEV_ORDER_ID}/as-request",
        json={"memo": "화장실 코너 재시공 필요"},
        headers=admin_h,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["as_requested"] is True
    assert body["as_memo"] == "화장실 코너 재시공 필요"

    detail = client.get(f"/api/admin/orders/{DEV_ORDER_ID}", headers=admin_h).json()
    assert any(
        ev["event_type"] == TimelineEventType.AS_REQUESTED.value for ev in detail["timeline"]
    )
    # 배정 협력사가 있는 시드 주문이라 AS 안내 메시지가 기록된다(Mock 발송/실패 무관하게 로그 존재).
    assert any(
        log["message_type"] == MessageType.PARTNER_AS_REQUEST.value
        for log in detail["message_logs"]
    )

    # 운영자 결정(2026-07-03): AS 안내도 협력사가 고객에게 직접 재방문 조율하도록 실번호를 전달한다.
    messages = client.get("/api/admin/messages", headers=admin_h).json()
    as_log = next(
        m for m in messages
        if m["order_id"] == DEV_ORDER_ID
        and m["message_type"] == MessageType.PARTNER_AS_REQUEST.value
    )
    assert "01098765432" in as_log["content"]
    assert "***-****-" not in as_log["content"]

    # 협력사 링크(잡 상세)에도 AS 요청/메모가 노출된다.
    partner_h = {"Authorization": f"Bearer {seed_partner_token}"}
    job = client.get(f"/api/partner/jobs/{DEV_ORDER_ID}", headers=partner_h).json()
    assert job["as_requested"] is True
    assert job["as_memo"] == "화장실 코너 재시공 필요"


def test_as_request_requires_memo(client, seed_admin_token):
    admin_h = {"Authorization": f"Bearer {seed_admin_token}"}
    res = client.post(
        f"/api/admin/orders/{DEV_ORDER_ID}/as-request",
        json={"memo": "   "},
        headers=admin_h,
    )
    assert res.status_code == 400


def test_as_request_requires_admin(client):
    res = client.post(
        f"/api/admin/orders/{DEV_ORDER_ID}/as-request",
        json={"memo": "인증 없음"},
    )
    assert res.status_code == 401


def test_as_request_without_partner_sets_flags_only(db_session):
    # 미배정 주문도 AS 플래그/메모/타임라인은 남기되, 협력사 안내 메시지는 발송하지 않는다.
    from datetime import date

    from app.repositories.messages import MessageRepository
    from app.repositories.order_groups import OrderGroupRepository
    from app.schemas.order import OrderGroupCreate, OrderLineCreate
    from app.services.orders import OrderService

    osvc = OrderService(db_session)
    group = osvc.create_group(
        OrderGroupCreate(
            customer_name="무배정",
            customer_phone="01000001111",
            customer_address="서울특별시 강남구 테스트로 2",
            lines=[OrderLineCreate(received_date=date(2026, 6, 1), service_name="청소")],
        )
    )
    order_id = OrderGroupRepository(db_session).list_lines(group.id)[0].id

    order = osvc.request_as(order_id, memo="재작업 필요", actor_user_id=None)
    assert order.as_requested is True
    assert order.as_memo == "재작업 필요"

    logs = MessageRepository(db_session).list_for_order(order_id)
    assert all(log.message_type != MessageType.PARTNER_AS_REQUEST.value for log in logs)


def test_customer_dto_excludes_as_fields():
    # AGENTS.md DTO 화이트리스트: AS 필드는 고객 DTO에 절대 노출되지 않는다(회귀 가드).
    from app.schemas.order import CustomerOrderLineRead

    fields = set(CustomerOrderLineRead.model_fields.keys())
    assert "as_memo" not in fields
    assert "as_requested" not in fields


def test_create_order_cannot_set_as_fields(client, seed_admin_token):
    # 심각#1 회귀 가드: 주문 생성 API로는 AS 플래그를 세팅할 수 없다(AS 전송 액션 전용).
    h = {"Authorization": f"Bearer {seed_admin_token}"}
    res = client.post(
        "/api/admin/orders/groups",
        json={
            "customer_name": "생성테스트",
            "customer_phone": "01022223333",
            "customer_address": "서울특별시 강남구 테스트로 3",
            "lines": [
                {
                    "received_date": "2026-06-01",
                    "service_name": "청소",
                    "as_requested": True,
                    "as_memo": "몰래 주입",
                }
            ],
        },
        headers=h,
    )
    assert res.status_code == 201, res.text
    line = res.json()["lines"][0]
    assert line["as_requested"] is False
    assert line["as_memo"] is None
