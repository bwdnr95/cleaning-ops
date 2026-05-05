from datetime import date, timedelta

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.domain.constants import OrderStatus
from app.domain.payment_status import PAYMENT_CHECK_STATUSES
from app.models.message import MessageLog
from app.models.order import Order
from app.models.photo import OrderPhoto
from app.schemas.dashboard import DashboardRecentActivity, DashboardRecentMessage, DashboardRecentPhoto, DashboardSummary


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def summary(self, *, today: date | None = None) -> DashboardSummary:
        current = today or date.today()
        tomorrow = current + timedelta(days=1)
        month_filter = (
            extract("year", Order.scheduled_date) == current.year,
            extract("month", Order.scheduled_date) == current.month,
        )

        return DashboardSummary(
            today_jobs=self._count(
                Order.scheduled_date == current,
                Order.status.in_(
                    [
                        OrderStatus.SCHEDULED,
                        OrderStatus.IN_PROGRESS,
                        OrderStatus.PHOTO_REVIEW_PENDING,
                    ]
                ),
            ),
            tomorrow_notice_targets=self._count(
                Order.scheduled_date == tomorrow,
                Order.status.in_([OrderStatus.SCHEDULE_CONFIRMED, OrderStatus.DAY_BEFORE_NOTICE_NEEDED]),
            ),
            partner_pending=self._count(Order.status == OrderStatus.PARTNER_CONFIRMING),
            photo_review_pending=self._count(Order.status == OrderStatus.PHOTO_REVIEW_PENDING),
            customer_delivery_needed=self._count(Order.status == OrderStatus.CUSTOMER_DELIVERY_NEEDED),
            payment_check_needed=self._count(
                Order.payment_status.in_(PAYMENT_CHECK_STATUSES)
            ),
            monthly_completed=self._count(Order.status == OrderStatus.COMPLETED, *month_filter),
            monthly_revenue=self._sum(
                Order.total_amount,
                Order.status.in_([OrderStatus.CUSTOMER_DELIVERY_DONE, OrderStatus.COMPLETED]),
                *month_filter,
            ),
        )

    def recent_activity(self, *, limit: int = 5) -> DashboardRecentActivity:
        photo_stmt = (
            select(OrderPhoto, Order)
            .join(Order, Order.id == OrderPhoto.order_id)
            .order_by(OrderPhoto.created_at.desc(), OrderPhoto.id.desc())
            .limit(limit)
        )
        message_stmt = (
            select(MessageLog, Order)
            .join(Order, Order.id == MessageLog.order_id)
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
        stmt = select(func.count()).select_from(Order).where(*conditions)
        return int(self.db.scalar(stmt) or 0)

    def _sum(self, column, *conditions) -> float:
        stmt = select(func.coalesce(func.sum(column), 0)).select_from(Order).where(*conditions)
        return float(self.db.scalar(stmt) or 0)
