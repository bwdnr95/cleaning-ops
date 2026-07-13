from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.seed import DEV_PARTNER_ID, DEV_PARTNER_USER_ID
from app.domain.constants import MessageType, OrderStatus
from app.domain.payment_status import PaymentStatus
from app.models.message import MessageLog
from app.models.order import Order
from app.models.partner import Partner
from app.repositories.order_groups import OrderGroupRepository
from app.schemas.order import OrderGroupCreate, OrderLineCreate, OrderUpdate
from app.services.messages import MessageService, NotificationRecoveryRunResult
from app.services.notification_recovery import NotificationRecoveryScheduler
from app.services.orders import OrderService


def _message_types(db: Session, order_id: str) -> list[MessageType]:
    return list(
        db.scalars(
            select(MessageLog.message_type)
            .where(MessageLog.order_id == order_id)
            .order_by(MessageLog.created_at.asc(), MessageLog.id.asc())
        )
    )


def test_recovery_sends_assignment_after_committed_state_gap(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "automation_send_partner_assignment", False)
    group = OrderService(db_session).create_group(
        OrderGroupCreate(
            customer_name="배정복구",
            customer_phone="01012341234",
            customer_address="서울특별시 강남구 테스트로 1",
            lines=[
                OrderLineCreate(
                    status=OrderStatus.PARTNER_CONFIRMING,
                    received_date=date(2030, 1, 1),
                    partner_id=DEV_PARTNER_ID,
                    service_name="입주청소",
                )
            ],
        )
    )
    order = OrderGroupRepository(db_session).list_lines(group.id)[0]
    assert _message_types(db_session, order.id) == []

    monkeypatch.setattr(settings, "automation_send_partner_assignment", True)
    first = MessageService(db_session).recover_workflow_notifications()
    second = MessageService(db_session).recover_workflow_notifications()

    assert first.sent == 1
    assert second.sent == 0
    assert _message_types(db_session, order.id) == [MessageType.PARTNER_ASSIGNMENT]


def test_same_partner_update_does_not_create_assignment_recovery_epoch(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "automation_send_partner_assignment", True)
    group = OrderService(db_session).create_group(
        OrderGroupCreate(
            customer_name="No-op assignment",
            customer_phone="01012341234",
            customer_address="Seoul",
            lines=[
                OrderLineCreate(
                    status=OrderStatus.PARTNER_CONFIRMING,
                    received_date=date(2030, 1, 1),
                    partner_id=DEV_PARTNER_ID,
                    service_name="Cleaning",
                )
            ],
        )
    )
    order = OrderGroupRepository(db_session).list_lines(group.id)[0]
    assert _message_types(db_session, order.id).count(MessageType.PARTNER_ASSIGNMENT) == 1

    OrderService(db_session).update(
        order.id,
        OrderUpdate(partner_id=DEV_PARTNER_ID),
    )
    result = MessageService(db_session).recover_workflow_notifications()

    assert result.sent == 0
    assert _message_types(db_session, order.id).count(MessageType.PARTNER_ASSIGNMENT) == 1


def test_recovery_covers_scheduled_assignment_gap(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "automation_send_partner_assignment", False)
    group = OrderService(db_session).create_group(
        OrderGroupCreate(
            customer_name="Scheduled assignment",
            customer_phone="01012341234",
            customer_address="Seoul",
            lines=[
                OrderLineCreate(
                    status=OrderStatus.SCHEDULED,
                    received_date=date(2030, 1, 1),
                    scheduled_date=date(2030, 1, 2),
                    partner_id=DEV_PARTNER_ID,
                    service_name="Cleaning",
                )
            ],
        )
    )
    order = OrderGroupRepository(db_session).list_lines(group.id)[0]

    monkeypatch.setattr(settings, "automation_send_partner_assignment", True)
    result = MessageService(db_session).recover_workflow_notifications()

    assert result.sent == 1
    assert _message_types(db_session, order.id).count(MessageType.PARTNER_ASSIGNMENT) == 1


