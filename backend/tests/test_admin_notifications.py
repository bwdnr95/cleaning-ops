from fastapi.testclient import TestClient

from app.domain.constants import OrderStatus, TimelineEventType


def _jpeg_bytes() -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * 64 + b"\xff\xd9"


def test_admin_notifications_include_partner_photo_and_memo(
    client: TestClient,
    seed_admin_token: str,
    seed_partner_token: str,
    seed_order_id: str,
) -> None:
    upload_response = client.post(
        f"/api/partner/jobs/{seed_order_id}/photos",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
        files={"file": ("before.jpg", _jpeg_bytes(), "image/jpeg")},
        data={"photo_type": "before"},
    )
    assert upload_response.status_code == 200, upload_response.text
    memo_response = client.post(
        f"/api/partner/jobs/{seed_order_id}/memo",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
        json={"text": "본사 전달 메모입니다."},
    )
    assert memo_response.status_code == 200, memo_response.text

    response = client.get(
        "/api/admin/notifications",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert any(
        item["event_type"] == TimelineEventType.MEMO_ADDED.value
        and item["actor_label"] == "협력사"
        and item["description"] == "본사 전달 메모입니다."
        for item in body
    )
    assert any(
        item["event_type"] == TimelineEventType.PHOTO_UPLOADED.value
        and item["title"] == "사진 업로드"
        and item["actor_label"] == "협력사"
        for item in body
    )


def test_admin_notifications_label_customer_as_photo_as_customer(
    client: TestClient,
    seed_admin_token: str,
    seed_order_id: str,
) -> None:
    admin_headers = {"Authorization": f"Bearer {seed_admin_token}"}
    detail_response = client.get(f"/api/admin/orders/{seed_order_id}", headers=admin_headers)
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()

    status_response = client.patch(
        f"/api/admin/orders/{seed_order_id}",
        headers=admin_headers,
        json={"status": OrderStatus.CUSTOMER_DELIVERY_DONE.value},
    )
    assert status_response.status_code == 200, status_response.text

    as_response = client.post(
        "/api/customer/orders/as-request",
        headers={"X-Customer-Token": detail["customer_token"]},
        data={
            "phone_suffix": detail["customer_phone"][-4:],
            "order_id": seed_order_id,
            "memo": "고객 AS 사진 확인 요청",
        },
        files={"files": ("customer-as.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert as_response.status_code == 200, as_response.text

    response = client.get("/api/admin/notifications", headers=admin_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert any(
        item["event_type"] == TimelineEventType.PHOTO_UPLOADED.value
        and item["title"] == "고객 AS 사진 업로드"
        and item["actor_label"] == "고객"
        for item in body
    )


def test_admin_notifications_scan_past_unrelated_timeline_noise(
    client: TestClient,
    seed_admin_token: str,
    seed_order_id: str,
) -> None:
    admin_headers = {"Authorization": f"Bearer {seed_admin_token}"}
    detail = client.get(f"/api/admin/orders/{seed_order_id}", headers=admin_headers).json()
    status_response = client.patch(
        f"/api/admin/orders/{seed_order_id}",
        headers=admin_headers,
        json={"status": OrderStatus.CUSTOMER_DELIVERY_DONE.value},
    )
    assert status_response.status_code == 200, status_response.text
    as_response = client.post(
        "/api/customer/orders/as-request",
        headers={"X-Customer-Token": detail["customer_token"]},
        data={
            "phone_suffix": detail["customer_phone"][-4:],
            "order_id": seed_order_id,
            "memo": "오래된 유효 고객 AS 알림",
        },
    )
    assert as_response.status_code == 200, as_response.text

    for index in range(101):
        response = client.patch(
            f"/api/admin/orders/{seed_order_id}",
            headers=admin_headers,
            json={"internal_memo": f"알림 대상이 아닌 운영 메모 {index}"},
        )
        assert response.status_code == 200, response.text

    notifications = client.get(
        "/api/admin/notifications?limit=20",
        headers=admin_headers,
    )
    assert notifications.status_code == 200, notifications.text
    assert any(
        item["event_type"] == TimelineEventType.AS_REQUESTED.value
        and item["description"] == "오래된 유효 고객 AS 알림"
        for item in notifications.json()
    )
