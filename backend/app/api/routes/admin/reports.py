from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_session, require_admin
from app.schemas.report import (
    PartnerPerformanceReport,
    RevenueReport,
    ServicePopularityReport,
    SettlementBacklogReport,
)
from app.services.reports import ReportService

router = APIRouter()


@router.get("/revenue", response_model=RevenueReport)
def revenue_report(
    granularity: str = Query("month", pattern="^(day|week|month)$"),
    start_date: date = Query(...),
    end_date: date = Query(...),
    partner_id: str | None = Query(None),
    service_item_id: str | None = Query(None),
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> RevenueReport:
    try:
        return ReportService(db).revenue(
            granularity=granularity,
            start_date=start_date,
            end_date=end_date,
            partner_id=partner_id,
            service_item_id=service_item_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/partners", response_model=PartnerPerformanceReport)
def partner_performance(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> PartnerPerformanceReport:
    return ReportService(db).partners(start_date=start_date, end_date=end_date)


@router.get("/services", response_model=ServicePopularityReport)
def service_popularity(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> ServicePopularityReport:
    return ReportService(db).services(start_date=start_date, end_date=end_date)


@router.get("/settlements", response_model=SettlementBacklogReport)
def settlement_backlog(
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> SettlementBacklogReport:
    return ReportService(db).settlements()
