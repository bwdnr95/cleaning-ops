"""AS(사후관리) 요청 전송 테스트 (배치3 항목5).

운영에서 주문에 AS 요청을 전송하면 (1) 주문에 AS 플래그+메모가 남고, (2) AS_REQUESTED
타임라인과 협력사 안내 메시지가 기록되며, (3) 협력사 링크(잡 상세)에도 AS 요청/메모가 노출된다.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.seed import DEV_ORDER_ID, DEV_PARTNER_ID, DEV_PARTNER_USER_ID
from app.domain.constants import MessageType, OrderStatus, PhotoType, TimelineEventType
from app.models.message import MessageLog
from app.models.partner import Partner
from app.schemas.order import OrderUpdate
from app.schemas.photo import PhotoCreate
from app.services.orders import OrderService
from app.services.photos import PhotoService

PNG_BYTES = b"\x89PNG\r\n\x1a\ncleanops-test-image"
CUSTOMER_HEADERS = {"X-Customer-Token": "ct2_seed-customer-token-2450"}


def test_as_request_sets_flags_notifies_and_shows_on_partner_link(
    client, seed_admin_token, seed_partner_token
):
    admin_h = {"Authorization": f"Bearer {seed_admin_token}"}
    status_res = client.patch(
        f"/api/admin/orders/{DEV_ORDER_ID}",
        json={"status": OrderStatus.CUSTOMER_DELIVERY_DONE.value},
        headers=admin_h,
    )
    assert status_res.status_code == 200, status_res.text

    res = client.post(
        f"/api/admin/orders/{DEV_ORDER_ID}/as-request",
        json={"memo": "화장실 코너 재시공 필요"},
        headers=admin_h,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["as_requested"] is True
    assert body["as_memo"] == "화장실 코너 재시공 필요"
    assert body["status"] == OrderStatus.CUSTOMER_CHECK_NEEDED.value

    detail = client.get(f"/api/admin/orders/{DEV_ORDER_ID}", headers=admin_h).json()
    assert any(
        ev["event_type"] == TimelineEventType.AS_REQUESTED.value for ev in detail["timeline"]
    )
    # 배정 협력사가 있는 시드 주문이라 AS 안내 메시지가 기록된다(Mock 발송/실패 무관하게 로그 존재).
    assert any(
        log["message_type"] == MessageType.PARTNER_AS_REQUEST.value
        for log in detail["message_logs"]
    )
    assert any(
        log["message_type"] == MessageType.CUSTOMER_AS_NOTICE.value
        for log in detail["message_logs"]
    )

    retry = client.post(
        f"/api/admin/orders/{DEV_ORDER_ID}/as-request",
        json={"memo": "화장실 코너 재시공 필요"},
        headers=admin_h,
    )
    assert retry.status_code == 409
    detail_after_retry = client.get(
        f"/api/admin/orders/{DEV_ORDER_ID}", headers=admin_h
    ).json()
    assert sum(
        log["message_type"] == MessageType.PARTNER_AS_REQUEST.value
        for log in detail_after_retry["message_logs"]
    ) == 1
    assert sum(
        log["message_type"] == MessageType.CUSTOMER_AS_NOTICE.value
        for log in detail_after_retry["message_logs"]
    ) == 1

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


def test_as_request_without_partner_is_rejected(db_session):
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

    with pytest.raises(ValueError, match="partner_not_assigned"):
        osvc.request_as(order_id, memo="재작업 필요", actor_user_id=None)

    logs = MessageRepository(db_session).list_for_order(order_id)
    assert all(log.message_type != MessageType.PARTNER_AS_REQUEST.value for log in logs)
    assert all(log.message_type != MessageType.CUSTOMER_AS_NOTICE.value for log in logs)


def test_as_request_rejects_pre_work_order_even_when_partner_assigned(db_session):
    from datetime import date

    from app.repositories.order_groups import OrderGroupRepository
    from app.schemas.order import OrderGroupCreate, OrderLineCreate
    from app.services.orders import OrderService

    osvc = OrderService(db_session)
    group = osvc.create_group(
        OrderGroupCreate(
            customer_name="작업전",
            customer_phone="01000002222",
            customer_address="서울특별시 강남구 테스트로 4",
            lines=[
                OrderLineCreate(
                    status=OrderStatus.PARTNER_CONFIRMING,
                    received_date=date(2026, 6, 1),
                    partner_id=DEV_PARTNER_ID,
                    team_name="강남 1팀",
                    service_name="청소",
                )
            ],
        )
    )
    order_id = OrderGroupRepository(db_session).list_lines(group.id)[0].id

    with pytest.raises(ValueError, match="invalid_as_request_status"):
        osvc.request_as(order_id, memo="재작업 필요", actor_user_id=None)


def test_customer_dto_excludes_as_fields():
    # AGENTS.md DTO 화이트리스트: AS 필드는 고객 DTO에 절대 노출되지 않는다(회귀 가드).
    from app.schemas.order import CustomerOrderLineRead

    fields = set(CustomerOrderLineRead.model_fields.keys())
    assert "as_memo" not in fields
    assert "as_requested" not in fields


def test_customer_as_intake_waits_for_admin_acceptance(
    client,
    seed_admin_token,
    seed_partner_token,
):
    admin_h = {"Authorization": f"Bearer {seed_admin_token}"}
    status_response = client.patch(
        f"/api/admin/orders/{DEV_ORDER_ID}",
        json={"status": OrderStatus.CUSTOMER_DELIVERY_DONE.value},
        headers=admin_h,
    )
    assert status_response.status_code == 200, status_response.text

    intake = client.post(
        "/api/customer/orders/as-requests",
        headers=CUSTOMER_HEADERS,
        json={
            "phone_suffix": "5432",
            "order_id": DEV_ORDER_ID,
            "memo": "욕실 실리콘 마감 상태를 다시 확인해주세요.",
        },
    )
    assert intake.status_code == 200, intake.text
    customer_line = next(line for line in intake.json()["lines"] if line["id"] == DEV_ORDER_ID)
    assert customer_line["aftercare_status"] == "pending"
    assert "as_requested" not in customer_line
    assert "as_memo" not in customer_line

    admin_detail = client.get(f"/api/admin/orders/{DEV_ORDER_ID}", headers=admin_h).json()
    assert admin_detail["status"] == OrderStatus.CUSTOMER_DELIVERY_DONE.value
    assert admin_detail["as_requested"] is False
    assert admin_detail["as_intake_pending"] is True
    assert admin_detail["as_memo"] == "욕실 실리콘 마감 상태를 다시 확인해주세요."
    assert all(
        log["message_type"]
        not in {MessageType.PARTNER_AS_REQUEST.value, MessageType.CUSTOMER_AS_NOTICE.value}
        for log in admin_detail["message_logs"]
    )
    assert any(
        event["event_type"] == TimelineEventType.AS_INTAKE_REQUESTED.value
        for event in admin_detail["timeline"]
    )

    partner_h = {"Authorization": f"Bearer {seed_partner_token}"}
    pending_partner_job = client.get(
        f"/api/partner/jobs/{DEV_ORDER_ID}",
        headers=partner_h,
    )
    assert pending_partner_job.status_code == 200
    assert pending_partner_job.json()["as_requested"] is False
    assert pending_partner_job.json()["as_memo"] is None
    assert pending_partner_job.json()["as_requested_at"] is None
    blocked_start = client.post(
        f"/api/partner/jobs/{DEV_ORDER_ID}/start",
        headers=partner_h,
    )
    blocked_upload = client.post(
        f"/api/partner/jobs/{DEV_ORDER_ID}/photos",
        headers=partner_h,
        data={"photo_type": "before"},
        files={"file": ("pending-as.png", PNG_BYTES, "image/png")},
    )
    assert blocked_start.status_code == 409
    assert blocked_upload.status_code == 409

    dashboard = client.get("/api/admin/dashboard/summary", headers=admin_h)
    assert dashboard.status_code == 200
    assert dashboard.json()["customer_check_needed"] >= 1
    pending_page = client.get(
        "/api/admin/orders/page",
        params={"status": "customer_check", "visit_preset": "all"},
        headers=admin_h,
    )
    assert pending_page.status_code == 200
    assert any(item["id"] == DEV_ORDER_ID for item in pending_page.json()["items"])

    accepted = client.post(
        f"/api/admin/orders/{DEV_ORDER_ID}/as-request",
        json={"memo": ""},
        headers=admin_h,
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["as_requested"] is True
    assert accepted.json()["as_intake_pending"] is False
    assert accepted.json()["as_memo"] == "욕실 실리콘 마감 상태를 다시 확인해주세요."

    paid_during_as = client.patch(
        f"/api/admin/orders/{DEV_ORDER_ID}",
        json={"payment_status": "paid"},
        headers=admin_h,
    )
    assert paid_during_as.status_code == 200
    assert paid_during_as.json()["status"] == OrderStatus.CUSTOMER_CHECK_NEEDED.value
    assert paid_during_as.json()["as_requested"] is True

    accepted_detail = client.get(f"/api/admin/orders/{DEV_ORDER_ID}", headers=admin_h).json()
    as_message_types = [
        log["message_type"]
        for log in accepted_detail["message_logs"]
        if log["message_type"]
        in {MessageType.PARTNER_AS_REQUEST.value, MessageType.CUSTOMER_AS_NOTICE.value}
    ]
    assert sorted(as_message_types) == sorted(
        [MessageType.PARTNER_AS_REQUEST, MessageType.CUSTOMER_AS_NOTICE]
    )
    verified = client.post(
        "/api/customer/orders/verify",
        headers=CUSTOMER_HEADERS,
        json={"phone_suffix": "5432"},
    )
    customer_line = next(line for line in verified.json()["lines"] if line["id"] == DEV_ORDER_ID)
    assert customer_line["aftercare_status"] == "in_progress"


def test_customer_as_intake_is_authenticated_and_idempotent(
    client,
    seed_admin_token,
):
    admin_h = {"Authorization": f"Bearer {seed_admin_token}"}
    client.patch(
        f"/api/admin/orders/{DEV_ORDER_ID}",
        json={"status": OrderStatus.CUSTOMER_DELIVERY_DONE.value},
        headers=admin_h,
    )
    url = "/api/customer/orders/as-requests"
    payload = {
        "phone_suffix": "5432",
        "order_id": DEV_ORDER_ID,
        "memo": "현관 바닥 오염을 확인해주세요.",
    }

    wrong_suffix = client.post(
        url,
        json={**payload, "phone_suffix": "0000"},
        headers=CUSTOMER_HEADERS,
    )
    assert wrong_suffix.status_code == 404
    foreign_order = client.post(
        url,
        json={**payload, "order_id": "not-this-group"},
        headers=CUSTOMER_HEADERS,
    )
    assert foreign_order.status_code == 404

    first = client.post(url, json=payload, headers=CUSTOMER_HEADERS)
    second = client.post(url, json=payload, headers=CUSTOMER_HEADERS)
    conflicting = client.post(
        url,
        json={**payload, "memo": "다른 요청"},
        headers=CUSTOMER_HEADERS,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert conflicting.status_code == 409
    detail = client.get(f"/api/admin/orders/{DEV_ORDER_ID}", headers=admin_h).json()
    intake_events = [
        event
        for event in detail["timeline"]
        if event["event_type"] == TimelineEventType.AS_INTAKE_REQUESTED.value
    ]
    assert len(intake_events) == 1


def test_pending_as_reassignment_waits_for_admin_acceptance(
    db_session,
    seed_order,
) -> None:
    partner = Partner(
        id="pending-as-partner",
        name="Pending AS Partner",
        phone="01044445555",
        is_active=True,
    )
    db_session.add(partner)
    seed_order.status = OrderStatus.CUSTOMER_DELIVERY_DONE
    db_session.commit()
    service = OrderService(db_session)
    service.submit_customer_as_intake(
        seed_order.id,
        group_id=seed_order.group_id,
        memo="Pending review",
    )

    service.update(seed_order.id, OrderUpdate(partner_id=partner.id))
    pending_partner_messages = list(
        db_session.scalars(
            select(MessageLog).where(
                MessageLog.order_id == seed_order.id,
                MessageLog.recipient_partner_id == partner.id,
            )
        )
    )
    assert pending_partner_messages == []

    service.request_as(seed_order.id, memo="", actor_user_id=None)
    accepted_partner_types = list(
        db_session.scalars(
            select(MessageLog.message_type).where(
                MessageLog.order_id == seed_order.id,
                MessageLog.recipient_partner_id == partner.id,
            )
        )
    )
    assert accepted_partner_types == [MessageType.PARTNER_AS_REQUEST]


def test_as_acceptance_rejects_inactive_partner(db_session, seed_order) -> None:
    inactive_partner = Partner(
        id="inactive-as-partner",
        name="Inactive AS Partner",
        phone="01055556666",
        is_active=False,
    )
    db_session.add(inactive_partner)
    seed_order.status = OrderStatus.CUSTOMER_DELIVERY_DONE
    seed_order.partner_id = inactive_partner.id
    db_session.commit()

    with pytest.raises(ValueError, match="partner_not_found"):
        OrderService(db_session).request_as(
            seed_order.id,
            memo="Do not disclose",
            actor_user_id=None,
        )

    db_session.refresh(seed_order)
    assert seed_order.as_requested is False


def test_paid_active_as_stays_startable_until_partner_completion(
    db_session,
    seed_order,
) -> None:
    seed_order.status = OrderStatus.CUSTOMER_DELIVERY_DONE
    seed_order.partner_id = DEV_PARTNER_ID
    db_session.commit()
    service = OrderService(db_session)
    service.request_as(seed_order.id, memo="Paid rework", actor_user_id=None)

    updated = service.update(
        seed_order.id,
        OrderUpdate(payment_status="paid"),
    )

    assert updated.status == OrderStatus.CUSTOMER_CHECK_NEEDED
    assert updated.as_requested is True
    PhotoService(db_session).upload_for_partner(
        PhotoCreate(
            order_id=seed_order.id,
            photo_type=PhotoType.BEFORE,
            file_url="/uploads/paid-active-as-before.png",
            file_name="paid-active-as-before.png",
        ),
        user_id=DEV_PARTNER_USER_ID,
        partner_id=DEV_PARTNER_ID,
    )
    started = service.start_partner_job(
        seed_order.id,
        actor_user_id=DEV_PARTNER_USER_ID,
        partner_id=DEV_PARTNER_ID,
    )
    assert started.status == OrderStatus.IN_PROGRESS


def test_legacy_completed_as_memo_is_not_treated_as_pending_intake(
    db_session,
    seed_order,
) -> None:
    seed_order.status = OrderStatus.COMPLETED
    seed_order.as_requested = False
    seed_order.as_intake_pending = False
    seed_order.as_memo = "Completed legacy AS memo"
    db_session.commit()

    submitted = OrderService(db_session).submit_customer_as_intake(
        seed_order.id,
        group_id=seed_order.group_id,
        memo="New AS request",
    )

    assert submitted.as_intake_pending is True
    assert submitted.as_memo == "New AS request"


def test_cancelling_pending_as_clears_customer_pending_state(
    client,
    seed_admin_token,
) -> None:
    admin_h = {"Authorization": f"Bearer {seed_admin_token}"}
    client.patch(
        f"/api/admin/orders/{DEV_ORDER_ID}",
        json={"status": OrderStatus.CUSTOMER_DELIVERY_DONE.value},
        headers=admin_h,
    )
    intake = client.post(
        "/api/customer/orders/as-requests",
        headers=CUSTOMER_HEADERS,
        json={
            "phone_suffix": "5432",
            "order_id": DEV_ORDER_ID,
            "memo": "Cancel pending intake",
        },
    )
    assert intake.status_code == 200

    cancelled = client.patch(
        f"/api/admin/orders/{DEV_ORDER_ID}",
        json={"status": OrderStatus.CANCELLED.value},
        headers=admin_h,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["as_intake_pending"] is False
    verified = client.post(
        "/api/customer/orders/verify",
        headers=CUSTOMER_HEADERS,
        json={"phone_suffix": "5432"},
    )
    line = next(item for item in verified.json()["lines"] if item["id"] == DEV_ORDER_ID)
    assert line["aftercare_status"] is None


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
