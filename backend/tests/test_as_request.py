"""AS(사후관리) 요청 전송 테스트 (배치3 항목5).

운영에서 주문에 AS 요청을 전송하면 (1) 주문에 AS 플래그+메모가 남고, (2) AS_REQUESTED
타임라인과 협력사 안내 메시지가 기록되며, (3) 협력사 링크(잡 상세)에도 AS 요청/메모가 노출된다.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.db.seed import DEV_CUSTOMER_TOKEN, DEV_ORDER_ID, DEV_PARTNER_ID, DEV_PARTNER_USER_ID
from app.domain.constants import MessageType, OrderStatus, TimelineEventType
from app.services.storage import StoredFile


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


def test_customer_as_request_waits_for_admin_acceptance_before_partner_notice(
    client, seed_admin_token, seed_partner_token
):
    admin_h = {"Authorization": f"Bearer {seed_admin_token}"}
    partner_h = {"Authorization": f"Bearer {seed_partner_token}"}
    status_res = client.patch(
        f"/api/admin/orders/{DEV_ORDER_ID}",
        json={"status": OrderStatus.CUSTOMER_DELIVERY_DONE.value},
        headers=admin_h,
    )
    assert status_res.status_code == 200, status_res.text

    png_bytes = b"\x89PNG\r\n\x1a\ncustomer-as"
    res = client.post(
        "/api/customer/orders/as-request",
        headers={"X-Customer-Token": DEV_CUSTOMER_TOKEN},
        data={
            "phone_suffix": "5432",
            "order_id": DEV_ORDER_ID,
            "memo": "욕실 코너 오염이 남아 있습니다.",
        },
        files=[("files", ("as.png", png_bytes, "image/png"))],
    )
    assert res.status_code == 200, res.text
    line = next(item for item in res.json()["lines"] if item["id"] == DEV_ORDER_ID)
    assert line["status"] == OrderStatus.CUSTOMER_CHECK_NEEDED.value
    assert "as_memo" not in line

    detail = client.get(f"/api/admin/orders/{DEV_ORDER_ID}", headers=admin_h).json()
    assert detail["as_requested"] is False
    assert detail["as_memo"] == "욕실 코너 오염이 남아 있습니다."
    assert any(
        ev["event_type"] == TimelineEventType.AS_REQUESTED.value
        and ev["description"] == "욕실 코너 오염이 남아 있습니다."
        and ev["event_metadata"]["source"] == "customer"
        for ev in detail["timeline"]
    )
    as_photos = [photo for photo in detail["photos"] if photo["file_name"] == "as.png"]
    assert len(as_photos) == 1
    assert as_photos[0]["photo_source"] == "customer_as"
    assert as_photos[0]["uploaded_by_user_id"] is None
    assert as_photos[0]["is_customer_visible"] is False
    assert as_photos[0]["file_url"] == f"/api/admin/photos/{as_photos[0]['id']}/file"
    assert not as_photos[0]["file_url"].startswith("/uploads/")
    assert client.get(as_photos[0]["file_url"]).status_code == 401
    file_res = client.get(as_photos[0]["file_url"], headers=admin_h)
    assert file_res.status_code == 200
    assert file_res.content == png_bytes
    assert all(log["message_type"] != MessageType.PARTNER_AS_REQUEST.value for log in detail["message_logs"])
    assert all(log["message_type"] != MessageType.CUSTOMER_AS_NOTICE.value for log in detail["message_logs"])

    partner_job = client.get(f"/api/partner/jobs/{DEV_ORDER_ID}", headers=partner_h).json()
    assert partner_job["as_requested"] is False
    assert partner_job["as_memo"] is None
    assert all(photo["file_name"] != "as.png" for photo in partner_job["photos"])
    premature_start = client.post(f"/api/partner/jobs/{DEV_ORDER_ID}/start", headers=partner_h)
    assert premature_start.status_code == 409
    assert premature_start.json()["detail"] == "invalid_status_transition"
    premature_upload = client.post(
        f"/api/partner/jobs/{DEV_ORDER_ID}/photos",
        headers=partner_h,
        data={"photo_type": "before"},
        files={"file": ("premature-before.png", png_bytes, "image/png")},
    )
    assert premature_upload.status_code == 409
    assert premature_upload.json()["detail"] == "invalid_status_for_upload"

    accepted = client.post(
        f"/api/admin/orders/{DEV_ORDER_ID}/as-request",
        json={"memo": detail["as_memo"]},
        headers=admin_h,
    )
    assert accepted.status_code == 200, accepted.text
    partner_after_accept = client.get(f"/api/partner/jobs/{DEV_ORDER_ID}", headers=partner_h).json()
    assert partner_after_accept["as_requested"] is True
    assert partner_after_accept["as_memo"] == "욕실 코너 오염이 남아 있습니다."
    partner_as_photo = next(photo for photo in partner_after_accept["photos"] if photo["file_name"] == "as.png")
    assert partner_as_photo["photo_source"] == "customer_as"
    assert partner_as_photo["file_url"] == f"/api/partner/jobs/{DEV_ORDER_ID}/photos/{partner_as_photo['id']}/file"
    assert client.get(partner_as_photo["file_url"]).status_code == 401
    partner_file_res = client.get(partner_as_photo["file_url"], headers=partner_h)
    assert partner_file_res.status_code == 200
    assert partner_file_res.content == png_bytes
    delete_customer_as_photo = client.delete(
        f"/api/partner/jobs/{DEV_ORDER_ID}/photos/{partner_as_photo['id']}",
        headers=partner_h,
    )
    assert delete_customer_as_photo.status_code == 403
    assert delete_customer_as_photo.json()["detail"] == "photo_delete_not_allowed"

    duplicate_admin_as = client.post(
        f"/api/admin/orders/{DEV_ORDER_ID}/as-request",
        json={"memo": "중복 AS 전송 시도"},
        headers=admin_h,
    )
    assert duplicate_admin_as.status_code == 409
    assert duplicate_admin_as.json()["detail"] == "as_request_already_accepted"
    partner_after_duplicate = client.get(f"/api/partner/jobs/{DEV_ORDER_ID}", headers=partner_h).json()
    assert any(photo["file_name"] == "as.png" for photo in partner_after_duplicate["photos"])

    wrong_partner = client.post(
        "/api/admin/partners",
        json={
            "name": "다른 협력사",
            "phone": "01044443333",
            "manager_name": "타협력",
            "login_phone": "01044443333",
            "login_password": "PartnerB123!",
        },
        headers=admin_h,
    )
    assert wrong_partner.status_code == 201, wrong_partner.text
    wrong_login = client.post(
        "/api/auth/partner/login",
        json={"identifier": "01044443333", "password": "PartnerB123!"},
    )
    assert wrong_login.status_code == 200, wrong_login.text
    wrong_partner_h = {"Authorization": f"Bearer {wrong_login.json()['access_token']}"}
    wrong_partner_file_res = client.get(partner_as_photo["file_url"], headers=wrong_partner_h)
    assert wrong_partner_file_res.status_code == 404
    assert wrong_partner_file_res.json()["detail"] == "order_not_found"

    repeated = client.post(
        "/api/customer/orders/as-request",
        headers={"X-Customer-Token": DEV_CUSTOMER_TOKEN},
        data={
            "phone_suffix": "5432",
            "order_id": DEV_ORDER_ID,
            "memo": "승인 뒤 재접수 시도",
        },
    )
    assert repeated.status_code == 409
    partner_after_repeat = client.get(f"/api/partner/jobs/{DEV_ORDER_ID}", headers=partner_h).json()
    assert partner_after_repeat["as_requested"] is True
    assert partner_after_repeat["as_memo"] == "욕실 코너 오염이 남아 있습니다."


def test_customer_as_request_rejects_repeat_before_admin_acceptance_and_deletes_file(
    client, seed_admin_token, monkeypatch
):
    from app.api.routes.customer import orders as customer_orders

    class FakeStorage:
        def __init__(self) -> None:
            self.saved_keys: list[str] = []
            self.deleted_keys: list[str] = []

        def save_private(self, *, data: bytes, file_name: str, content_type: str) -> StoredFile:
            storage_key = f"private/photos/{len(self.saved_keys) + 1}-{file_name}"
            self.saved_keys.append(storage_key)
            return StoredFile(
                storage_key=storage_key,
                file_url="",
                file_name=file_name,
                file_size=len(data),
                content_type=content_type,
            )

        def delete(self, storage_key: str) -> None:
            self.deleted_keys.append(storage_key)

    storage = FakeStorage()
    monkeypatch.setattr(customer_orders, "get_storage_provider", lambda: storage)
    admin_h = {"Authorization": f"Bearer {seed_admin_token}"}
    status_res = client.patch(
        f"/api/admin/orders/{DEV_ORDER_ID}",
        json={"status": OrderStatus.CUSTOMER_DELIVERY_DONE.value},
        headers=admin_h,
    )
    assert status_res.status_code == 200, status_res.text

    first_res = client.post(
        "/api/customer/orders/as-request",
        headers={"X-Customer-Token": DEV_CUSTOMER_TOKEN},
        data={
            "phone_suffix": "5432",
            "order_id": DEV_ORDER_ID,
            "memo": "첫 번째 AS 요청입니다.",
        },
        files=[("files", ("first.png", b"\x89PNG\r\n\x1a\nfirst", "image/png"))],
    )
    assert first_res.status_code == 200, first_res.text

    repeat_res = client.post(
        "/api/customer/orders/as-request",
        headers={"X-Customer-Token": DEV_CUSTOMER_TOKEN},
        data={
            "phone_suffix": "5432",
            "order_id": DEV_ORDER_ID,
            "memo": "두 번째 AS 요청입니다.",
        },
        files=[("files", ("second.png", b"\x89PNG\r\n\x1a\nsecond", "image/png"))],
    )
    assert repeat_res.status_code == 409
    assert repeat_res.json()["detail"] == "as_request_already_pending"
    assert storage.saved_keys == ["private/photos/1-first.png"]
    assert storage.deleted_keys == []

    detail = client.get(f"/api/admin/orders/{DEV_ORDER_ID}", headers=admin_h).json()
    assert detail["as_requested"] is False
    assert detail["as_memo"] == "첫 번째 AS 요청입니다."
    photo_names = [photo["file_name"] for photo in detail["photos"]]
    assert "first.png" in photo_names
    assert "second.png" not in photo_names


def test_customer_as_request_rejects_too_many_files_before_storage(
    client, seed_admin_token, monkeypatch
):
    from app.api.routes.customer import orders as customer_orders

    class FakeStorage:
        def __init__(self) -> None:
            self.saved_keys: list[str] = []

        def save_private(self, *, data: bytes, file_name: str, content_type: str) -> StoredFile:
            self.saved_keys.append(file_name)
            return StoredFile(
                storage_key=f"private/photos/{file_name}",
                file_url="",
                file_name=file_name,
                file_size=len(data),
                content_type=content_type,
            )

    storage = FakeStorage()
    monkeypatch.setattr(customer_orders, "get_storage_provider", lambda: storage)
    admin_h = {"Authorization": f"Bearer {seed_admin_token}"}
    status_res = client.patch(
        f"/api/admin/orders/{DEV_ORDER_ID}",
        json={"status": OrderStatus.CUSTOMER_DELIVERY_DONE.value},
        headers=admin_h,
    )
    assert status_res.status_code == 200, status_res.text

    png_bytes = b"\x89PNG\r\n\x1a\nas"
    res = client.post(
        "/api/customer/orders/as-request",
        headers={"X-Customer-Token": DEV_CUSTOMER_TOKEN},
        data={
            "phone_suffix": "5432",
            "order_id": DEV_ORDER_ID,
            "memo": "사진이 너무 많습니다.",
        },
        files=[
            ("files", (f"as-{index}.png", png_bytes, "image/png"))
            for index in range(customer_orders.settings.customer_as_max_files + 1)
        ],
    )
    assert res.status_code == 413
    assert res.json()["detail"] == "too_many_as_photos"
    assert storage.saved_keys == []


def test_customer_as_request_rejects_total_file_size_before_storage(
    client, seed_admin_token, monkeypatch
):
    from app.api.routes.customer import orders as customer_orders

    class FakeStorage:
        def __init__(self) -> None:
            self.saved_keys: list[str] = []

        def save_private(self, *, data: bytes, file_name: str, content_type: str) -> StoredFile:
            self.saved_keys.append(file_name)
            return StoredFile(
                storage_key=f"private/photos/{file_name}",
                file_url="",
                file_name=file_name,
                file_size=len(data),
                content_type=content_type,
            )

    storage = FakeStorage()
    monkeypatch.setattr(customer_orders, "get_storage_provider", lambda: storage)
    monkeypatch.setattr(customer_orders.settings, "customer_as_max_upload_bytes", 24)
    admin_h = {"Authorization": f"Bearer {seed_admin_token}"}
    status_res = client.patch(
        f"/api/admin/orders/{DEV_ORDER_ID}",
        json={"status": OrderStatus.CUSTOMER_DELIVERY_DONE.value},
        headers=admin_h,
    )
    assert status_res.status_code == 200, status_res.text

    res = client.post(
        "/api/customer/orders/as-request",
        headers={"X-Customer-Token": DEV_CUSTOMER_TOKEN},
        data={
            "phone_suffix": "5432",
            "order_id": DEV_ORDER_ID,
            "memo": "사진 총량 초과",
        },
        files=[
            ("files", ("one.png", b"\x89PNG\r\n\x1a\n11111111", "image/png")),
            ("files", ("two.png", b"\x89PNG\r\n\x1a\n22222222", "image/png")),
        ],
    )
    assert res.status_code == 413
    assert res.json()["detail"] == "as_photos_total_too_large"
    assert storage.saved_keys == []


def test_customer_as_upload_reads_oversized_file_in_bounded_chunks(monkeypatch):
    import anyio
    from fastapi import HTTPException

    from app.api.routes.customer import orders as customer_orders

    class VirtualUploadFile:
        def __init__(self, *, total_bytes: int) -> None:
            self.filename = "oversized.png"
            self.content_type = "image/png"
            self.total_bytes = total_bytes
            self.offset = 0
            self.read_sizes: list[int] = []

        async def read(self, size: int = -1) -> bytes:
            self.read_sizes.append(size)
            if self.offset >= self.total_bytes:
                return b""
            if size < 0:
                chunk_size = self.total_bytes - self.offset
            else:
                chunk_size = min(size, self.total_bytes - self.offset)
            self.offset += chunk_size
            return b"x" * chunk_size

    class FakeStorage:
        def __init__(self) -> None:
            self.saved_keys: list[str] = []

        def save_private(self, *, data: bytes, file_name: str, content_type: str) -> StoredFile:
            self.saved_keys.append(file_name)
            return StoredFile(
                storage_key=f"private/photos/{file_name}",
                file_url="",
                file_name=file_name,
                file_size=len(data),
                content_type=content_type,
            )

    async def store_file() -> None:
        await customer_orders._store_customer_as_files([upload], storage=storage)

    monkeypatch.setattr(customer_orders.settings, "photo_max_upload_bytes", 12)
    monkeypatch.setattr(customer_orders.settings, "customer_as_max_upload_bytes", 100)
    upload = VirtualUploadFile(total_bytes=13)
    storage = FakeStorage()

    with pytest.raises(HTTPException) as excinfo:
        anyio.run(store_file)

    assert excinfo.value.status_code == 413
    assert excinfo.value.detail == "photo_too_large"
    assert upload.read_sizes
    assert all(read_size > 0 for read_size in upload.read_sizes)
    assert max(upload.read_sizes) <= customer_orders.settings.photo_max_upload_bytes + 1
    assert storage.saved_keys == []


def test_customer_as_request_rejects_large_body_before_multipart_parse(client, monkeypatch):
    from app.api.routes.customer import orders as customer_orders

    monkeypatch.setattr(customer_orders.settings, "customer_as_max_upload_bytes", 12)
    monkeypatch.setattr(customer_orders.settings, "customer_as_request_body_overhead_bytes", 0)

    res = client.post(
        "/api/customer/orders/as-request",
        content=b"x" * 13,
        headers={
            "content-type": "multipart/form-data; boundary=too-large",
            "X-Customer-Token": DEV_CUSTOMER_TOKEN,
        },
    )

    assert res.status_code == 413
    assert res.json()["detail"] == "as_photos_total_too_large"


def test_customer_as_request_revalidates_stale_session_after_upload(db_session):
    from sqlalchemy.orm import sessionmaker

    from app.models.order import Order
    from app.services.orders import OrderService

    order = db_session.get(Order, DEV_ORDER_ID)
    assert order is not None
    order.status = OrderStatus.CUSTOMER_DELIVERY_DONE
    db_session.commit()

    session_factory = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    first_session = session_factory()
    second_session = session_factory()
    try:
        first_service = OrderService(first_session)
        second_service = OrderService(second_session)
        first_service.validate_customer_as_request(DEV_ORDER_ID, memo="느린 업로드")

        second_service.submit_customer_as_request(
            DEV_ORDER_ID,
            memo="먼저 완료된 요청",
            stored_files=[
                StoredFile(
                    storage_key="private/photos/first-wins.png",
                    file_url="",
                    file_name="first-wins.png",
                    file_size=10,
                    content_type="image/png",
                )
            ],
        )

        with pytest.raises(ValueError, match="as_request_already_pending"):
            first_service.submit_customer_as_request(
                DEV_ORDER_ID,
                memo="느린 업로드",
                stored_files=[
                    StoredFile(
                        storage_key="private/photos/slow-loser.png",
                        file_url="",
                        file_name="slow-loser.png",
                        file_size=10,
                        content_type="image/png",
                    )
                ],
            )
    finally:
        first_session.close()
        second_session.close()


def test_pending_customer_as_request_does_not_reset_customer_photo_evidence_cutoff(db_session):
    from datetime import UTC, datetime

    from app.domain.constants import PhotoType, RecipientType
    from app.models.order import Order
    from app.models.photo import OrderPhoto
    from app.schemas.message import MessageSendRequest
    from app.services.messages import MessageService
    from app.services.orders import OrderService

    order = db_session.get(Order, DEV_ORDER_ID)
    assert order is not None
    order.status = OrderStatus.CUSTOMER_DELIVERY_NEEDED
    visible_time = datetime(2026, 7, 1, 9, 0, tzinfo=UTC)
    for photo_type in (PhotoType.BEFORE, PhotoType.AFTER):
        db_session.add(
            OrderPhoto(
                id=f"pending-cutoff-{photo_type}",
                order_id=DEV_ORDER_ID,
                uploaded_by_user_id=DEV_PARTNER_USER_ID,
                photo_type=photo_type,
                storage_key=f"photos/pending-cutoff-{photo_type}.png",
                file_url=f"/uploads/pending-cutoff-{photo_type}.png",
                file_name=f"pending-cutoff-{photo_type}.png",
                file_size=10,
                content_type="image/png",
                is_customer_visible=True,
                created_at=visible_time,
            )
        )
    db_session.commit()

    OrderService(db_session).submit_customer_as_request(
        DEV_ORDER_ID,
        memo="운영 승인 전 고객 AS",
        stored_files=[
            StoredFile(
                storage_key="private/photos/pending-customer-as.png",
                file_url="",
                file_name="pending-customer-as.png",
                file_size=10,
                content_type="image/png",
            )
        ],
    )
    order = db_session.get(Order, DEV_ORDER_ID)
    assert order is not None
    order.status = OrderStatus.CUSTOMER_DELIVERY_NEEDED
    db_session.commit()

    sent = MessageService(db_session).send(
        MessageSendRequest(
            order_id=DEV_ORDER_ID,
            message_type=MessageType.CUSTOMER_PHOTO_READY,
            recipient_type=RecipientType.CUSTOMER,
        ),
        actor_user_id="seed-admin-user",
    )
    assert sent.message_type == MessageType.CUSTOMER_PHOTO_READY


def test_customer_as_intake_blocks_paid_auto_completion_until_admin_accepts(db_session):
    from app.domain.payment_status import PaymentStatus
    from app.models.order import Order
    from app.schemas.order import OrderUpdate
    from app.services.orders import OrderService

    service = OrderService(db_session)
    order = db_session.get(Order, DEV_ORDER_ID)
    assert order is not None
    order.status = OrderStatus.CUSTOMER_DELIVERY_DONE
    db_session.commit()

    submitted = service.submit_customer_as_request(
        DEV_ORDER_ID,
        memo="운영 승인 대기 AS",
        stored_files=[],
    )
    assert submitted.as_intake_pending is True
    request_id = submitted.active_as_request_id

    paid = service.update(
        DEV_ORDER_ID,
        OrderUpdate(payment_status=PaymentStatus.PAID),
        actor_user_id="seed-admin-user",
    )
    assert paid.status == OrderStatus.CUSTOMER_CHECK_NEEDED
    assert paid.active_as_request_id == request_id

    accepted = service.request_as(
        DEV_ORDER_ID,
        memo="운영 승인 대기 AS",
        actor_user_id="seed-admin-user",
    )
    assert accepted.as_intake_pending is False
    assert accepted.active_as_request_id == request_id


def test_partner_dto_scopes_customer_as_photos_to_active_request(db_session):
    from app.models.order import Order
    from app.repositories.photos import PhotoRepository
    from app.repositories.timeline import TimelineRepository
    from app.services.orders import (
        OrderService,
        active_customer_as_photo_ids,
        to_partner_job_dto,
    )

    osvc = OrderService(db_session)
    order = db_session.get(Order, DEV_ORDER_ID)
    assert order is not None
    order.status = OrderStatus.CUSTOMER_DELIVERY_DONE
    db_session.commit()

    osvc.submit_customer_as_request(
        DEV_ORDER_ID,
        memo="첫 번째 고객 AS",
        stored_files=[
            StoredFile(
                storage_key="private/photos/old-as.png",
                file_url="",
                file_name="old-as.png",
                file_size=10,
                content_type="image/png",
            )
        ],
    )
    osvc.request_as(DEV_ORDER_ID, memo="첫 번째 고객 AS", actor_user_id="seed-admin-user")

    order = db_session.get(Order, DEV_ORDER_ID)
    assert order is not None
    order.as_requested = False
    order.status = OrderStatus.CUSTOMER_DELIVERY_DONE
    db_session.commit()

    osvc.submit_customer_as_request(
        DEV_ORDER_ID,
        memo="두 번째 고객 AS",
        stored_files=[
            StoredFile(
                storage_key="private/photos/new-as.png",
                file_url="",
                file_name="new-as.png",
                file_size=10,
                content_type="image/png",
            )
        ],
    )
    osvc.request_as(DEV_ORDER_ID, memo="두 번째 고객 AS", actor_user_id="seed-admin-user")

    order = db_session.get(Order, DEV_ORDER_ID)
    assert order is not None
    events = TimelineRepository(db_session).list_for_order(DEV_ORDER_ID)
    photos = PhotoRepository(db_session).list_for_order(DEV_ORDER_ID)
    visible_customer_as_ids = active_customer_as_photo_ids(order, events)
    visible_customer_as_names = {
        photo.file_name for photo in photos if photo.id in visible_customer_as_ids
    }
    assert visible_customer_as_names == {"new-as.png"}

    dto = to_partner_job_dto(
        order,
        photos=photos,
        as_requested_at=events[-1].created_at,
        visible_customer_as_photo_ids=visible_customer_as_ids,
    )
    partner_photo_names = {photo.file_name for photo in dto.photos}
    assert "new-as.png" in partner_photo_names
    assert "old-as.png" not in partner_photo_names


def test_admin_as_after_completed_customer_as_does_not_reuse_old_request_id(db_session):
    from app.models.order import Order
    from app.repositories.photos import PhotoRepository
    from app.repositories.timeline import TimelineRepository
    from app.services.orders import (
        OrderService,
        active_customer_as_photo_ids,
        to_partner_job_dto,
    )

    osvc = OrderService(db_session)
    order = db_session.get(Order, DEV_ORDER_ID)
    assert order is not None
    order.status = OrderStatus.CUSTOMER_DELIVERY_DONE
    db_session.commit()

    osvc.submit_customer_as_request(
        DEV_ORDER_ID,
        memo="이전 고객 AS",
        stored_files=[
            StoredFile(
                storage_key="private/photos/previous-customer-as.png",
                file_url="",
                file_name="previous-customer-as.png",
                file_size=10,
                content_type="image/png",
            )
        ],
    )
    first_acceptance = osvc.request_as(
        DEV_ORDER_ID,
        memo="이전 고객 AS",
        actor_user_id="seed-admin-user",
    )
    old_request_id = first_acceptance.active_as_request_id
    assert old_request_id is not None

    order = db_session.get(Order, DEV_ORDER_ID)
    assert order is not None
    order.as_requested = False
    order.status = OrderStatus.CUSTOMER_CHECK_NEEDED
    db_session.commit()

    second_acceptance = osvc.request_as(
        DEV_ORDER_ID,
        memo="새 운영 AS",
        actor_user_id="seed-admin-user",
    )
    assert second_acceptance.active_as_request_id != old_request_id

    events = TimelineRepository(db_session).list_for_order(DEV_ORDER_ID)
    photos = PhotoRepository(db_session).list_for_order(DEV_ORDER_ID)
    visible_customer_as_ids = active_customer_as_photo_ids(second_acceptance, events)
    visible_customer_as_names = {
        photo.file_name for photo in photos if photo.id in visible_customer_as_ids
    }
    assert visible_customer_as_names == set()

    dto = to_partner_job_dto(
        second_acceptance,
        photos=photos,
        as_requested_at=events[-1].created_at,
        visible_customer_as_photo_ids=visible_customer_as_ids,
    )
    assert all(photo.file_name != "previous-customer-as.png" for photo in dto.photos)


def test_admin_acceptance_reloads_pending_customer_as_from_stale_session(db_session):
    from sqlalchemy.orm import sessionmaker

    from app.models.order import Order
    from app.repositories.photos import PhotoRepository
    from app.repositories.timeline import TimelineRepository
    from app.services.orders import (
        OrderService,
        active_customer_as_photo_ids,
        to_partner_job_dto,
    )

    order = db_session.get(Order, DEV_ORDER_ID)
    assert order is not None
    order.status = OrderStatus.CUSTOMER_DELIVERY_DONE
    db_session.commit()

    SessionLocal = sessionmaker(
        bind=db_session.get_bind(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    with SessionLocal() as admin_db, SessionLocal() as customer_db:
        stale_admin_order = admin_db.get(Order, DEV_ORDER_ID)
        assert stale_admin_order is not None
        assert stale_admin_order.active_as_request_id is None
        admin_db.commit()

        submitted = OrderService(customer_db).submit_customer_as_request(
            DEV_ORDER_ID,
            memo="고객이 먼저 접수한 AS",
            stored_files=[
                StoredFile(
                    storage_key="private/photos/stale-admin-as.png",
                    file_url="",
                    file_name="stale-admin-as.png",
                    file_size=10,
                    content_type="image/png",
                )
            ],
        )
        customer_as_request_id = submitted.active_as_request_id
        assert customer_as_request_id is not None

        accepted = OrderService(admin_db).request_as(
            DEV_ORDER_ID,
            memo="고객이 먼저 접수한 AS",
            actor_user_id="seed-admin-user",
        )

        assert accepted.active_as_request_id == customer_as_request_id
        events = TimelineRepository(admin_db).list_for_order(DEV_ORDER_ID)
        photos = PhotoRepository(admin_db).list_for_order(DEV_ORDER_ID)
        visible_customer_as_ids = active_customer_as_photo_ids(accepted, events)
        visible_customer_as_names = {
            photo.file_name for photo in photos if photo.id in visible_customer_as_ids
        }
        assert visible_customer_as_names == {"stale-admin-as.png"}

        dto = to_partner_job_dto(
            accepted,
            photos=photos,
            as_requested_at=events[-1].created_at,
            visible_customer_as_photo_ids=visible_customer_as_ids,
        )
        assert any(photo.file_name == "stale-admin-as.png" for photo in dto.photos)


def test_customer_as_request_deletes_uploaded_files_when_db_write_fails(client, seed_admin_token, monkeypatch):
    from app.api.routes.customer import orders as customer_orders

    class FakeStorage:
        def __init__(self) -> None:
            self.deleted_keys: list[str] = []

        def save_private(self, *, data: bytes, file_name: str, content_type: str) -> StoredFile:
            return StoredFile(
                storage_key="private/photos/customer-as.png",
                file_url="",
                file_name=file_name,
                file_size=len(data),
                content_type=content_type,
            )

        def delete(self, storage_key: str) -> None:
            self.deleted_keys.append(storage_key)

    storage = FakeStorage()
    admin_h = {"Authorization": f"Bearer {seed_admin_token}"}
    status_res = client.patch(
        f"/api/admin/orders/{DEV_ORDER_ID}",
        json={"status": OrderStatus.CUSTOMER_DELIVERY_DONE.value},
        headers=admin_h,
    )
    assert status_res.status_code == 200, status_res.text

    def fail_submit(
        _self,
        _order_id: str,
        *,
        memo: str,
        stored_files: list[StoredFile],
    ) -> None:
        assert memo == "DB 실패 경로"
        assert len(stored_files) == 1
        raise SQLAlchemyError("forced commit failure")

    monkeypatch.setattr(customer_orders, "get_storage_provider", lambda: storage)
    monkeypatch.setattr(
        customer_orders.OrderService,
        "submit_customer_as_request",
        fail_submit,
    )

    png_bytes = b"\x89PNG\r\n\x1a\ncustomer-as"
    res = client.post(
        "/api/customer/orders/as-request",
        headers={"X-Customer-Token": DEV_CUSTOMER_TOKEN},
        data={
            "phone_suffix": "5432",
            "order_id": DEV_ORDER_ID,
            "memo": "DB 실패 경로",
        },
        files=[("files", ("as.png", png_bytes, "image/png"))],
    )

    assert res.status_code == 500
    assert res.json()["detail"] == "customer_as_request_failed"
    assert storage.deleted_keys == ["private/photos/customer-as.png"]


def test_customer_as_request_deletes_partial_uploads_when_second_file_store_fails(
    client, seed_admin_token, monkeypatch
):
    from app.api.routes.customer import orders as customer_orders

    class FailingSecondSaveStorage:
        def __init__(self) -> None:
            self.save_count = 0
            self.deleted_keys: list[str] = []

        def save_private(self, *, data: bytes, file_name: str, content_type: str) -> StoredFile:
            self.save_count += 1
            if self.save_count == 2:
                raise OSError("forced storage failure")
            return StoredFile(
                storage_key="private/photos/first.png",
                file_url="",
                file_name=file_name,
                file_size=len(data),
                content_type=content_type,
            )

        def delete(self, storage_key: str) -> None:
            self.deleted_keys.append(storage_key)

    storage = FailingSecondSaveStorage()
    monkeypatch.setattr(customer_orders, "get_storage_provider", lambda: storage)
    admin_h = {"Authorization": f"Bearer {seed_admin_token}"}
    status_res = client.patch(
        f"/api/admin/orders/{DEV_ORDER_ID}",
        json={"status": OrderStatus.CUSTOMER_DELIVERY_DONE.value},
        headers=admin_h,
    )
    assert status_res.status_code == 200, status_res.text

    png_bytes = b"\x89PNG\r\n\x1a\ncustomer-as"
    with pytest.raises(OSError, match="forced storage failure"):
        client.post(
            "/api/customer/orders/as-request",
            headers={"X-Customer-Token": DEV_CUSTOMER_TOKEN},
            data={
                "phone_suffix": "5432",
                "order_id": DEV_ORDER_ID,
                "memo": "두 번째 파일 실패",
            },
            files=[
                ("files", ("first.png", png_bytes, "image/png")),
                ("files", ("second.png", png_bytes, "image/png")),
            ],
        )

    assert storage.deleted_keys == ["private/photos/first.png"]


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


def test_as_request_rejects_archived_partner_before_state_change(db_session):
    from datetime import UTC, datetime

    from app.models.order import Order
    from app.models.partner import Partner
    from app.services.orders import OrderService

    order = db_session.get(Order, DEV_ORDER_ID)
    partner = db_session.get(Partner, DEV_PARTNER_ID)
    assert order is not None
    assert partner is not None
    order.status = OrderStatus.CUSTOMER_DELIVERY_DONE
    partner.deleted_at = datetime.now(UTC)
    partner.is_active = False
    db_session.commit()

    with pytest.raises(ValueError, match="partner_not_found"):
        OrderService(db_session).request_as(
            order.id,
            memo="재방문 요청",
            actor_user_id="seed-admin-user",
        )

    db_session.refresh(order)
    assert order.as_requested is False
    assert order.status == OrderStatus.CUSTOMER_DELIVERY_DONE


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
