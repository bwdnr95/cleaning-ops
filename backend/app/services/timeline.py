from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.time import to_utc
from app.domain.constants import TimelineEventType
from app.models.timeline import OrderTimeline
from app.repositories.timeline import TimelineRepository


class TimelineService:
    def __init__(self, db: Session) -> None:
        self.repo = TimelineRepository(db)

    def record(
        self,
        *,
        order_id: str,
        event_type: TimelineEventType,
        title: str,
        actor_user_id: str | None = None,
        description: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> OrderTimeline:
        event = OrderTimeline(
            id=str(uuid4()),
            order_id=order_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            title=title,
            description=description,
            event_metadata=metadata,
            created_at=datetime.now(UTC),
        )
        return self.repo.add(event)

    def latest_created_at(
        self,
        *,
        order_id: str,
        event_type: TimelineEventType,
    ) -> datetime | None:
        return self.repo.latest_created_at(order_id=order_id, event_type=event_type)

    def latest_current_partner_confirmation(
        self,
        *,
        order_id: str,
        partner_id: str | None,
    ) -> datetime | None:
        if not partner_id:
            return None
        confirmed = self.repo.latest_event(
            order_id=order_id,
            event_type=TimelineEventType.PARTNER_CONFIRMED,
        )
        if confirmed is None:
            return None
        metadata = confirmed.event_metadata or {}
        if metadata.get("partner_id") != partner_id:
            return None

        required = self.repo.latest_event(
            order_id=order_id,
            event_type=TimelineEventType.PARTNER_CONFIRMATION_REQUIRED,
        )
        assigned = self.repo.latest_event(
            order_id=order_id,
            event_type=TimelineEventType.PARTNER_ASSIGNED,
        )
        epoch_start = max(
            (to_utc(event.created_at) for event in (required, assigned) if event is not None),
            default=None,
        )
        confirmed_at = to_utc(confirmed.created_at)
        if epoch_start is not None and confirmed_at <= epoch_start:
            return None
        return confirmed_at

    def latest_partner_work_epoch(
        self,
        *,
        order_id: str,
        partner_id: str | None,
        work_completed_at: datetime | None,
        work_is_active: bool,
    ) -> datetime | None:
        as_requested = self.repo.latest_event(
            order_id=order_id,
            event_type=TimelineEventType.AS_REQUESTED,
        )
        assigned = self.repo.latest_event(
            order_id=order_id,
            event_type=TimelineEventType.PARTNER_ASSIGNED,
        )
        confirmed_at = self.latest_current_partner_confirmation(
            order_id=order_id,
            partner_id=partner_id,
        )
        as_requested_at = to_utc(as_requested.created_at) if as_requested is not None else None
        completed_at = to_utc(work_completed_at) if work_completed_at is not None else None
        timestamps = [as_requested_at] if as_requested_at is not None else []
        if assigned is not None:
            assigned_at = to_utc(assigned.created_at)
            assignment_belongs_to_work = (
                work_is_active
                or completed_at is None
                or assigned_at <= completed_at
                or (as_requested_at is not None and as_requested_at > completed_at)
            )
            if assignment_belongs_to_work:
                timestamps.append(assigned_at)
        if confirmed_at is not None:
            timestamps.append(confirmed_at)
        return max(timestamps, default=None)
