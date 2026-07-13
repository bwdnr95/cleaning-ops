import asyncio
import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.db.session import SessionLocal
from app.services.messages import MessageService, NotificationRecoveryRunResult

logger = logging.getLogger(__name__)


class NotificationRecoveryScheduler:
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
        self._task = asyncio.create_task(
            self._run_loop(),
            name="notification-recovery-scheduler",
        )

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
        while not self._stopped.is_set():
            try:
                result = await asyncio.to_thread(self.run_once)
                self._log_result(result)
            except Exception:
                logger.exception("notification_recovery_scheduler_failed")

            try:
                await asyncio.wait_for(
                    self._stopped.wait(),
                    timeout=self.settings.automation_notification_recovery_interval_seconds,
                )
            except TimeoutError:
                pass

    def run_once(self) -> NotificationRecoveryRunResult:
        db = self.session_factory()
        try:
            return self.message_service_factory(db).recover_workflow_notifications()
        finally:
            db.close()

    def _log_result(self, result: NotificationRecoveryRunResult) -> None:
        logger.info(
            "notification_recovery_scheduler_completed",
            extra={
                "scanned_orders": result.scanned_orders,
                "attempted": result.attempted,
                "sent": result.sent,
                "skipped": result.skipped,
                "failed": result.failed,
            },
        )
