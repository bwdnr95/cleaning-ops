from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_session, require_admin
from app.schemas.broker import (
    BrokerAdminRead,
    BrokerCreate,
    BrokerDetailRead,
    BrokerUpdate,
)
from app.services.brokers import BrokerService

router = APIRouter()


@router.get("", response_model=list[BrokerAdminRead])
def list_brokers(
    include_inactive: bool = False,
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> list:
    return BrokerService(db).list_brokers(include_inactive=include_inactive)


@router.post("", response_model=BrokerDetailRead, status_code=201)
def create_broker(
    payload: BrokerCreate,
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> BrokerDetailRead:
    try:
        return BrokerService(db).create(payload)
    except ValueError as exc:
        raise broker_http_error(exc) from exc


@router.get("/{broker_id}", response_model=BrokerDetailRead)
def get_broker(
    broker_id: str,
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> BrokerDetailRead:
    try:
        return BrokerService(db).get_detail(broker_id)
    except ValueError as exc:
        raise broker_http_error(exc) from exc


@router.patch("/{broker_id}", response_model=BrokerDetailRead)
def update_broker(
    broker_id: str,
    payload: BrokerUpdate,
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> BrokerDetailRead:
    try:
        return BrokerService(db).update(broker_id, payload)
    except ValueError as exc:
        raise broker_http_error(exc) from exc


@router.delete("/{broker_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_broker(
    broker_id: str,
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> Response:
    try:
        BrokerService(db).delete(broker_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ValueError as exc:
        raise broker_http_error(exc) from exc


def broker_http_error(exc: ValueError) -> HTTPException:
    detail = str(exc)
    status_code = 404 if detail.endswith("_not_found") else 400
    return HTTPException(status_code=status_code, detail=detail)
