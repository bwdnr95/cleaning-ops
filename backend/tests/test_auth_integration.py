import hashlib
import hmac
import json
from collections.abc import Generator
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_session
from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.seed import (
    DEV_ADMIN_EMAIL,
    DEV_ADMIN_PASSWORD,
    DEV_PARTNER_ID,
    DEV_PARTNER_PASSWORD,
    DEV_PARTNER_PHONE,
    DEV_PARTNER_USER_ID,
    DEV_SERVICE_ITEM_ID,
    seed_dev_data,
)
from app.domain.constants import (
    MessageChannel,
    MessageStatus,
    MessageType,
    OrderStatus,
    PhotoType,
    RecipientType,
    TimelineEventType,
    UserRole,
)
from app.main import create_app
from app.models import Base, MessageLog, Order, OrderGroup, OrderPhoto, Partner, User
from app.repositories.timeline import TimelineRepository
from app.schemas.message import MessageSendRequest
from app.services.dashboard import DashboardService
from app.services.messages import MessageSendResult, MessageService

PNG_BYTES = b"\x89PNG\r\n\x1a\ncleanops-test-image"


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


def add_order_group(
    db: Session,
    *,
    group_id: str,
    customer_token: str,
    customer_name: str,
    customer_phone: str,
    customer_address: str,
    customer_visible_payment: bool = False,
    source_channel: str | None = None,
) -> None:
    db.add(
        OrderGroup(
            id=group_id,
            customer_token=customer_token,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_address=customer_address,
            customer_visible_payment=customer_visible_payment,
            source_channel=source_channel,
        )
    )


