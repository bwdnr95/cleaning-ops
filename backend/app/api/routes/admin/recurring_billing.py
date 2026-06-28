from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_session, require_admin
from app.schemas.recurring_billing import (
    MarkPaidRequest,
    MarkPaidResult,
    RecurringBillingRowRead,
    SettleMonthRequest,
    SettleMonthResult,
)
from app.services.exporters import to_csv_bytes
from app.services.recurring_billing import RecurringBillingService

router = APIRouter()


@router.get("", response_model=list[RecurringBillingRowRead])
def billing_summary(
    month: str, db: Session = Depends(get_session), _: CurrentUser = Depends(require_admin)
):
    return RecurringBillingService(db).month_summary(month)


@router.post("/mark-paid", response_model=MarkPaidResult)
def mark_paid(
    payload: MarkPaidRequest,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
):
    return RecurringBillingService(db).mark_month_paid(
        payload.contract_id, payload.month, actor_user_id=user.id
    )


@router.post("/settle", response_model=SettleMonthResult)
def settle(
    payload: SettleMonthRequest,
    db: Session = Depends(get_session),
    user: CurrentUser = Depends(require_admin),
):
    return RecurringBillingService(db).settle_month(
        payload.contract_id, payload.month, partner_id=payload.partner_id, actor_user_id=user.id
    )


@router.get("/export")
def export_csv(
    month: str,
    contract_id: str | None = None,
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
):
    table = RecurringBillingService(db).export_table(month, contract_id)
    # 기존 주문/리포트 export 와 동일한 직렬화(utf-8-sig BOM)를 사용한다.
    body = to_csv_bytes(table.headers, table.rows)
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"content-disposition": f'attachment; filename="recurring-billing-{month}.csv"'},
    )
