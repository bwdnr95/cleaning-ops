from collections.abc import Generator
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_session
from app.core.config import settings
from app.db.seed import (
    DEV_ADMIN_EMAIL,
    DEV_ADMIN_PASSWORD,
    DEV_PARTNER_ID,
    DEV_PARTNER_PASSWORD,
    DEV_PARTNER_PHONE,
    seed_dev_data,
)
from app.domain.constants import MessageType, OrderStatus, PhotoType, RecipientType, TimelineEventType
from app.main import create_app
from app.models import Base, Order, OrderPhoto
from app.repositories.timeline import TimelineRepository
from app.schemas.message import MessageSendRequest
from app.services.dashboard import DashboardService
from app.services.messages import MessageService


def make_test_client(seed_callback=None) -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as db:
        seed_dev_data(db)
        if seed_callback is not None:
            seed_callback(db)
            db.commit()

    app = create_app()

    def override_get_session() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
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


def test_seeded_admin_can_login_and_access_admin_route() -> None:
    client = make_test_client()
    session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)

    response = client.get(
        "/api/admin/orders",
        headers={"Authorization": f"Bearer {session['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()[0]["id"] == "seed-order-2450"


def test_seeded_partner_cannot_access_admin_route() -> None:
    client = make_test_client()
    session = login(client, "/api/auth/partner/login", DEV_PARTNER_PHONE, DEV_PARTNER_PASSWORD)

    response = client.get(
        "/api/admin/orders",
        headers={"Authorization": f"Bearer {session['access_token']}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "admin_required"


def test_seeded_partner_can_only_list_own_jobs() -> None:
    client = make_test_client()
    session = login(client, "/api/auth/partner/login", DEV_PARTNER_PHONE, DEV_PARTNER_PASSWORD)

    response = client.get(
        "/api/partner/jobs",
        headers={"Authorization": f"Bearer {session['access_token']}"},
    )

    assert response.status_code == 200
    jobs = response.json()
    assert [job["id"] for job in jobs] == ["seed-order-2450"]
    assert "total_amount" not in jobs[0]
    assert "payment_memo" not in jobs[0]


def test_partner_can_open_start_and_complete_own_job_with_timeline() -> None:
    client = make_test_client()
    partner_session = login(client, "/api/auth/partner/login", DEV_PARTNER_PHONE, DEV_PARTNER_PASSWORD)
    headers = {"Authorization": f"Bearer {partner_session['access_token']}"}

    detail_response = client.get("/api/partner/jobs/seed-order-2450", headers=headers)
    start_response = client.post("/api/partner/jobs/seed-order-2450/start", headers=headers)
    complete_response = client.post("/api/partner/jobs/seed-order-2450/complete", headers=headers)

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["id"] == "seed-order-2450"
    assert "total_amount" not in detail
    assert "source_channel" not in detail
    assert "payment_memo" not in detail

    assert start_response.status_code == 200
    assert start_response.json()["status"] == "작업진행"
    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == "사진검수대기"

    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    admin_detail = client.get(
        "/api/admin/orders/seed-order-2450",
        headers={"Authorization": f"Bearer {admin_session['access_token']}"},
    )

    assert admin_detail.status_code == 200
    body = admin_detail.json()
    assert body["status"] == "사진검수대기"
    status_events = [event for event in body["timeline"] if event["event_type"] == "status_changed"]
    assert [event["event_metadata"]["to"] for event in status_events[-2:]] == ["작업진행", "사진검수대기"]


def test_partner_cannot_open_or_mutate_unassigned_job() -> None:
    def seed_unassigned_job(db: Session) -> None:
        db.add(
            Order(
                id="unassigned-order-01",
                status=OrderStatus.SCHEDULE_CONFIRMED,
                received_date=date(2026, 5, 4),
                scheduled_date=date(2026, 5, 5),
                requested_time="10:00",
                partner_id=None,
                service_name="입주청소",
                customer_name="권한테스트",
                customer_phone="01011112222",
                customer_address="서울 테스트구 권한로 1",
                customer_token="unassigned-customer-token",
                customer_visible_payment=False,
            )
        )

    client = make_test_client(seed_unassigned_job)
    partner_session = login(client, "/api/auth/partner/login", DEV_PARTNER_PHONE, DEV_PARTNER_PASSWORD)
    headers = {"Authorization": f"Bearer {partner_session['access_token']}"}

    detail_response = client.get("/api/partner/jobs/unassigned-order-01", headers=headers)
    start_response = client.post("/api/partner/jobs/unassigned-order-01/start", headers=headers)
    complete_response = client.post("/api/partner/jobs/unassigned-order-01/complete", headers=headers)

    assert detail_response.status_code == 404
    assert start_response.status_code == 404
    assert complete_response.status_code == 404


def test_admin_order_detail_includes_timeline_photos_and_message_logs() -> None:
    client = make_test_client()
    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)

    response = client.get(
        "/api/admin/orders/seed-order-2450",
        headers={"Authorization": f"Bearer {admin_session['access_token']}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "seed-order-2450"
    assert body["source_channel"] is not None
    assert body["payment_memo"] is not None
    assert body["photos"] == []
    assert body["message_logs"] == []
    assert body["timeline"][0]["event_type"] == "created"


def test_admin_order_detail_reflects_status_and_partner_timeline_updates() -> None:
    client = make_test_client()
    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {admin_session['access_token']}"}

    patch_response = client.patch(
        "/api/admin/orders/seed-order-2450",
        headers=headers,
        json={
            "status": "협력사확인중",
            "partner_id": DEV_PARTNER_ID,
            "team_name": "상세 테스트팀",
        },
    )
    detail_response = client.get("/api/admin/orders/seed-order-2450", headers=headers)

    assert patch_response.status_code == 200
    assert detail_response.status_code == 200
    body = detail_response.json()
    assert body["status"] == "협력사확인중"
    assert body["team_name"] == "상세 테스트팀"
    event_types = [event["event_type"] for event in body["timeline"]]
    assert "status_changed" in event_types
    assert "partner_assigned" in event_types


def test_admin_calendar_lists_monthly_scheduled_orders_and_partner_filter() -> None:
    client = make_test_client()
    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {admin_session['access_token']}"}

    all_response = client.get("/api/admin/calendar?year=2026&month=5", headers=headers)
    partner_response = client.get(
        f"/api/admin/calendar?year=2026&month=5&partner_id={DEV_PARTNER_ID}",
        headers=headers,
    )

    assert all_response.status_code == 200
    assert partner_response.status_code == 200
    assert all_response.json()[0]["id"] == "seed-order-2450"
    assert all_response.json()[0]["scheduled_date"] == "2026-05-04"
    assert all_response.json()[0]["team_name"] == "강남 1팀"
    assert partner_response.json()[0]["partner_id"] == DEV_PARTNER_ID


def test_admin_calendar_rejects_partner_access() -> None:
    client = make_test_client()
    partner_session = login(client, "/api/auth/partner/login", DEV_PARTNER_PHONE, DEV_PARTNER_PASSWORD)

    response = client.get(
        "/api/admin/calendar?year=2026&month=5",
        headers={"Authorization": f"Bearer {partner_session['access_token']}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "admin_required"


def test_admin_can_create_order_and_update_operational_fields() -> None:
    client = make_test_client()
    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {admin_session['access_token']}"}

    create_response = client.post(
        "/api/admin/orders",
        headers=headers,
        json={
            "status": "신규접수",
            "received_date": "2026-05-04",
            "scheduled_date": "2026-05-06",
            "requested_time": "14:00",
            "service_name": "입주청소",
            "size_or_quantity": "32평",
            "service_detail": "방 3, 욕실 2",
            "special_request": "창틀 집중 요청",
            "source_channel": "전화",
            "customer_name": "신규고객",
            "customer_phone": "010-1111-2222",
            "customer_address": "서울 성동구 테스트로 1",
            "total_amount": 330000,
            "deposit_amount": 50000,
            "balance_amount": 280000,
            "onsite_extra_amount": 0,
            "vat_type": "included",
            "payment_status": "deposit_paid",
            "payment_memo": "계약금 확인",
            "evidence_memo": "현금영수증 요청",
            "partner_payment_amount": 200000,
            "partner_payment_status": "unpaid",
            "customer_visible_payment": True,
        },
    )

    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    assert created["customer_phone"] == "01011112222"
    assert created["customer_token"]

    update_response = client.patch(
        f"/api/admin/orders/{created['id']}",
        headers=headers,
        json={
            "customer_phone": "010-9999-8888",
            "customer_address": "서울 성동구 수정로 2",
            "service_name": "이사청소",
            "size_or_quantity": "40평",
            "total_amount": 410000,
            "payment_memo": "수정된 메모",
        },
    )
    detail_response = client.get(f"/api/admin/orders/{created['id']}", headers=headers)

    assert update_response.status_code == 200
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["customer_phone"] == "01099998888"
    assert detail["customer_address"] == "서울 성동구 수정로 2"
    assert detail["service_name"] == "이사청소"
    assert detail["size_or_quantity"] == "40평"
    assert detail["total_amount"] == 410000
    assert detail["payment_memo"] == "수정된 메모"
    assert detail["timeline"][0]["event_type"] == "created"


def test_refresh_token_rotates_and_rejects_reuse() -> None:
    client = make_test_client()
    session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)

    refresh_response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": session["refresh_token"]},
    )
    reused_response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": session["refresh_token"]},
    )

    assert refresh_response.status_code == 200
    assert refresh_response.json()["refresh_token"] != session["refresh_token"]
    assert reused_response.status_code == 401
    assert reused_response.json()["detail"] == "refresh_token_reused"


def test_logout_revokes_refresh_token() -> None:
    client = make_test_client()
    session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)

    logout_response = client.post(
        "/api/auth/logout",
        json={"refresh_token": session["refresh_token"]},
    )
    refresh_response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": session["refresh_token"]},
    )

    assert logout_response.status_code == 200
    assert logout_response.json()["message"] == "logout_complete"
    assert refresh_response.status_code == 401
    assert refresh_response.json()["detail"] == "refresh_token_reused"


def test_seeded_dashboard_summary_counts_tomorrow_notice_target() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as db:
        seed_dev_data(db)
        summary = DashboardService(db).summary(today=date(2026, 5, 3))

    assert summary.tomorrow_notice_targets == 1
    assert summary.today_jobs == 0


def test_admin_dashboard_recent_activity_returns_photos_and_messages() -> None:
    def seed_recent_activity(db: Session) -> None:
        db.add(
            OrderPhoto(
                id="recent-photo-01",
                order_id="seed-order-2450",
                uploaded_by_user_id="seed-partner-user",
                photo_type=PhotoType.AFTER,
                storage_key="photos/recent-photo-01.jpg",
                file_url="/uploads/photos/recent-photo-01.jpg",
                file_name="recent-photo-01.jpg",
                file_size=1200,
                content_type="image/jpeg",
                is_customer_visible=False,
            )
        )
        MessageService(db).send(
            MessageSendRequest(
                order_id="seed-order-2450",
                message_type=MessageType.CUSTOMER_PHOTO_READY,
                recipient_type=RecipientType.CUSTOMER,
            ),
            actor_user_id="seed-admin-user",
        )

    client = make_test_client(seed_recent_activity)
    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)

    response = client.get(
        "/api/admin/dashboard/recent-activity",
        headers={"Authorization": f"Bearer {admin_session['access_token']}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["photos"][0]["photo_id"] == "recent-photo-01"
    assert body["photos"][0]["order_id"] == "seed-order-2450"
    assert body["photos"][0]["is_customer_visible"] is False
    assert body["photos"][0]["file_url"] == "/uploads/photos/recent-photo-01.jpg"
    assert body["messages"][0]["order_id"] == "seed-order-2450"
    assert body["messages"][0]["message_type"] == "customer_photo_ready"
    assert body["messages"][0]["status"] == "sent"


def test_customer_link_verify_returns_customer_dto_only() -> None:
    client = make_test_client()

    response = client.post(
        "/api/customer/orders/seed-customer-token-2450/verify",
        json={"phone_suffix": "5432"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "seed-order-2450"
    assert body["customer_name"] == "박고객"
    assert body["total_amount"] is None
    assert "customer_phone" not in body
    assert "source_channel" not in body
    assert "payment_memo" not in body
    assert "evidence_memo" not in body
    assert "partner_payment_amount" not in body
    assert body["photos"] == []


def test_customer_link_verify_rejects_wrong_phone_suffix() -> None:
    client = make_test_client()

    response = client.post(
        "/api/customer/orders/seed-customer-token-2450/verify",
        json={"phone_suffix": "0000"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "order_not_found"


def test_customer_link_verify_returns_only_customer_visible_photos() -> None:
    def seed_photos(db: Session) -> None:
        db.add_all(
            [
                OrderPhoto(
                    id="photo-private",
                    order_id="seed-order-2450",
                    uploaded_by_user_id="seed-partner-user",
                    photo_type=PhotoType.BEFORE,
                    file_url="https://cdn.example.com/private-before.jpg",
                    file_name="private-before.jpg",
                    file_size=1000,
                    is_customer_visible=False,
                ),
                OrderPhoto(
                    id="photo-public",
                    order_id="seed-order-2450",
                    uploaded_by_user_id="seed-partner-user",
                    photo_type=PhotoType.AFTER,
                    file_url="https://cdn.example.com/public-after.jpg",
                    file_name="public-after.jpg",
                    file_size=2000,
                    is_customer_visible=True,
                ),
            ]
        )

    client = make_test_client(seed_photos)

    response = client.post(
        "/api/customer/orders/seed-customer-token-2450/verify",
        json={"phone_suffix": "5432"},
    )

    assert response.status_code == 200
    photos = response.json()["photos"]
    assert photos == [
        {
            "id": "photo-public",
            "photo_type": "after",
            "file_url": "https://cdn.example.com/public-after.jpg",
            "file_name": "public-after.jpg",
        }
    ]
    assert "uploaded_by_user_id" not in photos[0]
    assert "is_customer_visible" not in photos[0]


def test_partner_upload_admin_approve_customer_visibility_flow(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "storage_root", str(tmp_path / "uploads"))
    client = make_test_client()
    partner_session = login(client, "/api/auth/partner/login", DEV_PARTNER_PHONE, DEV_PARTNER_PASSWORD)

    upload_response = client.post(
        "/api/partner/jobs/seed-order-2450/photos",
        headers={"Authorization": f"Bearer {partner_session['access_token']}"},
        data={"photo_type": "before"},
        files={"file": ("upload-before.jpg", b"fake-jpeg-bytes", "image/jpeg")},
    )

    assert upload_response.status_code == 200
    uploaded = upload_response.json()
    assert uploaded["is_customer_visible"] is False
    assert uploaded["file_url"].startswith("/uploads/photos/")
    assert uploaded["file_name"] == "upload-before.jpg"
    assert uploaded["file_size"] == len(b"fake-jpeg-bytes")
    assert uploaded["content_type"] == "image/jpeg"
    assert "storage_key" not in uploaded

    before_approval = client.post(
        "/api/customer/orders/seed-customer-token-2450/verify",
        json={"phone_suffix": "5432"},
    )
    assert before_approval.status_code == 200
    assert before_approval.json()["photos"] == []

    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    queue_response = client.get(
        "/api/admin/photos/review-queue",
        headers={"Authorization": f"Bearer {admin_session['access_token']}"},
    )
    assert queue_response.status_code == 200
    assert queue_response.json()[0]["photos"][0]["id"] == uploaded["id"]
    detail_response = client.get(
        "/api/admin/orders/seed-order-2450",
        headers={"Authorization": f"Bearer {admin_session['access_token']}"},
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == "사진검수대기"
    event_types = [event["event_type"] for event in detail["timeline"]]
    assert "photo_uploaded" in event_types
    assert "status_changed" in event_types

    approve_response = client.post(
        f"/api/admin/photos/{uploaded['id']}/approve",
        headers={"Authorization": f"Bearer {admin_session['access_token']}"},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["is_customer_visible"] is True

    after_approval = client.post(
        "/api/customer/orders/seed-customer-token-2450/verify",
        json={"phone_suffix": "5432"},
    )
    assert after_approval.status_code == 200
    assert after_approval.json()["photos"] == [
        {
            "id": uploaded["id"],
            "photo_type": "before",
            "file_url": uploaded["file_url"],
            "file_name": "upload-before.jpg",
        }
    ]


def test_partner_upload_rejects_invalid_photo_content_type(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "storage_root", str(tmp_path / "uploads"))
    client = make_test_client()
    partner_session = login(client, "/api/auth/partner/login", DEV_PARTNER_PHONE, DEV_PARTNER_PASSWORD)

    response = client.post(
        "/api/partner/jobs/seed-order-2450/photos",
        headers={"Authorization": f"Bearer {partner_session['access_token']}"},
        data={"photo_type": "before"},
        files={"file": ("notes.txt", b"not an image", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "unsupported_photo_type"


def test_partner_upload_rejects_photo_over_size_limit(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "storage_root", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "photo_max_upload_bytes", 4)
    client = make_test_client()
    partner_session = login(client, "/api/auth/partner/login", DEV_PARTNER_PHONE, DEV_PARTNER_PASSWORD)

    response = client.post(
        "/api/partner/jobs/seed-order-2450/photos",
        headers={"Authorization": f"Bearer {partner_session['access_token']}"},
        data={"photo_type": "before"},
        files={"file": ("large.jpg", b"too-large", "image/jpeg")},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "photo_too_large"


def test_customer_photo_ready_message_includes_customer_link_and_timeline() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as db:
        seed_dev_data(db)
        log = MessageService(db).send(
            MessageSendRequest(
                order_id="seed-order-2450",
                message_type=MessageType.CUSTOMER_PHOTO_READY,
                recipient_type=RecipientType.CUSTOMER,
            ),
            actor_user_id="seed-admin-user",
        )
        order = db.get(Order, "seed-order-2450")
        events = TimelineRepository(db).list_for_order("seed-order-2450")

    assert log.status == "sent"
    assert "http://localhost:5173/customer?t=seed-customer-token-2450" in log.content
    assert order.status == OrderStatus.CUSTOMER_DELIVERY_DONE
    assert TimelineEventType.MESSAGE_SENT in {event.event_type for event in events}
    assert TimelineEventType.CUSTOMER_LINK_SENT in {event.event_type for event in events}


def test_admin_can_send_customer_photo_ready_message() -> None:
    client = make_test_client()
    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {admin_session['access_token']}"}

    response = client.post(
        "/api/admin/messages/send",
        headers=headers,
        json={
            "order_id": "seed-order-2450",
            "message_type": "customer_photo_ready",
            "recipient_type": "customer",
            "channel": "sms",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "sent"
    assert "/customer?t=seed-customer-token-2450" in body["content"]

    detail_response = client.get("/api/admin/orders/seed-order-2450", headers=headers)
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["message_logs"][0]["message_type"] == "customer_photo_ready"
    assert "message_sent" in {event["event_type"] for event in detail["timeline"]}
    assert "customer_link_sent" in {event["event_type"] for event in detail["timeline"]}
