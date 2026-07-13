from fastapi.testclient import TestClient

from app.domain.constants import OrderStatus, TimelineEventType


def _jpeg_bytes() -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * 64 + b"\xff\xd9"


SIGNATURE_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)
SPOOFED_SIGNATURE_DATA_URL = "data:image/png;base64,bm90LXBuZw=="


def _upload_photo(client: TestClient, token: str, order_id: str, photo_type: str) -> None:
    response = client.post(
        f"/api/partner/jobs/{order_id}/photos",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (f"{photo_type}.jpg", _jpeg_bytes(), "image/jpeg")},
        data={"photo_type": photo_type},
    )
    assert response.status_code == 200, response.text


def _confirm_partner_job(client: TestClient, token: str, order_id: str) -> None:
    response = client.post(
        f"/api/partner/jobs/{order_id}/confirm",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text


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


def test_partner_confirms_schedule_from_checking_status(
    client: TestClient,
    seed_partner_token: str,
    seed_admin_token: str,
    seed_order_id: str,
) -> None:
    update_response = client.patch(
        f"/api/admin/orders/{seed_order_id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
        json={"status": OrderStatus.PARTNER_CONFIRMING.value},
    )
    assert update_response.status_code == 200, update_response.text

    response = client.post(
        f"/api/partner/jobs/{seed_order_id}/confirm",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == OrderStatus.SCHEDULED.value


def test_start_partner_job_requires_before_photo(
    client: TestClient,
    seed_partner_token: str,
    seed_order_id: str,
) -> None:
    _confirm_partner_job(client, seed_partner_token, seed_order_id)
    response = client.post(
        f"/api/partner/jobs/{seed_order_id}/start",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "before_photo_required_for_start"


def test_complete_partner_job_advances_to_delivery_needed(
    client: TestClient,
    seed_partner_token: str,
    seed_admin_token: str,
    seed_order_id: str,
) -> None:
    _confirm_partner_job(client, seed_partner_token, seed_order_id)
    _upload_photo(client, seed_partner_token, seed_order_id, "before")
    client.post(
        f"/api/partner/jobs/{seed_order_id}/start",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    )
    _upload_photo(client, seed_partner_token, seed_order_id, "after")

    response = client.post(
        f"/api/partner/jobs/{seed_order_id}/complete",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
        json={"customer_signature_data_url": SIGNATURE_DATA_URL},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == OrderStatus.CUSTOMER_DELIVERY_NEEDED.value
    assert body["work_started_at"]
    assert body["work_completed_at"]
    assert body["has_recorded_customer_signature"] is True
    assert "customer_signature_file_url" not in body

    order = client.get(
        f"/api/admin/orders/{seed_order_id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    ).json()
    assert order["work_started_at"]
    assert order["work_completed_at"]
    assert order["customer_signature_file_url"]
    assert sorted(log["message_type"] for log in order["message_logs"]) == [
        "customer_balance_due",
        "customer_schedule_confirmed",
    ]


def test_complete_partner_job_requires_after_photo_and_signature(
    client: TestClient,
    seed_partner_token: str,
    seed_order_id: str,
) -> None:
    _confirm_partner_job(client, seed_partner_token, seed_order_id)
    _upload_photo(client, seed_partner_token, seed_order_id, "before")
    client.post(
        f"/api/partner/jobs/{seed_order_id}/start",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    )

    response = client.post(
        f"/api/partner/jobs/{seed_order_id}/complete",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
        json={"customer_signature_data_url": ""},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "completion_evidence_required"


def test_complete_partner_job_rejects_spoofed_signature(
    client: TestClient,
    seed_partner_token: str,
    seed_order_id: str,
) -> None:
    _confirm_partner_job(client, seed_partner_token, seed_order_id)
    _upload_photo(client, seed_partner_token, seed_order_id, "before")
    client.post(
        f"/api/partner/jobs/{seed_order_id}/start",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    )
    _upload_photo(client, seed_partner_token, seed_order_id, "after")

    response = client.post(
        f"/api/partner/jobs/{seed_order_id}/complete",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
        json={"customer_signature_data_url": SPOOFED_SIGNATURE_DATA_URL},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "completion_evidence_required"


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