def test_recovery_sends_confirmation_after_partner_state_gap(
    db_session: Session,
    seed_order: Order,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_order.status = OrderStatus.PARTNER_CONFIRMING
    seed_order.partner_id = DEV_PARTNER_ID
    seed_order.scheduled_date = date(2030, 1, 2)
    db_session.commit()
    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", False)

    OrderService(db_session).confirm_partner_job(
        seed_order.id,
        actor_user_id=DEV_PARTNER_USER_ID,
        partner_id=DEV_PARTNER_ID,
    )
    assert MessageType.CUSTOMER_SCHEDULE_CONFIRMED not in _message_types(
        db_session, seed_order.id
    )

    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", True)
    result = MessageService(db_session).recover_workflow_notifications()

    assert result.sent == 1
    assert _message_types(db_session, seed_order.id).count(
        MessageType.CUSTOMER_SCHEDULE_CONFIRMED
    ) == 1


def test_recovery_does_not_send_obsolete_confirmation_after_completion(
    db_session: Session,
    seed_order: Order,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_order.status = OrderStatus.PARTNER_CONFIRMING
    seed_order.partner_id = DEV_PARTNER_ID
    seed_order.scheduled_date = date(2030, 1, 2)
    db_session.commit()
    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", False)
    OrderService(db_session).confirm_partner_job(
        seed_order.id,
        actor_user_id=DEV_PARTNER_USER_ID,
        partner_id=DEV_PARTNER_ID,
    )
    seed_order.status = OrderStatus.COMPLETED
    db_session.commit()

    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", True)
    result = MessageService(db_session).recover_workflow_notifications()

    assert result.sent == 0
    assert MessageType.CUSTOMER_SCHEDULE_CONFIRMED not in _message_types(
        db_session, seed_order.id
    )


def test_recovery_sends_balance_for_latest_completion_only(
    db_session: Session,
    seed_order: Order,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "automation_send_customer_balance_due", True)
    seed_order.status = OrderStatus.CUSTOMER_DELIVERY_NEEDED
    seed_order.payment_status = PaymentStatus.BALANCE_PENDING
    seed_order.balance_amount = Decimal("120000")
    seed_order.work_completed_at = datetime.now(UTC)
    db_session.commit()

    first = MessageService(db_session).recover_workflow_notifications()
    second = MessageService(db_session).recover_workflow_notifications()

    assert first.sent == 1
    assert second.sent == 0
    assert _message_types(db_session, seed_order.id).count(MessageType.CUSTOMER_BALANCE_DUE) == 1


def test_recovery_completes_partial_as_notifications(
    db_session: Session,
    seed_order: Order,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_order.status = OrderStatus.CUSTOMER_DELIVERY_DONE
    seed_order.partner_id = DEV_PARTNER_ID
    db_session.commit()
    service = OrderService(db_session)
    monkeypatch.setattr(service, "_send_automation_message", lambda *args, **kwargs: None)

    service.request_as(seed_order.id, memo="주방 타일 재확인", actor_user_id=None)
    assert not {
        MessageType.PARTNER_AS_REQUEST,
        MessageType.CUSTOMER_AS_NOTICE,
    }.intersection(_message_types(db_session, seed_order.id))

    first = MessageService(db_session).recover_workflow_notifications()
    second = MessageService(db_session).recover_workflow_notifications()

    assert first.sent == 2
    assert second.sent == 0
    assert _message_types(db_session, seed_order.id).count(MessageType.PARTNER_AS_REQUEST) == 1
    assert _message_types(db_session, seed_order.id).count(MessageType.CUSTOMER_AS_NOTICE) == 1


def test_active_as_reassignment_uses_partner_assignment_epoch(
    db_session: Session,
    seed_order: Order,
) -> None:
    partner_b = Partner(
        id="as-partner-b",
        name="AS Partner B",
        phone="01022223333",
        is_active=True,
    )
    partner_c = Partner(
        id="as-partner-c",
        name="AS Partner C",
        phone="01033334444",
        is_active=True,
    )
    db_session.add_all([partner_b, partner_c])
    seed_order.status = OrderStatus.CUSTOMER_DELIVERY_DONE
    seed_order.partner_id = DEV_PARTNER_ID
    db_session.commit()
    service = OrderService(db_session)
    service.request_as(seed_order.id, memo="Rework", actor_user_id=None)

    service.update(seed_order.id, OrderUpdate(partner_id=partner_b.id))
    service.update(seed_order.id, OrderUpdate(partner_id=partner_c.id))
    service.update(seed_order.id, OrderUpdate(partner_id=partner_b.id))

    partner_recipients = list(
        db_session.scalars(
            select(MessageLog.recipient_partner_id)
            .where(
                MessageLog.order_id == seed_order.id,
                MessageLog.message_type == MessageType.PARTNER_AS_REQUEST,
            )
            .order_by(MessageLog.created_at.asc(), MessageLog.id.asc())
        )
    )
    assert partner_recipients.count(DEV_PARTNER_ID) == 1
    assert partner_recipients.count(partner_b.id) == 2
    assert partner_recipients.count(partner_c.id) == 1


def test_cancelled_as_is_not_recovered(
    db_session: Session,
    seed_order: Order,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_order.status = OrderStatus.CUSTOMER_DELIVERY_DONE
    seed_order.partner_id = DEV_PARTNER_ID
    db_session.commit()
    service = OrderService(db_session)
    monkeypatch.setattr(service, "_send_automation_message", lambda *args, **kwargs: None)
    service.request_as(seed_order.id, memo="Cancel this AS", actor_user_id=None)
    service.update(seed_order.id, OrderUpdate(status=OrderStatus.CANCELLED))

    result = MessageService(db_session).recover_workflow_notifications()

    assert result.sent == 0
    assert not {
        MessageType.PARTNER_AS_REQUEST,
        MessageType.CUSTOMER_AS_NOTICE,
    }.intersection(_message_types(db_session, seed_order.id))


def test_notification_recovery_scheduler_run_once_closes_session() -> None:
    class FakeSession(Session):
        is_closed = False

        def close(self) -> None:
            self.is_closed = True

    class FakeMessageService(MessageService):
        def recover_workflow_notifications(self) -> NotificationRecoveryRunResult:
            return NotificationRecoveryRunResult(
                scanned_orders=1,
                attempted=1,
                sent=1,
                skipped=0,
                failed=0,
            )

    db = FakeSession()
    scheduler = NotificationRecoveryScheduler(
        session_factory=lambda: db,
        message_service_factory=FakeMessageService,
    )

    result = scheduler.run_once()

    assert result.sent == 1
    assert db.is_closed is True
