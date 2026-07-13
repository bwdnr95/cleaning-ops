"""주문 상태 기반 지표(카운트·매출·정산 대상) 정의의 **단일 출처**.

대시보드 KPI / 주문목록 / 협력사 / 정산 / 리포트가 같은 개념("매출 대상 상태",
"협력사 진행/완료 작업", "정산 가능 상태")을 각자 정의해 숫자가 어긋나던 문제를 막기 위해,
어떤 상태가 어떤 집계에 들어가는지를 여기 한 곳에서만 정의한다.

각 서비스 모듈은 이 상수를 import 해서 쓰고, 값을 따로 재정의하지 않는다.
"""

from app.domain.constants import OrderStatus

# 매출 집계 대상 상태. (취소는 단일 상태값이라 이 화이트리스트에 없으므로 자동 제외)
# 사용처: dashboard.monthly_revenue, reports.revenue/services, order_page 'monthly_revenue' 탭.
REVENUE_STATUSES: tuple[OrderStatus, ...] = (
    OrderStatus.CUSTOMER_DELIVERY_DONE,
    OrderStatus.COMPLETED,
)

# 워크플로 '작업예정'(= 주문목록 '일정 및 작업 확정' 탭)에 묶이는 원본 상태들.
# 대시보드 '내일 안내 대상' KPI 와 주문목록 '일정 및 작업 확정' 탭/카운트가 동일 집합을 보도록 공유한다.
SCHEDULED_WORKFLOW_STATUSES: tuple[OrderStatus, ...] = (
    OrderStatus.SCHEDULE_CONFIRMED,
    OrderStatus.DAY_BEFORE_NOTICE_NEEDED,
    OrderStatus.DAY_BEFORE_NOTICE_DONE,
    OrderStatus.SCHEDULED,
    OrderStatus.IN_PROGRESS,
)

# 협력사 '진행 중' 작업으로 세는 상태(취소·완료 제외).
ACTIVE_JOB_STATUSES: tuple[OrderStatus, ...] = (
    OrderStatus.PARTNER_CONFIRMING,
    OrderStatus.SCHEDULE_CONFIRMED,
    OrderStatus.DAY_BEFORE_NOTICE_NEEDED,
    OrderStatus.DAY_BEFORE_NOTICE_DONE,
    OrderStatus.SCHEDULED,
    OrderStatus.IN_PROGRESS,
    OrderStatus.PHOTO_REVIEW_PENDING,
    OrderStatus.CUSTOMER_DELIVERY_NEEDED,
)

# 협력사 '완료' 작업으로 세는 상태.
COMPLETED_JOB_STATUSES: tuple[OrderStatus, ...] = (
    OrderStatus.CUSTOMER_DELIVERY_DONE,
    OrderStatus.COMPLETED,
)

# '작업완료'(= 협력사가 작업을 끝낸 '고객전달필요'부터 최종 '서비스완료'까지 전부).
# 대시보드 '미정산 확인'(작업완료 & 고객 미수)·'이번 달 완료'(당월 작업완료) 카드의 단일 기준.
WORK_DONE_STATUSES: tuple[OrderStatus, ...] = (
    OrderStatus.CUSTOMER_DELIVERY_NEEDED,
    OrderStatus.CUSTOMER_DELIVERY_DONE,
    OrderStatus.CUSTOMER_CHECK_NEEDED,
    OrderStatus.COMPLETED,
)

# 협력사 관리 화면의 '미정산 도급가' 표시 대상.
# 정산 실행/정산 탭의 공통 미정산 조건은 완료 전 정산 정책 때문에 더 넓게 유지하고,
# 협력사별 관리 요약은 실제 작업 진행 이후 상태만 보여준다.
PARTNER_ADMIN_UNPAID_STATUSES: tuple[OrderStatus, ...] = (
    OrderStatus.IN_PROGRESS,
    OrderStatus.PHOTO_REVIEW_PENDING,
    *WORK_DONE_STATUSES,
)
