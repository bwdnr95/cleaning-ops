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
from app.schemas.message import DayBeforeNoticeRunRead
from app.services.messages import MessageService

logger = logging.getLogger(__name__)


def next_daily_run_at(now: datetime, *, hour: int, minute: int) -> datetime:
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now <= candidate:
        return candidate
    return candidate + timedelta(days=1)


class DayBeforeNoticeScheduler:
    def __init__(
        self,
        *,
        app_settings: Settings = settings,
        session_factory: Callable[[], Session] = SessionLocal,
        message_service_factory: Callable[[Session], MessageService] = MessageService,
    ) -> None:
        self.settings = app_settings
        self.session_factory = session_factory
        self.message_service_factory = message_service_factory
        self._task: asyncio.Task[None] | None = None
        self._stopped = asyncio.Event()

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stopped.clear()
        self._task = asyncio.create_task(self._run_loop(), name="day-before-notice-scheduler")

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
            run_at = next_daily_run_at(
                now,
                hour=self.settings.automation_day_before_notice_hour,
                minute=self.settings.automation_day_before_notice_minute,
            )
            wait_seconds = max((run_at - now).total_seconds(), 0)
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=wait_seconds)
                continue
            except TimeoutError:
                pass

            try:
                result = self.run_once()
                logger.info(
                    "day_before_notice_scheduler_completed",
                    extra={
                        "target_date": result.target_date.isoformat(),
                        "scanned": result.scanned,
                        "sent": result.sent,
                        "skipped_already_sent": result.skipped_already_sent,
                        "failed": result.failed,
                    },
                )
            except Exception:
                logger.exception("day_before_notice_scheduler_failed")

    def run_once(self) -> DayBeforeNoticeRunRead:
        db = self.session_factory()
        try:
            return self.message_service_factory(db).send_day_before_notices()
        finally:
            db.close()


@asynccontextmanager
async def day_before_notice_lifespan(app: FastAPI) -> AsyncIterator[None]:
    scheduler: DayBeforeNoticeScheduler | None = None
    if settings.automation_day_before_notice_scheduler_enabled:
        scheduler = DayBeforeNoticeScheduler()
        app.state.day_before_notice_scheduler = scheduler
        scheduler.start()
    try:
        yield
    finally:
        if scheduler is not None:
            await scheduler.stop()
