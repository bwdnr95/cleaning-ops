from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from app.core.config import settings


def business_timezone() -> ZoneInfo:
    return ZoneInfo(settings.business_timezone)


def utc_now() -> datetime:
    return datetime.now(UTC)


def to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def to_business_time(value: datetime) -> datetime:
    return to_utc(value).astimezone(business_timezone())


def business_now() -> datetime:
    return to_business_time(utc_now())


def business_today(now: datetime | None = None) -> date:
    return to_business_time(now or utc_now()).date()
