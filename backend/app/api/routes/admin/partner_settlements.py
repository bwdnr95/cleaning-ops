from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_session, require_admin
from app.schemas.partner import (
    PartnerSettlementActionRequest,
    PartnerSettlementActionResult,
    PartnerSettlementListRead,
)
from app.services.partner_settlements import PartnerSettlementService

router = APIRouter()


@router.get("/{partner_id}/settlements", response_model=PartnerSettlementListRead)
def list_partner_settlements(
    partner_id: str,
    status: str = Query(default="unpaid", pattern="^(unpaid|paid|all)$"),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> PartnerSettlementListRead:
    try:
        return PartnerSettlementService(db).list_settlements(
            partner_id=partner_id,
            status=status,
            from_date=from_date,
            to_date=to_date,
        )
    except ValueError as exc:
        raise settlement_http_error(exc) from exc


@router.post("/{partner_id}/settlements/settle", response_model=PartnerSettlementActionResult)
def settle_partner_orders(
    partner_id: str,
    payload: PartnerSettlementActionRequest,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
) -> PartnerSettlementActionResult:
    try:
        result = PartnerSettlementService(db).settle(
            partner_id=partner_id,
            order_ids=payload.order_ids,
            memo=payload.memo,
            actor_user_id=user.id,
        )
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise settlement_http_error(exc) from exc
    except Exception:
        db.rollback()
        raise


@router.post("/{partner_id}/settlements/revert", response_model=PartnerSettlementActionResult)
def revert_partner_orders(
    partner_id: str,
    payload: PartnerSettlementActionRequest,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
) -> PartnerSettlementActionResult:
    try:
        result = PartnerSettlementService(db).revert(
            partner_id=partner_id,
            order_ids=payload.order_ids,
            actor_user_id=user.id,
        )
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise settlement_http_error(exc) from exc
    except Exception:
        db.rollback()
        raise


def settlement_http_error(exc: ValueError) -> HTTPException:
    detail = str(exc)
    if detail in {"partner_not_found", "settlement_order_not_found"}:
        return HTTPException(status_code=404, detail=detail)
    if detail in {
        "invalid_settlement_order",
        "invalid_settlement_action",
        "settlement_order_partner_mismatch",
    }:
        return HTTPException(status_code=422, detail=detail)
    return HTTPException(status_code=400, detail=detail)
