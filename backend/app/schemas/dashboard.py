from datetime import datetime

from app.domain.constants import MessageChannel, MessageStatus, MessageType, PhotoType, RecipientType
from app.schemas.common import ApiModel


class DashboardSummary(ApiModel):
    # --- 현행 대시보드 카드(고객사 260702 재정의) ---
    today_jobs: int                  # 오늘 작업 예정 = 오늘 방문 + '일정 및 작업 확정' 상태
    tomorrow_notice_targets: int     # 내일 안내 대상 = 내일 방문 + '일정 및 작업 확정' 상태
    partner_pending: int             # 협력사 확인 필요 = 협력사확인중
    unpaid_check_needed: int         # 미정산 확인 = 작업완료 & 고객 미수
    customer_check_needed: int       # 고객 확인 필요 = 고객확인필요 상태
    monthly_completed: int           # 이번 달 완료 = 당월 작업완료(고객전달필요~서비스완료)
    monthly_contract_amount: float   # 이번 달 계약금액 = 당월 방문건 계약금+잔금 합(취소 제외)
    outstanding_receivable: float    # 미정산 금액 = 고객 미수금(미납 잔액 누적 합)
    # --- 레거시 지표(현행 카드엔 미표시. 리스트 드릴다운 탭/리포트 정합용으로 유지) ---
    photo_review_pending: int        # 사진검수대기
    customer_delivery_needed: int    # 고객전달필요
    payment_check_needed: int        # 결제 확인 필요(미납 + 방문일 도래)
    monthly_revenue: float           # 당월 매출(전달완료/서비스완료 소비자가 합)


class DashboardRecentPhoto(ApiModel):
    photo_id: str
    order_id: str
    photo_type: PhotoType
    file_url: str
    file_name: str | None = None
    is_customer_visible: bool
    uploaded_at: datetime | None = None
    service_name: str
    size_or_quantity: str | None = None
    customer_name: str
    team_name: str | None = None


class DashboardRecentMessage(ApiModel):
    id: str
    order_id: str
    message_type: MessageType
    recipient_type: RecipientType
    recipient_name: str
    recipient_phone: str
    channel: MessageChannel
    status: MessageStatus
    sent_at: datetime | None = None
    created_at: datetime | None = None
    service_name: str


class DashboardRecentActivity(ApiModel):
    photos: list[DashboardRecentPhoto]
    messages: list[DashboardRecentMessage]
