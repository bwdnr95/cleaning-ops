from collections.abc import Callable, Generator
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_session
from app.core.config import settings
from app.db.seed import (
    DEV_ADMIN_EMAIL,
    DEV_ADMIN_PASSWORD,
    DEV_ORDER_ID,
    DEV_PARTNER_PASSWORD,
    DEV_PARTNER_PHONE,
    DEV_PARTNER_USER_ID,
    seed_dev_data,
)
from app.domain.constants import OrderStatus, PhotoType, TimelineEventType
from app.main import create_app
from app.models import Base, Order, OrderGroup, OrderPhoto, Partner
from app.services.photos import PhotoService


SeedCallback = Callable[[Session], None]
PNG_BYTES = b"\x89PNG\r\n\x1a\ncleanops-test-image"


def make_test_client(
    tmp_path: Path,
    monkeypatch,
    seed_callback: SeedCallback | None = None,
) -> TestClient:
    monkeypatch.setattr(settings, "storage_root", str(tmp_path / "storage"))
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    with testing_session_local() as db:
        seed_dev_data(db)
        if seed_callback is not None:
            seed_callback(db)
        db.commit()

    app = create_app()

    def override_get_session() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app)


def login(client: TestClient, path: str, identifier: str, password: str) -> dict:
    response = client.post(path, json={"identifier": identifier, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def partner_headers(client: TestClient) -> dict[str, str]:
    session = login(client, "/api/auth/partner/login", DEV_PARTNER_PHONE, DEV_PARTNER_PASSWORD)
    return auth_headers(session["access_token"])


def admin_headers(client: TestClient) -> dict[str, str]:
    session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    return auth_headers(session["access_token"])


def seed_photo(
    db: Session,
    *,
    photo_id: str,
    order_id: str = DEV_ORDER_ID,
    photo_type: PhotoType = PhotoType.BEFORE,
    is_customer_visible: bool = False,
) -> None:
    db.add(
        OrderPhoto(
            id=photo_id,
            order_id=order_id,
            uploaded_by_user_id=DEV_PARTNER_USER_ID,
            photo_type=photo_type,
            file_url=f"/uploads/photos/{photo_id}.jpg",
            file_name=f"{photo_id}.jpg",
            file_size=128,
            content_type="image/jpeg",
            is_customer_visible=is_customer_visible,
        )
    )


def add_order_group(
    db: Session,
    *,
    group_id: str,
    customer_token: str,
    customer_name: str,
    customer_phone: str,
    customer_address: str,
) -> None:
    db.add(
        OrderGroup(
            id=group_id,
            customer_token=customer_token,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_address=customer_address,
            customer_visible_payment=False,
        )
    )


def seed_other_partner_order_with_photo(db: Session) -> None:
    db.add(
        Partner(
            id="other-partner-01",
            name="Other Partner",
            manager_name="Other Manager",
            phone="01000001111",
            service_areas="Seoul",
            available_services="Cleaning",
            memo=None,
            is_active=True,
        )
    )
    add_order_group(
        db,
        group_id="other-partner-order-group",
        customer_token="other-partner-customer-token",
        customer_name="Other Customer",
        customer_phone="01022223333",
        customer_address="Seoul Other Address",
    )
    db.add(
        Order(
            id="other-partner-order",
            group_id="other-partner-order-group",
            status=OrderStatus.SCHEDULE_CONFIRMED,
            received_date=date(2026, 5, 5),
            scheduled_date=date(2026, 5, 7),
            requested_time="11:00",
            partner_id="other-partner-01",
            team_name="Other Team",
            service_name="Other Partner Job",
            customer_name="Other Customer",
            customer_phone="01022223333",
            customer_address="Seoul Other Address",
            customer_token="other-partner-customer-token",
            customer_visible_payment=False,
        )
    )
    seed_photo(
        db,
        photo_id="other-partner-photo",
        order_id="other-partner-order",
        photo_type=PhotoType.AFTER,
    )


def test_partner_job_detail_includes_only_scoped_job_photos(tmp_path, monkeypatch) -> None:
    def seed(db: Session) -> None:
        seed_photo(db, photo_id="own-before-photo", photo_type=PhotoType.BEFORE)
        seed_photo(db, photo_id="own-after-photo", photo_type=PhotoType.AFTER)
        seed_other_partner_order_with_photo(db)

    client = make_test_client(tmp_path, monkeypatch, seed)
    headers = partner_headers(client)

    detail_response = client.get(f"/api/partner/jobs/{DEV_ORDER_ID}", headers=headers)
    other_response = client.get("/api/partner/jobs/other-partner-order", headers=headers)

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["id"] == DEV_ORDER_ID
    assert "total_amount" not in detail
    assert "payment_memo" not in detail
    assert "source_channel" not in detail
    assert {photo["id"] for photo in detail["photos"]} == {"own-before-photo", "own-after-photo"}
    assert {photo["order_id"] for photo in detail["photos"]} == {DEV_ORDER_ID}
    assert all("uploaded_by_user_id" not in photo for photo in detail["photos"])
    assert other_response.status_code == 404
    assert other_response.json()["detail"] == "order_not_found"


def test_partner_job_list_does_not_include_other_partner_photos(tmp_path, monkeypatch) -> None:
    def seed(db: Session) -> None:
        seed_photo(db, photo_id="own-list-photo", photo_type=PhotoType.ETC)
        seed_other_partner_order_with_photo(db)

    client = make_test_client(tmp_path, monkeypatch, seed)
    headers = partner_headers(client)

    response = client.get("/api/partner/jobs", headers=headers)

    assert response.status_code == 200
    jobs = response.json()
    assert [job["id"] for job in jobs] == [DEV_ORDER_ID]
    assert {photo["id"] for photo in jobs[0]["photos"]} == {"own-list-photo"}
    assert all(photo["order_id"] == DEV_ORDER_ID for photo in jobs[0]["photos"])


def test_partner_upload_auto_publishes_and_records_timeline(tmp_path, monkeypatch) -> None:
    client = make_test_client(tmp_path, monkeypatch)
    headers = partner_headers(client)

    response = client.post(
        f"/api/partner/jobs/{DEV_ORDER_ID}/photos",
        headers=headers,
        data={"photo_type": "before"},
        files={"file": ("upload-before.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 200, response.text
    uploaded = response.json()
    assert uploaded["photo_type"] == "before"
    assert uploaded["file_name"] == "upload-before.png"
    assert uploaded["file_url"].startswith("/uploads/photos/")
    assert uploaded["photo_source"] == "partner"
    assert uploaded["is_customer_visible"] is True
    assert "uploaded_by_user_id" not in uploaded

    detail_response = client.get(f"/api/partner/jobs/{DEV_ORDER_ID}", headers=headers)
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == OrderStatus.SCHEDULE_CONFIRMED
    assert uploaded["id"] in {photo["id"] for photo in detail["photos"]}
    assert all(photo["is_customer_visible"] is True for photo in detail["photos"])

    admin_detail_response = client.get(
        f"/api/admin/orders/{DEV_ORDER_ID}",
        headers=admin_headers(client),
    )
    assert admin_detail_response.status_code == 200
    event_types = {event["event_type"] for event in admin_detail_response.json()["timeline"]}
    assert {"photo_uploaded", "photo_approved"}.issubset(event_types)
    assert "status_changed" not in event_types


def test_partner_can_delete_uploaded_photo_before_completion(tmp_path, monkeypatch) -> None:
    client = make_test_client(tmp_path, monkeypatch)
    headers = partner_headers(client)

    upload_response = client.post(
        f"/api/partner/jobs/{DEV_ORDER_ID}/photos",
        headers=headers,
        data={"photo_type": "before"},
        files={"file": ("wrong-before.png", PNG_BYTES, "image/png")},
    )
    assert upload_response.status_code == 200, upload_response.text
    photo_id = upload_response.json()["id"]
    storage_root = Path(settings.storage_root)
    assert [path for path in storage_root.rglob("*") if path.is_file()]

    delete_response = client.delete(
        f"/api/partner/jobs/{DEV_ORDER_ID}/photos/{photo_id}",
        headers=headers,
    )

    assert delete_response.status_code == 204, delete_response.text
    detail_response = client.get(f"/api/partner/jobs/{DEV_ORDER_ID}", headers=headers)
    assert detail_response.status_code == 200
    assert photo_id not in {photo["id"] for photo in detail_response.json()["photos"]}
    assert not [path for path in storage_root.rglob("*") if path.is_file()]

    admin_detail_response = client.get(
        f"/api/admin/orders/{DEV_ORDER_ID}",
        headers=admin_headers(client),
    )
    assert admin_detail_response.status_code == 200
    assert any(
        event["event_type"] == TimelineEventType.PHOTO_REVOKED.value
        and event["title"] == "협력사 사진 삭제"
        for event in admin_detail_response.json()["timeline"]
    )


def test_partner_delete_rejects_other_partner_photo(tmp_path, monkeypatch) -> None:
    def seed(db: Session) -> None:
        seed_other_partner_order_with_photo(db)

    client = make_test_client(tmp_path, monkeypatch, seed)
    headers = partner_headers(client)

    response = client.delete(
        "/api/partner/jobs/other-partner-order/photos/other-partner-photo",
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "order_not_found"


def test_partner_delete_rejects_locked_job_status(tmp_path, monkeypatch) -> None:
    def seed(db: Session) -> None:
        order = db.get(Order, DEV_ORDER_ID)
        assert order is not None
        order.status = OrderStatus.CUSTOMER_DELIVERY_NEEDED
        seed_photo(db, photo_id="locked-before-photo", photo_type=PhotoType.BEFORE)

    client = make_test_client(tmp_path, monkeypatch, seed)
    headers = partner_headers(client)

    response = client.delete(
        f"/api/partner/jobs/{DEV_ORDER_ID}/photos/locked-before-photo",
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "invalid_status_for_delete"


def test_partner_upload_removes_stored_file_when_db_write_fails(tmp_path, monkeypatch) -> None:
    def fail_upload(self, **kwargs):
        raise RuntimeError("db_down")

    monkeypatch.setattr(PhotoService, "upload_stored_for_partner", fail_upload)
    client = make_test_client(tmp_path, monkeypatch)
    headers = partner_headers(client)

    with pytest.raises(RuntimeError, match="db_down"):
        client.post(
            f"/api/partner/jobs/{DEV_ORDER_ID}/photos",
            headers=headers,
            data={"photo_type": "before"},
            files={"file": ("upload-before.png", PNG_BYTES, "image/png")},
        )

    storage_root = Path(settings.storage_root)
    assert not [path for path in storage_root.rglob("*") if path.is_file()]


def test_partner_upload_rejects_spoofed_photo_content(tmp_path, monkeypatch) -> None:
    client = make_test_client(tmp_path, monkeypatch)
    headers = partner_headers(client)

    response = client.post(
        f"/api/partner/jobs/{DEV_ORDER_ID}/photos",
        headers=headers,
        data={"photo_type": "before"},
        files={"file": ("spoofed.jpg", b"not really an image", "image/jpeg")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "unsupported_photo_type"


def test_customer_dto_exposes_only_approved_photos(tmp_path, monkeypatch) -> None:
    def seed(db: Session) -> None:
        seed_photo(db, photo_id="customer-hidden-photo", photo_type=PhotoType.BEFORE)
        seed_photo(
            db,
            photo_id="customer-visible-photo",
            photo_type=PhotoType.AFTER,
            is_customer_visible=True,
        )

    client = make_test_client(tmp_path, monkeypatch, seed)

    response = client.post(
        "/api/customer/orders/verify",
        headers={"X-Customer-Token": "ct2_seed-customer-token-2450"},
        json={"phone_suffix": "5432"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["customer_phone"] == "01098765432"
    assert body["lines"][0]["photos"] == [
        {
            "id": "customer-visible-photo",
            "photo_type": "after",
            "file_url": "/uploads/photos/customer-visible-photo.jpg",
            "file_name": "customer-visible-photo.jpg",
        }
    ]
    assert "payment_memo" not in body
    assert "partner_payment_amount" not in body
