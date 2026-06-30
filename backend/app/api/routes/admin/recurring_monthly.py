from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_session, require_admin
from app.schemas.recurring_monthly import RecurringMonthlyRowRead, SetMonthlyStatusRequest
from app.services.recurring_monthly import RecurringMonthlyService

router = APIRouter()


@router.get("", response_model=list[RecurringMonthlyRowRead])
def list_monthly(
    month: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
):
    return RecurringMonthlyService(db).list_month(month)


@router.post("/set", response_model=RecurringMonthlyRowRead)
def set_monthly(
    payload: SetMonthlyStatusRequest,
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
):
    try:
        return RecurringMonthlyService(db).set_status(
            payload.contract_id, payload.month,
            tax_invoice_issued=payload.tax_invoice_issued, balance_paid=payload.balance_paid,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404 if str(exc).endswith("_not_found") else 400, detail=str(exc)
        ) from exc
