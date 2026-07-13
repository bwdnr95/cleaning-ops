from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import AsyncIterator
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.db.session import SessionLocal
from app.services.recurring import RecurringService

logger = logging.getLogger(__name__)


def next_recurring_order_run_at(now: datetime, *, hour: int, minute: int) -> datetime:
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now <= candidate:
        return candidate
    return candidate + timedelta(days=1)


class RecurringOrderScheduler:
    def __init__(
        self,
        *,
        app_settings: Settings = settings,
        session_factory: Callable[[], Session] = SessionLocal,
        recurring_service_factory: Callable[[Session], RecurringService] = RecurringService,
    ) -> None:
        self.settings = app_settings
        self.session_factory = session_factory
        self.recurring_service_factory = recurring_service_factory
        self._task: asyncio.Task[None] | None = None
        self._stopped = asyncio.Event()

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stopped.clear()
        self._task = asyncio.create_task(self._run_loop(), name="recurring-order-scheduler")

    async def stop(self) -> None:
        self._stopped.set()
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass

    async def _run_loop(self) -> None:
        timezone = ZoneInfo(self.settings.business_timezone)
        while not self._stopped.is_set():
            now = datetime.now(timezone)
            run_at = next_recurring_order_run_at(
                now,
                hour=self.settings.automation_recurring_order_hour,
                minute=self.settings.automation_recurring_order_minute,
            )
            wait_seconds = max((run_at - now).total_seconds(), 0)
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=wait_seconds)
                continue
            except TimeoutError:
                pass

            self.run_once_safely()

    def run_once(self) -> int:
        db = self.session_factory()
        try:
            return self.recurring_service_factory(db).generate_current_month_orders(actor_user_id=None)
        finally:
            db.close()

    def run_once_safely(self) -> None:
        try:
            created_count = self.run_once()
            logger.info(
                "recurring_order_scheduler_completed",
                extra={"created_count": created_count},
            )
        except Exception:
            logger.exception("recurring_order_scheduler_failed")


@asynccontextmanager
async def recurring_order_lifespan(app: FastAPI) -> AsyncIterator[None]:
    scheduler: RecurringOrderScheduler | None = None
    if settings.automation_recurring_order_scheduler_enabled:
        scheduler = RecurringOrderScheduler()
        app.state.recurring_order_scheduler = scheduler
        scheduler.run_once_safely()
        scheduler.start()
    try:
        yield
    finally:
        if scheduler is not None:
            await scheduler.stop()
