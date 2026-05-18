from fastapi.testclient import TestClient

from app.domain.constants import OrderStatus, TimelineEventType


def _jpeg_bytes() -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * 64 + b"\xff\xd9"


def _upload(client: TestClient, partner_token: str, order_id: str) -> str:
    response = client.post(
        f"/api/partner/jobs/{order_id}/photos",
        headers={"Authorization": f"Bearer {partner_token}"},
        files={"file": ("after.jpg", _jpeg_bytes(), "image/jpeg")},
        data={"photo_type": "after"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _setup_delivery_needed(client: TestClient, partner_token: str, order_id: str) -> str:
    client.post(
        f"/api/partner/jobs/{order_id}/start",
        headers={"Authorization": f"Bearer {partner_token}"},
    )
    photo_id = _upload(client, partner_token, order_id)
    response = client.post(
        f"/api/partner/jobs/{order_id}/complete",
        headers={"Authorization": f"Bearer {partner_token}"},
    )
    assert response.status_code == 200
    return photo_id


def test_admin_revoke_returns_to_in_progress_when_no_photos_left(
    client: TestClient,
    seed_partner_token: str,
    seed_admin_token: str,
    seed_order_id: str,
) -> None:
    photo_id = _setup_delivery_needed(client, seed_partner_token, seed_order_id)

    response = client.post(
        f"/api/admin/photos/{photo_id}/revoke",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )

    assert response.status_code == 200
    assert response.json()["is_customer_visible"] is False
    detail = client.get(
        f"/api/admin/orders/{seed_order_id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    ).json()
    events = [event["event_type"] for event in detail["timeline"]]
    assert TimelineEventType.PHOTO_REVOKED.value in events
    assert detail["status"] == OrderStatus.IN_PROGRESS.value


def test_revoke_keeps_status_when_other_visible_photos_exist(
    client: TestClient,
    seed_partner_token: str,
    seed_admin_token: str,
    seed_order_id: str,
) -> None:
    client.post(
        f"/api/partner/jobs/{seed_order_id}/start",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    )
    photo_id = _upload(client, seed_partner_token, seed_order_id)
    _upload(client, seed_partner_token, seed_order_id)
    complete = client.post(
        f"/api/partner/jobs/{seed_order_id}/complete",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    )
    assert complete.status_code == 200

    response = client.post(
        f"/api/admin/photos/{photo_id}/revoke",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )

    assert response.status_code == 200
    detail = client.get(
        f"/api/admin/orders/{seed_order_id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    ).json()
    assert detail["status"] == OrderStatus.CUSTOMER_DELIVERY_NEEDED.value


def test_revoke_keeps_delivery_done_status(
    client: TestClient,
    seed_partner_token: str,
    seed_admin_token: str,
    seed_order_id: str,
) -> None:
    photo_id = _setup_delivery_needed(client, seed_partner_token, seed_order_id)
    client.patch(
        f"/api/admin/orders/{seed_order_id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
        json={"status": OrderStatus.CUSTOMER_DELIVERY_DONE.value},
    )

    response = client.post(
        f"/api/admin/photos/{photo_id}/revoke",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )

    assert response.status_code == 200
    detail = client.get(
        f"/api/admin/orders/{seed_order_id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    ).json()
    assert detail["status"] == OrderStatus.CUSTOMER_DELIVERY_DONE.value


def test_revoke_idempotent_when_already_hidden(
    client: TestClient,
    seed_partner_token: str,
    seed_admin_token: str,
    seed_order_id: str,
) -> None:
    photo_id = _setup_delivery_needed(client, seed_partner_token, seed_order_id)
    first = client.post(
        f"/api/admin/photos/{photo_id}/revoke",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    detail_after_first = client.get(
        f"/api/admin/orders/{seed_order_id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    ).json()

    second = client.post(
        f"/api/admin/photos/{photo_id}/revoke",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    detail_after_second = client.get(
        f"/api/admin/orders/{seed_order_id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    ).json()

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["is_customer_visible"] is False
    first_revoke_count = [
        event["event_type"] for event in detail_after_first["timeline"]
    ].count(TimelineEventType.PHOTO_REVOKED.value)
    second_revoke_count = [
        event["event_type"] for event in detail_after_second["timeline"]
    ].count(TimelineEventType.PHOTO_REVOKED.value)
    assert second_revoke_count == first_revoke_count
