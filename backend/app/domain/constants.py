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
    COMPLETED = "서비스완료"
    CANCELLED = "취소"


class PhotoType(StrEnum):
    BEFORE = "before"
    AFTER = "after"
    ETC = "etc"


class MessageType(StrEnum):
    CUSTOMER_SCHEDULE_CONFIRMED = "customer_schedule_confirmed"
    CUSTOMER_DAY_BEFORE = "customer_day_before"
    PARTNER_ASSIGNMENT = "partner_assignment"
    CUSTOMER_PHOTO_READY = "customer_photo_ready"


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
    CUSTOMER_LINK_SENT = "customer_link_sent"
    MEMO_ADDED = "memo_added"


class AuditEventType(StrEnum):
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    TOKEN_REFRESH = "token_refresh"
    PASSWORD_CHANGE = "password_change"
    ACCESS_DENIED = "access_denied"


class AuditSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


ORDER_STATUSES: tuple[str, ...] = tuple(status.value for status in OrderStatus)
