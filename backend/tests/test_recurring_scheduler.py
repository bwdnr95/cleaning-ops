from __future__ import annotations

import asyncio
from calendar import monthrange
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.time import business_today, utc_now
from app.db.seed import DEV_PARTNER_ID
from app.domain.constants import OrderStatus
from app.domain.recurrence import ScheduleSpec, iter_due_dates
from app.models.order import Order
from app.schemas.recurring import RecurringContractCreate
from app.schemas.order import OrderLineCreate
from app.services.recurring import RecurringService
from app.services.recurring_generation import RecurringOrderGenerationError
from app.services.recurring_scheduler import (
    RecurringOrderScheduler,
    next_recurring_order_run_at,
    recurring_order_lifespan,
)
from app.services.orders import OrderService


def _contract_payload() -> RecurringContractCreate:
    today = business_today()
    return RecurringContractCreate(
        label="자동생성 정기청소",
        customer_name="자동생성 고객",
        customer_phone="01012345678",
        customer_address="서울시 강남구",
        recurrence_mode="weekly",
        interval_weeks=1,
        weekdays=[today.weekday()],
        start_date=date(today.year, today.month, 1),
        default_partner_id=DEV_PARTNER_ID,
        service_name="정기청소",
        total_amount=88000,
    )


def test_next_recurring_order_run_at_uses_today_when_before_schedule() -> None:
    timezone = ZoneInfo("Asia/Seoul")
    now = datetime(2026, 7, 6, 0, 4, tzinfo=timezone)

    result = next_recurring_order_run_at(now, hour=0, minute=5)

    assert result == datetime(2026, 7, 6, 0, 5, tzinfo=timezone)


def test_next_recurring_order_run_at_moves_to_tomorrow_after_schedule() -> None:
    timezone = ZoneInfo("Asia/Seoul")
    now = datetime(2026, 7, 6, 0, 6, tzinfo=timezone)

    result = next_recurring_order_run_at(now, hour=0, minute=5)

    assert result == datetime(2026, 7, 7, 0, 5, tzinfo=timezone)


def test_recurring_lifespan_defaults_to_off_in_tests(monkeypatch) -> None:
    monkeypatch.setattr(settings, "automation_recurring_order_scheduler_enabled", False)
    app = FastAPI()

    async def exercise() -> None:
        async with recurring_order_lifespan(app):
            assert not hasattr(app.state, "recurring_order_scheduler")

    asyncio.run(exercise())


def test_recurring_lifespan_runs_once_then_starts_and_stops_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "automation_recurring_order_scheduler_enabled", True)
    app = FastAPI()
    events: list[str] = []

    class FakeScheduler:
        def run_once_safely(self) -> None:
            events.append("run_once")

        def start(self) -> None:
            events.append("start")

        async def stop(self) -> None:
            events.append("stop")

    monkeypatch.setattr(
        "app.services.recurring_scheduler.RecurringOrderScheduler",
        lambda: FakeScheduler(),
    )

    async def exercise() -> None:
        async with recurring_order_lifespan(app):
            assert hasattr(app.state, "recurring_order_scheduler")
            assert events == ["run_once", "start"]

    asyncio.run(exercise())
    assert events == ["run_once", "start", "stop"]


def test_recurring_scheduler_run_once_closes_session() -> None:
    calls: list[FakeSession] = []

    class FakeSession:
        is_closed = False

        def close(self) -> None:
            self.is_closed = True

    class FakeRecurringService:
        def __init__(self, db: FakeSession) -> None:
            self.db = db

        def generate_current_month_orders(self, *, actor_user_id: str | None) -> int:
            calls.append(self.db)
            assert actor_user_id is None
            return 3

    db = FakeSession()
    scheduler = RecurringOrderScheduler(
        session_factory=lambda: db,
        recurring_service_factory=FakeRecurringService,
    )

    result = scheduler.run_once()

    assert result == 3
    assert calls == [db]
    assert db.is_closed is True


