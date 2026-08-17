from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from pathlib import Path
from runpy import run_path
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from sqlalchemy import select

from app.core.config import settings
from app.core.time import business_today
from app.db.seed import DEV_PARTNER_ID
from app.domain.constants import (
    MessageChannel,
    MessageStatus,
    MessageType,
    OrderStatus,
    RecipientType,
    TimelineEventType,
)
from app.models.message import MessageLog
from app.models.order_visit import OrderVisit
from app.schemas.message import DayBeforeNoticeRunRead
from app.services.day_before_scheduler import (
    DayBeforeNoticeScheduler,
    day_before_notice_lifespan,
    next_daily_run_at,
)
from app.services.messages import MessageProviderSendInput, MessageService, MockMessageProvider
from app.services.timeline import TimelineService


def _confirm_order(db_session, order) -> None:
    order.partner_id = DEV_PARTNER_ID
    TimelineService(db_session).record(
        order_id=order.id,
        event_type=TimelineEventType.PARTNER_CONFIRMED,
        title="테스트 협력사 확인",
        metadata={"partner_id": DEV_PARTNER_ID},
    )


def _add_prior_day_before_log(db_session, order, target_visit_date: date) -> None:
    attempted_at = datetime.now(ZoneInfo("UTC")) - timedelta(days=1)
    db_session.add(
        MessageLog(
            id=str(uuid4()),
            order_id=order.id,
            recipient_type=RecipientType.CUSTOMER,
            recipient_name=order.customer_name,
            recipient_phone=order.customer_phone,
            recipient_partner_id=None,
            message_type=MessageType.CUSTOMER_DAY_BEFORE,
            target_visit_date=target_visit_date,
            channel=MessageChannel.SMS,
            content=f"prior visit: {target_visit_date.isoformat()}",
            status=MessageStatus.SENT,
            error_message=None,
            provider="mock",
            requested_at=attempted_at,
            sent_at=attempted_at,
        )
    )


class CapturingMessageProvider(MockMessageProvider):
    def __init__(self) -> None:
        self.inputs: list[MessageProviderSendInput] = []

    def send_with_context(self, send_input: MessageProviderSendInput):
        self.inputs.append(send_input)
        return super().send_with_context(send_input)


def test_next_daily_run_at_uses_today_when_before_schedule() -> None:
    timezone = ZoneInfo("Asia/Seoul")
    now = datetime(2026, 7, 6, 9, 59, tzinfo=timezone)

    result = next_daily_run_at(now, hour=10, minute=0)

    assert result == datetime(2026, 7, 6, 10, 0, tzinfo=timezone)


def test_next_daily_run_at_moves_to_tomorrow_after_schedule() -> None:
    timezone = ZoneInfo("Asia/Seoul")
    now = datetime(2026, 7, 6, 10, 1, tzinfo=timezone)

    result = next_daily_run_at(now, hour=10, minute=0)

    assert result == datetime(2026, 7, 7, 10, 0, tzinfo=timezone)


def test_day_before_lifespan_defaults_to_off(monkeypatch) -> None:
    monkeypatch.setattr(settings, "automation_day_before_notice_scheduler_enabled", False)
    app = FastAPI()

    async def exercise() -> None:
        async with day_before_notice_lifespan(app):
            assert not hasattr(app.state, "day_before_notice_scheduler")

    asyncio.run(exercise())


def test_day_before_lifespan_starts_and_stops_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "automation_day_before_notice_scheduler_enabled", True)
    app = FastAPI()
    events = []

    class FakeScheduler:
        def start(self) -> None:
            events.append("start")

        async def stop(self) -> None:
            events.append("stop")

    monkeypatch.setattr(
        "app.services.day_before_scheduler.DayBeforeNoticeScheduler",
        lambda: FakeScheduler(),
    )

    async def exercise() -> None:
        async with day_before_notice_lifespan(app):
            assert hasattr(app.state, "day_before_notice_scheduler")
            assert events == ["start"]

    asyncio.run(exercise())
    assert events == ["start", "stop"]


