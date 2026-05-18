from __future__ import annotations

from typing import Any

from sqlalchemy.sql import Select

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


def test_complete_partner_job_locks_order_before_photo_count() -> None:
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
    service = OrderService(session)  # type: ignore[arg-type]
    service.photos.count_visible_for_order = lambda _order_id: 1  # type: ignore[method-assign]
    service.timeline.record = lambda **_kwargs: None  # type: ignore[method-assign]

    service.complete_partner_job(
        "order-1",
        actor_user_id="partner-user-1",
        partner_id="partner-1",
    )

    assert session.statements[0]._for_update_arg is not None
    assert order.status == OrderStatus.CUSTOMER_DELIVERY_NEEDED
    assert session.is_committed is True


def test_revoke_refreshes_photo_after_order_lock_before_idempotent_return() -> None:
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

    session.refresh = refresh_stale_photo  # type: ignore[method-assign]
    service = PhotoService(session)  # type: ignore[arg-type]
    service.photos.get = lambda _photo_id: photo  # type: ignore[method-assign]

    def fail_if_timeline_records(**_kwargs: Any) -> None:
        raise AssertionError("stale revoke should return without duplicate timeline")

    service.timeline.record = fail_if_timeline_records  # type: ignore[method-assign]

    result = service.revoke_visibility("photo-1", actor_user_id="admin-user-1")

    assert result is photo
    assert session.statements[0]._for_update_arg is not None
    assert session.is_refreshed is True
    assert session.is_committed is False
