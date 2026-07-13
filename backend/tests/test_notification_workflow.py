from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import event, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.time import business_today
from app.db.seed import DEV_PARTNER_ID, DEV_PARTNER_USER_ID
from app.domain.constants import (
    MessageChannel,
    MessageStatus,
    MessageType,
    OrderStatus,
    RecipientType,
    TimelineEventType,
)
from app.domain.payment_status import PaymentStatus
from app.models.message import MessageLog
from app.models.order import Order
from app.models.order_group import OrderGroup
from app.models.partner import Partner
from app.models.timeline import OrderTimeline
from app.schemas.message import MessageSendRequest
from app.schemas.order import OrderCreate, OrderGroupUpdate, OrderUpdate
from app.services.messages import (
    SOLAPI_MESSAGE_LOG_CUSTOM_FIELD,
    MessageProvider,
    MessageProviderSendInput,
    MessageSendResult,
    MessageService,
    SolapiMessageProvider,
)
from app.services.orders import OrderService
from app.services.timeline import TimelineService


def _pending_message(
    *,
    order_id: str,
    message_type: MessageType,
    requested_at: datetime,
) -> MessageLog:
    return MessageLog(
        id=str(uuid4()),
        order_id=order_id,
        recipient_type=RecipientType.CUSTOMER,
        recipient_name="테스트",
        recipient_phone="01012345678",
        message_type=message_type,
        channel=MessageChannel.ALIMTALK,
        content="pending",
        status=MessageStatus.PENDING,
        provider="solapi",
        requested_at=requested_at,
    )


def _schedule_confirmation_logs(db: Session, order_id: str) -> list[MessageLog]:
    return list(
        db.scalars(
            select(MessageLog).where(
                MessageLog.order_id == order_id,
                MessageLog.message_type == MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
            )
        )
    )