def test_day_before_scheduler_run_once_closes_session() -> None:
    calls = []

    class FakeSession:
        is_closed = False

        def close(self) -> None:
            self.is_closed = True

    class FakeMessageService:
        def __init__(self, db: FakeSession) -> None:
            self.db = db

        def send_day_before_notices(self) -> DayBeforeNoticeRunRead:
            calls.append(self.db)
            return DayBeforeNoticeRunRead(
                target_date=date(2026, 7, 7),
                scanned=1,
                sent=1,
                skipped_already_sent=0,
                failed=0,
                sent_order_ids=["order-1"],
            )

    db = FakeSession()
    scheduler = DayBeforeNoticeScheduler(
        session_factory=lambda: db,  # type: ignore[arg-type]
        message_service_factory=FakeMessageService,  # type: ignore[arg-type]
    )

    result = scheduler.run_once()

    assert result.sent == 1
    assert calls == [db]
    assert db.is_closed is True


def test_day_before_notice_does_not_regress_scheduled_order(db_session, seed_order) -> None:
    target_date = date(2030, 1, 2)
    seed_order.status = OrderStatus.SCHEDULED
    seed_order.scheduled_date = target_date
    _confirm_order(db_session, seed_order)
    db_session.commit()

    result = MessageService(db_session).send_day_before_notices(target_date=target_date)

    db_session.refresh(seed_order)
    assert result.sent == 1
    assert seed_order.status == OrderStatus.SCHEDULED


def test_day_before_notice_sends_for_later_visit_after_first_notice(
    db_session,
    seed_order,
    monkeypatch,
) -> None:
    first_visit = date(2030, 1, 2)
    later_visit = date(2030, 1, 5)
    seed_order.status = OrderStatus.DAY_BEFORE_NOTICE_DONE
    seed_order.scheduled_date = first_visit
    seed_order.visits = [
        OrderVisit(id=str(uuid4()), order_id=seed_order.id, visit_date=first_visit),
        OrderVisit(id=str(uuid4()), order_id=seed_order.id, visit_date=later_visit),
    ]
    _confirm_order(db_session, seed_order)
    db_session.commit()
    prior_log = MessageLog(
        id=str(uuid4()),
        order_id=seed_order.id,
        recipient_type=RecipientType.CUSTOMER,
        recipient_name=seed_order.customer_name,
        recipient_phone=seed_order.customer_phone,
        recipient_partner_id=None,
        message_type=MessageType.CUSTOMER_DAY_BEFORE,
        target_visit_date=first_visit,
        channel=MessageChannel.SMS,
        content=f"prior visit: {first_visit.isoformat()}",
        status=MessageStatus.SENT,
        error_message=None,
        provider="mock",
        requested_at=datetime.now(ZoneInfo("UTC")),
        sent_at=datetime.now(ZoneInfo("UTC")),
    )
    db_session.add(prior_log)
    db_session.commit()
    monkeypatch.setattr(settings, "message_provider", "solapi")
    monkeypatch.setattr(settings, "solapi_api_key", "test-key")
    monkeypatch.setattr(settings, "solapi_api_secret", "test-secret")
    monkeypatch.setattr(settings, "solapi_sender_number", "01012345678")
    monkeypatch.setattr(settings, "solapi_kakao_pf_id", "test-profile")
    monkeypatch.setattr(
        settings,
        "solapi_kakao_template_customer_day_before",
        "test-day-before-template",
    )
    provider = CapturingMessageProvider()

    result = MessageService(db_session, provider=provider).send_day_before_notices(
        target_date=later_visit
    )

    assert result.scanned == 1
    assert result.sent == 1
    assert result.sent_order_ids == [seed_order.id]
    db_session.refresh(seed_order)
    assert seed_order.status == OrderStatus.DAY_BEFORE_NOTICE_DONE
    log = db_session.scalar(
        select(MessageLog).where(
            MessageLog.order_id == seed_order.id,
            MessageLog.message_type == MessageType.CUSTOMER_DAY_BEFORE,
            MessageLog.target_visit_date == later_visit,
        )
    )
    assert log is not None
    assert later_visit.isoformat() in log.content
    assert first_visit.isoformat() not in log.content
    assert len(provider.inputs) == 1
    assert provider.inputs[0].kakao_variables is not None
    expected_schedule = later_visit.isoformat()
    if seed_order.requested_time:
        expected_schedule = f"{expected_schedule} {seed_order.requested_time}"
    assert provider.inputs[0].kakao_variables["#{방문일정}"] == expected_schedule


