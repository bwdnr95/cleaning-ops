from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    PARTNER = "partner"


class OrderStatus(StrEnum):
    NEW = "신규접수"
    CONSULTING = "상담중"
    PARTNER_CONFIRMING = "협력사확인중"
    SCHEDULE_CONFIRMED = "일정확정"
    DAY_BEFORE_NOTICE_NEEDED = "전날안내필요"
    DAY_BEFORE_NOTICE_DONE = "전날안내완료"
    SCHEDULED = "작업예정"
    IN_PROGRESS = "작업진행"
    PHOTO_REVIEW_PENDING = "사진검수대기"
    CUSTOMER_DELIVERY_NEEDED = "고객전달필요"
    CUSTOMER_DELIVERY_DONE = "고객전달완료"
    # 컴플레인/이슈로 최종결제(미수금)가 막힌 건을 따로 관리하는 상태. 최종결제완료 직전 단계.
    CUSTOMER_CHECK_NEEDED = "고객확인필요"
    COMPLETED = "서비스완료"
    CANCELLED = "취소"


class PhotoType(StrEnum):
    BEFORE = "before"
    AFTER = "after"
    ETC = "etc"


class VatType(StrEnum):
    INCLUDED = "included"
    EXCLUDED = "excluded"


class RecurrenceMode(StrEnum):
    MONTHLY = "monthly"   # 매월 지정일
    WEEKLY = "weekly"     # N주 간격, start_date 요일 기준


class RecurringBillingMode(StrEnum):
    PER_VISIT = "per_visit"  # 회당 금액 × 그달 방문 횟수(월 합산). 월액이 방문 횟수에 따라 변동.
    MONTHLY = "monthly"      # 월 고정 금액(방문 횟수 무관).


class RecurringContractStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"


class RecurringOccurrenceStatus(StrEnum):
    PENDING = "pending"       # 도래했으나 미생성 (승인 대기)
    GENERATED = "generated"   # 승인되어 주문 라인 생성됨
    SKIPPED = "skipped"       # 운영자가 건너뜀


class ReceiptType(StrEnum):
    """증빙자료 유형(1차 선택)."""

    CASH_RECEIPT = "cash_receipt"
    TAX_INVOICE = "tax_invoice"
    CARD_PAYMENT = "card_payment"
    NONE = "none"


class ReceiptStatus(StrEnum):
    """증빙자료 발급 상태(2차 선택). NONE 유형이면 NOT_APPLICABLE."""

    ISSUED = "issued"
    PENDING = "pending"
    NOT_APPLICABLE = "not_applicable"


class MessageType(StrEnum):
    CUSTOMER_SCHEDULE_CONFIRMED = "customer_schedule_confirmed"
    CUSTOMER_DAY_BEFORE = "customer_day_before"
    PARTNER_ASSIGNMENT = "partner_assignment"
    CUSTOMER_PHOTO_READY = "customer_photo_ready"
    CUSTOMER_BALANCE_DUE = "customer_balance_due"
    CUSTOMER_QUOTE = "customer_quote"
    PARTNER_CUSTOMER_INFO = "partner_customer_info"
    PARTNER_AS_REQUEST = "partner_as_request"


class MessageChannel(StrEnum):
    SMS = "sms"
    LMS = "lms"
    ALIMTALK = "alimtalk"


class MessageStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    DELIVERED = "delivered"
    DELIVERY_FAILED = "delivery_failed"


class RecipientType(StrEnum):
    CUSTOMER = "customer"
    PARTNER = "partner"


class TimelineEventType(StrEnum):
    CREATED = "created"
    STATUS_CHANGED = "status_changed"
    PARTNER_ASSIGNED = "partner_assigned"
    MESSAGE_SENT = "message_sent"
    PHOTO_UPLOADED = "photo_uploaded"
    PHOTO_APPROVED = "photo_approved"
    PHOTO_REVOKED = "photo_revoked"
    CUSTOMER_LINK_SENT = "customer_link_sent"
    MEMO_ADDED = "memo_added"
    ORDER_DELETED = "order_deleted"
    PARTNER_SETTLED = "partner_settled"
    PARTNER_SETTLEMENT_REVERTED = "partner_settlement_reverted"
    BROKER_SETTLED = "broker_settled"
    BROKER_SETTLEMENT_REVERTED = "broker_settlement_reverted"
    AS_REQUESTED = "as_requested"
    QUOTE_SENT = "quote_sent"
    PARTNER_UNPAID_NOTICE_SENT = "partner_unpaid_notice_sent"


class AuditEventType(StrEnum):
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    TOKEN_REFRESH = "token_refresh"
    PASSWORD_CHANGE = "password_change"
    ACCESS_DENIED = "access_denied"
    PARTNER_ACCOUNT_CREATED = "partner_account_created"
    PARTNER_PASSWORD_RESET = "partner_password_reset"
    PARTNER_ACCOUNT_ACTIVATED = "partner_account_activated"
    PARTNER_ACCOUNT_DEACTIVATED = "partner_account_deactivated"


class AuditSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


ORDER_STATUSES: tuple[str, ...] = tuple(status.value for status in OrderStatus)
