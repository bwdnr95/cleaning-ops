from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.deps import get_session
from app.domain.constants import OrderStatus, TimelineEventType
from app.models.order import Order

CUSTOMER_HEADERS = {"X-Customer-Token": "ct2_seed-customer-token-2450"}


def test_create_group_with_multiple_lines(client: TestClient, seed_admin_token: str) -> None:
    response = client.post(
        "/api/admin/orders/groups",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
        json={
            "customer_name": "박고객",
            "customer_phone": "010-1234-5678",
            "customer_address": "서울시 강남구",
            "source_channel": "test",
            "customer_visible_payment": False,
            "lines": [
                {
                    "status": "신규접수",
                    "received_date": "2026-05-18",
                    "scheduled_date": "2026-05-20",
                    "service_name": "사무실 청소",
                    "total_amount": 300000,
                    "partner_id": "seed-partner-01",
                },
                {
                    "status": "신규접수",
                    "received_date": "2026-05-18",
                    "scheduled_date": "2026-05-21",
                    "service_name": "화장실 청소",
                    "total_amount": 100000,
                    "partner_id": None,
                },
            ],
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert len(body["lines"]) == 2
    lines = {line["service_name"]: line for line in body["lines"]}
    assert lines["사무실 청소"]["total_amount"] == 300000
    assert lines["사무실 청소"]["partner_id"] == "seed-partner-01"
    assert lines["화장실 청소"]["partner_id"] is None
    assert {line["group_id"] for line in body["lines"]} == {body["id"]}
    assert {line["customer_token"] for line in body["lines"]} == {body["customer_token"]}


def test_customer_verify_returns_group_with_lines(client: TestClient) -> None:
    response = client.post(
        "/api/customer/orders/verify",
        headers=CUSTOMER_HEADERS,
        json={"phone_suffix": "5432"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "seed-order-group-2450"
    assert body["customer_name"] == "박고객"
    assert len(body["lines"]) >= 1
    assert all("photos" in line for line in body["lines"])
    assert body["lines"][0]["id"] == "seed-order-2450"


def test_current_customer_token_is_rejected_from_legacy_url_route(client: TestClient) -> None:
    response = client.post(
        "/api/customer/orders/ct2_seed-customer-token-2450/verify",
        json={"phone_suffix": "5432"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "order_not_found"


def test_partner_only_sees_own_line_in_group(
    client: TestClient,
    seed_admin_token: str,
    seed_partner_token: str,
) -> None:
    create = client.post(
        "/api/admin/orders/groups",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
        json={
            "customer_name": "박고객",
            "customer_phone": "010-7777-8888",
            "customer_address": "서울시 강남구",
            "lines": [
                {
                    "status": "일정확정",
                    "received_date": "2026-05-18",
                    "service_name": "line A",
                    "partner_id": "seed-partner-01",
                },
                {
                    "status": "일정확정",
                    "received_date": "2026-05-18",
                    "service_name": "line B",
                    "partner_id": None,
                },
            ],
        },
    ).json()
    lines = {line["service_name"]: line for line in create["lines"]}
    line_a_id = lines["line A"]["id"]
    line_b_id = lines["line B"]["id"]

    jobs = client.get(
        "/api/partner/jobs",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    ).json()
    job_ids = [job["id"] for job in jobs]
    assert line_a_id in job_ids
    assert line_b_id not in job_ids

    direct = client.get(
        f"/api/partner/jobs/{line_b_id}",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    )
    assert direct.status_code == 404


def test_partner_dto_does_not_leak_group_metadata(
    client: TestClient,
    seed_partner_token: str,
) -> None:
    jobs = client.get(
        "/api/partner/jobs",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    ).json()
    for job in jobs:
        for forbidden in (
            "group_id",
            "source_channel",
            "customer_visible_payment",
            "customer_token",
            "notes",
            "partner_payment_amount",
            "partner_payment_status",
            "total_amount",
            "evidence_memo",
        ):
            assert forbidden not in job, f"partner DTO leak: {forbidden}"


def test_add_line_to_existing_group(client: TestClient, seed_admin_token: str) -> None:
    group = client.post(
        "/api/admin/orders/groups",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
        json={
            "customer_name": "박고객",
            "customer_phone": "010-3333-4444",
            "customer_address": "서울",
            "lines": [
                {"status": "신규접수", "received_date": "2026-05-18", "service_name": "line 1"}
            ],
        },
    ).json()

    add = client.post(
        f"/api/admin/orders/groups/{group['id']}/lines",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
        json={"status": "신규접수", "received_date": "2026-05-18", "service_name": "line 2"},
    )
    assert add.status_code == 201
    assert add.json()["group_id"] == group["id"]

    refreshed = client.get(
        f"/api/admin/orders/groups/{group['id']}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    ).json()
    assert len(refreshed["lines"]) == 2


def test_partial_cancel_does_not_cancel_other_lines(
    client: TestClient,
    seed_admin_token: str,
) -> None:
    group = client.post(
        "/api/admin/orders/groups",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
        json={
            "customer_name": "박",
            "customer_phone": "010-5555-6666",
            "customer_address": "서울",
            "lines": [
                {"status": "일정확정", "received_date": "2026-05-18", "service_name": "A"},
                {"status": "일정확정", "received_date": "2026-05-18", "service_name": "B"},
            ],
        },
    ).json()
    line_a_id, line_b_id = group["lines"][0]["id"], group["lines"][1]["id"]

    client.patch(
        f"/api/admin/orders/{line_a_id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
        json={"status": OrderStatus.CANCELLED.value},
    )

    refreshed = client.get(
        f"/api/admin/orders/groups/{group['id']}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    ).json()
    statuses = {line["id"]: line["status"] for line in refreshed["lines"]}
    assert statuses[line_a_id] == OrderStatus.CANCELLED.value
    assert statuses[line_b_id] == OrderStatus.SCHEDULE_CONFIRMED.value


def test_admin_detail_exposes_group_notes_and_group_updates_record_line_timeline(
    client: TestClient,
    seed_admin_token: str,
) -> None:
    headers = {"Authorization": f"Bearer {seed_admin_token}"}
    group = client.post(
        "/api/admin/orders/groups",
        headers=headers,
        json={
            "customer_name": "Group Notes Customer",
            "customer_phone": "010-1000-2000",
            "customer_address": "Old Address",
            "notes": "Preserve this group memo",
            "lines": [
                {
                    "status": OrderStatus.NEW.value,
                    "received_date": "2026-05-18",
                    "service_name": "line 1",
                },
                {
                    "status": OrderStatus.NEW.value,
                    "received_date": "2026-05-18",
                    "service_name": "line 2",
                },
            ],
        },
    ).json()
    line_ids = [line["id"] for line in group["lines"]]

    detail = client.get(f"/api/admin/orders/{line_ids[0]}", headers=headers).json()
    assert detail["group_notes"] == "Preserve this group memo"

    update_response = client.patch(
        f"/api/admin/orders/groups/{group['id']}",
        headers=headers,
        json={"customer_address": "New Address", "customer_address_detail": "Unit 1204"},
    )
    assert update_response.status_code == 200

    for line_id in line_ids:
        line_detail = client.get(f"/api/admin/orders/{line_id}", headers=headers).json()
        group_change_events = [
            event
            for event in line_detail["timeline"]
            if event["event_type"] == TimelineEventType.MEMO_ADDED.value
            and event["event_metadata"]
            and event["event_metadata"].get("source") == "order_group_update"
        ]
        assert group_change_events
        assert group_change_events[-1]["event_metadata"]["changes"]["customer_address"] == {
            "from": "Old Address",
            "to": "New Address",
        }
        assert group_change_events[-1]["event_metadata"]["changes"]["customer_address_detail"] == {
            "from": None,
            "to": "Unit 1204",
        }


def test_admin_order_edit_updates_line_and_group_atomically(
    client: TestClient,
    seed_admin_token: str,
) -> None:
    headers = {"Authorization": f"Bearer {seed_admin_token}"}
    response = client.patch(
        "/api/admin/orders/seed-order-2450/edit",
        headers=headers,
        json={
            "line": {"special_request": "현관 비밀번호 확인"},
            "group": {"customer_address_detail": "101동 1204호"},
        },
    )

    assert response.status_code == 200, response.text
    detail = client.get("/api/admin/orders/seed-order-2450", headers=headers).json()
    group = client.get(
        "/api/admin/orders/groups/seed-order-group-2450",
        headers=headers,
    ).json()
    assert detail["special_request"] == "현관 비밀번호 확인"
    assert detail["customer_address_detail"] == "101동 1204호"
    assert group["customer_address_detail"] == "101동 1204호"


def test_admin_order_edit_persists_group_fields_on_target_and_sibling_lines(
    client: TestClient,
    seed_admin_token: str,
) -> None:
    headers = {"Authorization": f"Bearer {seed_admin_token}"}
    created = client.post(
        "/api/admin/orders/groups",
        headers=headers,
        json={
            "customer_name": "기존 고객",
            "customer_phone": "010-1111-2222",
            "customer_address": "기존 주소",
            "lines": [
                {"received_date": "2026-08-12", "service_name": "대상 라인"},
                {"received_date": "2026-08-12", "service_name": "형제 라인"},
            ],
        },
    )
    assert created.status_code == 201, created.text
    group = created.json()
    target_id, sibling_id = [line["id"] for line in group["lines"]]

    response = client.patch(
        f"/api/admin/orders/{target_id}/edit",
        headers=headers,
        json={
            "line": {},
            "group": {
                "customer_name": "변경 고객",
                "customer_phone": "010-9999-8888",
                "customer_address": "변경 주소",
                "source_channel": "소개",
                "customer_visible_payment": True,
            },
        },
    )

    assert response.status_code == 200, response.text
    refreshed_group = client.get(
        f"/api/admin/orders/groups/{group['id']}", headers=headers
    ).json()
    target = client.get(f"/api/admin/orders/{target_id}", headers=headers).json()
    sibling = client.get(f"/api/admin/orders/{sibling_id}", headers=headers).json()
    for row in (refreshed_group, target, sibling):
        assert row["customer_name"] == "변경 고객"
        assert row["customer_phone"] == "01099998888"
        assert row["customer_address"] == "변경 주소"
        assert row["source_channel"] == "소개"
        assert row["customer_visible_payment"] is True

    session_generator = client.app.dependency_overrides[get_session]()
    stored_db = next(session_generator)
    try:
        stored_lines = stored_db.scalars(
            select(Order).where(Order.id.in_([target_id, sibling_id]))
        ).all()
        assert len(stored_lines) == 2
        for stored in stored_lines:
            assert stored.customer_name == "변경 고객"
            assert stored.customer_phone == "01099998888"
            assert stored.customer_address == "변경 주소"
            assert stored.source_channel == "소개"
            assert stored.customer_visible_payment is True
    finally:
        session_generator.close()


def test_admin_order_edit_rolls_back_group_when_line_validation_fails(
    client: TestClient,
    seed_admin_token: str,
) -> None:
    headers = {"Authorization": f"Bearer {seed_admin_token}"}
    before = client.get(
        "/api/admin/orders/groups/seed-order-group-2450",
        headers=headers,
    ).json()

    response = client.patch(
        "/api/admin/orders/seed-order-2450/edit",
        headers=headers,
        json={
            "line": {"service_item_id": "missing-service-item"},
            "group": {"customer_name": "롤백되어야 하는 이름"},
        },
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "service_item_not_found"
    after = client.get(
        "/api/admin/orders/groups/seed-order-group-2450",
        headers=headers,
    ).json()
    assert after["customer_name"] == before["customer_name"]
    assert after["lines"][0]["service_item_id"] == before["lines"][0]["service_item_id"]
