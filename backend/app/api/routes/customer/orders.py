from collections import defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.core.config import settings
from app.core.time import utc_now
from app.domain.phone import phone_suffix_matches
from app.repositories.orders import OrderRepository
from app.repositories.photos import PhotoRepository
from app.schemas.order import CustomerOrderRead, CustomerVerifyRequest
from app.services.orders import to_customer_order_dto

router = APIRouter()

_customer_verify_attempts: dict[str, dict] = defaultdict(lambda: {"count": 0, "locked_until": None})


@router.post("/{customer_token}/verify", response_model=CustomerOrderRead)
def verify_customer_order(
    customer_token: str,
    payload: CustomerVerifyRequest,
    request: Request,
    db: Session = Depends(get_session),
) -> CustomerOrderRead:
    rate_limit_key = _customer_verify_rate_limit_key(customer_token, request)
    _check_customer_verify_lockout(rate_limit_key)

    order = OrderRepository(db).get_by_customer_token(customer_token)
    if order is None or not phone_suffix_matches(order.customer_phone, payload.phone_suffix):
        _record_customer_verify_failure(rate_limit_key)
        raise HTTPException(status_code=404, detail="order_not_found")
    _reset_customer_verify_failures(rate_limit_key)

    photos = PhotoRepository(db).list_for_order(order.id, customer_visible_only=True)
    return to_customer_order_dto(order, photos=photos)


def _customer_verify_rate_limit_key(customer_token: str, request: Request) -> str:
    return f"{customer_token}:{_client_ip(request) or 'unknown'}"


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else None


def _check_customer_verify_lockout(rate_limit_key: str) -> None:
    attempt = _customer_verify_attempts.get(rate_limit_key)
    if not attempt or not attempt["locked_until"]:
        return
    if utc_now() < attempt["locked_until"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="customer_verify_locked",
        )
    _customer_verify_attempts[rate_limit_key] = {"count": 0, "locked_until": None}


def _record_customer_verify_failure(rate_limit_key: str) -> None:
    attempt = _customer_verify_attempts[rate_limit_key]
    attempt["count"] += 1
    if attempt["count"] >= settings.customer_verify_max_attempts:
        attempt["locked_until"] = utc_now() + timedelta(
            minutes=settings.customer_verify_lockout_minutes
        )


def _reset_customer_verify_failures(rate_limit_key: str) -> None:
    _customer_verify_attempts.pop(rate_limit_key, None)
