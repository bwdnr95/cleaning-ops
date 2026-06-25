"""주문 목록 화면(관리자)의 필터·정렬·집계 의미를 서버에서 그대로 재현하는 헬퍼.

프론트엔드 OrdersPage.tsx / orderStatus.ts / time.ts 의 로직을 1:1로 옮긴 것이다.
서버 페이지네이션 엔드포인트가 브라우저와 동일한 결과를 내도록 보장한다.
"""

from __future__ import annotations

import re
from datetime import date

from app.models.order import Order

# ---------------------------------------------------------------------------
# 상태 워크플로 매핑 (frontend/src/domain/orderStatus.ts)
# ---------------------------------------------------------------------------

# 13개 원본 상태 → 단순화 상태
SIMPLIFIED_ORDER_STATUS: dict[str, str] = {
    "신규접수": "상담중",
    "상담중": "상담중",
    "협력사확인중": "협력사확인중",
    "일정확정": "작업예정",
    "전날안내필요": "작업예정",
    "전날안내완료": "작업예정",
    "작업예정": "작업예정",
    "작업진행": "작업예정",
    "사진검수대기": "고객전달필요",
    "고객전달필요": "고객전달필요",
    "고객전달완료": "고객전달필요",
    "고객확인필요": "고객확인필요",
    "서비스완료": "서비스완료",
    "취소": "취소",
}

# orderWorkflowStatusValue: 서비스완료지만 최종결제 미완이면 '고객전달필요'로 끌어내린다.
_FINAL_PAYMENT_COMPLETE_STATUSES = ("paid", "complete", "completed")


def is_final_payment_complete(payment_status: str | None) -> bool:
    return (payment_status or "") in _FINAL_PAYMENT_COMPLETE_STATUSES


def simplified_order_status(status: str | None) -> str:
    if not status:
        return ""
    return SIMPLIFIED_ORDER_STATUS.get(status, status)


def order_workflow_status(status: str | None, payment_status: str | None) -> str:
    """프론트 orderWorkflowStatusValue 와 동일. 탭 매칭에 쓰는 표시 상태."""
    simplified = simplified_order_status(status)
    if simplified == "서비스완료" and not is_final_payment_complete(payment_status):
        return "고객전달필요"
    return simplified


# ---------------------------------------------------------------------------
# 상태 탭 정의 (frontend ORDER_STATUS_TAB_OPTIONS / getStatusTabs)
# ---------------------------------------------------------------------------

# (tab key, 매칭에 쓰는 워크플로 상태값)
ORDER_STATUS_TAB_OPTIONS: list[tuple[str, str]] = [
    ("consulting_unassigned", "상담중"),
    ("schedule_partner_checking", "협력사확인중"),
    ("schedule_work_confirmed", "작업예정"),
    ("work_done", "고객전달필요"),
    ("customer_check_needed", "고객확인필요"),
    ("final_payment_complete", "서비스완료"),
    ("cancel", "취소"),
]
ORDER_STATUS_TAB_KEYS = {key for key, _ in ORDER_STATUS_TAB_OPTIONS}
_TAB_STATUS_BY_KEY = dict(ORDER_STATUS_TAB_OPTIONS)


def status_tab_value(tab: str | None) -> str | None:
    """탭 key 에 대응하는 워크플로 상태값. 'all'/미지원 키는 None."""
    if not tab or tab == "all":
        return None
    return _TAB_STATUS_BY_KEY.get(tab)


# ---------------------------------------------------------------------------
# 결제 상태 헬퍼 (frontend paymentStatus.ts)
# ---------------------------------------------------------------------------

# isBalanceIncomplete 와 동일한 집합.
BALANCE_INCOMPLETE_STATUSES = ("pending", "deposit_paid", "balance_pending", "unpaid")


def is_balance_incomplete(payment_status: str | None) -> bool:
    return (payment_status or "") in BALANCE_INCOMPLETE_STATUSES


def has_past_incomplete_balance(order: Order, today: date) -> bool:
    """과거 방문 + 잔금 미완 (frontend hasPastIncompleteBalance)."""
    return bool(
        order.scheduled_date is not None
        and order.scheduled_date < today
        and is_balance_incomplete(order.payment_status)
    )


# ---------------------------------------------------------------------------
# 표시값 포매팅 (검색 매칭에 사용; frontend format.ts / phone.ts)
# ---------------------------------------------------------------------------


def format_quantity(value: str | None) -> str:
    """frontend formatQuantity 와 동일. size_or_quantity 표시값."""
    if value is None:
        return ""
    text = str(value)
    if text.strip() == "":
        return text

    decimal_only = re.match(r"^(\s*)(\d+)\.(\d+)(\s*)$", text)
    if decimal_only:
        return (
            f"{decimal_only.group(1)}"
            f"{_format_decimal_quantity(decimal_only.group(2), decimal_only.group(3))}"
            f"{decimal_only.group(4)}"
        )

    decimal_with_unit = re.match(r"^(\s*)(\d+)\.(\d+)(\s*[^\d.\s].*)$", text, re.UNICODE | re.DOTALL)
    if decimal_with_unit:
        return (
            f"{decimal_with_unit.group(1)}"
            f"{_format_decimal_quantity(decimal_with_unit.group(2), decimal_with_unit.group(3))}"
            f"{decimal_with_unit.group(4)}"
        )

    return text


def _format_decimal_quantity(integer_part: str, decimal_part: str) -> str:
    normalized_integer = re.sub(r"^0+(?=\d)", "", integer_part)
    trimmed_decimal = decimal_part.rstrip("0")
    if not trimmed_decimal:
        return normalized_integer or "0"
    return f"{normalized_integer or '0'}.{trimmed_decimal}"


def digits_only(value: str | None) -> str:
    return re.sub(r"\D", "", str(value or ""))


def format_phone(phone: str | None) -> str:
    """frontend formatPhone 와 동일. 검색 매칭에서 표시 전화번호로 사용."""
    if not phone:
        return "-"
    digits = digits_only(phone)
    if not digits:
        return phone
    if re.fullmatch(r"0+", digits):
        return "-"
    if digits.startswith("02"):
        if len(digits) == 9:
            return f"{digits[:2]}-{digits[2:5]}-{digits[5:]}"
        if len(digits) == 10:
            return f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    if len(digits) == 11:
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    return phone
