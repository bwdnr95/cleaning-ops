from fastapi.testclient import TestClient

from app.domain.constants import OrderStatus, TimelineEventType


def _jpeg_bytes() -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * 64 + b"\xff\xd9"


def test_partner_upload_is_auto_visible(
    client: TestClient,
    seed_partner_token: str,
    seed_order_id: str,
) -> None:
    response = client.post(
        f"/api/partner/jobs/{seed_order_id}/photos",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
        files={"file": ("after.jpg", _jpeg_bytes(), "image/jpeg")},
        data={"photo_type": "after"},
    )

    assert response.status_code == 200
    assert response.json()["is_customer_visible"] is True


def test_partner_upload_does_not_change_status(
    client: TestClient,
    seed_partner_token: str,
    seed_admin_token: str,
    seed_order_id: str,
) -> None:
    pre_status = client.get(
        f"/api/admin/orders/{seed_order_id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    ).json()["status"]

    response = client.post(
        f"/api/partner/jobs/{seed_order_id}/photos",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
        files={"file": ("after.jpg", _jpeg_bytes(), "image/jpeg")},
        data={"photo_type": "after"},
    )
    assert response.status_code == 200

    order = client.get(
        f"/api/admin/orders/{seed_order_id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    ).json()
    assert order["status"] == pre_status
    timeline_events = [event["event_type"] for event in order["timeline"]]
    assert TimelineEventType.PHOTO_UPLOADED.value in timeline_events
    assert TimelineEventType.PHOTO_APPROVED.value in timeline_events
    assert TimelineEventType.STATUS_CHANGED.value not in timeline_events


def test_complete_partner_job_advances_to_delivery_needed(
    client: TestClient,
    seed_partner_token: str,
    seed_order_id: str,
) -> None:
    client.post(
        f"/api/partner/jobs/{seed_order_id}/start",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    )
    client.post(
        f"/api/partner/jobs/{seed_order_id}/photos",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
        files={"file": ("after.jpg", _jpeg_bytes(), "image/jpeg")},
        data={"photo_type": "after"},
    )

    response = client.post(
        f"/api/partner/jobs/{seed_order_id}/complete",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == OrderStatus.CUSTOMER_DELIVERY_NEEDED.value


def test_complete_partner_job_requires_photo(
    client: TestClient,
    seed_partner_token: str,
    seed_order_id: str,
) -> None:
    client.post(
        f"/api/partner/jobs/{seed_order_id}/start",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    )

    response = client.post(
        f"/api/partner/jobs/{seed_order_id}/complete",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "photo_required_for_completion"


def test_complete_partner_job_blocked_outside_in_progress(
    client: TestClient,
    seed_partner_token: str,
    seed_order_id: str,
) -> None:
    response = client.post(
        f"/api/partner/jobs/{seed_order_id}/complete",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "invalid_status_transition"
