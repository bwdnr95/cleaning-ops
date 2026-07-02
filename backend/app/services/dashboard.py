from datetime import date, timedelta

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.core.time import business_today
from app.domain.constants import OrderStatus
from app.domain.order_metrics import (
    REVENUE_STATUSES,
    SCHEDULED_WORKFLOW_STATUSES,
    TODAY_JOBS_EXCLUDED_STATUSES,
)
from app.domain.payment_status import PAYMENT_CHECK_STATUSES
from app.models.message import MessageLog
from app.models.order import Order
from app.models.photo import OrderPhoto
from app.schemas.dashboard import DashboardRecentActivity, DashboardRecentMessage, DashboardRecentPhoto, DashboardSummary

class DashboardService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def summary(self, *, today: date | None = None) -> DashboardSummary:
        current = today or business_today()
        tomorrow = current + timedelta(days=1)
        month_filter = (
            extract("year", Order.scheduled_date) == current.year,
            extract("month", Order.scheduled_date) == current.month,
        )

        return DashboardSummary(
            # 3-2: '오늘 작업 예정'은 확정 이전 상태(상담중/미배정·협력사확인중)를 날짜가 있어도 제외한다.
            # 주문 리스트 'today' 탭과 동일 기준으로 숫자를 일치시킨다.
            today_jobs=self._count(
                Order.scheduled_date == current,
                Order.status.not_in(TODAY_JOBS_EXCLUDED_STATUSES),
            ),
            # 내일 방문 예정 '일정 및 작업 확정'(작업예정 워크플로) 전체 — 주문목록 같은 탭/카운트와 일치.
            tomorrow_notice_targets=self._count(
                Order.scheduled_date == tomorrow,
                Order.status.in_(SCHEDULED_WORKFLOW_STATUSES),
            ),
            partner_pending=self._count(Order.status == OrderStatus.PARTNER_CONFIRMING),
            photo_review_pending=self._count(Order.status == OrderStatus.PHOTO_REVIEW_PENDING),
            customer_delivery_needed=self._count(Order.status == OrderStatus.CUSTOMER_DELIVERY_NEEDED),
            # 결제 확인 필요: 미납 계열 + 취소 제외. 단 '방문일이 미래(오늘 이후)'인 건은
            # 아직 결제를 챙길 시점이 아니라 제외한다(미배정=방문일 없음은 유지).
            # 주문목록 payment_check 탭(order_page._matches_status_tab)과 동일 기준.
            payment_check_needed=self._count(
                Order.payment_status.in_(PAYMENT_CHECK_STATUSES),
                Order.status != OrderStatus.CANCELLED,
                (Order.scheduled_date <= current) | Order.scheduled_date.is_(None),
            ),
            monthly_completed=self._count(Order.status == OrderStatus.COMPLETED, *month_filter),
            # 매출 = 기본가 + 현장추가비(주문목록 '총금액'·리포트 매출과 동일 정의)
            monthly_revenue=self._sum(
                func.coalesce(Order.total_amount, 0) + func.coalesce(Order.onsite_extra_amount, 0),
                Order.status.in_(REVENUE_STATUSES),
                *month_filter,
            ),
        )

    def recent_activity(self, *, limit: int = 5) -> DashboardRecentActivity:
        photo_stmt = (
            select(OrderPhoto, Order)
            .join(Order, Order.id == OrderPhoto.order_id)
            .where(Order.deleted_at.is_(None))
            .order_by(OrderPhoto.created_at.desc(), OrderPhoto.id.desc())
            .limit(limit)
        )
        message_stmt = (
            select(MessageLog, Order)
            .join(Order, Order.id == MessageLog.order_id)
            .where(Order.deleted_at.is_(None))
            .order_by(MessageLog.created_at.desc(), MessageLog.id.desc())
            .limit(limit)
        )

        return DashboardRecentActivity(
            photos=[
                DashboardRecentPhoto(
                    photo_id=photo.id,
                    order_id=order.id,
                    photo_type=photo.photo_type,
                    file_url=photo.file_url,
                    file_name=photo.file_name,
                    is_customer_visible=photo.is_customer_visible,
                    uploaded_at=photo.created_at,
                    service_name=order.service_name,
                    size_or_quantity=order.size_or_quantity,
                    customer_name=order.customer_name,
                    team_name=order.team_name,
                )
                for photo, order in self.db.execute(photo_stmt)
            ],
            messages=[
                DashboardRecentMessage(
                    id=message.id,
                    order_id=order.id,
                    message_type=message.message_type,
                    recipient_type=message.recipient_type,
                    recipient_name=message.recipient_name,
                    recipient_phone=message.recipient_phone,
                    channel=message.channel,
                    status=message.status,
                    sent_at=message.sent_at,
                    created_at=message.created_at,
                    service_name=order.service_name,
                )
                for message, order in self.db.execute(message_stmt)
            ],
        )

    def _count(self, *conditions) -> int:
        stmt = select(func.count()).select_from(Order).where(Order.deleted_at.is_(None), *conditions)
        return int(self.db.scalar(stmt) or 0)

    def _sum(self, column, *conditions) -> float:
        stmt = (
            select(func.coalesce(func.sum(column), 0))
            .select_from(Order)
            .where(Order.deleted_at.is_(None), *conditions)
        )
        return float(self.db.scalar(stmt) or 0)