def test_day_before_notice_sends_after_first_visit_is_removed(db_session, seed_order) -> None:
    first_visit = date(2030, 1, 2)
    later_visit = date(2030, 1, 5)
    seed_order.status = OrderStatus.DAY_BEFORE_NOTICE_DONE
    seed_order.scheduled_date = later_visit
    seed_order.visits = [
        OrderVisit(id=str(uuid4()), order_id=seed_order.id, visit_date=later_visit),
    ]
    _confirm_order(db_session, seed_order)
    _add_prior_day_before_log(db_session, seed_order, first_visit)
    db_session.commit()

    result = MessageService(db_session).send_day_before_notices(target_date=later_visit)

    assert result.scanned == 1
    assert result.sent == 1
    assert result.sent_order_ids == [seed_order.id]


def test_day_before_notice_sends_after_legacy_null_target_success(
    db_session,
    seed_order,
) -> None:
    first_visit = business_today() - timedelta(days=2)
    later_visit = business_today() + timedelta(days=1)
    attempted_local = datetime.combine(
        first_visit - timedelta(days=1),
        datetime.min.time(),
        tzinfo=ZoneInfo("Asia/Seoul"),
    ).replace(hour=10)
    seed_order.status = OrderStatus.DAY_BEFORE_NOTICE_DONE
    seed_order.scheduled_date = first_visit
    seed_order.visits = [
        OrderVisit(id=str(uuid4()), order_id=seed_order.id, visit_date=first_visit),
        OrderVisit(id=str(uuid4()), order_id=seed_order.id, visit_date=later_visit),
    ]
    _confirm_order(db_session, seed_order)
    db_session.add(
        MessageLog(
            id=str(uuid4()),
            order_id=seed_order.id,
            recipient_type=RecipientType.CUSTOMER,
            recipient_name=seed_order.customer_name,
            recipient_phone=seed_order.customer_phone,
            recipient_partner_id=None,
            message_type=MessageType.CUSTOMER_DAY_BEFORE,
            target_visit_date=None,
            channel=MessageChannel.SMS,
            content=f"legacy visit: {first_visit.isoformat()}",
            status=MessageStatus.SENT,
            error_message=None,
            provider="mock",
            requested_at=attempted_local.astimezone(ZoneInfo("UTC")),
            sent_at=attempted_local.astimezone(ZoneInfo("UTC")),
        )
    )
    db_session.commit()

    result = MessageService(db_session).send_day_before_notices(target_date=later_visit)

    assert result.scanned == 1
    assert result.sent == 1
    assert result.sent_order_ids == [seed_order.id]


def test_migration_backfilled_prior_notice_keeps_rescheduled_visit_eligible(
    db_session, seed_order
) -> None:
    first_visit = business_today() - timedelta(days=2)
    later_visit = business_today() + timedelta(days=1)
    attempted_local = datetime.combine(
        first_visit - timedelta(days=1),
        datetime.min.time(),
        tzinfo=ZoneInfo("Asia/Seoul"),
    ).replace(hour=10)
    seed_order.status = OrderStatus.DAY_BEFORE_NOTICE_DONE
    seed_order.scheduled_date = later_visit
    seed_order.visits = [
        OrderVisit(id=str(uuid4()), order_id=seed_order.id, visit_date=later_visit),
    ]
    _confirm_order(db_session, seed_order)
    legacy_log = MessageLog(
        id=str(uuid4()),
        order_id=seed_order.id,
        recipient_type=RecipientType.CUSTOMER,
        recipient_name=seed_order.customer_name,
        recipient_phone=seed_order.customer_phone,
        recipient_partner_id=None,
        message_type=MessageType.CUSTOMER_DAY_BEFORE,
        target_visit_date=None,
        channel=MessageChannel.SMS,
        content=f"legacy visit: {first_visit.isoformat()}",
        status=MessageStatus.SENT,
        error_message=None,
        provider="mock",
        requested_at=attempted_local.astimezone(ZoneInfo("UTC")),
        sent_at=attempted_local.astimezone(ZoneInfo("UTC")),
    )
    db_session.add(legacy_log)
    db_session.flush()
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "0033_day_before_target_visit_date.py"
    )
    run_path(str(migration_path))["_backfill_day_before_target_dates"](
        db_session.connection()
    )
    db_session.expire(legacy_log, ["target_visit_date"])
    assert legacy_log.target_visit_date == first_visit
    db_session.commit()

    result = MessageService(db_session).send_day_before_notices(target_date=later_visit)

    assert result.scanned == 1
    assert result.sent == 1
    assert result.sent_order_ids == [seed_order.id]


