from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.seed import DEV_PARTNER_ID, DEV_PARTNER_USER_ID
from app.domain.constants import MessageType, OrderStatus, TimelineEventType
from app.models.message import MessageLog
from app.models.order import Order
from app.models.timeline import OrderTimeline
from app.services.orders import OrderService


def test_partner_confirmation_sends_customer_reservation_confirmation(
    db_session: Session,
    seed_order: Order,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", True)
    seed_order.status = OrderStatus.PARTNER_CONFIRMING
    seed_order.partner_id = DEV_PARTNER_ID
    seed_order.scheduled_date = date(2030, 1, 2)
    db_session.commit()

    confirmed = OrderService(db_session).confirm_partner_job(
        seed_order.id,
        actor_user_id=DEV_PARTNER_USER_ID,
        partner_id=DEV_PARTNER_ID,
    )

    assert confirmed.status == OrderStatus.SCHEDULED
    logs = list(
        db_session.scalars(
            select(MessageLog).where(
                MessageLog.order_id == seed_order.id,
                MessageLog.message_type == MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
            )
        )
    )
    assert len(logs) == 1
    events = list(
        db_session.scalars(
            select(OrderTimeline).where(OrderTimeline.order_id == seed_order.id)
        )
    )
    assert any(event.event_type == TimelineEventType.STATUS_CHANGED for event in events)
    assert any(event.event_type == TimelineEventType.MESSAGE_SENT for event in events)


def test_partner_confirmation_respects_disabled_customer_message(
    db_session: Session,
    seed_order: Order,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", False)
    seed_order.status = OrderStatus.PARTNER_CONFIRMING
    seed_order.partner_id = DEV_PARTNER_ID
    seed_order.scheduled_date = date(2030, 1, 2)
    db_session.commit()

    confirmed = OrderService(db_session).confirm_partner_job(
        seed_order.id,
        actor_user_id=DEV_PARTNER_USER_ID,
        partner_id=DEV_PARTNER_ID,
    )

    assert confirmed.status == OrderStatus.SCHEDULED
    logs = list(
        db_session.scalars(
            select(MessageLog).where(MessageLog.order_id == seed_order.id)
        )
    )
    assert logs == []
