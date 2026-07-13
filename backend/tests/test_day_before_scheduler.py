from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.seed import DEV_PARTNER_ID
from app.domain.constants import OrderStatus, TimelineEventType
from app.schemas.message import DayBeforeNoticeRunRead
from app.services.day_before_scheduler import (
    DayBeforeNoticeScheduler,
    day_before_notice_lifespan,
    is_day_before_catchup_due,
    next_daily_run_at,
)
from app.services.messages import MessageService
from app.services.timeline import TimelineService


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


def test_day_before_catchup_runs_once_after_scheduled_time() -> None:
    timezone = ZoneInfo("Asia/Seoul")
    now = datetime(2026, 7, 6, 10, 5, tzinfo=timezone)

    assert is_day_before_catchup_due(
        now,
        hour=10,
        minute=0,
        last_run_date=None,
    )
    assert not is_day_before_catchup_due(
        now,
        hour=10,
        minute=0,
        last_run_date=now.date(),
    )
    assert is_day_before_catchup_due(
        datetime(2026, 7, 6, 23, 59, tzinfo=timezone),
        hour=10,
        minute=0,
        last_run_date=None,
    )
    assert not is_day_before_catchup_due(
        datetime(2026, 7, 6, 9, 59, tzinfo=timezone),
        hour=10,
        minute=0,
        last_run_date=None,
    )


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
    calls: list[Session] = []

    class FakeSession(Session):
        is_closed = False

        def close(self) -> None:
            self.is_closed = True

    class FakeMessageService(MessageService):
        def __init__(self, db: Session) -> None:
            super().__init__(db)

        def send_day_before_notices(
            self,
            *,
            target_date: date | None = None,
            actor_user_id: str | None = None,
        ) -> DayBeforeNoticeRunRead:
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
        session_factory=lambda: db,
        message_service_factory=FakeMessageService,
    )

    result = scheduler.run_once()

    assert result.sent == 1
    assert calls == [db]
    assert db.is_closed is True


def test_day_before_scheduler_failure_waits_before_retry(monkeypatch) -> None:
    scheduler = DayBeforeNoticeScheduler()
    run_calls = 0
    wait_timeouts: list[float] = []

    def fail_once() -> DayBeforeNoticeRunRead:
        nonlocal run_calls
        run_calls += 1
        raise RuntimeError("database unavailable")

    async def fake_wait_for(awaitable, *, timeout: float):
        wait_timeouts.append(timeout)
        if len(wait_timeouts) == 1:
            awaitable.close()
            raise TimeoutError
        scheduler._stopped.set()
        return await awaitable

    monkeypatch.setattr(scheduler, "run_once", fail_once)
    monkeypatch.setattr(
        "app.services.day_before_scheduler.is_day_before_catchup_due",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)

    asyncio.run(scheduler._run_loop())

    assert run_calls == 1
    assert len(wait_timeouts) == 2
    assert wait_timeouts[1] >= 60


def test_day_before_scheduler_retries_known_failures_until_success(monkeypatch) -> None:
    scheduler = DayBeforeNoticeScheduler()
    run_calls = 0
    wait_timeouts: list[float] = []

    def run_with_two_failures() -> DayBeforeNoticeRunRead:
        nonlocal run_calls
        run_calls += 1
        is_success = run_calls == 3
        if is_success:
            scheduler._stopped.set()
        return DayBeforeNoticeRunRead(
            target_date=date.today() + timedelta(days=1),
            scanned=1,
            sent=1 if is_success else 0,
            skipped_already_sent=0,
            failed=0 if is_success else 1,
            sent_order_ids=["order-1"] if is_success else [],
            failed_order_ids=[] if is_success else ["order-1"],
        )

    async def fake_wait_for(awaitable, *, timeout: float):
        wait_timeouts.append(timeout)
        awaitable.close()
        raise TimeoutError

    monkeypatch.setattr(scheduler, "run_once", run_with_two_failures)
    monkeypatch.setattr(
        "app.services.day_before_scheduler.is_day_before_catchup_due",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)

    asyncio.run(scheduler._run_loop())

    assert run_calls == 3
    assert len(wait_timeouts) == 3
    assert wait_timeouts[1] >= 60
    assert wait_timeouts[2] >= 60


def test_day_before_scheduler_retries_stale_pending_candidate(monkeypatch) -> None:
    scheduler = DayBeforeNoticeScheduler()
    run_calls = 0

    def run_pending_then_success() -> DayBeforeNoticeRunRead:
        nonlocal run_calls
        run_calls += 1
        is_success = run_calls == 2
        if is_success:
            scheduler._stopped.set()
        return DayBeforeNoticeRunRead(
            target_date=date.today() + timedelta(days=1),
            scanned=1,
            sent=1 if is_success else 0,
            skipped_already_sent=0 if is_success else 1,
            failed=0,
            retryable=0 if is_success else 1,
            sent_order_ids=["order-1"] if is_success else [],
            skipped_order_ids=[] if is_success else ["order-1"],
            retryable_order_ids=[] if is_success else ["order-1"],
        )

    async def fake_wait_for(awaitable, *, timeout: float):
        awaitable.close()
        raise TimeoutError

    monkeypatch.setattr(scheduler, "run_once", run_pending_then_success)
    monkeypatch.setattr(
        "app.services.day_before_scheduler.is_day_before_catchup_due",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)

    asyncio.run(scheduler._run_loop())

    assert run_calls == 2


def test_day_before_notice_does_not_regress_scheduled_order(db_session, seed_order) -> None:
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

    db_session.refresh(seed_order)
    assert result.sent == 1
    assert seed_order.status == OrderStatus.SCHEDULED


def test_day_before_notice_skips_unconfirmed_scheduled_order(db_session, seed_order) -> None:
    target_date = date(2030, 1, 2)
    seed_order.status = OrderStatus.SCHEDULED
    seed_order.partner_id = DEV_PARTNER_ID
    seed_order.scheduled_date = target_date
    db_session.commit()

    result = MessageService(db_session).send_day_before_notices(target_date=target_date)

    assert result.scanned == 1
    assert result.sent == 0
    assert result.skipped_unconfirmed == 1
    assert result.unconfirmed_order_ids == [seed_order.id]
    assert result.failed == 0
