from enum import StrEnum


class PaymentStatus(StrEnum):
    PENDING = "pending"
    DEPOSIT_PAID = "deposit_paid"
    BALANCE_PENDING = "balance_pending"
    PAID = "paid"
    UNPAID = "unpaid"
    REFUNDED = "refunded"


class PartnerPaymentStatus(StrEnum):
    UNPAID = "unpaid"
    READY = "ready"
    PAID = "paid"
    HOLD = "hold"


PAYMENT_CHECK_STATUSES: tuple[str, ...] = (
    PaymentStatus.PENDING,
    PaymentStatus.BALANCE_PENDING,
    PaymentStatus.UNPAID,
)

PAYMENT_DONE_STATUSES: tuple[str, ...] = (
    PaymentStatus.DEPOSIT_PAID,
    PaymentStatus.PAID,
)

PARTNER_SETTLEMENT_PENDING_STATUSES: tuple[str, ...] = (
    PartnerPaymentStatus.UNPAID,
    PartnerPaymentStatus.READY,
)

PAYMENT_TRACKED_FIELDS: tuple[str, ...] = (
    "total_amount",
    "discount_amount",
    "deposit_amount",
    "balance_amount",
    "onsite_extra_amount",
    "payment_status",
    "payment_memo",
    "evidence_memo",
    "receipt_type",
    "receipt_status",
    "partner_payment_amount",
    "partner_payment_status",
    "partner_settled_at",
    "broker_payment_amount",
    "broker_payment_status",
    "broker_settled_at",
    "customer_visible_payment",
)


def is_payment_check_needed(payment_status: str | None) -> bool:
    return payment_status in PAYMENT_CHECK_STATUSES
