from collections import OrderedDict
from datetime import datetime, timedelta
from hashlib import sha256
from threading import Lock
from typing import TypedDict

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.core.config import settings
from app.core.time import utc_now
from app.domain.phone import phone_suffix_matches
from app.models.order_group import OrderGroup
from app.repositories.order_groups import OrderGroupRepository
from app.repositories.photos import PhotoRepository
from app.schemas.order import CustomerAsRequest, CustomerOrderGroupRead, CustomerVerifyRequest
from app.services.orders import OrderService, to_customer_group_dto

router = APIRouter()


class CustomerVerifyAttempt(TypedDict):
    count: int
    locked_until: datetime | None
    last_seen: datetime


_CUSTOMER_VERIFY_CACHE_LIMIT = 10_000
_customer_verify_attempts: OrderedDict[str, CustomerVerifyAttempt] = OrderedDict()
_customer_verify_lock = Lock()


@router.post("/verify", response_model=CustomerOrderGroupRead)
def verify_customer_order(
    payload: CustomerVerifyRequest,
    customer_token: str | None = Header(default=None, alias="X-Customer-Token"),
    db: Session = Depends(get_session),
) -> CustomerOrderGroupRead:
    group = _require_verified_customer_group(
        _require_customer_token(customer_token),
        phone_suffix=payload.phone_suffix,
        db=db,
    )
    return _customer_group_read(group, db=db)


@router.post("/as-requests", response_model=CustomerOrderGroupRead)
def submit_customer_as_request(
    payload: CustomerAsRequest,
    customer_token: str | None = Header(default=None, alias="X-Customer-Token"),
    db: Session = Depends(get_session),
) -> CustomerOrderGroupRead:
    group = _require_verified_customer_group(
        _require_customer_token(customer_token),
        phone_suffix=payload.phone_suffix,
        db=db,
    )
    try:
        OrderService(db).submit_customer_as_intake(
            payload.order_id,
            group_id=group.id,
            memo=payload.memo,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "order_not_found":
            raise HTTPException(status_code=404, detail=detail) from exc
        if detail in {
            "as_request_already_pending",
            "as_request_already_requested",
            "invalid_as_request_status",
        }:
            raise HTTPException(status_code=409, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc

    return _customer_group_read(group, db=db)


def _require_customer_token(customer_token: str | None) -> str:
    if not customer_token or not customer_token.strip():
        raise HTTPException(status_code=404, detail="order_not_found")
    return customer_token.strip()


def _require_verified_customer_group(
    customer_token: str,
    *,
    phone_suffix: str,
    db: Session,
) -> OrderGroup:
    rate_limit_key = _customer_verify_rate_limit_key(customer_token)
    group = OrderGroupRepository(db).get_by_customer_token(customer_token)
    if group is None:
        raise HTTPException(status_code=404, detail="order_not_found")
    _consume_customer_verify_attempt(rate_limit_key)
    if not phone_suffix_matches(group.customer_phone, phone_suffix):
        raise HTTPException(status_code=404, detail="order_not_found")
    _reset_customer_verify_failures(rate_limit_key)
    return group


def _customer_group_read(group: OrderGroup, *, db: Session) -> CustomerOrderGroupRead:
    group_repo = OrderGroupRepository(db)

    photo_repo = PhotoRepository(db)
    lines_with_photos = [
        (line, photo_repo.list_for_order(line.id, customer_visible_only=True))
        for line in group_repo.list_lines(group.id)
    ]
    return to_customer_group_dto(group, lines_with_photos=lines_with_photos)


def _customer_verify_rate_limit_key(customer_token: str) -> str:
    return sha256(customer_token.encode("utf-8")).hexdigest()


def _consume_customer_verify_attempt(rate_limit_key: str) -> None:
    now = utc_now()
    with _customer_verify_lock:
        _prune_customer_verify_attempts(now)
        attempt = _customer_verify_attempts.get(rate_limit_key)
        if attempt is not None:
            locked_until = attempt["locked_until"]
            if locked_until is not None and now < locked_until:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="customer_verify_locked",
                )
            if locked_until is not None:
                _customer_verify_attempts.pop(rate_limit_key, None)
                attempt = None
        if attempt is None:
            if len(_customer_verify_attempts) >= _CUSTOMER_VERIFY_CACHE_LIMIT:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="customer_verify_limiter_saturated",
                )
            attempt = CustomerVerifyAttempt(
                count=0,
                locked_until=None,
                last_seen=now,
            )
            _customer_verify_attempts[rate_limit_key] = attempt
        attempt["count"] += 1
        attempt["last_seen"] = now
        _customer_verify_attempts.move_to_end(rate_limit_key)
        if attempt["count"] >= settings.customer_verify_max_attempts:
            attempt["locked_until"] = now + timedelta(
                minutes=settings.customer_verify_lockout_minutes
            )


def _reset_customer_verify_failures(rate_limit_key: str) -> None:
    with _customer_verify_lock:
        _customer_verify_attempts.pop(rate_limit_key, None)


def _prune_customer_verify_attempts(now: datetime) -> None:
    stale_before = now - timedelta(
        minutes=max(settings.customer_verify_lockout_minutes * 2, 30)
    )
    stale_keys = [
        key
        for key, attempt in _customer_verify_attempts.items()
        if attempt["last_seen"] < stale_before
        and (attempt["locked_until"] is None or attempt["locked_until"] <= now)
    ]
    for key in stale_keys:
        _customer_verify_attempts.pop(key, None)
