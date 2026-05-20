import pytest
from sqlalchemy import select

from app.domain.constants import (
    MessageChannel,
    MessageStatus,
    MessageType,
    RecipientType,
    TimelineEventType,
)
from app.models.message import MessageLog
from app.models.order import Order
from app.models.order_group import OrderGroup
from app.models.timeline import OrderTimeline
from app.repositories.messages import MessageRepository
from app.repositories.order_groups import OrderGroupRepository
from app.repositories.orders import OrderRepository
from app.services.orders import OrderService


def test_delete_order_marks_deleted_at_and_records_timeline(db_session, seed_admin_user, seed_order):
    service = OrderService(db_session)

    service.delete_order(order_id=seed_order.id, actor_user_id=seed_admin_user.id)

    db_session.commit()
    db_session.refresh(seed_order)
    assert seed_order.deleted_at is not None

    events = db_session.execute(
        select(OrderTimeline).where(
            OrderTimeline.order_id == seed_order.id,
            OrderTimeline.event_type == TimelineEventType.ORDER_DELETED,
        )
    ).scalars().all()
    assert len(events) == 1
    assert events[0].actor_user_id == seed_admin_user.id


def test_delete_order_is_idempotent_404_on_already_deleted(db_session, seed_admin_user, seed_order):
    service = OrderService(db_session)
    service.delete_order(order_id=seed_order.id, actor_user_id=seed_admin_user.id)
    db_session.commit()

    with pytest.raises(LookupError):
        service.delete_order(order_id=seed_order.id, actor_user_id=seed_admin_user.id)


def test_delete_last_line_in_group_cascades_group_soft_delete(db_session, seed_admin_user, seed_order):
    service = OrderService(db_session)
    service.delete_order(order_id=seed_order.id, actor_user_id=seed_admin_user.id)
    db_session.commit()

    group = db_session.get(OrderGroup, seed_order.group_id)
    assert group.deleted_at is not None


def test_delete_partial_lines_keeps_group_alive(db_session, seed_admin_user, seed_order, make_extra_line):
    extra = make_extra_line(seed_order.group_id)
    service = OrderService(db_session)

    service.delete_order(order_id=extra.id, actor_user_id=seed_admin_user.id)
    db_session.commit()

    group = db_session.get(OrderGroup, seed_order.group_id)
    assert group.deleted_at is None
    db_session.refresh(seed_order)
    assert seed_order.deleted_at is None


def test_bulk_delete_orders_returns_succeeded_and_failed(db_session, seed_admin_user, seed_order):
    service = OrderService(db_session)
    result = service.bulk_delete_orders(
        order_ids=[seed_order.id, "non-existent-id"],
        actor_user_id=seed_admin_user.id,
    )
    db_session.commit()

    assert result.succeeded == [seed_order.id]
    assert len(result.failed) == 1
    assert result.failed[0].order_id == "non-existent-id"
    assert result.failed[0].reason == "not_found"


def test_deleted_order_not_in_admin_list(db_session, seed_admin_user, seed_order):
    OrderService(db_session).delete_order(order_id=seed_order.id, actor_user_id=seed_admin_user.id)
    db_session.commit()

    ids = [order.id for order in OrderRepository(db_session).list_orders()]
    assert seed_order.id not in ids


def test_deleted_order_message_logs_hidden_from_admin_message_list(
    db_session,
    seed_admin_user,
    seed_order,
):
    db_session.add(
        MessageLog(
            id=f"{seed_order.id}-message-log",
            order_id=seed_order.id,
            recipient_type=RecipientType.CUSTOMER,
            recipient_name=seed_order.customer_name,
            recipient_phone=seed_order.customer_phone,
            message_type=MessageType.CUSTOMER_DAY_BEFORE,
            channel=MessageChannel.SMS,
            content="message for deleted order",
            status=MessageStatus.SENT,
            error_message=None,
        )
    )
    db_session.commit()

    OrderService(db_session).delete_order(order_id=seed_order.id, actor_user_id=seed_admin_user.id)
    db_session.commit()

    ids = [message.id for message in MessageRepository(db_session).list_messages()]
    assert f"{seed_order.id}-message-log" not in ids


def test_deleted_order_not_visible_to_partner(
    db_session,
    seed_admin_user,
    seed_order_assigned_to_partner,
):
    order = seed_order_assigned_to_partner
    OrderService(db_session).delete_order(order_id=order.id, actor_user_id=seed_admin_user.id)
    db_session.commit()

    ids = [job.id for job in OrderRepository(db_session).list_for_partner(order.partner_id)]
    assert order.id not in ids


def test_deleted_group_not_visible_to_customer(db_session, seed_admin_user, seed_order_with_customer_token):
    order, group = seed_order_with_customer_token
    OrderService(db_session).delete_order(order_id=order.id, actor_user_id=seed_admin_user.id)
    db_session.commit()

    assert OrderGroupRepository(db_session).get_by_customer_token(group.customer_token) is None


def test_delete_order_api_204(client, seed_admin_token, seed_order_id):
    response = client.delete(
        f"/api/admin/orders/{seed_order_id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    assert response.status_code == 204

    response = client.get(
        f"/api/admin/orders/{seed_order_id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    assert response.status_code == 404


def test_delete_order_api_404_for_already_deleted(client, seed_admin_token, seed_order_id):
    client.delete(
        f"/api/admin/orders/{seed_order_id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    response = client.delete(
        f"/api/admin/orders/{seed_order_id}",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    assert response.status_code == 404


def test_delete_order_api_requires_admin(client, seed_partner_token, seed_order_id):
    response = client.delete(
        f"/api/admin/orders/{seed_order_id}",
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    )
    assert response.status_code in {401, 403}


def test_bulk_delete_orders_api(client, seed_admin_token, seed_order_id):
    response = client.post(
        "/api/admin/orders/bulk-delete",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
        json={"order_ids": [seed_order_id, "non-existent-id"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["succeeded"] == [seed_order_id]
    assert len(body["failed"]) == 1
    assert body["failed"][0]["order_id"] == "non-existent-id"
    assert body["failed"][0]["reason"] == "not_found"