def solapi_webhook_signature(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


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
    early_complete_response = client.post("/api/partner/jobs/seed-order-2450/complete", headers=headers)
    start_response = client.post("/api/partner/jobs/seed-order-2450/start", headers=headers)
    upload_response = client.post(
        "/api/partner/jobs/seed-order-2450/photos",
        headers=headers,
        data={"photo_type": "after"},
        files={"file": ("complete-after.png", PNG_BYTES, "image/png")},
    )
    complete_response = client.post("/api/partner/jobs/seed-order-2450/complete", headers=headers)
    restart_response = client.post("/api/partner/jobs/seed-order-2450/start", headers=headers)
    recomplete_response = client.post("/api/partner/jobs/seed-order-2450/complete", headers=headers)

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["id"] == "seed-order-2450"
    assert "total_amount" not in detail
    assert "source_channel" not in detail
    assert "payment_memo" not in detail

    assert early_complete_response.status_code == 409
    assert early_complete_response.json()["detail"] == "invalid_status_transition"
    assert start_response.status_code == 200
    assert start_response.json()["status"] == "작업진행"
    assert upload_response.status_code == 200
    assert upload_response.json()["is_customer_visible"] is True
    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == "고객전달필요"
    assert restart_response.status_code == 409
    assert restart_response.json()["detail"] == "invalid_status_transition"
    assert recomplete_response.status_code == 409
    assert recomplete_response.json()["detail"] == "invalid_status_transition"

    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    admin_detail = client.get(
        "/api/admin/orders/seed-order-2450",
        headers={"Authorization": f"Bearer {admin_session['access_token']}"},
    )

    assert admin_detail.status_code == 200
    body = admin_detail.json()
    assert body["status"] == "고객전달필요"
    status_events = [event for event in body["timeline"] if event["event_type"] == "status_changed"]
    status_targets = {event["event_metadata"]["to"] for event in status_events}
    assert {"작업진행", "고객전달필요"}.issubset(status_targets)


def test_partner_cannot_open_or_mutate_unassigned_job() -> None:
    def seed_unassigned_job(db: Session) -> None:
        add_order_group(
            db,
            group_id="unassigned-order-01-group",
            customer_token="unassigned-customer-token",
            customer_name="권한테스트",
            customer_phone="01011112222",
            customer_address="서울 테스트구 권한로 1",
        )
        db.add(
            Order(
                id="unassigned-order-01",
                group_id="unassigned-order-01-group",
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


def test_inactive_partner_token_cannot_use_job_mutation_routes() -> None:
    def deactivate_seed_partner(db: Session) -> None:
        partner = db.get(Partner, DEV_PARTNER_ID)
        assert partner is not None
        partner.is_active = False

    client = make_test_client(deactivate_seed_partner)
    token = create_access_token(
        user_id=DEV_PARTNER_USER_ID,
        role=UserRole.PARTNER,
        partner_id=DEV_PARTNER_ID,
    )
    headers = {"Authorization": f"Bearer {token}"}

    responses = [
        client.get("/api/partner/jobs", headers=headers),
        client.post("/api/partner/jobs/seed-order-2450/start", headers=headers),
        client.post("/api/partner/jobs/seed-order-2450/complete", headers=headers),
        client.post(
            "/api/partner/jobs/seed-order-2450/photos",
            headers=headers,
            data={"photo_type": "before"},
            files={"file": ("blocked.png", PNG_BYTES, "image/png")},
        ),
    ]

    assert {response.status_code for response in responses} == {401}
    assert {response.json()["detail"] for response in responses} == {"user_not_found"}


def test_other_partner_token_cannot_mutate_seed_partner_job() -> None:
    def seed_other_partner_user(db: Session) -> None:
        db.add(
            Partner(
                id="other-partner-scope",
                name="Other Scope Partner",
                manager_name="Other Manager",
                phone="01033334444",
                service_areas="Seoul",
                available_services="Cleaning",
                memo=None,
                is_active=True,
            )
        )
        db.add(
            User(
                id="other-partner-user",
                role=UserRole.PARTNER,
                name="Other Partner User",
                email=None,
                phone="01033334444",
                password_hash=hash_password("OtherPartner123!"),
                partner_id="other-partner-scope",
                is_active=True,
            )
        )

    client = make_test_client(seed_other_partner_user)
    token = create_access_token(
        user_id="other-partner-user",
        role=UserRole.PARTNER,
        partner_id="other-partner-scope",
    )
    headers = {"Authorization": f"Bearer {token}"}

    responses = [
        client.get("/api/partner/jobs/seed-order-2450", headers=headers),
        client.post("/api/partner/jobs/seed-order-2450/start", headers=headers),
        client.post("/api/partner/jobs/seed-order-2450/complete", headers=headers),
        client.post(
            "/api/partner/jobs/seed-order-2450/photos",
            headers=headers,
            data={"photo_type": "before"},
            files={"file": ("not-owned.png", PNG_BYTES, "image/png")},
        ),
    ]

    assert {response.status_code for response in responses} == {404}
    assert {response.json()["detail"] for response in responses} == {"order_not_found"}


def test_seed_partner_token_cannot_mutate_other_partner_order() -> None:
    """역방향 cross-partner ownership 검증 (P1-9): seed partner 토큰이 다른 partner 의 order 를 못 본다."""

    def seed_other_partner_order(db: Session) -> None:
        db.add(
            Partner(
                id="other-partner-scope-reverse",
                name="Reverse Scope Partner",
                manager_name="Reverse Manager",
                phone="01055556666",
                service_areas="Seoul",
                available_services="Cleaning",
                memo=None,
                is_active=True,
            )
        )
        add_order_group(
            db,
            group_id="other-partner-order-01-group",
            customer_token="other-partner-order-01-token",
            customer_name="다른 협력사 고객",
            customer_phone="01077778888",
            customer_address="서울시 송파구",
        )
        db.add(
            Order(
                id="other-partner-order-01",
                group_id="other-partner-order-01-group",
                customer_name="다른 협력사 고객",
                customer_phone="01077778888",
                customer_address="서울시 송파구",
                service_name="입주청소",
                status=OrderStatus.SCHEDULED,
                received_date=date(2026, 5, 31),
                scheduled_date=date(2026, 6, 1),
                requested_time="10:00",
                partner_id="other-partner-scope-reverse",
                customer_token="other-partner-order-01-token",
                customer_visible_payment=False,
            )
        )

    client = make_test_client(seed_other_partner_order)
    token = create_access_token(
        user_id=DEV_PARTNER_USER_ID,
        role=UserRole.PARTNER,
        partner_id=DEV_PARTNER_ID,
    )
    headers = {"Authorization": f"Bearer {token}"}

    responses = [
        client.get("/api/partner/jobs/other-partner-order-01", headers=headers),
        client.post("/api/partner/jobs/other-partner-order-01/start", headers=headers),
        client.post("/api/partner/jobs/other-partner-order-01/complete", headers=headers),
        client.post(
            "/api/partner/jobs/other-partner-order-01/photos",
            headers=headers,
            data={"photo_type": "before"},
            files={"file": ("reverse-attempt.png", PNG_BYTES, "image/png")},
        ),
    ]

    assert {response.status_code for response in responses} == {404}
    assert {response.json()["detail"] for response in responses} == {"order_not_found"}


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
    assert "created" in {event["event_type"] for event in body["timeline"]}


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


def test_admin_payment_and_settlement_update_records_timeline_and_queue() -> None:
    client = make_test_client()
    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {admin_session['access_token']}"}

    update_response = client.patch(
        "/api/admin/orders/seed-order-2450",
        headers=headers,
        json={
            "payment_status": "balance_pending",
            "payment_memo": "잔금 확인 필요",
            "partner_payment_status": "paid",
        },
    )
    detail_response = client.get("/api/admin/orders/seed-order-2450", headers=headers)
    summary_response = client.get("/api/admin/dashboard/summary", headers=headers)

    assert update_response.status_code == 200
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["payment_status"] == "balance_pending"
    assert detail["partner_payment_status"] == "paid"

    payment_events = [event for event in detail["timeline"] if event["event_type"] == "memo_added"]
    assert payment_events
    changes = payment_events[-1]["event_metadata"]["changes"]
    assert changes["payment_status"] == {"from": "deposit_paid", "to": "balance_pending"}
    assert changes["partner_payment_status"] == {"from": "unpaid", "to": "paid"}

    assert summary_response.status_code == 200
    assert summary_response.json()["payment_check_needed"] == 1


def test_admin_schedule_update_records_timeline() -> None:
    client = make_test_client()
    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {admin_session['access_token']}"}

    update_response = client.patch(
        "/api/admin/orders/seed-order-2450",
        headers=headers,
        json={
            "scheduled_date": "2026-05-06",
            "requested_time": "16:30",
        },
    )
    detail_response = client.get("/api/admin/orders/seed-order-2450", headers=headers)

    assert update_response.status_code == 200
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["scheduled_date"] == "2026-05-06"
    assert detail["requested_time"] == "16:30"

    schedule_events = [
        event
        for event in detail["timeline"]
        if event["event_type"] == "memo_added" and event["title"] == "방문 일정 변경"
    ]
    assert schedule_events
    changes = schedule_events[-1]["event_metadata"]["changes"]
    assert changes["scheduled_date"] == {"from": "2026-05-04", "to": "2026-05-06"}
    assert changes["requested_time"] == {"from": "09:00", "to": "16:30"}


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
    assert all_response.json()[0]["customer_phone"] == "01098765432"
    assert partner_response.json()[0]["partner_id"] == DEV_PARTNER_ID


def test_admin_calendar_includes_group_address_detail() -> None:
    client = make_test_client()
    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {admin_session['access_token']}"}

    create_response = client.post(
        "/api/admin/orders/groups",
        headers=headers,
        json={
            "customer_name": "Calendar Detail Customer",
            "customer_phone": "010-1111-2222",
            "customer_address": "Seoul Gangnam",
            "customer_address_detail": "Unit 1204",
            "lines": [
                {
                    "status": OrderStatus.SCHEDULE_CONFIRMED.value,
                    "received_date": "2026-05-18",
                    "scheduled_date": "2026-05-22",
                    "service_name": "calendar detail clean",
                },
            ],
        },
    )
    assert create_response.status_code == 201, create_response.text
    line_id = create_response.json()["lines"][0]["id"]

    response = client.get("/api/admin/calendar?year=2026&month=5", headers=headers)

    assert response.status_code == 200
    item = next(item for item in response.json() if item["id"] == line_id)
    assert item["customer_address"] == "Seoul Gangnam"
    assert item["customer_address_detail"] == "Unit 1204"
    assert item["customer_phone"] == "01011112222"


def test_admin_calendar_rejects_partner_access() -> None:
    client = make_test_client()
    partner_session = login(client, "/api/auth/partner/login", DEV_PARTNER_PHONE, DEV_PARTNER_PASSWORD)

    response = client.get(
        "/api/admin/calendar?year=2026&month=5",
        headers={"Authorization": f"Bearer {partner_session['access_token']}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "admin_required"


def test_admin_order_list_returns_more_than_legacy_page_limit() -> None:
    client = make_test_client()
    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {admin_session['access_token']}"}
    created_service_names = set()

    for index in range(55):
        service_name = f"pagination-check-{index:02d}"
        created_service_names.add(service_name)
        create_response = client.post(
            "/api/admin/orders",
            headers=headers,
            json={
                "status": OrderStatus.NEW.value,
                "received_date": "2026-05-10",
                "scheduled_date": "2026-05-25",
                "service_name": service_name,
                "customer_name": f"Pagination Customer {index:02d}",
                "customer_phone": "010-1234-5678",
                "customer_address": f"Seoul Pagination QA {index:02d}",
            },
        )
        assert create_response.status_code == 201, create_response.text

    list_response = client.get("/api/admin/orders?include_past_paid=true", headers=headers)

    assert list_response.status_code == 200
    body = list_response.json()
    assert len(body) >= 56
    assert created_service_names <= {order["service_name"] for order in body}


def test_admin_can_create_order_and_update_operational_fields() -> None:
    client = make_test_client()
    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {admin_session['access_token']}"}

    create_response = client.post(
        "/api/admin/orders",
        headers=headers,
        json={
            "status": "일정확정",
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

    group_update_response = client.patch(
        f"/api/admin/orders/groups/{created['group_id']}",
        headers=headers,
        json={
            "customer_phone": "010-9999-8888",
            "customer_address": "서울 성동구 수정로 2",
        },
    )
    update_response = client.patch(
        f"/api/admin/orders/{created['id']}",
        headers=headers,
        json={
            "service_name": "이사청소",
            "size_or_quantity": "40평",
            "total_amount": 410000,
            "payment_memo": "수정된 메모",
        },
    )
    detail_response = client.get(f"/api/admin/orders/{created['id']}", headers=headers)

    assert group_update_response.status_code == 200
    assert update_response.status_code == 200
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["customer_phone"] == "01099998888"
    assert detail["customer_address"] == "서울 성동구 수정로 2"
    assert detail["service_name"] == "이사청소"
    assert detail["size_or_quantity"] == "40평"
    assert detail["total_amount"] == 410000
    assert detail["payment_memo"] == "수정된 메모"
    assert "created" in {event["event_type"] for event in detail["timeline"]}


def test_admin_service_catalog_crud_and_order_catalog_selection() -> None:
    client = make_test_client()
    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {admin_session['access_token']}"}

    category_response = client.post(
        "/api/admin/services/categories",
        headers=headers,
        json={
            "name": "테스트 청소",
            "description": "주문 선택 테스트용",
            "is_active": True,
            "sort_order": 20,
        },
    )
    assert category_response.status_code == 201, category_response.text
    category = category_response.json()

    item_response = client.post(
        "/api/admin/services/items",
        headers=headers,
        json={
            "category_id": category["id"],
            "name": "프리미엄 입주청소",
            "unit": "평",
            "base_price": 390000,
            "description": "기본 견적 자동 반영",
            "is_active": True,
            "sort_order": 10,
        },
    )
    assert item_response.status_code == 201, item_response.text
    item = item_response.json()

    unused_item_response = client.post(
        "/api/admin/services/items",
        headers=headers,
        json={
            "category_id": category["id"],
            "name": "삭제 가능한 임시상품",
            "unit": "건",
            "base_price": 10000,
            "is_active": True,
            "sort_order": 99,
        },
    )
    assert unused_item_response.status_code == 201, unused_item_response.text
    unused_item = unused_item_response.json()

    delete_unused_response = client.delete(
        f"/api/admin/services/items/{unused_item['id']}",
        headers=headers,
    )
    assert delete_unused_response.status_code == 204

    catalog_response = client.get("/api/admin/services", headers=headers)
    assert catalog_response.status_code == 200
    active_category = next(category for category in catalog_response.json() if category["id"] == item["category_id"])
    assert active_category["items"][0]["name"] == "프리미엄 입주청소"

    create_order_response = client.post(
        "/api/admin/orders",
        headers=headers,
        json={
            "status": "신규접수",
            "received_date": "2026-05-05",
            "scheduled_date": "2026-05-08",
            "requested_time": "10:00",
            "service_item_id": item["id"],
            "service_name": "직접입력값",
            "customer_name": "상품선택고객",
            "customer_phone": "010-5555-6666",
            "customer_address": "서울 강남구 상품로 1",
            "customer_visible_payment": False,
        },
    )

    assert create_order_response.status_code == 201, create_order_response.text
    created = create_order_response.json()
    assert created["service_category_id"] == category["id"]
    assert created["service_item_id"] == item["id"]
    assert created["service_name"] == "프리미엄 입주청소"
    assert created["total_amount"] == 390000

    delete_used_response = client.delete(
        f"/api/admin/services/items/{item['id']}",
        headers=headers,
    )
    assert delete_used_response.status_code == 400
    assert delete_used_response.json()["detail"] == "service_item_in_use"

    inactive_response = client.patch(
        f"/api/admin/services/items/{item['id']}",
        headers=headers,
        json={"is_active": False},
    )
    assert inactive_response.status_code == 200

    inactive_catalog_response = client.get("/api/admin/services", headers=headers)
    assert inactive_catalog_response.status_code == 200
    active_category_after_toggle = next(
        category for category in inactive_catalog_response.json() if category["id"] == item["category_id"]
    )
    assert active_category_after_toggle["items"] == []

    inactive_order_response = client.post(
        "/api/admin/orders",
        headers=headers,
        json={
            "status": "신규접수",
            "received_date": "2026-05-05",
            "service_item_id": item["id"],
            "service_name": "비활성상품",
            "customer_name": "비활성고객",
            "customer_phone": "010-7777-8888",
            "customer_address": "서울 강남구 비활성로 1",
            "customer_visible_payment": False,
        },
    )

    assert inactive_order_response.status_code == 400
    assert inactive_order_response.json()["detail"] == "service_item_not_available"


def test_admin_can_create_partner_with_login_and_view_operational_detail() -> None:
    client = make_test_client()
    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {admin_session['access_token']}"}

    create_response = client.post(
        "/api/admin/partners",
        headers=headers,
        json={
            "name": "Ops Partner A",
            "manager_name": "Manager A",
            "phone": "010-2222-3333",
            "service_areas": "Seoul",
            "available_services": "move-in, regular",
            "memo": "Created from admin partner test",
            "is_active": True,
            "login_phone": "010-2222-3333",
            "login_password": "PartnerTest123!",
        },
    )

    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    assert created["phone"] == "01022223333"
    assert created["login_phone"] == "01022223333"
    assert created["user_id"]
    assert created["scheduled_job_count"] == 0
    assert created["jobs"] == []

    partner_session = login(client, "/api/auth/partner/login", "01022223333", "PartnerTest123!")
    assert partner_session["user"]["role"] == "partner"
    assert partner_session["user"]["partner_id"] == created["id"]

    list_response = client.get("/api/admin/partners?include_inactive=true", headers=headers)
    detail_response = client.get(f"/api/admin/partners/{created['id']}", headers=headers)

    assert list_response.status_code == 200
    assert created["id"] in {partner["id"] for partner in list_response.json()}
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["id"] == created["id"]
    assert detail["manager_name"] == "Manager A"
    assert "total_amount" not in detail

    delete_response = client.delete(f"/api/admin/partners/{created['id']}", headers=headers)
    deleted_list_response = client.get("/api/admin/partners?include_inactive=true", headers=headers)
    deleted_login_response = client.post(
        "/api/auth/partner/login",
        json={"identifier": "01022223333", "password": "PartnerTest123!"},
    )

    assert delete_response.status_code == 204
    assert created["id"] not in {partner["id"] for partner in deleted_list_response.json()}
    assert deleted_login_response.status_code == 401


def test_admin_partner_categories_crud_and_unmapped_partners_are_unclassified() -> None:
    client = make_test_client()
    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {admin_session['access_token']}"}

    category_response = client.post(
        "/api/admin/partners/categories",
        headers=headers,
        json={
            "name": "에어컨 청소",
            "description": "냉난방 특화 협력사",
            "is_active": True,
            "sort_order": 30,
        },
    )
    assert category_response.status_code == 201, category_response.text
    category = category_response.json()

    partner_response = client.post(
        "/api/admin/partners",
        headers=headers,
        json={
            "name": "Aircon Partner",
            "partner_category_id": category["id"],
            "manager_name": "Aircon Manager",
            "phone": "010-4444-5555",
            "service_areas": "Seoul",
            "available_services": "aircon",
            "memo": None,
            "is_active": True,
        },
    )
    assert partner_response.status_code == 201, partner_response.text
    partner = partner_response.json()
    assert partner["partner_category_id"] == category["id"]
    assert partner["partner_category_name"] == "에어컨 청소"

    categories_response = client.get(
        "/api/admin/partners/categories?include_inactive=true",
        headers=headers,
    )
    assert categories_response.status_code == 200
    created_category = next(
        item for item in categories_response.json() if item["id"] == category["id"]
    )
    assert created_category["partner_count"] == 1

    rename_response = client.patch(
        f"/api/admin/partners/categories/{category['id']}",
        headers=headers,
        json={"name": "시스템 에어컨 청소", "sort_order": 40},
    )
    assert rename_response.status_code == 200
    assert rename_response.json()["name"] == "시스템 에어컨 청소"

    refreshed_partner = client.get(f"/api/admin/partners/{partner['id']}", headers=headers)
    assert refreshed_partner.status_code == 200
    assert refreshed_partner.json()["partner_category_name"] == "시스템 에어컨 청소"

    delete_response = client.delete(
        f"/api/admin/partners/categories/{category['id']}",
        headers=headers,
    )
    assert delete_response.status_code == 204

    unmapped_partner = client.get(f"/api/admin/partners/{partner['id']}", headers=headers)
    assert unmapped_partner.status_code == 200
    assert unmapped_partner.json()["partner_category_id"] is None
    assert unmapped_partner.json()["partner_category_name"] is None

    invalid_partner_response = client.post(
        "/api/admin/partners",
        headers=headers,
        json={
            "name": "Invalid Category Partner",
            "partner_category_id": "missing-category",
            "phone": "010-5555-6666",
            "is_active": True,
        },
    )
    assert invalid_partner_response.status_code == 404
    assert invalid_partner_response.json()["detail"] == "partner_category_not_found"


def test_admin_partner_detail_counts_assigned_jobs_without_settlement_fields() -> None:
    client = make_test_client()
    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {admin_session['access_token']}"}

    response = client.get(f"/api/admin/partners/{DEV_PARTNER_ID}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == DEV_PARTNER_ID
    assert body["scheduled_job_count"] == 1
    assert body["active_job_count"] == 1
    assert body["completed_job_count"] == 0
    assert body["login_phone"] == DEV_PARTNER_PHONE
    assert body["jobs"][0]["id"] == "seed-order-2450"
    assert "total_amount" not in body["jobs"][0]
    assert "partner_payment_amount" not in body["jobs"][0]
    assert "payment_memo" not in body["jobs"][0]

    delete_response = client.delete(f"/api/admin/partners/{DEV_PARTNER_ID}", headers=headers)
    assert delete_response.status_code == 400
    assert delete_response.json()["detail"] == "partner_in_use"


def test_admin_partner_deactivation_blocks_login_and_existing_partner_token() -> None:
    client = make_test_client()
    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    partner_session = login(client, "/api/auth/partner/login", DEV_PARTNER_PHONE, DEV_PARTNER_PASSWORD)
    admin_headers = {"Authorization": f"Bearer {admin_session['access_token']}"}
    partner_headers = {"Authorization": f"Bearer {partner_session['access_token']}"}

    deactivate_response = client.patch(
        f"/api/admin/partners/{DEV_PARTNER_ID}",
        headers=admin_headers,
        json={"is_active": False},
    )
    relogin_response = client.post(
        "/api/auth/partner/login",
        json={"identifier": DEV_PARTNER_PHONE, "password": DEV_PARTNER_PASSWORD},
    )
    jobs_response = client.get("/api/partner/jobs", headers=partner_headers)

    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["is_active"] is False
    assert deactivate_response.json()["user_is_active"] is False
    assert relogin_response.status_code == 401
    assert relogin_response.json()["detail"] == "invalid_credentials"
    assert jobs_response.status_code == 401

    reactivate_response = client.patch(
        f"/api/admin/partners/{DEV_PARTNER_ID}",
        headers=admin_headers,
        json={"is_active": True},
    )

    assert reactivate_response.status_code == 200
    assert reactivate_response.json()["is_active"] is True
    assert login(client, "/api/auth/partner/login", DEV_PARTNER_PHONE, DEV_PARTNER_PASSWORD)["user"]["partner_id"] == DEV_PARTNER_ID


def test_admin_can_reset_partner_password_and_revoke_old_password() -> None:
    client = make_test_client()
    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {admin_session['access_token']}"}

    reset_response = client.post(
        f"/api/admin/partners/{DEV_PARTNER_ID}/reset-password",
        headers=headers,
        json={
            "login_phone": DEV_PARTNER_PHONE,
            "password": "PartnerReset123!",
        },
    )

    assert reset_response.status_code == 200
    body = reset_response.json()
    assert body["partner_id"] == DEV_PARTNER_ID
    assert body["login_phone"] == DEV_PARTNER_PHONE
    assert body["temporary_password"] == "PartnerReset123!"

    reset_login = login(client, "/api/auth/partner/login", DEV_PARTNER_PHONE, "PartnerReset123!")
    old_login_response = client.post(
        "/api/auth/partner/login",
        json={"identifier": DEV_PARTNER_PHONE, "password": DEV_PARTNER_PASSWORD},
    )

    assert reset_login["user"]["partner_id"] == DEV_PARTNER_ID
    assert old_login_response.status_code == 401
    assert old_login_response.json()["detail"] == "invalid_credentials"


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


def test_dashboard_summary_matches_operational_queue_definitions() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def make_order(
        order_id: str,
        *,
        status: OrderStatus,
        scheduled_date: date,
        payment_status: str | None = None,
        total_amount: int = 0,
    ) -> Order:
        return Order(
            id=order_id,
            group_id=f"group-{order_id}",
            status=status,
            received_date=date(2026, 5, 1),
            scheduled_date=scheduled_date,
            requested_time="10:00",
            service_name="테스트청소",
            customer_name=f"고객-{order_id}",
            customer_phone="01011112222",
            customer_address="서울 테스트구",
            payment_status=payment_status,
            total_amount=total_amount,
            customer_token=f"token-{order_id}",
            customer_visible_payment=False,
        )

    with TestingSessionLocal() as db:
        db.add_all(
            [
                make_order(
                    "today-scheduled",
                    status=OrderStatus.SCHEDULED,
                    scheduled_date=date(2026, 5, 4),
                ),
                make_order(
                    "today-confirmed",
                    status=OrderStatus.SCHEDULE_CONFIRMED,
                    scheduled_date=date(2026, 5, 4),
                ),
                make_order(
                    "today-day-before-done",
                    status=OrderStatus.DAY_BEFORE_NOTICE_DONE,
                    scheduled_date=date(2026, 5, 4),
                ),
                # 3-2: 오늘 방문이어도 상담중은 '오늘 작업 예정'에서 제외돼야 한다(구 로직이면 today_jobs=5).
                make_order(
                    "today-consulting",
                    status=OrderStatus.CONSULTING,
                    scheduled_date=date(2026, 5, 4),
                ),
                make_order(
                    "today-cancelled",
                    status=OrderStatus.CANCELLED,
                    scheduled_date=date(2026, 5, 4),
                ),
                make_order(
                    "tomorrow-notice",
                    status=OrderStatus.SCHEDULE_CONFIRMED,
                    scheduled_date=date(2026, 5, 5),
                ),
                make_order(
                    "partner-pending",
                    status=OrderStatus.PARTNER_CONFIRMING,
                    scheduled_date=date(2026, 5, 6),
                ),
                make_order(
                    "photo-review",
                    status=OrderStatus.CUSTOMER_DELIVERY_NEEDED,
                    scheduled_date=date(2026, 5, 4),
                ),
                make_order(
                    "customer-delivery",
                    status=OrderStatus.CUSTOMER_DELIVERY_NEEDED,
                    scheduled_date=date(2026, 5, 7),
                ),
                # 과거 방문 + 미납 → '결제 확인 필요'로 카운트(오늘 이전이라 챙길 시점).
                make_order(
                    "payment-pending",
                    status=OrderStatus.CONSULTING,
                    scheduled_date=date(2026, 5, 2),
                    payment_status="balance_pending",
                ),
                # 미래 방문 + 미납 → 아직 결제 챙길 시점이 아니라 카운트에서 제외(#1).
                make_order(
                    "payment-future",
                    status=OrderStatus.CONSULTING,
                    scheduled_date=date(2026, 5, 20),
                    payment_status="unpaid",
                ),
                make_order(
                    "payment-paid",
                    status=OrderStatus.CONSULTING,
                    scheduled_date=date(2026, 5, 8),
                    payment_status="deposit_paid",
                ),
                make_order(
                    "completed",
                    status=OrderStatus.COMPLETED,
                    scheduled_date=date(2026, 5, 9),
                    total_amount=400000,
                ),
                make_order(
                    "delivered",
                    status=OrderStatus.CUSTOMER_DELIVERY_DONE,
                    scheduled_date=date(2026, 5, 9),
                    total_amount=300000,
                ),
            ]
        )
        db.commit()

        summary = DashboardService(db).summary(today=date(2026, 5, 4))

    # 3-2: 오늘(2026-05-04) 방문 중 확정 이후만: scheduled/confirmed/day-before-done/photo-review = 4.
    # (오늘 상담중·취소는 제외 — 상담중 미제외 시 5가 된다.)
    assert summary.today_jobs == 4
    assert summary.tomorrow_notice_targets == 1
    assert summary.partner_pending == 1
    assert summary.photo_review_pending == 0
    assert summary.customer_delivery_needed == 2
    # 미납 계열 중 과거 방문(payment-pending)만 카운트, 미래 방문(payment-future)은 제외 → 1.
    assert summary.payment_check_needed == 1
    assert summary.monthly_completed == 1
    assert summary.monthly_revenue == 700000


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
                is_customer_visible=True,
            )
        )
        db.add(
            OrderPhoto(
                id="aaa-visible-photo",
                order_id="seed-order-2450",
                uploaded_by_user_id="seed-partner-user",
                photo_type=PhotoType.AFTER,
                storage_key="photos/recent-photo-visible.jpg",
                file_url="/uploads/photos/recent-photo-visible.jpg",
                file_name="recent-photo-visible.jpg",
                file_size=1200,
                content_type="image/jpeg",
                is_customer_visible=True,
            )
        )
        db.flush()
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
    assert body["photos"][0]["is_customer_visible"] is True
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
    assert body["id"] == "seed-order-group-2450"
    assert body["customer_name"] == "박고객"
    assert body["customer_phone"] == "01098765432"
    assert "source_channel" not in body
    assert "payment_memo" not in body
    assert "evidence_memo" not in body
    assert "partner_payment_amount" not in body
    assert body["lines"][0]["id"] == "seed-order-2450"
    assert body["lines"][0]["total_amount"] is None
    assert body["lines"][0]["photos"] == []


def test_customer_link_verify_rejects_wrong_phone_suffix() -> None:
    client = make_test_client()

    response = client.post(
        "/api/customer/orders/seed-customer-token-2450/verify",
        json={"phone_suffix": "0000"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "order_not_found"


def test_customer_link_verify_locks_after_repeated_wrong_suffix(monkeypatch) -> None:
    def seed_rate_limited_order(db: Session) -> None:
        add_order_group(
            db,
            group_id="customer-rate-limit-group",
            customer_token="rate-limit-token",
            customer_name="Rate Limited Customer",
            customer_phone="01011112222",
            customer_address="Seoul",
        )
        db.add(
            Order(
                id="customer-rate-limit-order",
                group_id="customer-rate-limit-group",
                status=OrderStatus.SCHEDULE_CONFIRMED,
                received_date=date(2026, 5, 5),
                service_name="입주청소",
                customer_name="Rate Limited Customer",
                customer_phone="01011112222",
                customer_address="Seoul",
                customer_token="rate-limit-token",
                customer_visible_payment=False,
            )
        )

    monkeypatch.setattr(settings, "customer_verify_max_attempts", 2)
    client = make_test_client(seed_rate_limited_order)

    for _ in range(2):
        response = client.post(
            "/api/customer/orders/rate-limit-token/verify",
            json={"phone_suffix": "0000"},
        )
        assert response.status_code == 404

    locked_response = client.post(
        "/api/customer/orders/rate-limit-token/verify",
        json={"phone_suffix": "2222"},
    )

    assert locked_response.status_code == 429
    assert locked_response.json()["detail"] == "customer_verify_locked"


def test_customer_link_verify_rejects_malformed_phone_suffix() -> None:
    client = make_test_client()

    response = client.post(
        "/api/customer/orders/seed-customer-token-2450/verify",
        json={"phone_suffix": "12ab"},
    )

    assert response.status_code == 422


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
    photos = response.json()["lines"][0]["photos"]
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


def test_partner_upload_auto_visible_customer_delivery_flow(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "storage_root", str(tmp_path / "uploads"))
    client = make_test_client()
    partner_session = login(client, "/api/auth/partner/login", DEV_PARTNER_PHONE, DEV_PARTNER_PASSWORD)
    partner_headers = {"Authorization": f"Bearer {partner_session['access_token']}"}

    upload_response = client.post(
        "/api/partner/jobs/seed-order-2450/photos",
        headers=partner_headers,
        data={"photo_type": "before"},
        files={"file": ("upload-before.png", PNG_BYTES, "image/png")},
    )

    assert upload_response.status_code == 200
    uploaded = upload_response.json()
    assert uploaded["is_customer_visible"] is True
    assert uploaded["file_url"].startswith("/uploads/photos/")
    assert uploaded["file_name"] == "upload-before.png"
    assert uploaded["file_size"] == len(PNG_BYTES)
    assert uploaded["content_type"] == "image/png"
    assert "storage_key" not in uploaded
    assert "uploaded_by_user_id" not in uploaded

    auto_visible = client.post(
        "/api/customer/orders/seed-customer-token-2450/verify",
        json={"phone_suffix": "5432"},
    )
    assert auto_visible.status_code == 200
    assert auto_visible.json()["lines"][0]["photos"] == [
        {
            "id": uploaded["id"],
            "photo_type": "before",
            "file_url": uploaded["file_url"],
            "file_name": "upload-before.png",
        }
    ]

    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    admin_headers = {"Authorization": f"Bearer {admin_session['access_token']}"}
    detail_response = client.get(
        "/api/admin/orders/seed-order-2450",
        headers=admin_headers,
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == "일정확정"
    event_types = [event["event_type"] for event in detail["timeline"]]
    assert "photo_uploaded" in event_types
    assert "photo_approved" in event_types

    start_response = client.post("/api/partner/jobs/seed-order-2450/start", headers=partner_headers)
    complete_response = client.post(
        "/api/partner/jobs/seed-order-2450/complete",
        headers=partner_headers,
    )
    assert start_response.status_code == 200
    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == "고객전달필요"

    delivery_queue = client.get(
        "/api/admin/photos/review-queue",
        headers=admin_headers,
    )
    assert delivery_queue.status_code == 200
    delivery_item = delivery_queue.json()[0]
    assert delivery_item["order_id"] == "seed-order-2450"
    assert delivery_item["pending_photo_count"] == 0
    assert delivery_item["approved_photo_count"] == 1
    assert delivery_item["can_send_customer_link"] is True
    assert delivery_item["last_customer_link_sent_at"] is None
    assert delivery_item["photos"][0]["id"] == uploaded["id"]
    assert delivery_item["photos"][0]["is_customer_visible"] is True

    send_response = client.post(
        "/api/admin/messages/send",
        headers=admin_headers,
        json={
            "order_id": "seed-order-2450",
            "message_type": "customer_photo_ready",
            "recipient_type": "customer",
            "channel": "sms",
        },
    )
    assert send_response.status_code == 200
    assert send_response.json()["status"] == "sent"

    delivered_detail = client.get(
        "/api/admin/orders/seed-order-2450",
        headers=admin_headers,
    )
    assert delivered_detail.status_code == 200
    delivered = delivered_detail.json()
    assert delivered["status"] == "고객전달필요"
    delivered_events = {event["event_type"] for event in delivered["timeline"]}
    assert "message_sent" in delivered_events
    assert "customer_link_sent" in delivered_events

    delivered_queue = client.get(
        "/api/admin/photos/review-queue",
        headers=admin_headers,
    )
    assert delivered_queue.status_code == 200
    delivered_item = delivered_queue.json()[0]
    assert delivered_item["order_id"] == "seed-order-2450"
    assert delivered_item["can_send_customer_link"] is True
    assert delivered_item["last_customer_link_sent_at"] is not None


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


def test_admin_e2e_order_to_customer_delivery_flow(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "storage_root", str(tmp_path / "uploads"))
    client = make_test_client()
    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    admin_headers = {"Authorization": f"Bearer {admin_session['access_token']}"}

    create_response = client.post(
        "/api/admin/orders",
        headers=admin_headers,
        json={
            "status": "일정확정",
            "received_date": "2026-05-05",
            "scheduled_date": "2026-05-09",
            "requested_time": "09:30",
            "partner_id": DEV_PARTNER_ID,
            "team_name": "강남 1팀",
            "service_item_id": DEV_SERVICE_ITEM_ID,
            "service_name": "입주청소",
            "size_or_quantity": "24평",
            "special_request": "창틀 집중 확인",
            "customer_name": "E2E고객",
            "customer_phone": "010-1111-2222",
            "customer_address": "서울 강남구 E2E로 9",
            "payment_status": "deposit_paid",
            "payment_memo": "고객에게 노출하지 않는 메모",
            "partner_payment_amount": 180000,
            "partner_payment_status": "unpaid",
            "customer_visible_payment": False,
        },
    )

    assert create_response.status_code == 201, create_response.text
    order = create_response.json()
    order_id = order["id"]
    assert order["service_item_id"] == DEV_SERVICE_ITEM_ID
    assert order["total_amount"] == 280000

    assignment_response = client.post(
        "/api/admin/messages/send",
        headers=admin_headers,
        json={
            "order_id": order_id,
            "message_type": "partner_assignment",
            "recipient_type": "partner",
            "channel": "sms",
        },
    )
    schedule_response = client.post(
        "/api/admin/messages/send",
        headers=admin_headers,
        json={
            "order_id": order_id,
            "message_type": "customer_schedule_confirmed",
            "recipient_type": "customer",
            "channel": "sms",
        },
    )

    assert assignment_response.status_code == 200
    assert assignment_response.json()["recipient_type"] == "partner"
    assert schedule_response.status_code == 200
    assert "/c/" in schedule_response.json()["content"]

    partner_session = login(client, "/api/auth/partner/login", DEV_PARTNER_PHONE, DEV_PARTNER_PASSWORD)
    partner_headers = {"Authorization": f"Bearer {partner_session['access_token']}"}
    partner_jobs = client.get("/api/partner/jobs", headers=partner_headers)
    assert partner_jobs.status_code == 200
    assert order_id in {job["id"] for job in partner_jobs.json()}

    partner_detail = client.get(f"/api/partner/jobs/{order_id}", headers=partner_headers)
    assert partner_detail.status_code == 200
    assert "total_amount" not in partner_detail.json()
    assert "payment_memo" not in partner_detail.json()

    start_response = client.post(f"/api/partner/jobs/{order_id}/start", headers=partner_headers)
    upload_response = client.post(
        f"/api/partner/jobs/{order_id}/photos",
        headers=partner_headers,
        data={"photo_type": "after"},
        files={"file": ("e2e-after.png", PNG_BYTES, "image/png")},
    )

    assert start_response.status_code == 200
    assert upload_response.status_code == 200
    uploaded = upload_response.json()
    assert uploaded["is_customer_visible"] is True

    auto_visible = client.post(
        f"/api/customer/orders/{order['customer_token']}/verify",
        json={"phone_suffix": "2222"},
    )
    assert auto_visible.status_code == 200
    assert auto_visible.json()["lines"][0]["photos"] == [
        {
            "id": uploaded["id"],
            "photo_type": "after",
            "file_url": uploaded["file_url"],
            "file_name": "e2e-after.png",
        }
    ]

    complete_response = client.post(f"/api/partner/jobs/{order_id}/complete", headers=partner_headers)
    send_photo_response = client.post(
        "/api/admin/messages/send",
        headers=admin_headers,
        json={
            "order_id": order_id,
            "message_type": "customer_photo_ready",
            "recipient_type": "customer",
            "channel": "sms",
        },
    )

    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == "고객전달필요"
    assert send_photo_response.status_code == 200

    customer_response = client.post(
        f"/api/customer/orders/{order['customer_token']}/verify",
        json={"phone_suffix": "2222"},
    )
    assert customer_response.status_code == 200
    customer = customer_response.json()
    assert customer["id"] == order["group_id"]
    assert customer["lines"][0]["id"] == order_id
    assert customer["lines"][0]["total_amount"] is None
    assert "payment_memo" not in customer
    assert "partner_payment_amount" not in customer
    assert customer["lines"][0]["photos"] == [
        {
            "id": uploaded["id"],
            "photo_type": "after",
            "file_url": uploaded["file_url"],
            "file_name": "e2e-after.png",
        }
    ]

    admin_detail = client.get(f"/api/admin/orders/{order_id}", headers=admin_headers)
    assert admin_detail.status_code == 200
    detail = admin_detail.json()
    assert detail["status"] == "고객전달필요"
    event_types = {event["event_type"] for event in detail["timeline"]}
    assert {
        "created",
        "partner_assigned",
        "message_sent",
        "customer_link_sent",
        "photo_uploaded",
        "photo_approved",
        "status_changed",
    }.issubset(event_types)


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
        db.add(
            OrderPhoto(
                id="message-ready-photo",
                order_id="seed-order-2450",
                uploaded_by_user_id="seed-partner-user",
                photo_type=PhotoType.AFTER,
                file_url="https://cdn.example.com/message-ready.jpg",
                file_name="message-ready.jpg",
                is_customer_visible=True,
            )
        )
        db.flush()
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
    assert "http://localhost:5173/c/seed-customer-token-2450" in log.content
    assert order.status == OrderStatus.SCHEDULE_CONFIRMED
    assert TimelineEventType.MESSAGE_SENT in {event.event_type for event in events}
    assert TimelineEventType.STATUS_CHANGED not in {event.event_type for event in events}
    assert TimelineEventType.CUSTOMER_LINK_SENT in {event.event_type for event in events}


def test_customer_balance_due_message_includes_balance_link_and_timeline() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as db:
        seed_dev_data(db)
        order = db.get(Order, "seed-order-2450")
        original_status = order.status
        log = MessageService(db).send(
            MessageSendRequest(
                order_id="seed-order-2450",
                message_type=MessageType.CUSTOMER_BALANCE_DUE,
                recipient_type=RecipientType.CUSTOMER,
            ),
            actor_user_id="seed-admin-user",
        )
        db.refresh(order)
        events = TimelineRepository(db).list_for_order("seed-order-2450")

    assert log.status == "sent"
    assert "잔금:" in log.content
    assert "http://localhost:5173/c/seed-customer-token-2450" in log.content
    assert order.status == original_status
    assert TimelineEventType.MESSAGE_SENT in {event.event_type for event in events}
    assert TimelineEventType.STATUS_CHANGED not in {event.event_type for event in events}
    assert TimelineEventType.CUSTOMER_LINK_SENT in {event.event_type for event in events}


def test_failed_customer_message_is_logged_without_status_or_link_side_effects() -> None:
    class FailingProvider:
        def send(self, content: str, recipient_phone: str) -> MessageSendResult:
            return MessageSendResult(status=MessageStatus.FAILED, error_message="provider_down")

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as db:
        seed_dev_data(db)
        order = db.get(Order, "seed-order-2450")
        original_status = order.status
        log = MessageService(db, provider=FailingProvider()).send(
            MessageSendRequest(
                order_id="seed-order-2450",
                message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
                recipient_type=RecipientType.CUSTOMER,
            ),
            actor_user_id="seed-admin-user",
        )
        db.refresh(order)
        events = TimelineRepository(db).list_for_order("seed-order-2450")

    assert log.status == MessageStatus.FAILED
    assert log.error_message == "provider_down"
    assert order.status == original_status
    event_types = {event.event_type for event in events}
    assert TimelineEventType.MESSAGE_SENT in event_types
    assert TimelineEventType.STATUS_CHANGED not in event_types
    assert TimelineEventType.CUSTOMER_LINK_SENT not in event_types


def test_message_send_persists_pending_log_before_provider_call_and_records_exceptions() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as db:
        seed_dev_data(db)
        order = db.get(Order, "seed-order-2450")
        original_status = order.status

        class ExplodingProvider:
            provider_name = "exploding"

            def send(self, content: str, recipient_phone: str) -> MessageSendResult:
                pending_logs = [
                    log
                    for log in db.query(MessageLog).all()
                    if log.status == MessageStatus.PENDING
                    and log.message_type == MessageType.CUSTOMER_SCHEDULE_CONFIRMED
                ]
                assert len(pending_logs) == 1
                raise RuntimeError("provider boom")

        log = MessageService(db, provider=ExplodingProvider()).send(
            MessageSendRequest(
                order_id="seed-order-2450",
                message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
                recipient_type=RecipientType.CUSTOMER,
            ),
            actor_user_id="seed-admin-user",
        )
        db.refresh(order)
        events = TimelineRepository(db).list_for_order("seed-order-2450")

    assert log.status == MessageStatus.FAILED
    assert log.provider == "exploding"
    assert log.provider_error_code == "provider_exception"
    assert "provider boom" in (log.error_message or "")
    assert order.status == original_status
    message_events = [
        event for event in events if event.event_type == TimelineEventType.MESSAGE_SENT
    ]
    assert message_events
    assert message_events[-1].event_metadata["status"] == MessageStatus.FAILED
    assert TimelineEventType.STATUS_CHANGED not in {event.event_type for event in events}
    assert TimelineEventType.CUSTOMER_LINK_SENT not in {event.event_type for event in events}


def test_admin_message_send_route_returns_failed_log_when_provider_fails(monkeypatch) -> None:
    class FailingProvider:
        provider_name = "failing"

        def send(self, content: str, recipient_phone: str) -> MessageSendResult:
            return MessageSendResult(
                status=MessageStatus.FAILED,
                error_message="provider_down",
                provider=self.provider_name,
                provider_error_code="provider_down",
            )

    monkeypatch.setattr("app.services.messages.build_message_provider", lambda: FailingProvider())
    client = make_test_client()
    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {admin_session['access_token']}"}

    response = client.post(
        "/api/admin/messages/send",
        headers=headers,
        json={
            "order_id": "seed-order-2450",
            "message_type": "customer_schedule_confirmed",
            "recipient_type": "customer",
            "channel": "sms",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["provider"] == "failing"
    assert body["provider_error_code"] == "provider_down"
    assert body["error_message"] == "provider_down"

    detail_response = client.get("/api/admin/orders/seed-order-2450", headers=headers)
    detail = detail_response.json()
    assert detail["status"] == OrderStatus.SCHEDULE_CONFIRMED
    message_events = [
        event
        for event in detail["timeline"]
        if event["event_type"] == "message_sent"
        and event["event_metadata"].get("status") == "failed"
    ]
    assert message_events
    assert "customer_link_sent" not in {event["event_type"] for event in detail["timeline"]}


def test_admin_message_settings_reports_solapi_readiness_without_secret_values(monkeypatch) -> None:
    monkeypatch.setattr(settings, "message_provider", "solapi")
    monkeypatch.setattr(settings, "solapi_api_key", "api-key")
    monkeypatch.setattr(settings, "solapi_api_secret", "api-secret")
    monkeypatch.setattr(settings, "solapi_sender_number", "010-1111-2222")
    monkeypatch.setattr(settings, "solapi_webhook_secret", "webhook-secret")
    monkeypatch.setattr(settings, "solapi_kakao_pf_id", "pf-id")
    monkeypatch.setattr(settings, "solapi_kakao_template_customer_schedule_confirmed", "KA_SCHEDULE")
    monkeypatch.setattr(settings, "solapi_kakao_template_customer_day_before", "KA_DAY_BEFORE")
    monkeypatch.setattr(settings, "solapi_kakao_template_partner_assignment", "KA_PARTNER")
    monkeypatch.setattr(settings, "solapi_kakao_template_customer_photo_ready", "KA_PHOTO")
    monkeypatch.setattr(settings, "solapi_kakao_template_customer_quote", "KA_QUOTE")
    monkeypatch.setattr(settings, "solapi_kakao_template_partner_customer_info", "KA_PARTNER_CUSTOMER")
    monkeypatch.setattr(settings, "solapi_kakao_template_customer_balance_due", "KA_BALANCE")
    monkeypatch.setattr(settings, "kakao_channel_url", "https://pf.kakao.com/_cleanjob")

    client = make_test_client()
    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {admin_session['access_token']}"}

    response = client.get("/api/admin/messages/settings", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "solapi"
    assert body["kakao_channel_url"] == "https://pf.kakao.com/_cleanjob"
    assert body["solapi_credentials_configured"] is True
    assert body["solapi_sender_configured"] is True
    assert body["solapi_webhook_configured"] is True
    assert body["kakao_pf_id_configured"] is True
    assert body["can_send_sms"] is True
    assert body["can_send_alimtalk"] is True
    assert body["warnings"] == []
    assert set(body["kakao_templates_configured"].values()) == {True}
    assert "api-secret" not in response.text
    assert "webhook-secret" not in response.text


def test_admin_message_settings_warns_for_unready_solapi(monkeypatch) -> None:
    monkeypatch.setattr(settings, "message_provider", "solapi")
    monkeypatch.setattr(settings, "solapi_api_key", "")
    monkeypatch.setattr(settings, "solapi_api_secret", "")
    monkeypatch.setattr(settings, "solapi_sender_number", "")
    monkeypatch.setattr(settings, "solapi_webhook_secret", "")
    monkeypatch.setattr(settings, "solapi_kakao_pf_id", "")
    monkeypatch.setattr(settings, "solapi_kakao_template_customer_schedule_confirmed", "")
    monkeypatch.setattr(settings, "solapi_kakao_template_customer_day_before", "")
    monkeypatch.setattr(settings, "solapi_kakao_template_partner_assignment", "")
    monkeypatch.setattr(settings, "solapi_kakao_template_customer_photo_ready", "")
    monkeypatch.setattr(settings, "solapi_kakao_template_customer_quote", "")
    monkeypatch.setattr(settings, "solapi_kakao_template_partner_customer_info", "")
    monkeypatch.setattr(settings, "kakao_channel_url", "")

    client = make_test_client()
    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {admin_session['access_token']}"}

    response = client.get("/api/admin/messages/settings", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["kakao_channel_url"] is None
    assert body["can_send_sms"] is False
    assert body["can_send_alimtalk"] is False
    assert "solapi_missing_credentials" in body["warnings"]
    assert "solapi_missing_sender_number" in body["warnings"]
    assert "solapi_missing_webhook_secret" in body["warnings"]
    assert "solapi_missing_kakao_pf_id" in body["warnings"]
    assert "solapi_missing_kakao_template_ids" in body["warnings"]


def test_admin_can_send_customer_photo_ready_message() -> None:
    def seed_visible_photo(db: Session) -> None:
        db.add(
            OrderPhoto(
                id="admin-message-photo",
                order_id="seed-order-2450",
                uploaded_by_user_id="seed-partner-user",
                photo_type=PhotoType.AFTER,
                file_url="https://cdn.example.com/admin-message.jpg",
                file_name="admin-message.jpg",
                is_customer_visible=True,
            )
        )

    client = make_test_client(seed_visible_photo)
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
    assert body["provider"] == "mock"
    assert body["requested_at"] is not None
    assert "/c/seed-customer-token-2450" in body["content"]

    detail_response = client.get("/api/admin/orders/seed-order-2450", headers=headers)
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == "일정확정"
    assert detail["message_logs"][0]["message_type"] == "customer_photo_ready"
    assert detail["message_logs"][0]["provider"] == "mock"
    assert "message_sent" in {event["event_type"] for event in detail["timeline"]}
    assert "status_changed" not in {event["event_type"] for event in detail["timeline"]}
    assert "customer_link_sent" in {event["event_type"] for event in detail["timeline"]}


def test_admin_can_send_day_before_notice_and_update_timeline() -> None:
    client = make_test_client()
    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {admin_session['access_token']}"}

    response = client.post(
        "/api/admin/messages/send",
        headers=headers,
        json={
            "order_id": "seed-order-2450",
            "message_type": "customer_day_before",
            "recipient_type": "customer",
            "channel": "sms",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "sent"
    assert body["recipient_type"] == "customer"
    assert "/c/seed-customer-token-2450" in body["content"]

    detail_response = client.get("/api/admin/orders/seed-order-2450", headers=headers)
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == OrderStatus.DAY_BEFORE_NOTICE_DONE
    event_types = {event["event_type"] for event in detail["timeline"]}
    assert "message_sent" in event_types
    assert "status_changed" in event_types
    assert "customer_link_sent" in event_types


def test_solapi_webhook_marks_message_delivered(monkeypatch) -> None:
    def seed_solapi_message(db: Session) -> None:
        db.add(
            MessageLog(
                id="solapi-webhook-message",
                order_id="seed-order-2450",
                recipient_type=RecipientType.CUSTOMER,
                recipient_name="Webhook Customer",
                recipient_phone="01098765432",
                message_type=MessageType.CUSTOMER_DAY_BEFORE,
                channel=MessageChannel.SMS,
                content="webhook target",
                status=MessageStatus.SENT,
                provider="solapi",
                provider_message_id="M4V20260505120000TEST",
                provider_group_id="G4V20260505120000TEST",
                requested_at=datetime(2026, 5, 5, 3, 0, tzinfo=UTC),
                sent_at=datetime(2026, 5, 5, 3, 0, tzinfo=UTC),
            )
        )

    monkeypatch.setattr(settings, "solapi_webhook_secret", "webhook-secret")
    client = make_test_client(seed_solapi_message)
    body = json.dumps(
        [
            {
                "messageId": "M4V20260505120000TEST",
                "groupId": "G4V20260505120000TEST",
                "statusCode": "4000",
                "statusMessage": "수신 완료",
                "dateReported": "2026-05-05T03:00:05.000Z",
                "dateReceived": "2026-05-05T03:00:04.000Z",
            }
        ],
        separators=(",", ":"),
    ).encode("utf-8")

    response = client.post(
        "/api/webhooks/solapi",
        headers={
            "Content-Type": "application/json",
            "X-Solapi-Signature": solapi_webhook_signature("webhook-secret", body),
        },
        content=body,
    )

    assert response.status_code == 200
    assert response.json() == {"received": 1, "updated": 1, "ignored": 0, "unknown": 0}

    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    messages = client.get(
        "/api/admin/messages",
        headers={"Authorization": f"Bearer {admin_session['access_token']}"},
    ).json()
    message = next(item for item in messages if item["id"] == "solapi-webhook-message")
    assert message["status"] == "delivered"
    assert message["provider_status_code"] == "4000"
    assert message["provider_status_message"] == "수신 완료"
    assert message["delivered_at"] is not None

    detail = client.get(
        "/api/admin/orders/seed-order-2450",
        headers={"Authorization": f"Bearer {admin_session['access_token']}"},
    ).json()
    delivery_events = [
        event
        for event in detail["timeline"]
        if event["event_type"] == "message_sent"
        and event["event_metadata"].get("status") == "delivered"
    ]
    assert delivery_events


def test_solapi_webhook_records_delivery_failure_timeline(monkeypatch) -> None:
    def seed_solapi_message(db: Session) -> None:
        db.add(
            MessageLog(
                id="solapi-webhook-failed-message",
                order_id="seed-order-2450",
                recipient_type=RecipientType.CUSTOMER,
                recipient_name="Webhook Customer",
                recipient_phone="01098765432",
                message_type=MessageType.CUSTOMER_DAY_BEFORE,
                channel=MessageChannel.SMS,
                content="webhook target",
                status=MessageStatus.SENT,
                provider="solapi",
                provider_message_id="M4V20260505120000FAIL",
                provider_group_id="G4V20260505120000FAIL",
                requested_at=datetime(2026, 5, 5, 3, 0, tzinfo=UTC),
                sent_at=datetime(2026, 5, 5, 3, 0, tzinfo=UTC),
            )
        )

    monkeypatch.setattr(settings, "solapi_webhook_secret", "webhook-secret")
    client = make_test_client(seed_solapi_message)
    body = json.dumps(
        [
            {
                "messageId": "M4V20260505120000FAIL",
                "groupId": "G4V20260505120000FAIL",
                "statusCode": "9999",
                "statusMessage": "수신 실패",
                "dateReported": "2026-05-05T03:01:05.000Z",
            }
        ],
        separators=(",", ":"),
    ).encode("utf-8")

    response = client.post(
        "/api/webhooks/solapi",
        headers={
            "Content-Type": "application/json",
            "X-Solapi-Signature": solapi_webhook_signature("webhook-secret", body),
        },
        content=body,
    )

    assert response.status_code == 200

    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    messages = client.get(
        "/api/admin/messages",
        headers={"Authorization": f"Bearer {admin_session['access_token']}"},
    ).json()
    message = next(item for item in messages if item["id"] == "solapi-webhook-failed-message")
    assert message["status"] == "delivery_failed"
    assert message["provider_error_code"] == "9999"
    assert message["error_message"] == "수신 실패"

    detail = client.get(
        "/api/admin/orders/seed-order-2450",
        headers={"Authorization": f"Bearer {admin_session['access_token']}"},
    ).json()
    failure_events = [
        event
        for event in detail["timeline"]
        if event["event_type"] == "message_sent"
        and event["event_metadata"].get("status") == "delivery_failed"
    ]
    assert failure_events


def test_solapi_webhook_rejects_invalid_secret(monkeypatch) -> None:
    monkeypatch.setattr(settings, "solapi_webhook_secret", "webhook-secret")
    client = make_test_client()
    body = b"[]"

    response = client.post(
        "/api/webhooks/solapi",
        headers={"Content-Type": "application/json", "X-Solapi-Signature": "wrong"},
        content=body,
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid_solapi_webhook_secret"


def test_solapi_webhook_requires_configured_secret(monkeypatch) -> None:
    monkeypatch.setattr(settings, "solapi_webhook_secret", "")
    client = make_test_client()

    response = client.post(
        "/api/webhooks/solapi",
        headers={"Content-Type": "application/json"},
        content=b"[]",
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "solapi_webhook_secret_required"


def test_admin_can_preview_alimtalk_template_variables(monkeypatch) -> None:
    monkeypatch.setattr(settings, "solapi_kakao_template_customer_day_before", "KA_DAY_BEFORE")
    client = make_test_client()
    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {admin_session['access_token']}"}

    response = client.post(
        "/api/admin/messages/preview",
        headers=headers,
        json={
            "order_id": "seed-order-2450",
            "message_type": "customer_day_before",
            "recipient_type": "customer",
            "channel": "alimtalk",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["channel"] == "alimtalk"
    assert body["kakao_template_id"] == "KA_DAY_BEFORE"
    assert body["kakao_template_configured"] is True
    assert body["kakao_pf_id_configured"] is False
    assert body["fallback_sms_enabled"] is True
    assert body["can_send"] is True
    assert "solapi_missing_kakao_pf_id" in body["warnings"]
    assert "alimtalk_fallback_sms_enabled" in body["warnings"]
    assert body["kakao_variables"]["#{고객명}"] == "박고객"
    assert "http://localhost:5173/c/seed-customer-token-2450" in body["fallback_sms_content"]


def test_admin_alimtalk_preview_blocks_when_template_missing_without_fallback(monkeypatch) -> None:
    monkeypatch.setattr(settings, "solapi_kakao_pf_id", "pf-id")
    monkeypatch.setattr(settings, "solapi_kakao_template_customer_day_before", "")
    monkeypatch.setattr(settings, "solapi_alimtalk_fallback_sms", False)
    client = make_test_client()
    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {admin_session['access_token']}"}

    response = client.post(
        "/api/admin/messages/preview",
        headers=headers,
        json={
            "order_id": "seed-order-2450",
            "message_type": "customer_day_before",
            "recipient_type": "customer",
            "channel": "alimtalk",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["kakao_pf_id_configured"] is True
    assert body["kakao_template_configured"] is False
    assert body["fallback_sms_enabled"] is False
    assert body["can_send"] is False
    assert body["fallback_sms_content"] is None
    assert body["warnings"] == ["solapi_missing_kakao_template_id"]


def test_admin_can_send_partner_assignment_to_partner_only() -> None:
    client = make_test_client()
    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {admin_session['access_token']}"}

    response = client.post(
        "/api/admin/messages/send",
        headers=headers,
        json={
            "order_id": "seed-order-2450",
            "message_type": "partner_assignment",
            "recipient_type": "customer",
            "channel": "sms",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "sent"
    assert body["recipient_type"] == "partner"
    assert body["recipient_phone"] == DEV_PARTNER_PHONE
    assert "신규 작업이 배정되었습니다" in body["content"]

    messages_response = client.get("/api/admin/messages", headers=headers)
    assert messages_response.status_code == 200
    messages = messages_response.json()
    assert messages[0]["message_type"] == "partner_assignment"
    assert messages[0]["recipient_type"] == "partner"


def test_partner_assignment_message_requires_assigned_partner() -> None:
    def seed_unassigned(db: Session) -> None:
        add_order_group(
            db,
            group_id="message-unassigned-group",
            customer_token="message-unassigned-token",
            customer_name="미배정고객",
            customer_phone="01011112222",
            customer_address="서울 테스트구",
        )
        db.add(
            Order(
                id="message-unassigned-order",
                group_id="message-unassigned-group",
                status=OrderStatus.CONSULTING,
                received_date=date(2026, 5, 4),
                scheduled_date=date(2026, 5, 6),
                requested_time="15:00",
                partner_id=None,
                service_name="입주청소",
                customer_name="미배정고객",
                customer_phone="01011112222",
                customer_address="서울 테스트구",
                customer_token="message-unassigned-token",
                customer_visible_payment=False,
            )
        )

    client = make_test_client(seed_unassigned)
    admin_session = login(client, "/api/auth/admin/login", DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {admin_session['access_token']}"}

    response = client.post(
        "/api/admin/messages/send",
        headers=headers,
        json={
            "order_id": "message-unassigned-order",
            "message_type": "partner_assignment",
            "recipient_type": "partner",
            "channel": "sms",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "partner_not_assigned"


def test_admin_cannot_send_photo_ready_without_customer_visible_photo() -> None:
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

    assert response.status_code == 400
    assert response.json()["detail"] == "no_customer_visible_photos"
