from datetime import date, timedelta

from sqlalchemy import case, extract, func, or_, select
from sqlalchemy.orm import Session

from app.core.time import business_today
from app.domain.constants import OrderStatus
from app.domain.order_metrics import (
    REVENUE_STATUSES,
    SCHEDULED_WORKFLOW_STATUSES,
    WORK_DONE_STATUSES,
)
from app.domain.payment_status import PAYMENT_CHECK_STATUSES, PaymentStatus
from app.models.message import MessageLog
from app.models.order import Order
from app.models.photo import OrderPhoto
from app.schemas.dashboard import (
    DashboardRecentActivity,
    DashboardRecentMessage,
    DashboardRecentPhoto,
    DashboardSummary,
)


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

        # 소비자가(총액) = total_amount + onsite_extra. 계약금/잔금(deposit/balance)은 import·정기 주문에서
        # 비어 있을 수 있어(₩0로 샘) 금액 지표는 항상 채워지는 total 기반으로 계산한다(매출·인사이트와 동일 기준).
        consumer_total = func.coalesce(Order.total_amount, 0) + func.coalesce(Order.onsite_extra_amount, 0)
        # 고객 미수금(미납 잔액): 계약금만 낸(balance_pending) 건은 잔금만, 그 외 미납(pending/unpaid)은 소비자가 전액.
        outstanding_amount = case(
            (
                Order.payment_status == PaymentStatus.BALANCE_PENDING,
                func.coalesce(Order.balance_amount, 0),
            ),
            else_=consumer_total,
        )

        return DashboardSummary(
            # 오늘/내일 '일정 및 작업 확정'(작업예정 워크플로) 방문 — 주문목록 today/tomorrow_notice 탭과 일치.
            today_jobs=self._count(
                Order.scheduled_date == current,
                Order.status.in_(SCHEDULED_WORKFLOW_STATUSES),
            ),
            tomorrow_notice_targets=self._count(
                Order.scheduled_date == tomorrow,
                Order.status.in_(SCHEDULED_WORKFLOW_STATUSES),
            ),
            partner_pending=self._count(Order.status == OrderStatus.PARTNER_CONFIRMING),
            # 미정산 확인 = 작업완료(고객전달필요~서비스완료) 중 고객 미수(미납) 건.
            unpaid_check_needed=self._count(
                Order.status.in_(WORK_DONE_STATUSES),
                Order.payment_status.in_(PAYMENT_CHECK_STATUSES),
            ),
            customer_check_needed=self._count(
                or_(
                    Order.status == OrderStatus.CUSTOMER_CHECK_NEEDED,
                    Order.as_intake_pending.is_(True),
                )
            ),
            # 이번 달 완료 = 당월 방문 + 작업완료 상태.
            monthly_completed=self._count(Order.status.in_(WORK_DONE_STATUSES), *month_filter),
            # 이번 달 계약금액 = 당월 방문건(취소 제외)의 소비자가(총액=계약금+잔금) 합(결제 여부 무관).
            monthly_contract_amount=self._sum(
                consumer_total,
                Order.status != OrderStatus.CANCELLED,
                *month_filter,
            ),
            # 미정산 금액 = '미정산 확인'과 동일 모집단(작업완료 & 고객 미수)의 미수금 합.
            # 미래 예약·상담 리드는 아직 미수금이 아니므로 작업완료(WORK_DONE) 게이트로 제외한다.
            outstanding_receivable=self._sum(
                outstanding_amount,
                Order.status.in_(WORK_DONE_STATUSES),
                Order.payment_status.in_(PAYMENT_CHECK_STATUSES),
            ),
            # --- 레거시 지표(현행 카드엔 미표시, 리스트 드릴다운/리포트 정합용) ---
            photo_review_pending=self._count(Order.status == OrderStatus.PHOTO_REVIEW_PENDING),
            customer_delivery_needed=self._count(Order.status == OrderStatus.CUSTOMER_DELIVERY_NEEDED),
            payment_check_needed=self._count(
                Order.payment_status.in_(PAYMENT_CHECK_STATUSES),
                Order.status != OrderStatus.CANCELLED,
                (Order.scheduled_date <= current) | Order.scheduled_date.is_(None),
            ),
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
        stmt = (
            select(func.count())
            .select_from(Order)
            .where(
                Order.deleted_at.is_(None),
                Order.recurring_contract_id.is_(None),
                *conditions,
            )
        )
        return int(self.db.scalar(stmt) or 0)

    def _sum(self, column, *conditions) -> float:
        stmt = (
            select(func.coalesce(func.sum(column), 0))
            .select_from(Order)
            .where(Order.deleted_at.is_(None), *conditions)
        )
        return float(self.db.scalar(stmt) or 0)
