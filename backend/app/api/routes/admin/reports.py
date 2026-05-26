from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_session, require_admin
from app.schemas.report import (
    PartnerPerformanceReport,
    RevenueReport,
    ServicePopularityReport,
    SettlementBacklogReport,
)
from app.services.exporters import to_csv_bytes, to_xlsx_bytes
from app.services.reports import ReportService

router = APIRouter()

_XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


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


@router.get("/revenue/export")
def revenue_export(
    granularity: str = Query("month", pattern="^(day|week|month)$"),
    start_date: date = Query(...),
    end_date: date = Query(...),
    partner_id: str | None = Query(None),
    service_item_id: str | None = Query(None),
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> Response:
    report = ReportService(db).revenue(
        granularity=granularity,
        start_date=start_date,
        end_date=end_date,
        partner_id=partner_id,
        service_item_id=service_item_id,
    )
    rows = [[bucket.period, bucket.completed_count, bucket.revenue] for bucket in report.buckets]
    return _export_response(
        "revenue",
        ["period", "completed_count", "revenue"],
        rows,
        format,
    )


@router.get("/partners", response_model=PartnerPerformanceReport)
def partner_performance(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> PartnerPerformanceReport:
    return ReportService(db).partners(start_date=start_date, end_date=end_date)


@router.get("/partners/export")
def partners_export(
    start_date: date = Query(...),
    end_date: date = Query(...),
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> Response:
    report = ReportService(db).partners(start_date=start_date, end_date=end_date)
    rows = [
        [
            row.partner_id,
            row.partner_name,
            row.job_count,
            row.avg_unit_price,
            row.pending_settlement_count,
            row.expected_settlement_amount,
        ]
        for row in report.rows
    ]
    return _export_response(
        "partners",
        [
            "partner_id",
            "partner_name",
            "job_count",
            "avg_unit_price",
            "pending_settlement_count",
            "expected_settlement_amount",
        ],
        rows,
        format,
    )


@router.get("/services", response_model=ServicePopularityReport)
def service_popularity(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> ServicePopularityReport:
    return ReportService(db).services(start_date=start_date, end_date=end_date)


@router.get("/services/export")
def services_export(
    start_date: date = Query(...),
    end_date: date = Query(...),
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> Response:
    report = ReportService(db).services(start_date=start_date, end_date=end_date)
    rows = [
        [
            row.service_item_id,
            row.service_name,
            row.job_count,
            row.revenue,
            round(row.revenue_share_pct, 2),
        ]
        for row in report.rows
    ]
    return _export_response(
        "services",
        ["service_item_id", "service_name", "job_count", "revenue", "revenue_share_pct"],
        rows,
        format,
    )


@router.get("/settlements", response_model=SettlementBacklogReport)
def settlement_backlog(
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> SettlementBacklogReport:
    return ReportService(db).settlements()


@router.get("/settlements/export")
def settlements_export(
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> Response:
    report = ReportService(db).settlements()
    rows = [
        [
            row.order_id,
            row.scheduled_date,
            row.service_name,
            row.partner_id,
            row.partner_name,
            row.total_amount,
            row.expected_settlement_amount,
            row.status,
        ]
        for row in report.rows
    ]
    return _export_response(
        "settlements",
        [
            "order_id",
            "scheduled_date",
            "service_name",
            "partner_id",
            "partner_name",
            "total_amount",
            "expected_settlement_amount",
            "status",
        ],
        rows,
        format,
    )


def _export_response(name: str, headers: list[str], rows: list[list], format: str) -> Response:
    if format == "csv":
        body = to_csv_bytes(headers, rows)
        media_type = "text/csv; charset=utf-8"
        filename = f"{name}.csv"
    elif format == "xlsx":
        body = to_xlsx_bytes(headers, rows, sheet_name=name)
        media_type = _XLSX_MEDIA
        filename = f"{name}.xlsx"
    else:
        raise HTTPException(status_code=400, detail="unsupported_format")

    return Response(
        content=body,
        media_type=media_type,
        headers={"content-disposition": f'attachment; filename="{filename}"'},
    )
