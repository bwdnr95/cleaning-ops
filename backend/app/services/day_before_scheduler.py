import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.db.session import SessionLocal
from app.schemas.message import DayBeforeNoticeRunRead
from app.services.messages import MessageService
from app.services.notification_recovery import NotificationRecoveryScheduler

logger = logging.getLogger(__name__)


def next_daily_run_at(now: datetime, *, hour: int, minute: int) -> datetime:
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now <= candidate:
        return candidate
    return candidate + timedelta(days=1)


def is_day_before_catchup_due(
    now: datetime,
    *,
    hour: int,
    minute: int,
    last_run_date: date | None,
) -> bool:
    if last_run_date == now.date():
        return False
    primary = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return now > primary


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
        last_run_date: date | None = None
        while not self._stopped.is_set():
            now = datetime.now(timezone)
            if is_day_before_catchup_due(
                now,
                hour=self.settings.automation_day_before_notice_hour,
                minute=self.settings.automation_day_before_notice_minute,
                last_run_date=last_run_date,
            ):
                run_at = now
            else:
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
                result = await asyncio.to_thread(self.run_once)
                self._log_result(result, run_kind="scheduled")
                last_run_date = datetime.now(timezone).date()
            except Exception:
                logger.exception("day_before_notice_scheduler_failed")
                retry_seconds = max(
                    self.settings.message_pending_retry_after_minutes * 60 + 1,
                    60,
                )
                try:
                    await asyncio.wait_for(self._stopped.wait(), timeout=retry_seconds)
                    return
                except TimeoutError:
                    pass
                continue

            while (result.failed > 0 or result.retryable > 0) and not self._stopped.is_set():
                if datetime.now(timezone).date() != last_run_date:
                    break
                retry_seconds = self.settings.message_pending_retry_after_minutes * 60 + 1
                try:
                    await asyncio.wait_for(self._stopped.wait(), timeout=retry_seconds)
                    break
                except TimeoutError:
                    pass
                try:
                    result = await asyncio.to_thread(self.run_once)
                    self._log_result(result, run_kind="recovery")
                except Exception:
                    logger.exception("day_before_notice_scheduler_recovery_failed")

    def _log_result(self, result: DayBeforeNoticeRunRead, *, run_kind: str) -> None:
        logger.info(
            "day_before_notice_scheduler_completed",
            extra={
                "run_kind": run_kind,
                "target_date": result.target_date.isoformat(),
                "scanned": result.scanned,
                "sent": result.sent,
                "skipped_already_sent": result.skipped_already_sent,
                "skipped_unconfirmed": result.skipped_unconfirmed,
                "failed": result.failed,
                "retryable": result.retryable,
            },
        )

    def run_once(self) -> DayBeforeNoticeRunRead:
        db = self.session_factory()
        try:
            return self.message_service_factory(db).send_day_before_notices()
        finally:
            db.close()


@asynccontextmanager
async def day_before_notice_lifespan(app: FastAPI) -> AsyncIterator[None]:
    scheduler: DayBeforeNoticeScheduler | None = None
    recovery_scheduler: NotificationRecoveryScheduler | None = None
    if settings.automation_day_before_notice_scheduler_enabled:
        scheduler = DayBeforeNoticeScheduler()
        app.state.day_before_notice_scheduler = scheduler
        scheduler.start()
    if settings.automation_notification_recovery_enabled:
        recovery_scheduler = NotificationRecoveryScheduler()
        app.state.notification_recovery_scheduler = recovery_scheduler
        recovery_scheduler.start()
    try:
        yield
    finally:
        if recovery_scheduler is not None:
            await recovery_scheduler.stop()
        if scheduler is not None:
            await scheduler.stop()
