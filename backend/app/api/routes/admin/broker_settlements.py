from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_session, require_admin
from app.schemas.broker import (
    BrokerSettlementActionRequest,
    BrokerSettlementActionResult,
    BrokerSettlementListRead,
)
from app.services.broker_settlements import BrokerSettlementService

router = APIRouter()


@router.get("/{broker_id}/settlements", response_model=BrokerSettlementListRead)
def list_broker_settlements(
    broker_id: str,
    status: str = Query(default="unpaid", pattern="^(unpaid|paid|all)$"),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> BrokerSettlementListRead:
    try:
        return BrokerSettlementService(db).list_settlements(
            broker_id=broker_id, status=status, from_date=from_date, to_date=to_date
        )
    except ValueError as exc:
        raise broker_settlement_http_error(exc) from exc


@router.post("/{broker_id}/settlements/settle", response_model=BrokerSettlementActionResult)
def settle_broker_orders(
    broker_id: str,
    payload: BrokerSettlementActionRequest,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
) -> BrokerSettlementActionResult:
    try:
        result = BrokerSettlementService(db).settle(
            broker_id=broker_id,
            order_ids=payload.order_ids,
            memo=payload.memo,
            actor_user_id=user.id,
        )
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise broker_settlement_http_error(exc) from exc
    except Exception:
        db.rollback()
        raise


@router.post("/{broker_id}/settlements/revert", response_model=BrokerSettlementActionResult)
def revert_broker_orders(
    broker_id: str,
    payload: BrokerSettlementActionRequest,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
) -> BrokerSettlementActionResult:
    try:
        result = BrokerSettlementService(db).revert(
            broker_id=broker_id,
            order_ids=payload.order_ids,
            actor_user_id=user.id,
        )
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise broker_settlement_http_error(exc) from exc
    except Exception:
        db.rollback()
        raise


def broker_settlement_http_error(exc: ValueError) -> HTTPException:
    detail = str(exc)
    if detail in {"broker_not_found", "settlement_order_not_found"}:
        return HTTPException(status_code=404, detail=detail)
    if detail in {
        "invalid_settlement_order",
        "invalid_settlement_action",
        "settlement_order_broker_mismatch",
    }:
        return HTTPException(status_code=422, detail=detail)
    return HTTPException(status_code=400, detail=detail)