def _record_current_partner_confirmation(
    db: Session,
    order: Order,
    *,
    confirmed_at: datetime | None = None,
) -> None:
    order.partner_id = DEV_PARTNER_ID
    event = TimelineService(db).record(
        order_id=order.id,
        event_type=TimelineEventType.PARTNER_CONFIRMED,
        title="partner confirmed",
        metadata={"partner_id": DEV_PARTNER_ID},
    )
    if confirmed_at is not None:
        event.created_at = confirmed_at


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
    assert len(_schedule_confirmation_logs(db_session, seed_order.id)) == 1
    confirmed_again = OrderService(db_session).confirm_partner_job(
        seed_order.id,
        actor_user_id=DEV_PARTNER_USER_ID,
        partner_id=DEV_PARTNER_ID,
    )
    assert confirmed_again.status == OrderStatus.SCHEDULED
    assert len(_schedule_confirmation_logs(db_session, seed_order.id)) == 1
    events = list(
        db_session.scalars(select(OrderTimeline).where(OrderTimeline.order_id == seed_order.id))
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
    assert _schedule_confirmation_logs(db_session, seed_order.id) == []


def test_confirmed_schedule_change_requires_partner_reconfirmation(
    db_session: Session,
    seed_order: Order,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", True)
    seed_order.status = OrderStatus.PARTNER_CONFIRMING
    seed_order.partner_id = DEV_PARTNER_ID
    seed_order.scheduled_date = date(2030, 1, 2)
    db_session.commit()
    service = OrderService(db_session)
    service.confirm_partner_job(
        seed_order.id,
        actor_user_id=DEV_PARTNER_USER_ID,
        partner_id=DEV_PARTNER_ID,
    )

    changed = service.update(
        seed_order.id,
        OrderUpdate(
            status=OrderStatus.SCHEDULED,
            scheduled_date=date(2030, 1, 3),
        ),
    )

    assert changed.status == OrderStatus.PARTNER_CONFIRMING
    assert (
        TimelineService(db_session).latest_current_partner_confirmation(
            order_id=seed_order.id,
            partner_id=DEV_PARTNER_ID,
        )
        is None
    )
    assert len(_schedule_confirmation_logs(db_session, seed_order.id)) == 1
    service.confirm_partner_job(
        seed_order.id,
        actor_user_id=DEV_PARTNER_USER_ID,
        partner_id=DEV_PARTNER_ID,
    )
    assert len(_schedule_confirmation_logs(db_session, seed_order.id)) == 2


def test_inflight_schedule_confirmation_cannot_confirm_rescheduled_order(
    db_session: Session,
    seed_order: Order,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_date = date(2030, 1, 2)
    replacement_date = date(2030, 1, 3)
    seed_order.status = OrderStatus.SCHEDULED
    seed_order.partner_id = DEV_PARTNER_ID
    seed_order.scheduled_date = original_date
    TimelineService(db_session).record(
        order_id=seed_order.id,
        event_type=TimelineEventType.PARTNER_CONFIRMED,
        title="partner confirmed",
        metadata={"partner_id": DEV_PARTNER_ID},
    )
    db_session.commit()

    OtherSession = sessionmaker(bind=db_session.get_bind())
    mutation_errors: list[str] = []

    class ReschedulingProvider(MessageProvider):
        provider_name = "rescheduling-provider"

        def send(self, content: str, recipient_phone: str) -> MessageSendResult:
            with OtherSession() as other_db:
                try:
                    OrderService(other_db).update(
                        seed_order.id,
                        OrderUpdate(scheduled_date=replacement_date),
                    )
                except ValueError as exc:
                    mutation_errors.append(str(exc))
            return MessageSendResult(status=MessageStatus.SENT, provider=self.provider_name)

    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", True)
    log = MessageService(db_session, provider=ReschedulingProvider()).send(
        MessageSendRequest(
            order_id=seed_order.id,
            message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
            recipient_type=RecipientType.CUSTOMER,
        )
    )

    db_session.refresh(seed_order)
    assert log.status == MessageStatus.SENT
    assert mutation_errors == ["message_dispatch_in_progress"]
    assert seed_order.scheduled_date == original_date
    assert seed_order.status == OrderStatus.SCHEDULED
    assert len(_schedule_confirmation_logs(db_session, seed_order.id)) == 1


def test_inflight_customer_message_blocks_group_contact_update(
    db_session: Session,
    seed_order: Order,
) -> None:
    group_id = seed_order.group_id
    original_phone = seed_order.customer_phone
    OtherSession = sessionmaker(bind=db_session.get_bind())
    mutation_errors: list[str] = []

    class GroupUpdatingProvider(MessageProvider):
        provider_name = "group-updating-provider"

        def send(self, content: str, recipient_phone: str) -> MessageSendResult:
            with OtherSession() as other_db:
                try:
                    OrderService(other_db).update_group(
                        group_id,
                        OrderGroupUpdate(customer_phone="010-9999-0000"),
                    )
                except ValueError as exc:
                    mutation_errors.append(str(exc))
            return MessageSendResult(status=MessageStatus.SENT, provider=self.provider_name)

    log = MessageService(db_session, provider=GroupUpdatingProvider()).send(
        MessageSendRequest(
            order_id=seed_order.id,
            message_type=MessageType.CUSTOMER_ACCESS_LINK,
            recipient_type=RecipientType.CUSTOMER,
        )
    )

    db_session.refresh(seed_order)
    group = db_session.get(OrderGroup, group_id)
    assert group is not None
    assert log.status == MessageStatus.SENT
    assert mutation_errors == ["message_dispatch_in_progress"]
    assert seed_order.customer_phone == original_phone
    assert group.customer_phone == original_phone


def test_group_update_locks_order_lines_before_pending_dispatch_check(
    db_session: Session,
    seed_order: Order,
) -> None:
    group_id = seed_order.group_id
    statements: list[str] = []
    bind = db_session.get_bind()

    def capture_statement(conn, cursor, statement, parameters, context, executemany) -> None:
        statements.append(" ".join(statement.lower().split()))

    event.listen(bind, "before_cursor_execute", capture_statement)
    try:
        OrderService(db_session).update_group(
            group_id,
            OrderGroupUpdate(customer_phone="010-8888-0000"),
        )
    finally:
        event.remove(bind, "before_cursor_execute", capture_statement)

    order_lock_index = next(
        index
        for index, statement in enumerate(statements)
        if " from orders " in statement
        and "where orders.group_id" in statement
        and "order by orders.id asc" in statement
    )
    pending_check_index = next(
        index
        for index, statement in enumerate(statements)
        if " from message_logs join orders " in statement and "message_logs.status" in statement
    )
    assert order_lock_index < pending_check_index


def test_inflight_assignment_cannot_advance_unassigned_order(
    db_session: Session,
    seed_order: Order,
) -> None:
    seed_order.status = OrderStatus.NEW
    seed_order.partner_id = DEV_PARTNER_ID
    db_session.commit()
    OtherSession = sessionmaker(bind=db_session.get_bind())
    mutation_errors: list[str] = []

    class UnassigningProvider(MessageProvider):
        provider_name = "unassigning-provider"

        def send(self, content: str, recipient_phone: str) -> MessageSendResult:
            with OtherSession() as other_db:
                try:
                    OrderService(other_db).update(
                        seed_order.id,
                        OrderUpdate(partner_id=None),
                    )
                except ValueError as exc:
                    mutation_errors.append(str(exc))
            return MessageSendResult(status=MessageStatus.SENT, provider=self.provider_name)

    log = MessageService(db_session, provider=UnassigningProvider()).send(
        MessageSendRequest(
            order_id=seed_order.id,
            message_type=MessageType.PARTNER_ASSIGNMENT,
            recipient_type=RecipientType.PARTNER,
        )
    )

    db_session.refresh(seed_order)
    assert log.status == MessageStatus.SENT
    assert mutation_errors == ["message_dispatch_in_progress"]
    assert seed_order.partner_id == DEV_PARTNER_ID
    assert seed_order.status == OrderStatus.PARTNER_CONFIRMING


def test_concurrent_manual_send_is_blocked_by_pending_attempt(
    db_session: Session,
    seed_order: Order,
) -> None:
    seed_order.status = OrderStatus.SCHEDULED
    seed_order.partner_id = DEV_PARTNER_ID
    seed_order.scheduled_date = date(2030, 1, 2)
    TimelineService(db_session).record(
        order_id=seed_order.id,
        event_type=TimelineEventType.PARTNER_CONFIRMED,
        title="partner confirmed",
        metadata={"partner_id": DEV_PARTNER_ID},
    )
    db_session.commit()
    OtherSession = sessionmaker(bind=db_session.get_bind())
    blocked_errors: list[str] = []

    class NeverCalledProvider(MessageProvider):
        def send(self, content: str, recipient_phone: str) -> MessageSendResult:
            raise AssertionError("second provider call must be blocked")

    class RacingProvider(MessageProvider):
        provider_name = "racing-provider"

        def send(self, content: str, recipient_phone: str) -> MessageSendResult:
            with OtherSession() as other_db:
                try:
                    MessageService(other_db, provider=NeverCalledProvider()).send(
                        MessageSendRequest(
                            order_id=seed_order.id,
                            message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
                            recipient_type=RecipientType.CUSTOMER,
                        )
                    )
                except ValueError as exc:
                    blocked_errors.append(str(exc))
            return MessageSendResult(status=MessageStatus.SENT, provider=self.provider_name)

    result = MessageService(db_session, provider=RacingProvider()).send(
        MessageSendRequest(
            order_id=seed_order.id,
            message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
            recipient_type=RecipientType.CUSTOMER,
        )
    )

    assert result.status == MessageStatus.SENT
    assert blocked_errors == ["message_send_in_progress"]
    assert len(_schedule_confirmation_logs(db_session, seed_order.id)) == 1


def test_webhook_custom_field_wins_when_provider_response_is_lost(
    db_session: Session,
    seed_order: Order,
) -> None:
    seed_order.status = OrderStatus.SCHEDULED
    seed_order.partner_id = DEV_PARTNER_ID
    seed_order.scheduled_date = date(2030, 1, 2)
    TimelineService(db_session).record(
        order_id=seed_order.id,
        event_type=TimelineEventType.PARTNER_CONFIRMED,
        title="partner confirmed",
        metadata={"partner_id": DEV_PARTNER_ID},
    )
    db_session.commit()
    OtherSession = sessionmaker(bind=db_session.get_bind())
    delivered_at = datetime(2030, 1, 1, 0, 0, 5, tzinfo=UTC)

    class WebhookFirstProvider(MessageProvider):
        provider_name = "solapi"

        def send_with_context(
            self,
            send_input: MessageProviderSendInput,
        ) -> MessageSendResult:
            assert send_input.message_log_id is not None
            with OtherSession() as other_db:
                pending = other_db.scalar(
                    select(MessageLog).where(
                        MessageLog.order_id == seed_order.id,
                        MessageLog.message_type == MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
                        MessageLog.status == MessageStatus.PENDING,
                    )
                )
                assert pending is not None
                MessageService(other_db).process_solapi_webhook_events(
                    [
                        {
                            "messageId": "webhook-first-message",
                            "groupId": "webhook-first-group",
                            "statusCode": "4000",
                            "statusMessage": "수신 완료",
                            "dateReported": delivered_at.isoformat(),
                            "dateReceived": delivered_at.isoformat(),
                            "customFields": {
                                SOLAPI_MESSAGE_LOG_CUSTOM_FIELD: send_input.message_log_id,
                            },
                        }
                    ]
                )
            raise RuntimeError("provider response lost after webhook")

    log = MessageService(db_session, provider=WebhookFirstProvider()).send(
        MessageSendRequest(
            order_id=seed_order.id,
            message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
            recipient_type=RecipientType.CUSTOMER,
        )
    )

    assert log.status == MessageStatus.DELIVERED
    assert log.provider_status_code == "4000"
    assert log.provider_status_message == "수신 완료"
    assert log.delivered_at is not None
    assert log.provider_group_id == "webhook-first-group"
    link_events = list(
        db_session.scalars(
            select(OrderTimeline).where(
                OrderTimeline.order_id == seed_order.id,
                OrderTimeline.event_type == TimelineEventType.CUSTOMER_LINK_SENT,
            )
        )
    )
    assert len(link_events) == 1
    dispatch_events = list(
        db_session.scalars(
            select(OrderTimeline).where(
                OrderTimeline.order_id == seed_order.id,
                OrderTimeline.event_type == TimelineEventType.MESSAGE_SENT,
                OrderTimeline.title == "메시지 발송",
            )
        )
    )
    dispatch_metadata = dispatch_events[-1].event_metadata
    assert dispatch_metadata is not None
    assert dispatch_metadata["status"] == MessageStatus.DELIVERED


def test_unexpected_solapi_response_context_failure_stays_pending(
    db_session: Session,
    seed_order: Order,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_order.status = OrderStatus.SCHEDULED
    seed_order.partner_id = DEV_PARTNER_ID
    seed_order.scheduled_date = date(2030, 1, 2)
    TimelineService(db_session).record(
        order_id=seed_order.id,
        event_type=TimelineEventType.PARTNER_CONFIRMED,
        title="partner confirmed",
        metadata={"partner_id": DEV_PARTNER_ID},
    )
    db_session.commit()

    class ExitFailureResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            raise RuntimeError("response cleanup failed")

        def read(self) -> bytes:
            return b'{"groupInfo":{"groupId":"accepted-group"}}'

    monkeypatch.setattr(
        "app.services.messages.urlopen",
        lambda request, timeout: ExitFailureResponse(),
    )
    provider = SolapiMessageProvider(
        api_key="api-key",
        api_secret="api-secret",
        sender_number="02-123-4567",
    )

    log = MessageService(db_session, provider=provider).send(
        MessageSendRequest(
            order_id=seed_order.id,
            message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
            recipient_type=RecipientType.CUSTOMER,
            channel=MessageChannel.SMS,
        )
    )

    assert log.status == MessageStatus.PENDING
    assert log.provider == "solapi"
    assert log.provider_error_code == "solapi_outcome_unknown"


def test_message_reconciliation_locks_order_before_message(
    db_session: Session,
    seed_order: Order,
) -> None:
    pending = _pending_message(
        order_id=seed_order.id,
        message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
        requested_at=datetime.now(UTC),
    )
    db_session.add(pending)
    db_session.commit()
    observed_tables: list[str] = []

    def record_select(
        _connection,
        _cursor,
        statement: str,
        _parameters,
        _context,
        _executemany,
    ) -> None:
        normalized = statement.lower()
        if " from orders " in normalized.replace("\n", " "):
            observed_tables.append("orders")
        elif " from message_logs " in normalized.replace("\n", " "):
            observed_tables.append("message_logs")

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", record_select)
    try:
        order, log = MessageService(db_session)._lock_order_then_message(
            order_id=seed_order.id,
            message_id=pending.id,
        )
    finally:
        event.remove(engine, "before_cursor_execute", record_select)

    assert order is not None
    assert log is not None
    assert observed_tables[:2] == ["orders", "message_logs"]


def test_webhook_batch_uses_stable_message_lock_order(
    db_session: Session,
    seed_order: Order,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_at = datetime.now(UTC)
    logs: list[MessageLog] = []
    for suffix in ("b", "a"):
        log = _pending_message(
            order_id=seed_order.id,
            message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
            requested_at=requested_at,
        )
        log.id = f"webhook-lock-{suffix}"
        log.provider_message_id = f"provider-lock-{suffix}"
        logs.append(log)
    db_session.add_all(logs)
    db_session.commit()
    service = MessageService(db_session)
    original_lock = service._lock_order_then_message
    lock_order: list[str] = []

    def record_lock(*, order_id: str, message_id: str):
        lock_order.append(message_id)
        return original_lock(order_id=order_id, message_id=message_id)

    monkeypatch.setattr(service, "_lock_order_then_message", record_lock)
    service.process_solapi_webhook_events(
        [
            {
                "messageId": "provider-lock-b",
                "statusCode": "4000",
                "dateReported": "2030-01-01T00:00:02Z",
            },
            {
                "messageId": "provider-lock-a",
                "statusCode": "4000",
                "dateReported": "2030-01-01T00:00:01Z",
            },
        ]
    )

    assert lock_order == ["webhook-lock-a", "webhook-lock-b"]


def test_inflight_day_before_cannot_complete_reconfirmed_time_change(
    db_session: Session,
    seed_order: Order,
) -> None:
    seed_order.status = OrderStatus.SCHEDULE_CONFIRMED
    seed_order.partner_id = DEV_PARTNER_ID
    seed_order.scheduled_date = business_today() + timedelta(days=1)
    seed_order.requested_time = "09:00"
    TimelineService(db_session).record(
        order_id=seed_order.id,
        event_type=TimelineEventType.PARTNER_CONFIRMED,
        title="partner confirmed",
        metadata={"partner_id": DEV_PARTNER_ID},
    )
    db_session.commit()
    OtherSession = sessionmaker(bind=db_session.get_bind())
    mutation_errors: list[str] = []

    class ReconfirmingProvider(MessageProvider):
        provider_name = "reconfirming-provider"

        def send(self, content: str, recipient_phone: str) -> MessageSendResult:
            with OtherSession() as other_db:
                service = OrderService(other_db)
                try:
                    service.update(
                        seed_order.id,
                        OrderUpdate(requested_time="10:00"),
                    )
                except ValueError as exc:
                    mutation_errors.append(str(exc))
            return MessageSendResult(status=MessageStatus.SENT, provider=self.provider_name)

    log = MessageService(db_session, provider=ReconfirmingProvider()).send(
        MessageSendRequest(
            order_id=seed_order.id,
            message_type=MessageType.CUSTOMER_DAY_BEFORE,
            recipient_type=RecipientType.CUSTOMER,
        )
    )

    db_session.refresh(seed_order)
    assert log.status == MessageStatus.SENT
    assert mutation_errors == ["message_dispatch_in_progress"]
    assert seed_order.requested_time == "09:00"
    assert seed_order.status == OrderStatus.DAY_BEFORE_NOTICE_DONE


def test_confirmed_partner_change_requires_new_partner_confirmation(
    db_session: Session,
    seed_order: Order,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    partner_b = Partner(
        id="confirmation-partner-b",
        name="Confirmation Partner B",
        phone="01066667777",
        is_active=True,
    )
    db_session.add(partner_b)
    seed_order.status = OrderStatus.PARTNER_CONFIRMING
    seed_order.partner_id = DEV_PARTNER_ID
    seed_order.scheduled_date = date(2030, 1, 2)
    db_session.commit()
    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", True)
    service = OrderService(db_session)
    service.confirm_partner_job(
        seed_order.id,
        actor_user_id=DEV_PARTNER_USER_ID,
        partner_id=DEV_PARTNER_ID,
    )

    changed = service.update(
        seed_order.id,
        OrderUpdate(
            status=OrderStatus.SCHEDULED,
            partner_id=partner_b.id,
        ),
    )

    assert changed.status == OrderStatus.PARTNER_CONFIRMING
    assert (
        TimelineService(db_session).latest_current_partner_confirmation(
            order_id=seed_order.id,
            partner_id=partner_b.id,
        )
        is None
    )
    service.confirm_partner_job(
        seed_order.id,
        actor_user_id="partner-b-user",
        partner_id=partner_b.id,
    )
    assert len(_schedule_confirmation_logs(db_session, seed_order.id)) == 2


def test_retried_full_schedule_update_cannot_restore_scheduled_without_confirmation(
    db_session: Session,
    seed_order: Order,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", True)
    seed_order.status = OrderStatus.PARTNER_CONFIRMING
    seed_order.partner_id = DEV_PARTNER_ID
    seed_order.scheduled_date = date(2030, 1, 2)
    db_session.commit()
    service = OrderService(db_session)
    service.confirm_partner_job(
        seed_order.id,
        actor_user_id=DEV_PARTNER_USER_ID,
        partner_id=DEV_PARTNER_ID,
    )
    payload = OrderUpdate(
        status=OrderStatus.SCHEDULED,
        partner_id=DEV_PARTNER_ID,
        scheduled_date=date(2030, 1, 3),
    )

    first = service.update(seed_order.id, payload)
    second = service.update(seed_order.id, payload)

    assert first.status == OrderStatus.PARTNER_CONFIRMING
    assert second.status == OrderStatus.PARTNER_CONFIRMING
    assert (
        TimelineService(db_session).latest_current_partner_confirmation(
            order_id=seed_order.id,
            partner_id=DEV_PARTNER_ID,
        )
        is None
    )
    assert len(_schedule_confirmation_logs(db_session, seed_order.id)) == 1


def test_initial_scheduled_order_with_partner_requires_explicit_confirmation(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "automation_send_partner_assignment", True)
    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", True)

    created = OrderService(db_session).create(
        OrderCreate(
            status=OrderStatus.SCHEDULED,
            received_date=date(2030, 1, 1),
            scheduled_date=date(2030, 1, 2),
            partner_id=DEV_PARTNER_ID,
            service_name="입주청소",
            customer_name="확인 고객",
            customer_phone="01012345678",
            customer_address="서울 강남구 테스트로 1",
        )
    )

    assert created.status == OrderStatus.PARTNER_CONFIRMING
    assert _schedule_confirmation_logs(db_session, created.id) == []
    assert (
        db_session.scalar(
            select(OrderTimeline).where(
                OrderTimeline.order_id == created.id,
                OrderTimeline.event_type == TimelineEventType.PARTNER_CONFIRMATION_REQUIRED,
            )
        )
        is not None
    )

    confirmed = OrderService(db_session).confirm_partner_job(
        created.id,
        actor_user_id=DEV_PARTNER_USER_ID,
        partner_id=DEV_PARTNER_ID,
    )
    assert confirmed.status == OrderStatus.SCHEDULED
    assert len(_schedule_confirmation_logs(db_session, created.id)) == 1


def test_schedule_change_does_not_override_explicit_completed_status(
    db_session: Session,
    seed_order: Order,
) -> None:
    seed_order.status = OrderStatus.SCHEDULED
    seed_order.scheduled_date = date(2030, 1, 2)
    db_session.commit()

    updated = OrderService(db_session).update(
        seed_order.id,
        OrderUpdate(
            status=OrderStatus.COMPLETED,
            scheduled_date=date(2030, 1, 3),
        ),
    )

    assert updated.status == OrderStatus.COMPLETED


def test_legacy_scheduled_order_change_requires_confirmation_epoch(
    db_session: Session,
    seed_order: Order,
) -> None:
    seed_order.status = OrderStatus.SCHEDULED
    seed_order.scheduled_date = date(2030, 1, 2)
    db_session.commit()

    updated = OrderService(db_session).update(
        seed_order.id,
        OrderUpdate(scheduled_date=date(2030, 1, 3)),
    )

    assert updated.status == OrderStatus.PARTNER_CONFIRMING
    assert (
        TimelineService(db_session).latest_current_partner_confirmation(
            order_id=seed_order.id,
            partner_id=seed_order.partner_id,
        )
        is None
    )


def test_partner_confirmation_requires_visit_date(
    db_session: Session,
    seed_order: Order,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", True)
    seed_order.status = OrderStatus.PARTNER_CONFIRMING
    seed_order.partner_id = DEV_PARTNER_ID
    seed_order.scheduled_date = None
    db_session.commit()

    with pytest.raises(ValueError, match="schedule_required_for_confirmation"):
        OrderService(db_session).confirm_partner_job(
            seed_order.id,
            actor_user_id=DEV_PARTNER_USER_ID,
            partner_id=DEV_PARTNER_ID,
        )

    db_session.refresh(seed_order)
    assert seed_order.status == OrderStatus.PARTNER_CONFIRMING
    assert _schedule_confirmation_logs(db_session, seed_order.id) == []


def test_schedule_confirmation_preview_requires_partner_confirmation(
    db_session: Session,
    seed_order: Order,
) -> None:
    seed_order.status = OrderStatus.PARTNER_CONFIRMING
    seed_order.scheduled_date = date(2030, 1, 2)
    db_session.commit()

    with pytest.raises(ValueError, match="partner_confirmation_required"):
        MessageService(db_session).preview(
            MessageSendRequest(
                order_id=seed_order.id,
                message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
                recipient_type=RecipientType.CUSTOMER,
            )
        )


def test_cancelled_order_blocks_assignment_and_balance_messages(
    db_session: Session,
    seed_order: Order,
) -> None:
    seed_order.status = OrderStatus.CANCELLED
    seed_order.partner_id = DEV_PARTNER_ID
    seed_order.work_completed_at = datetime.now(UTC)
    seed_order.payment_status = PaymentStatus.BALANCE_PENDING
    seed_order.balance_amount = Decimal("100000")
    db_session.commit()
    service = MessageService(db_session)

    with pytest.raises(ValueError, match="partner_assignment_not_allowed"):
        service.send(
            MessageSendRequest(
                order_id=seed_order.id,
                message_type=MessageType.PARTNER_ASSIGNMENT,
                recipient_type=RecipientType.PARTNER,
            )
        )
    with pytest.raises(ValueError, match="customer_balance_not_due"):
        service.send(
            MessageSendRequest(
                order_id=seed_order.id,
                message_type=MessageType.CUSTOMER_BALANCE_DUE,
                recipient_type=RecipientType.CUSTOMER,
            )
        )


def test_adding_visit_date_keeps_partner_confirmation_pending(
    db_session: Session,
    seed_order: Order,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", True)
    seed_order.status = OrderStatus.PARTNER_CONFIRMING
    seed_order.partner_id = DEV_PARTNER_ID
    seed_order.scheduled_date = None
    db_session.commit()

    updated = OrderService(db_session).update(
        seed_order.id,
        OrderUpdate(scheduled_date=date(2030, 1, 2)),
    )

    assert updated.status == OrderStatus.PARTNER_CONFIRMING
    assert _schedule_confirmation_logs(db_session, seed_order.id) == []


def test_partner_confirmation_skips_recent_pending_attempt(
    db_session: Session,
    seed_order: Order,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", True)
    seed_order.status = OrderStatus.SCHEDULED
    seed_order.partner_id = DEV_PARTNER_ID
    seed_order.scheduled_date = date(2030, 1, 2)
    TimelineService(db_session).record(
        order_id=seed_order.id,
        event_type=TimelineEventType.PARTNER_CONFIRMED,
        title="partner confirmed",
        metadata={"partner_id": DEV_PARTNER_ID},
    )
    pending = _pending_message(
        order_id=seed_order.id,
        message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
        requested_at=datetime.now(UTC),
    )
    db_session.add(pending)
    db_session.commit()

    confirmed = OrderService(db_session).confirm_partner_job(
        seed_order.id,
        actor_user_id=DEV_PARTNER_USER_ID,
        partner_id=DEV_PARTNER_ID,
    )

    assert confirmed.status == OrderStatus.SCHEDULED
    logs = _schedule_confirmation_logs(db_session, seed_order.id)
    assert [(log.id, log.status) for log in logs] == [(pending.id, MessageStatus.PENDING)]


def test_partner_confirmation_marks_stale_solapi_pending_unknown_without_retry(
    db_session: Session,
    seed_order: Order,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", True)
    seed_order.status = OrderStatus.SCHEDULED
    seed_order.partner_id = DEV_PARTNER_ID
    seed_order.scheduled_date = date(2030, 1, 2)
    pending_requested_at = datetime.now(UTC) - timedelta(
        minutes=settings.message_pending_retry_after_minutes + 1
    )
    confirmed = TimelineService(db_session).record(
        order_id=seed_order.id,
        event_type=TimelineEventType.PARTNER_CONFIRMED,
        title="partner confirmed",
        metadata={"partner_id": DEV_PARTNER_ID},
    )
    confirmed.created_at = pending_requested_at - timedelta(minutes=1)
    pending = _pending_message(
        order_id=seed_order.id,
        message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
        requested_at=pending_requested_at,
    )
    db_session.add(pending)
    db_session.commit()

    OrderService(db_session).confirm_partner_job(
        seed_order.id,
        actor_user_id=DEV_PARTNER_USER_ID,
        partner_id=DEV_PARTNER_ID,
    )

    logs = _schedule_confirmation_logs(db_session, seed_order.id)
    assert len(logs) == 1
    db_session.refresh(pending)
    assert pending.status == MessageStatus.PENDING
    assert pending.provider_error_code == "solapi_outcome_unknown"
    assert (
        db_session.scalar(
            select(OrderTimeline).where(
                OrderTimeline.order_id == seed_order.id,
                OrderTimeline.title == "SOLAPI 발송 결과 확인 필요",
            )
        )
        is not None
    )


def test_direct_send_persists_stale_solapi_unknown_before_rejecting_retry(
    db_session: Session,
    seed_order: Order,
) -> None:
    seed_order.status = OrderStatus.SCHEDULED
    seed_order.partner_id = DEV_PARTNER_ID
    seed_order.scheduled_date = date(2030, 1, 2)
    pending_requested_at = datetime.now(UTC) - timedelta(
        minutes=settings.message_pending_retry_after_minutes + 1
    )
    confirmed = TimelineService(db_session).record(
        order_id=seed_order.id,
        event_type=TimelineEventType.PARTNER_CONFIRMED,
        title="partner confirmed",
        metadata={"partner_id": DEV_PARTNER_ID},
    )
    confirmed.created_at = pending_requested_at - timedelta(minutes=1)
    pending = _pending_message(
        order_id=seed_order.id,
        message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
        requested_at=pending_requested_at,
    )
    db_session.add(pending)
    db_session.commit()

    with pytest.raises(ValueError, match="message_outcome_unknown"):
        MessageService(db_session).send(
            MessageSendRequest(
                order_id=seed_order.id,
                message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
                recipient_type=RecipientType.CUSTOMER,
            )
        )

    db_session.rollback()
    db_session.refresh(pending)
    assert pending.status == MessageStatus.PENDING
    assert pending.provider_error_code == "solapi_outcome_unknown"


def test_partner_confirmation_backs_off_after_recent_failure(
    db_session: Session,
    seed_order: Order,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", True)
    seed_order.status = OrderStatus.SCHEDULED
    seed_order.partner_id = DEV_PARTNER_ID
    seed_order.scheduled_date = date(2030, 1, 2)
    TimelineService(db_session).record(
        order_id=seed_order.id,
        event_type=TimelineEventType.PARTNER_CONFIRMED,
        title="partner confirmed",
        metadata={"partner_id": DEV_PARTNER_ID},
    )
    failed = _pending_message(
        order_id=seed_order.id,
        message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
        requested_at=datetime.now(UTC),
    )
    failed.status = MessageStatus.FAILED
    failed.provider_error_code = "provider_failed"
    db_session.add(failed)
    db_session.commit()

    confirmed = OrderService(db_session).confirm_partner_job(
        seed_order.id,
        actor_user_id=DEV_PARTNER_USER_ID,
        partner_id=DEV_PARTNER_ID,
    )

    assert confirmed.status == OrderStatus.SCHEDULED
    assert [
        (log.id, log.status) for log in _schedule_confirmation_logs(db_session, seed_order.id)
    ] == [(failed.id, MessageStatus.FAILED)]


def test_unknown_provider_outcome_blocks_only_its_confirmation_epoch(
    db_session: Session,
    seed_order: Order,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", True)
    seed_order.status = OrderStatus.PARTNER_CONFIRMING
    seed_order.partner_id = DEV_PARTNER_ID
    seed_order.scheduled_date = date(2030, 1, 2)
    old_unknown = _pending_message(
        order_id=seed_order.id,
        message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
        requested_at=datetime.now(UTC) - timedelta(days=1),
    )
    old_unknown.provider_error_code = "solapi_outcome_unknown"
    db_session.add(old_unknown)
    db_session.commit()

    OrderService(db_session).confirm_partner_job(
        seed_order.id,
        actor_user_id=DEV_PARTNER_USER_ID,
        partner_id=DEV_PARTNER_ID,
    )

    logs = _schedule_confirmation_logs(db_session, seed_order.id)
    assert len(logs) == 2
    assert old_unknown.status == MessageStatus.PENDING
    assert sum(log.status == MessageStatus.SENT for log in logs) == 1


def test_current_confirmation_unknown_outcome_is_not_automatically_retried(
    db_session: Session,
    seed_order: Order,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", False)
    seed_order.status = OrderStatus.PARTNER_CONFIRMING
    seed_order.partner_id = DEV_PARTNER_ID
    seed_order.scheduled_date = date(2030, 1, 2)
    db_session.commit()
    OrderService(db_session).confirm_partner_job(
        seed_order.id,
        actor_user_id=DEV_PARTNER_USER_ID,
        partner_id=DEV_PARTNER_ID,
    )
    unknown = _pending_message(
        order_id=seed_order.id,
        message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
        requested_at=datetime.now(UTC),
    )
    unknown.provider_error_code = "solapi_invalid_response"
    db_session.add(unknown)
    db_session.commit()

    monkeypatch.setattr(settings, "automation_send_schedule_confirmed", True)
    OrderService(db_session).confirm_partner_job(
        seed_order.id,
        actor_user_id=DEV_PARTNER_USER_ID,
        partner_id=DEV_PARTNER_ID,
    )

    assert [
        (log.id, log.status) for log in _schedule_confirmation_logs(db_session, seed_order.id)
    ] == [(unknown.id, MessageStatus.PENDING)]
    with pytest.raises(ValueError, match="message_outcome_unknown"):
        MessageService(db_session).send(
            MessageSendRequest(
                order_id=seed_order.id,
                message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
                recipient_type=RecipientType.CUSTOMER,
            )
        )
    service = MessageService(db_session)
    resolved = service.resolve_unknown_outcome(
        unknown.id,
        resolution="confirmed_not_sent",
        actor_user_id="admin-user",
    )
    resent = service.send(
        MessageSendRequest(
            order_id=seed_order.id,
            message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
            recipient_type=RecipientType.CUSTOMER,
        )
    )

    assert resolved.status == MessageStatus.FAILED
    assert resolved.provider_error_code == "manually_confirmed_not_sent"
    assert resent.status == MessageStatus.SENT
    resolution_events = list(
        db_session.scalars(
            select(OrderTimeline).where(
                OrderTimeline.order_id == seed_order.id,
                OrderTimeline.title == "SOLAPI 불명 결과 수동 확정",
            )
        )
    )
    assert len(resolution_events) == 1
    assert resolution_events[0].actor_user_id == "admin-user"


def test_confirmed_sent_unknown_day_before_applies_current_workflow_side_effects(
    db_session: Session,
    seed_order: Order,
) -> None:
    seed_order.status = OrderStatus.SCHEDULE_CONFIRMED
    seed_order.scheduled_date = business_today() + timedelta(days=1)
    _record_current_partner_confirmation(db_session, seed_order)
    unknown = _pending_message(
        order_id=seed_order.id,
        message_type=MessageType.CUSTOMER_DAY_BEFORE,
        requested_at=datetime.now(UTC),
    )
    unknown.provider_error_code = "solapi_outcome_unknown"
    db_session.add(unknown)
    db_session.commit()

    resolved = MessageService(db_session).resolve_unknown_outcome(
        unknown.id,
        resolution="confirmed_sent",
        actor_user_id="admin-user",
    )

    db_session.refresh(seed_order)
    assert resolved.status == MessageStatus.SENT
    assert resolved.provider_error_code == "manually_confirmed_sent"
    assert seed_order.status == OrderStatus.DAY_BEFORE_NOTICE_DONE
    events = list(
        db_session.scalars(select(OrderTimeline).where(OrderTimeline.order_id == seed_order.id))
    )
    assert TimelineEventType.CUSTOMER_LINK_SENT in {event.event_type for event in events}


def test_unknown_day_before_must_be_resolved_before_schedule_change(
    db_session: Session,
    seed_order: Order,
) -> None:
    seed_order.status = OrderStatus.SCHEDULE_CONFIRMED
    seed_order.partner_id = DEV_PARTNER_ID
    seed_order.scheduled_date = business_today() + timedelta(days=1)
    seed_order.requested_time = "09:00"
    TimelineService(db_session).record(
        order_id=seed_order.id,
        event_type=TimelineEventType.PARTNER_CONFIRMED,
        title="old confirmation",
        metadata={"partner_id": DEV_PARTNER_ID},
    )
    unknown = _pending_message(
        order_id=seed_order.id,
        message_type=MessageType.CUSTOMER_DAY_BEFORE,
        requested_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    unknown.provider_error_code = "solapi_outcome_unknown"
    db_session.add(unknown)
    db_session.commit()

    with pytest.raises(ValueError, match="message_dispatch_in_progress"):
        OrderService(db_session).update(
            seed_order.id,
            OrderUpdate(requested_time="10:00"),
        )

    resolved = MessageService(db_session).resolve_unknown_outcome(
        unknown.id,
        resolution="confirmed_sent",
        actor_user_id="admin-user",
    )

    db_session.refresh(seed_order)
    assert resolved.status == MessageStatus.SENT
    assert seed_order.status == OrderStatus.SCHEDULE_CONFIRMED

    changed = OrderService(db_session).update(
        seed_order.id,
        OrderUpdate(requested_time="10:00"),
    )
    assert changed.requested_time == "10:00"
    assert changed.status == OrderStatus.PARTNER_CONFIRMING


def test_day_before_skips_recent_pending_attempt(
    db_session: Session,
    seed_order: Order,
) -> None:
    target_date = date(2030, 1, 2)
    seed_order.status = OrderStatus.SCHEDULED
    seed_order.scheduled_date = target_date
    _record_current_partner_confirmation(db_session, seed_order)
    pending = _pending_message(
        order_id=seed_order.id,
        message_type=MessageType.CUSTOMER_DAY_BEFORE,
        requested_at=datetime.now(UTC),
    )
    db_session.add(pending)
    db_session.commit()

    result = MessageService(db_session).send_day_before_notices(target_date=target_date)

    assert result.sent == 0
    assert result.skipped_already_sent == 1
    assert result.failed == 0
    logs = list(
        db_session.scalars(
            select(MessageLog).where(
                MessageLog.order_id == seed_order.id,
                MessageLog.message_type == MessageType.CUSTOMER_DAY_BEFORE,
            )
        )
    )
    assert [(log.id, log.status) for log in logs] == [(pending.id, MessageStatus.PENDING)]
    db_session.refresh(seed_order)
    assert seed_order.status == OrderStatus.SCHEDULED


def test_day_before_marks_stale_solapi_pending_unknown_without_retry(
    db_session: Session,
    seed_order: Order,
) -> None:
    target_date = date(2030, 1, 2)
    seed_order.status = OrderStatus.SCHEDULED
    seed_order.scheduled_date = target_date
    requested_at = datetime.now(UTC) - timedelta(
        minutes=settings.message_pending_retry_after_minutes + 1
    )
    _record_current_partner_confirmation(
        db_session,
        seed_order,
        confirmed_at=requested_at - timedelta(seconds=1),
    )
    pending = _pending_message(
        order_id=seed_order.id,
        message_type=MessageType.CUSTOMER_DAY_BEFORE,
        requested_at=requested_at,
    )
    db_session.add(pending)
    db_session.commit()

    result = MessageService(db_session).send_day_before_notices(target_date=target_date)

    assert result.sent == 0
    assert result.skipped_already_sent == 1
    assert result.failed == 0
    logs = list(
        db_session.scalars(
            select(MessageLog).where(
                MessageLog.order_id == seed_order.id,
                MessageLog.message_type == MessageType.CUSTOMER_DAY_BEFORE,
            )
        )
    )
    assert len(logs) == 1
    db_session.refresh(pending)
    assert pending.status == MessageStatus.PENDING
    assert pending.provider_error_code == "solapi_outcome_unknown"
    db_session.refresh(seed_order)
    assert seed_order.status == OrderStatus.SCHEDULED

    second_result = MessageService(db_session).send_day_before_notices(target_date=target_date)
    assert second_result.sent == 0
    assert second_result.skipped_already_sent == 1
    assert (
        len(
            list(
                db_session.scalars(
                    select(MessageLog).where(
                        MessageLog.order_id == seed_order.id,
                        MessageLog.message_type == MessageType.CUSTOMER_DAY_BEFORE,
                    )
                )
            )
        )
        == 1
    )


def test_day_before_allows_new_visit_day_after_old_success(
    db_session: Session,
    seed_order: Order,
) -> None:
    target_date = date(2030, 1, 2)
    seed_order.status = OrderStatus.SCHEDULED
    seed_order.scheduled_date = target_date
    _record_current_partner_confirmation(db_session, seed_order)
    old_success = _pending_message(
        order_id=seed_order.id,
        message_type=MessageType.CUSTOMER_DAY_BEFORE,
        requested_at=datetime.now(UTC) - timedelta(days=1),
    )
    old_success.status = MessageStatus.SENT
    old_success.sent_at = old_success.requested_at
    db_session.add(old_success)
    db_session.commit()

    result = MessageService(db_session).send_day_before_notices(target_date=target_date)

    assert result.sent == 1
    logs = list(
        db_session.scalars(
            select(MessageLog).where(
                MessageLog.order_id == seed_order.id,
                MessageLog.message_type == MessageType.CUSTOMER_DAY_BEFORE,
            )
        )
    )
    assert len(logs) == 2


@pytest.mark.parametrize("mutation", ["cancel", "reschedule"])
def test_day_before_rechecks_locked_target_before_sending(
    db_session: Session,
    seed_order: Order,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    target_date = date(2030, 1, 2)
    seed_order.status = OrderStatus.SCHEDULED
    seed_order.scheduled_date = target_date
    _record_current_partner_confirmation(db_session, seed_order)
    db_session.commit()
    service = MessageService(db_session)
    original_send_once = service.send_automation_once
    has_mutated = False

    def mutate_before_locked_send(payload, **kwargs):
        nonlocal has_mutated
        if not has_mutated:
            current = db_session.get(Order, seed_order.id)
            assert current is not None
            if mutation == "cancel":
                current.status = OrderStatus.CANCELLED
            else:
                current.scheduled_date = target_date + timedelta(days=1)
            db_session.commit()
            has_mutated = True
        return original_send_once(payload, **kwargs)

    monkeypatch.setattr(service, "send_automation_once", mutate_before_locked_send)
    result = service.send_day_before_notices(target_date=target_date)

    assert result.sent == 0
    assert result.failed == 1
    assert (
        list(
            db_session.scalars(
                select(MessageLog).where(
                    MessageLog.order_id == seed_order.id,
                    MessageLog.message_type == MessageType.CUSTOMER_DAY_BEFORE,
                )
            )
        )
        == []
    )


def test_manual_day_before_rejects_cancelled_order(
    db_session: Session,
    seed_order: Order,
) -> None:
    seed_order.status = OrderStatus.CANCELLED
    seed_order.scheduled_date = date(2030, 1, 2)
    db_session.commit()

    with pytest.raises(ValueError, match="day_before_notice_not_allowed"):
        MessageService(db_session).send(
            MessageSendRequest(
                order_id=seed_order.id,
                message_type=MessageType.CUSTOMER_DAY_BEFORE,
                recipient_type=RecipientType.CUSTOMER,
            )
        )


def test_delivery_failed_day_before_is_recovered_after_cooldown(
    db_session: Session,
    seed_order: Order,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_order.status = OrderStatus.DAY_BEFORE_NOTICE_DONE
    seed_order.scheduled_date = business_today() + timedelta(days=1)
    failed_requested_at = datetime.now(UTC) - timedelta(minutes=20)
    _record_current_partner_confirmation(
        db_session,
        seed_order,
        confirmed_at=failed_requested_at - timedelta(seconds=1),
    )
    failed = _pending_message(
        order_id=seed_order.id,
        message_type=MessageType.CUSTOMER_DAY_BEFORE,
        requested_at=failed_requested_at,
    )
    failed.status = MessageStatus.DELIVERY_FAILED
    failed.provider_error_code = "9999"
    db_session.add(failed)
    db_session.commit()
    service = MessageService(db_session)
    monkeypatch.setattr(
        "app.services.messages.business_now",
        lambda: datetime(2030, 1, 1, 9, 59, tzinfo=UTC),
    )
    early_targets = service._workflow_recovery_targets(seed_order)
    assert MessageType.CUSTOMER_DAY_BEFORE not in {target.message_type for target in early_targets}
    monkeypatch.setattr(
        "app.services.messages.business_now",
        lambda: datetime(2030, 1, 1, 10, 1, tzinfo=UTC),
    )

    result = service.recover_workflow_notifications()

    assert result.attempted == 1
    assert result.sent == 1
    logs = list(
        db_session.scalars(
            select(MessageLog).where(
                MessageLog.order_id == seed_order.id,
                MessageLog.message_type == MessageType.CUSTOMER_DAY_BEFORE,
            )
        )
    )
    assert len(logs) == 2
    assert {log.status for log in logs} == {
        MessageStatus.DELIVERY_FAILED,
        MessageStatus.SENT,
    }


def test_old_day_before_success_does_not_complete_current_backoff_epoch(
    db_session: Session,
    seed_order: Order,
) -> None:
    target_date = date(2030, 1, 2)
    seed_order.status = OrderStatus.SCHEDULED
    seed_order.scheduled_date = target_date
    _record_current_partner_confirmation(db_session, seed_order)
    old_success = _pending_message(
        order_id=seed_order.id,
        message_type=MessageType.CUSTOMER_DAY_BEFORE,
        requested_at=datetime.now(UTC) - timedelta(days=1),
    )
    old_success.status = MessageStatus.SENT
    old_success.sent_at = old_success.requested_at
    recent_failure = _pending_message(
        order_id=seed_order.id,
        message_type=MessageType.CUSTOMER_DAY_BEFORE,
        requested_at=datetime.now(UTC),
    )
    recent_failure.status = MessageStatus.FAILED
    recent_failure.provider_error_code = "provider_failed"
    db_session.add_all([old_success, recent_failure])
    db_session.commit()

    result = MessageService(db_session).send_day_before_notices(target_date=target_date)

    assert result.sent == 0
    assert result.skipped_already_sent == 1
    db_session.refresh(seed_order)
    assert seed_order.status == OrderStatus.SCHEDULED


def test_day_before_epoch_accepts_sqlite_naive_confirmation_timestamp(
    db_session: Session,
    seed_order: Order,
) -> None:
    target_date = date(2030, 1, 2)
    seed_order.status = OrderStatus.SCHEDULED
    seed_order.partner_id = DEV_PARTNER_ID
    seed_order.scheduled_date = target_date
    TimelineService(db_session).record(
        order_id=seed_order.id,
        event_type=TimelineEventType.PARTNER_CONFIRMED,
        title="partner confirmed",
        metadata={"partner_id": DEV_PARTNER_ID},
    )
    db_session.commit()

    result = MessageService(db_session).send_day_before_notices(target_date=target_date)

    assert result.sent == 1
    assert result.failed == 0


def test_customer_schedule_template_hides_auth_suffix_and_private_payment(
    db_session: Session,
    seed_order: Order,
) -> None:
    seed_order.scheduled_date = date(2030, 1, 2)
    seed_order.total_amount = Decimal("300000")
    seed_order.deposit_amount = Decimal("100000")
    seed_order.balance_amount = Decimal("200000")
    seed_order.customer_visible_payment = False
    seed_order.status = OrderStatus.SCHEDULED
    seed_order.partner_id = DEV_PARTNER_ID
    TimelineService(db_session).record(
        order_id=seed_order.id,
        event_type=TimelineEventType.PARTNER_CONFIRMED,
        title="partner confirmed",
        metadata={"partner_id": DEV_PARTNER_ID},
    )
    db_session.commit()

    preview = MessageService(db_session).preview(
        MessageSendRequest(
            order_id=seed_order.id,
            message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
            recipient_type=RecipientType.CUSTOMER,
            channel=MessageChannel.ALIMTALK,
        )
    )

    assert preview.kakao_variables is not None
    assert preview.kakao_variables["#{연락처}"] == "010-****-****"
    for key in ("#{금액}", "#{계약금}", "#{잔금}", "#{총금액}"):
        assert preview.kakao_variables[key] == "-"


@pytest.mark.parametrize(
    "status",
    [OrderStatus.IN_PROGRESS, OrderStatus.COMPLETED],
)
def test_customer_access_link_lms_is_available_across_operational_statuses(
    db_session: Session,
    seed_order: Order,
    status: OrderStatus,
) -> None:
    seed_order.status = status
    db_session.commit()

    log = MessageService(db_session).send(
        MessageSendRequest(
            order_id=seed_order.id,
            message_type=MessageType.CUSTOMER_ACCESS_LINK,
            recipient_type=RecipientType.CUSTOMER,
        )
    )

    assert log.status == MessageStatus.SENT
    assert log.channel == MessageChannel.LMS
    assert "/c#token=" in log.content
    link_events = list(
        db_session.scalars(
            select(OrderTimeline).where(
                OrderTimeline.order_id == seed_order.id,
                OrderTimeline.event_type == TimelineEventType.CUSTOMER_LINK_SENT,
            )
        )
    )
    assert len(link_events) == 1


def test_customer_link_timeline_uses_actual_fallback_channel(
    db_session: Session,
    seed_order: Order,
) -> None:
    class LmsFallbackProvider(MessageProvider):
        provider_name = "lms-fallback-provider"

        def send(self, content: str, recipient_phone: str) -> MessageSendResult:
            return MessageSendResult(
                status=MessageStatus.SENT,
                channel=MessageChannel.LMS,
                provider=self.provider_name,
            )

        def send_with_context(self, send_input: MessageProviderSendInput) -> MessageSendResult:
            assert send_input.channel == MessageChannel.ALIMTALK
            return self.send(send_input.content, send_input.recipient_phone)

    seed_order.status = OrderStatus.SCHEDULED
    seed_order.scheduled_date = date(2030, 1, 2)
    _record_current_partner_confirmation(db_session, seed_order)
    db_session.commit()

    log = MessageService(db_session, provider=LmsFallbackProvider()).send(
        MessageSendRequest(
            order_id=seed_order.id,
            message_type=MessageType.CUSTOMER_SCHEDULE_CONFIRMED,
            recipient_type=RecipientType.CUSTOMER,
            channel=MessageChannel.ALIMTALK,
        )
    )

    link_event = db_session.scalars(
        select(OrderTimeline).where(
            OrderTimeline.order_id == seed_order.id,
            OrderTimeline.event_type == TimelineEventType.CUSTOMER_LINK_SENT,
        )
    ).one()
    assert log.channel == MessageChannel.LMS
    assert link_event.event_metadata is not None
    assert link_event.event_metadata["channel"] == MessageChannel.LMS


def test_balance_send_reloads_paid_order_before_provider_call(
    db_session: Session,
    seed_order: Order,
) -> None:
    seed_order.status = OrderStatus.CUSTOMER_DELIVERY_NEEDED
    seed_order.payment_status = PaymentStatus.BALANCE_PENDING
    seed_order.balance_amount = Decimal("200000")
    db_session.expire_on_commit = False
    db_session.commit()
    assert db_session.get(Order, seed_order.id) is seed_order

    OtherSession = sessionmaker(bind=db_session.get_bind())
    with OtherSession() as other_db:
        other_db.execute(
            update(Order)
            .where(Order.id == seed_order.id)
            .values(payment_status=PaymentStatus.PAID, balance_amount=0)
        )
        other_db.commit()

    with pytest.raises(ValueError, match="customer_balance_not_due"):
        MessageService(db_session).send(
            MessageSendRequest(
                order_id=seed_order.id,
                message_type=MessageType.CUSTOMER_BALANCE_DUE,
                recipient_type=RecipientType.CUSTOMER,
            )
        )


@pytest.mark.parametrize(
    "status",
    [OrderStatus.IN_PROGRESS, OrderStatus.CUSTOMER_CHECK_NEEDED],
)
def test_balance_recovery_requires_post_completion_workflow_status(
    db_session: Session,
    seed_order: Order,
    status: OrderStatus,
) -> None:
    seed_order.status = status
    seed_order.work_completed_at = datetime.now(UTC)
    seed_order.payment_status = PaymentStatus.BALANCE_PENDING
    seed_order.balance_amount = Decimal("200000")
    seed_order.as_requested = False
    seed_order.as_intake_pending = False
    db_session.commit()
    service = MessageService(db_session)

    targets = service._workflow_recovery_targets(seed_order)
    assert MessageType.CUSTOMER_BALANCE_DUE not in {target.message_type for target in targets}
    with pytest.raises(ValueError, match="customer_balance_not_due"):
        service.send(
            MessageSendRequest(
                order_id=seed_order.id,
                message_type=MessageType.CUSTOMER_BALANCE_DUE,
                recipient_type=RecipientType.CUSTOMER,
            )
        )
