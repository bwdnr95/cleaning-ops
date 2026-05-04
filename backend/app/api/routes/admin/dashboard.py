from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_session, require_admin
from app.schemas.dashboard import DashboardRecentActivity, DashboardSummary
from app.services.dashboard import DashboardService

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> DashboardSummary:
    return DashboardService(db).summary()


@router.get("/recent-activity", response_model=DashboardRecentActivity)
def dashboard_recent_activity(
    db: Session = Depends(get_session),
    _: CurrentUser = Depends(require_admin),
) -> DashboardRecentActivity:
    return DashboardService(db).recent_activity()
