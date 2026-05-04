from calendar import monthrange
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_session, require_admin
from app.repositories.orders import OrderRepository
from app.schemas.order import AdminCalendarOrderRead

router = APIRouter()


@router.get("", response_model=list[AdminCalendarOrderRead])
def list_calendar_orders(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    partner_id: str | None = None,
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> list[AdminCalendarOrderRead]:
    last_day = monthrange(year, month)[1]
    start_date = date(year, month, 1)
    end_date = date(year, month, last_day)
    return [
        AdminCalendarOrderRead.model_validate(order)
        for order in OrderRepository(db).list_scheduled_between(
            start_date,
            end_date,
            partner_id=partner_id,
        )
    ]
