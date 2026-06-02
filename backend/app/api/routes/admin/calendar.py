from calendar import monthrange
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_session, require_admin
from app.repositories.order_groups import OrderGroupRepository
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
    group_repo = OrderGroupRepository(db)
    rows: list[AdminCalendarOrderRead] = []
    for order in OrderRepository(db).list_scheduled_between(
        start_date,
        end_date,
        partner_id=partner_id,
    ):
        group = group_repo.get(order.group_id) if order.group_id else None
        rows.append(
            AdminCalendarOrderRead(
                id=order.id,
                status=order.status,
                scheduled_date=order.scheduled_date,
                requested_time=order.requested_time,
                partner_id=order.partner_id,
                team_name=order.team_name,
                service_name=order.service_name,
                size_or_quantity=order.size_or_quantity,
                customer_name=(group.customer_name if group else order.customer_name) or "",
                customer_phone=(group.customer_phone if group else order.customer_phone),
                customer_address=(group.customer_address if group else order.customer_address) or "",
                customer_address_detail=group.customer_address_detail if group else None,
            )
        )
    return rows
