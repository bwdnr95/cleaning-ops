"""관리자 주문 목록 서버 페이지네이션 서비스.

브라우저가 하던 필터/정렬/탭 카운트/집계를 서버에서 동일하게 수행하고,
요청한 페이지만 직렬화한다. 정렬은 DB가 아니라 기존 파이썬 정렬 헬퍼를 재사용한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import business_today
from app.domain.constants import OrderStatus
from app.domain.order_list import (
    ORDER_STATUS_TAB_OPTIONS,
    digits_only,
    format_phone,
    format_quantity,
    has_past_incomplete_balance,
    order_workflow_status,
    status_tab_value,
)
from app.domain.order_metrics import (
    REVENUE_STATUSES,
    SCHEDULED_WORKFLOW_STATUSES,
    WORK_DONE_STATUSES,
)
from app.domain.payment_status import PAYMENT_CHECK_STATUSES, PaymentStatus
from app.models.order import Order
from app.models.order_group import OrderGroup
from app.repositories.order_groups import OrderGroupRepository
from app.repositories.orders import (
    order_received_sort_key,
    order_visit_sort_key,
)
from app.schemas.order import AdminOrderRead
from app.services.orders import is_customer_as_intake_pending, to_admin_order_dto


@dataclass
class OrderPageSummary:
    count: int = 0
    consumer_total: float = 0.0
    partner_total: float = 0.0
    profit: float = 0.0
    outstanding_total: float = 0.0


@dataclass
class OrderPageInsight:
    """상단 인사이트(전역 집계, 필터와 무관하게 전체 비삭제 주문 기준)."""

    today_jobs: int = 0
    unassigned: int = 0
    schedule_confirmed: int = 0
    work_done: int = 0
    unpaid_total: float = 0.0
    month_total: float = 0.0


@dataclass
class OrderPageResult:
    items: list[AdminOrderRead]
    total: int
    status_counts: dict[str, int]
    summary: OrderPageSummary = field(default_factory=OrderPageSummary)
    insight: OrderPageInsight = field(default_factory=OrderPageInsight)


# 결제확인 상태 집합은 domain/payment_status(단일 출처)를 사용한다.
_PAYMENT_CHECK_STATUSES = PAYMENT_CHECK_STATUSES

# 완료/정산 중심 탭에서만 '오늘부터' 프리셋에서도 과거 완납을 노출한다.
# 기본 진입 탭인 'all'은 '오늘부터'의 의미(미래 중심)를 지키도록 과거 완납을 숨기고,
# 과거 완납은 검색 또는 '전체' 방문일 프리셋으로 조회한다.
_PAST_PAID_VISIBLE_TABS = frozenset(
    {
        "work_done",
        "customer_check_needed",
        "final_payment_complete",
        "done",
        "monthly_done",
        "monthly_revenue",
    }
)


# 방문일 프리셋에서 start/end 를 산출할 때 쓰는 키 집합. 'upcoming'/'all' 은 별도 처리.
_BOUNDED_VISIT_PRESETS = {"today", "tomorrow", "week", "month"}


def _to_float(value) -> float:
    if value is None:
        return 0.0
    return float(value)


def _order_outstanding(order: Order) -> float:
    """고객 미수금(잔여). 취소·완납이면 0. 잔금대기는 잔금만, 그 외 미납은 소비자총액 전액.
    대시보드 `outstanding_receivable`와 동일 산식이라 '미수금' 숫자가 화면 간 일치한다."""
    if order.status == OrderStatus.CANCELLED:
        return 0.0
    if order.payment_status not in _PAYMENT_CHECK_STATUSES:
        return 0.0
    if order.payment_status == PaymentStatus.BALANCE_PENDING:
        return _to_float(order.balance_amount)
    return _to_float(order.total_amount) + _to_float(order.onsite_extra_amount)


class OrderPageService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.group_repo = OrderGroupRepository(db)

    def list_page(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        sort: str = "visit_asc",
        status: str | None = None,
        visit_preset: str | None = None,
        visit_from: date | None = None,
        visit_to: date | None = None,
        received_preset: str | None = None,
        received_from: date | None = None,
        received_to: date | None = None,
        partner_id: str | None = None,
        broker_id: str | None = None,
        q: str | None = None,
    ) -> OrderPageResult:
        today = business_today()

        # 검색어가 있거나(=과거 완납까지 검색 노출) 방문 프리셋이 'all' 이면 과거 완납도 포함.
        keyword = (q or "").strip().lower()
        has_search = bool(keyword)
        # 과거 완납 노출: 검색 중이거나, 과거완납 노출 탭일 때.
        include_archived = has_search or (status in _PAST_PAID_VISIBLE_TABS)

        all_orders = self._load_orders()
        # 그룹을 일괄 조회해 두고 DTO/검색에서 재사용한다.
        groups_by_id = self.group_repo.list_by_ids(order.group_id for order in all_orders)
        # 인사이트는 필터와 무관한 전역 집계라 필터 적용 전 전체 집합으로 계산한다.
        insight = self._compute_insight(all_orders, today)
        rows = all_orders

        # 1) 방문일 필터
        rows = [
            order
            for order in rows
            if self._matches_visit_filter(
                order,
                today,
                preset=visit_preset,
                visit_from=visit_from,
                visit_to=visit_to,
                include_archived_for_search=include_archived,
            )
        ]
        # 2) 접수일 필터
        rows = [
            order
            for order in rows
            if self._matches_received_filter(
                order,
                today,
                preset=received_preset,
                received_from=received_from,
                received_to=received_to,
            )
        ]
        # 3) 협력사 필터
        if partner_id:
            rows = [order for order in rows if order.partner_id == partner_id]
        # 3-1) 중개사 필터 (협력사와 동일 패턴)
        if broker_id:
            rows = [order for order in rows if order.broker_id == broker_id]
        # 4) 검색 필터
        if has_search:
            rows = [
                order
                for order in rows
                if self._matches_query(order, keyword, groups_by_id.get(order.group_id))
            ]

        # 5) 상태 탭 카운트 (상태 탭 적용 *전*의 집합 기준)
        status_counts = self._status_counts(rows)

        # 6) 상태 탭 필터 적용 → 최종 집합 (표준 탭 + 대시보드 진입용 특수 탭)
        rows = [order for order in rows if self._matches_status_tab(order, status)]
        # '전체'(기본) 보기에선 취소건을 건수/금액 집계에서 뺀다(기록은 '취소' 탭에 보존).
        # 단, 검색 중엔 취소건도 찾을 수 있도록 포함한다.
        if (not status or status == "all") and not has_search:
            rows = [order for order in rows if order.status != OrderStatus.CANCELLED]

        total = len(rows)
        summary = self._summarize(rows)

        # 7) 정렬 (기존 파이썬 정렬 키 재사용)
        rows = self._sort(rows, sort, today)

        # 8) 페이지 슬라이스 + 직렬화
        page = max(page, 1)
        page_size = max(page_size, 1)
        offset = (page - 1) * page_size
        page_rows = rows[offset : offset + page_size]
        items = [
            to_admin_order_dto(order, group=groups_by_id.get(order.group_id))
            for order in page_rows
        ]

        return OrderPageResult(
            items=items,
            total=total,
            status_counts=status_counts,
            summary=summary,
            insight=insight,
        )

    @staticmethod
    def _compute_insight(orders: list[Order], today: date) -> OrderPageInsight:
        today_jobs = 0
        unassigned = 0
        schedule_confirmed = 0
        work_done = 0
        unpaid_total = 0.0
        month_total = 0.0
        for order in orders:
            # 취소건은 기록만 남기고 인사이트(건수·금액) 집계에서 제외한다.
            # (today_jobs만 취소 제외하고 월매출/미수금은 안 하던 자기모순 버그 수정 — 대시보드 정의와 일치)
            if order.status == OrderStatus.CANCELLED:
                continue
            workflow = order_workflow_status(order.status, order.payment_status)
            amount = _to_float(order.total_amount) + _to_float(order.onsite_extra_amount)
            # '이번 달'은 당월 방문(scheduled_date) 건만 — 대시보드 '이번 달 계약금액'과 같은 개념.
            if order.scheduled_date and (order.scheduled_date.year, order.scheduled_date.month) == (today.year, today.month):
                month_total += amount
            # 미수금은 잔여(잔금대기=잔금, 그 외 미납=소비자총액) 기준 — 대시보드 미정산 금액과 동일 산식.
            unpaid_total += _order_outstanding(order)
            if not (order.team_name or "").strip():
                unassigned += 1
            # '오늘 작업'은 대시보드 today_jobs와 동일하게 오늘 방문 + '일정 및 작업 확정'(작업예정 워크플로)만.
            if order.scheduled_date == today and workflow == "작업예정":
                today_jobs += 1
            if workflow == "작업예정":
                schedule_confirmed += 1
            elif workflow == "고객전달필요":
                work_done += 1
        return OrderPageInsight(
            today_jobs=today_jobs,
            unassigned=unassigned,
            schedule_confirmed=schedule_confirmed,
            work_done=work_done,
            unpaid_total=unpaid_total,
            month_total=month_total,
        )

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _load_orders(self) -> list[Order]:
        """삭제되지 않은 모든 주문을 가져온다(과거 완납 포함). 필터는 파이썬에서 적용."""
        stmt = select(Order).where(Order.deleted_at.is_(None))
        return list(self.db.scalars(stmt))

    def _matches_visit_filter(
        self,
        order: Order,
        today: date,
        *,
        preset: str | None,
        visit_from: date | None,
        visit_to: date | None,
        include_archived_for_search: bool,
    ) -> bool:
        value = order.scheduled_date

        if preset == "upcoming":
            if include_archived_for_search:
                return True
            # 오늘부터: 미정/오늘·미래/과거 잔금 미완납을 노출, 과거 완납은 제외.
            return value is None or value >= today or has_past_incomplete_balance(order, today)

        # 명시적 프리셋이 날짜 경계를 정하면 그 경계를 사용한다.
        start, end = self._resolve_date_range(preset, today, visit_from, visit_to)
        return self._matches_date_range(value, start, end)

    def _matches_received_filter(
        self,
        order: Order,
        today: date,
        *,
        preset: str | None,
        received_from: date | None,
        received_to: date | None,
    ) -> bool:
        start, end = self._resolve_date_range(preset, today, received_from, received_to)
        return self._matches_date_range(order.received_date, start, end)

    def _resolve_date_range(
        self,
        preset: str | None,
        today: date,
        explicit_from: date | None,
        explicit_to: date | None,
    ) -> tuple[date | None, date | None]:
        """프리셋(today/tomorrow/week/month)이면 경계를 계산, 그 외엔 명시 from/to 사용.

        frontend createDateFilter 와 동일 규칙. 'all'/'upcoming'/None 은 경계 없음(None,None).
        """
        if preset in _BOUNDED_VISIT_PRESETS:
            if preset == "today":
                return today, today
            if preset == "tomorrow":
                tomorrow = today + timedelta(days=1)
                return tomorrow, tomorrow
            if preset == "week":
                # 월요일 시작 ~ 일요일.
                monday = today - timedelta(days=(today.weekday()))
                return monday, monday + timedelta(days=6)
            if preset == "month":
                first = today.replace(day=1)
                if today.month == 12:
                    next_first = today.replace(year=today.year + 1, month=1, day=1)
                else:
                    next_first = today.replace(month=today.month + 1, day=1)
                last = next_first - timedelta(days=1)
                return first, last
        return explicit_from, explicit_to

    @staticmethod
    def _matches_date_range(value: date | None, start: date | None, end: date | None) -> bool:
        """frontend matchesDateFilter. 경계가 없으면 통과, 값이 없으면(경계 있음) 제외."""
        if start is None and end is None:
            return True
        if value is None:
            return False
        # start>end 면 스왑(프론트 normalizeDateRange).
        if start is not None and end is not None and start > end:
            start, end = end, start
        if start is not None and value < start:
            return False
        if end is not None and value > end:
            return False
        return True

    def _matches_query(self, order: Order, keyword: str, group: OrderGroup | None) -> bool:
        """frontend matchesOrderQuery. DTO 표시값과 동일한 필드/포맷으로 매칭한다."""
        # DTO 가 노출하는 표시값과 정확히 일치시킨다.
        customer_name = (group.customer_name if group else order.customer_name) or ""
        customer_phone = (group.customer_phone if group else order.customer_phone) or ""
        customer_address = (group.customer_address if group else order.customer_address) or ""
        customer_address_detail = (group.customer_address_detail if group else None) or ""

        status_label = _status_label(order.status)
        candidates = [
            status_label,
            order.status,  # rawStatus
            order.service_name,
            format_quantity(order.size_or_quantity),
            customer_address,
            customer_address_detail,
            f"{customer_address} {customer_address_detail}".strip(),
            customer_name,
            format_phone(customer_phone),
            order.team_name or "미배정",
        ]
        for candidate in candidates:
            if candidate and keyword in str(candidate).lower():
                return True

        keyword_digits = digits_only(keyword)
        if keyword_digits and keyword_digits in digits_only(format_phone(customer_phone)):
            return True
        return False

    # 대시보드 KPI 진입용 특수 탭은 KPI 카운트(services/dashboard.py)와 동일하게 *원본 상태*로 필터링한다.
    # 그래야 KPI 숫자와 클릭 후 목록 행 수가 정확히 일치한다(예: '고객 전달 필요' KPI=목록).
    # today/tomorrow_notice/monthly_* 의 날짜 조건은 방문일 필터(visit_preset)가 함께 처리한다.
    _RAW_STATUS_TAB = {
        # 내일 안내 대상 = 내일 '일정 및 작업 확정'(작업예정 워크플로) 전체와 동일 집합.
        "tomorrow_notice": SCHEDULED_WORKFLOW_STATUSES,
        "photo_review": (OrderStatus.PHOTO_REVIEW_PENDING,),
        "deliver": (OrderStatus.CUSTOMER_DELIVERY_NEEDED,),
        "partner_pending": (OrderStatus.PARTNER_CONFIRMING,),
        # 고객 확인 필요(대시보드 카드 드릴다운).
        "customer_check": (OrderStatus.CUSTOMER_CHECK_NEEDED,),
        # 이번 달 완료 = 작업완료(고객전달필요~서비스완료). 월 조건은 visit_preset(month)가 건다.
        "monthly_done": WORK_DONE_STATUSES,
        "monthly_revenue": REVENUE_STATUSES,
    }

    @classmethod
    def _matches_status_tab(cls, order: Order, status_key: str | None) -> bool:
        if not status_key or status_key == "all":
            return True
        # '오늘 작업 예정' = 오늘 방문 + '일정 및 작업 확정'(작업예정 워크플로). 대시보드 today_jobs 와 동일.
        # 날짜는 visit_preset(today) 가 건다.
        if status_key == "today":
            return order.status in SCHEDULED_WORKFLOW_STATUSES
        # 미정산 확인 = 작업완료(고객전달필요~서비스완료) & 고객 미수(미납). 대시보드 unpaid_check_needed 와 동일.
        if status_key == "unpaid_check":
            return (
                order.status in WORK_DONE_STATUSES
                and order.payment_status in _PAYMENT_CHECK_STATUSES
            )
        # 미정산 금액(고객 미수금) 드릴다운 = 작업완료 & 미수('미정산 확인'과 동일 모집단). 대시보드 outstanding_receivable 와 동일.
        if status_key == "receivable":
            return (
                order.status in WORK_DONE_STATUSES
                and order.payment_status in _PAYMENT_CHECK_STATUSES
            )
        if status_key in {"customer_check", "customer_check_needed"}:
            return (
                order.status == OrderStatus.CUSTOMER_CHECK_NEEDED
                or is_customer_as_intake_pending(order)
            )
        if status_key == "payment_check":
            # (레거시 탭) 미납 계열 + 취소 제외 + 방문일이 미래면 제외.
            today = business_today()
            return (
                order.status != OrderStatus.CANCELLED
                and order.payment_status in _PAYMENT_CHECK_STATUSES
                and (order.scheduled_date is None or order.scheduled_date <= today)
            )
        if status_key in cls._RAW_STATUS_TAB:
            return order.status in cls._RAW_STATUS_TAB[status_key]
        workflow = order_workflow_status(order.status, order.payment_status)
        if status_key == "pending":
            return workflow in ("상담중", "협력사확인중")
        if status_key in ("work",):
            return workflow == "작업예정"
        if status_key == "done":
            return workflow in ("고객전달필요", "서비스완료")
        tab_status = status_tab_value(status_key)
        if tab_status is not None:
            return workflow == tab_status
        return True

    @staticmethod
    def _status_counts(rows: list[Order]) -> dict[str, int]:
        # '전체' 카운트는 취소 제외(취소는 '취소' 탭 카운트에만 반영).
        counts: dict[str, int] = {
            "all": sum(1 for order in rows if order.status != OrderStatus.CANCELLED),
        }
        for key, _ in ORDER_STATUS_TAB_OPTIONS:
            counts[key] = 0
        for order in rows:
            workflow = order_workflow_status(order.status, order.payment_status)
            for key, tab_status in ORDER_STATUS_TAB_OPTIONS:
                if key == "customer_check_needed":
                    matches = (
                        order.status == OrderStatus.CUSTOMER_CHECK_NEEDED
                        or is_customer_as_intake_pending(order)
                    )
                else:
                    matches = workflow == tab_status
                if matches:
                    counts[key] += 1
        return counts

    @staticmethod
    def _summarize(rows: list[Order]) -> OrderPageSummary:
        consumer_total = 0.0
        partner_total = 0.0
        outstanding_total = 0.0
        for order in rows:
            consumer_total += _to_float(order.total_amount) + _to_float(order.onsite_extra_amount)
            partner_total += _to_float(order.partner_payment_amount)
            outstanding_total += _order_outstanding(order)
        return OrderPageSummary(
            count=len(rows),
            consumer_total=consumer_total,
            partner_total=partner_total,
            profit=consumer_total - partner_total,
            # 필터된 목록의 고객 미수금 합(잔여 기준). receivable 드릴다운 시 대시보드 '미정산 금액' 카드와 일치.
            outstanding_total=outstanding_total,
        )

    @staticmethod
    def _sort(rows: list[Order], sort: str, today: date) -> list[Order]:
        ordered = list(rows)
        if sort in {"received_asc", "received_desc"}:
            ordered.sort(
                key=lambda order: order_received_sort_key(order, reverse_received=sort == "received_desc"),
            )
        else:
            reverse_visit = sort == "visit_desc"
            ordered.sort(key=lambda order: order_visit_sort_key(order, today, reverse_visit=reverse_visit))
        return ordered


def _status_label(status: str | None) -> str:
    """frontend orderStatusLabel. 검색 텍스트 매칭에 쓰는 한글 라벨."""
    return _ORDER_STATUS_LABELS.get(status or "", status or "")


# frontend ORDER_STATUS_LABELS 와 동일.
_ORDER_STATUS_LABELS: dict[str, str] = {
    "신규접수": "상담중/미배정",
    "상담중": "상담중/미배정",
    "협력사확인중": "일정 및 협력사 확인중",
    "일정확정": "일정 및 작업 확정",
    "전날안내필요": "일정 및 작업 확정",
    "전날안내완료": "일정 및 작업 확정",
    "작업예정": "일정 및 작업 확정",
    "작업진행": "일정 및 작업 확정",
    "사진검수대기": "작업완료",
    "고객전달필요": "작업완료",
    "고객전달완료": "작업완료",
    "고객확인필요": "고객확인필요",
    "서비스완료": "최종결제완료",
    "취소": "취소",
}
