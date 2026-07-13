from __future__ import annotations

from typing import Any, cast

import pytest
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.core.config import settings
from app.domain.constants import OrderStatus, PhotoType
from app.models.order import Order
from app.models.photo import OrderPhoto
from app.services.orders import OrderService
from app.services.photos import PhotoService


class _ScalarResult:
    def __init__(self, value: Any) -> None:
        self.value = value

    def scalar_one_or_none(self) -> Any:
        return self.value


class _FakeSession:
    def __init__(self, scalar_value: Any) -> None:
        self.scalar_value = scalar_value
        self.statements: list[Select[Any]] = []
        self.is_committed = False
        self.is_refreshed = False

    def execute(self, statement: Select[Any]) -> _ScalarResult:
        self.statements.append(statement)
        return _ScalarResult(self.scalar_value)

    def commit(self) -> None:
        self.is_committed = True

    def refresh(self, _entity: Any) -> None:
        self.is_refreshed = True


def test_complete_partner_job_locks_order_before_photo_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "automation_send_customer_balance_due", False)
    order = Order(
        id="order-1",
        group_id="group-1",
        status=OrderStatus.IN_PROGRESS.value,
        received_date="2026-05-18",
        scheduled_date=None,
        requested_time=None,
        partner_id="partner-1",
        team_name="Team",
        service_name="Service",
        customer_name="Customer",
        customer_phone="01012345678",
        customer_address="Seoul",
        customer_token="token",
        customer_visible_payment=False,
    )
    session = _FakeSession(order)
    service = OrderService(cast(Session, cast(object, session)))
    monkeypatch.setattr(
        service.photos,
        "has_visible_type",
        lambda _order_id, _photo_type, **_kwargs: True,
    )
    monkeypatch.setattr(service.timeline, "record", lambda **_kwargs: None)
    monkeypatch.setattr(
        service.timeline,
        "latest_partner_work_epoch",
        lambda **_kwargs: None,
    )

    service.complete_partner_job(
        "order-1",
        actor_user_id="partner-user-1",
        partner_id="partner-1",
        customer_signature_data_url=(
            "data:image/png;base64,"
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
        ),
    )

    assert session.statements[0]._for_update_arg is not None
    assert order.status == OrderStatus.CUSTOMER_DELIVERY_NEEDED
    assert session.is_committed is True


def test_revoke_refreshes_photo_after_order_lock_before_idempotent_return(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    photo = OrderPhoto(
        id="photo-1",
        order_id="order-1",
        uploaded_by_user_id="partner-user-1",
        photo_type=PhotoType.AFTER.value,
        storage_key="photo-1",
        file_url="/uploads/photo-1.jpg",
        file_name="photo-1.jpg",
        file_size=100,
        content_type="image/jpeg",
        is_customer_visible=True,
    )
    order = Order(
        id="order-1",
        group_id="group-1",
        status=OrderStatus.CUSTOMER_DELIVERY_NEEDED.value,
        received_date="2026-05-18",
        scheduled_date=None,
        requested_time=None,
        partner_id="partner-1",
        team_name="Team",
        service_name="Service",
        customer_name="Customer",
        customer_phone="01012345678",
        customer_address="Seoul",
        customer_token="token",
        customer_visible_payment=False,
    )
    session = _FakeSession(order)

    def refresh_stale_photo(entity: Any) -> None:
        session.is_refreshed = True
        entity.is_customer_visible = False

    monkeypatch.setattr(session, "refresh", refresh_stale_photo)
    service = PhotoService(cast(Session, cast(object, session)))
    monkeypatch.setattr(service.photos, "get", lambda _photo_id: photo)

    def fail_if_timeline_records(**_kwargs: Any) -> None:
        raise AssertionError("stale revoke should return without duplicate timeline")

    monkeypatch.setattr(service.timeline, "record", fail_if_timeline_records)

    result = service.revoke_visibility("photo-1", actor_user_id="admin-user-1")

    assert result is photo
    assert session.statements[0]._for_update_arg is not None
    assert session.is_refreshed is True
    assert session.is_committed is False


def test_partner_photo_delete_locks_order_before_status_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order = Order(
        id="order-1",
        group_id="group-1",
        status=OrderStatus.CUSTOMER_DELIVERY_NEEDED.value,
        received_date="2026-05-18",
        partner_id="partner-1",
        service_name="Service",
        customer_visible_payment=False,
    )
    session = _FakeSession(order)
    service = PhotoService(cast(Session, cast(object, session)))

    with pytest.raises(ValueError, match="invalid_status_for_delete"):
        service.delete_for_partner(
            order_id="order-1",
            photo_id="photo-1",
            user_id="partner-user-1",
            partner_id="partner-1",
        )

    assert session.statements[0]._for_update_arg is not None
    assert session.is_committed is False