def test_recurring_scheduler_run_once_generates_current_month_orders(db_session: Session) -> None:
    contract = RecurringService(db_session).create_contract(_contract_payload(), actor_user_id=None)

    db_session.execute(delete(Order).where(Order.recurring_contract_id == contract.id))
    db_session.commit()

    TestingSessionLocal = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    scheduler = RecurringOrderScheduler(session_factory=TestingSessionLocal)

    created_count = scheduler.run_once()

    rows = list(
        db_session.scalars(
            select(Order).where(
                Order.deleted_at.is_(None),
                Order.recurring_contract_id == contract.id,
            )
        )
    )
    assert created_count == len(rows)
    assert created_count >= 4
    assert all(row.recurring_planned_date is not None for row in rows)


def test_recurring_scheduler_does_not_duplicate_legacy_current_month_order(
    db_session: Session,
) -> None:
    today = business_today()
    contract = RecurringService(db_session).create_contract(_contract_payload(), actor_user_id=None)
    db_session.execute(delete(Order).where(Order.recurring_contract_id == contract.id))
    db_session.commit()
    month_first = date(today.year, today.month, 1)
    month_last = date(today.year, today.month, monthrange(today.year, today.month)[1])
    due_dates = [
        due
        for _seq, due in iter_due_dates(
            ScheduleSpec(
                mode="weekly",
                start_date=month_first,
                interval_weeks=1,
                weekdays=(today.weekday(),),
            ),
            until=month_last,
        )
        if month_first <= due <= month_last
    ]
    group = RecurringService(db_session).groups.get(contract.order_group_id)
    assert group is not None
    OrderService(db_session).add_recurring_line(
        group,
        OrderLineCreate(
            status=OrderStatus.SCHEDULE_CONFIRMED,
            received_date=today,
            scheduled_date=due_dates[0],
            service_name="구버전 정기청소",
        ),
        recurring_contract_id=contract.id,
        actor_user_id=None,
    )
    db_session.commit()

    TestingSessionLocal = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    scheduler = RecurringOrderScheduler(session_factory=TestingSessionLocal)

    created_count = scheduler.run_once()

    rows = list(
        db_session.scalars(
            select(Order).where(
                Order.deleted_at.is_(None),
                Order.recurring_contract_id == contract.id,
            )
        )
    )
    assert created_count == len(due_dates) - 1
    assert len(rows) == len(due_dates)
    assert sum(1 for row in rows if row.scheduled_date == due_dates[0]) == 1


def test_recurring_scheduler_surfaces_contract_generation_failures(
    db_session: Session,
) -> None:
    contract = RecurringService(db_session).create_contract(_contract_payload(), actor_user_id=None)
    db_session.execute(delete(Order).where(Order.recurring_contract_id == contract.id))
    contract.service_item_id = "missing-service-item"
    db_session.commit()
    TestingSessionLocal = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    scheduler = RecurringOrderScheduler(session_factory=TestingSessionLocal)

    try:
        scheduler.run_once()
    except RecurringOrderGenerationError as exc:
        assert exc.failed_contract_ids == (contract.id,)
    else:
        raise AssertionError("expected recurring generation failure")


def test_recurring_scheduler_surfaces_missing_order_group(
    db_session: Session,
) -> None:
    contract = RecurringService(db_session).create_contract(_contract_payload(), actor_user_id=None)
    db_session.execute(delete(Order).where(Order.recurring_contract_id == contract.id))
    group = RecurringService(db_session).groups.get(contract.order_group_id)
    assert group is not None
    group.deleted_at = utc_now()
    db_session.commit()
    TestingSessionLocal = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    scheduler = RecurringOrderScheduler(session_factory=TestingSessionLocal)

    try:
        scheduler.run_once()
    except RecurringOrderGenerationError as exc:
        assert exc.failed_contract_ids == (contract.id,)
    else:
        raise AssertionError("expected recurring generation failure")
