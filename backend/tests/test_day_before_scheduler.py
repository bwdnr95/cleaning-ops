from __future__ import annotations

import asyncio
from datetime import date, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import FastAPI

from app.core.config import settings
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
from app.schemas.message import DayBeforeNoticeRunRead
from app.services.day_before_scheduler import (
    DayBeforeNoticeScheduler,
    day_before_notice_lifespan,
    next_daily_run_at,
)
from app.services.messages import MessageService
from app.services.timeline import TimelineService


def _confirm_order(db_session, order) -> None:
    order.partner_id = DEV_PARTNER_ID
    TimelineService(db_session).record(
        order_id=order.id,
        event_type=TimelineEventType.PARTNER_CONFIRMED,
        title="테스트 협력사 확인",
        metadata={"partner_id": DEV_PARTNER_ID},
    )


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