def test_day_before_notice_done_single_visit_without_prior_log_is_not_candidate(
    db_session, seed_order
) -> None:
    target_date = date(2030, 1, 5)
    seed_order.status = OrderStatus.DAY_BEFORE_NOTICE_DONE
    seed_order.scheduled_date = target_date
    seed_order.visits = [
        OrderVisit(id=str(uuid4()), order_id=seed_order.id, visit_date=target_date),
    ]
    _confirm_order(db_session, seed_order)
    db_session.commit()

    result = MessageService(db_session).send_day_before_notices(target_date=target_date)

    assert result.scanned == 0
    assert result.sent == 0


def test_day_before_notice_skips_pending_delivery_attempt(db_session, seed_order) -> None:
    target_date = date(2030, 1, 2)
    seed_order.status = OrderStatus.SCHEDULED
    seed_order.scheduled_date = target_date
    _confirm_order(db_session, seed_order)
    db_session.add(
        MessageLog(
            id=str(uuid4()),
            order_id=seed_order.id,
            recipient_type=RecipientType.CUSTOMER,
            recipient_name=seed_order.customer_name,
            recipient_phone=seed_order.customer_phone,
                recipient_partner_id=None,
                message_type=MessageType.CUSTOMER_DAY_BEFORE,
                target_visit_date=target_date,
                channel=MessageChannel.ALIMTALK,
            content="pending",
            status=MessageStatus.PENDING,
            error_message=None,
            provider="solapi",
            requested_at=datetime.now(ZoneInfo("UTC")),
        )
    )
    db_session.commit()

    result = MessageService(db_session).send_day_before_notices(target_date=target_date)

    assert result.sent == 0
    assert result.skipped_already_sent == 1
    assert result.skipped_order_ids == [seed_order.id]


def test_day_before_notice_skips_legacy_pending_attempt_for_same_target(
    db_session,
    seed_order,
) -> None:
    target_date = business_today() + timedelta(days=1)
    seed_order.status = OrderStatus.SCHEDULED
    seed_order.scheduled_date = target_date
    seed_order.visits = [
        OrderVisit(id=str(uuid4()), order_id=seed_order.id, visit_date=target_date),
    ]
    _confirm_order(db_session, seed_order)
    db_session.add(
        MessageLog(
            id=str(uuid4()),
            order_id=seed_order.id,
            recipient_type=RecipientType.CUSTOMER,
            recipient_name=seed_order.customer_name,
            recipient_phone=seed_order.customer_phone,
            recipient_partner_id=None,
            message_type=MessageType.CUSTOMER_DAY_BEFORE,
            target_visit_date=None,
            channel=MessageChannel.ALIMTALK,
            content="legacy pending",
            status=MessageStatus.PENDING,
            error_message=None,
            provider="solapi",
            requested_at=datetime.now(ZoneInfo("UTC")),
        )
    )
    db_session.commit()

    result = MessageService(db_session).send_day_before_notices(target_date=target_date)

    assert result.sent == 0
    assert result.skipped_already_sent == 1
    assert result.skipped_order_ids == [seed_order.id]


def test_day_before_notice_skips_legacy_sent_only_timestamp_across_midnight(
    db_session,
    seed_order,
) -> None:
    target_date = date(2030, 1, 3)
    timezone = ZoneInfo("Asia/Seoul")
    seed_order.status = OrderStatus.SCHEDULED
    seed_order.scheduled_date = target_date
    seed_order.visits = [
        OrderVisit(id=str(uuid4()), order_id=seed_order.id, visit_date=target_date),
    ]
    _confirm_order(db_session, seed_order)
    db_session.add(
        MessageLog(
            id=str(uuid4()),
            order_id=seed_order.id,
            recipient_type=RecipientType.CUSTOMER,
            recipient_name=seed_order.customer_name,
            recipient_phone=seed_order.customer_phone,
            recipient_partner_id=None,
            message_type=MessageType.CUSTOMER_DAY_BEFORE,
            target_visit_date=None,
            channel=MessageChannel.SMS,
            content="legacy sent",
            status=MessageStatus.SENT,
            error_message=None,
            provider="mock",
            requested_at=None,
            sent_at=datetime(2030, 1, 2, 0, 1, tzinfo=timezone).astimezone(ZoneInfo("UTC")),
            created_at=datetime(2030, 1, 1, 23, 59, tzinfo=timezone).astimezone(
                ZoneInfo("UTC")
            ),
        )
    )
    db_session.commit()

    result = MessageService(db_session).send_day_before_notices(target_date=target_date)

    assert result.sent == 0
    assert result.skipped_already_sent == 1
    assert result.skipped_order_ids == [seed_order.id]
