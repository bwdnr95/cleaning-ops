"""운영 260630 #1·#2 회귀 테스트.

#1: "결제 확인 필요"(대시보드 카운트 + 주문목록 payment_check 탭)에서 방문일이
    미래(오늘 이후)인 건을 제외한다. 단 미배정(방문일 없음)은 유지한다.
#2: 협력사 정산 item에 그룹(고객) 합계를 실어 0원 라인 보조표시에 쓴다.
"""

from datetime import date, timedelta
from uuid import uuid4

from app.core.time import business_today
from app.db.seed import DEV_PARTNER_ID
from app.domain.constants import OrderStatus
from app.domain.payment_status import PaymentStatus
from app.models.order import Order
from app.models.order_group import OrderGroup
from app.services.dashboard import DashboardService
from app.services.order_page import OrderPageService
from app.services.partner_settlements import PartnerSettlementService


def _order(db, *, scheduled, payment_status=PaymentStatus.UNPAID, status=OrderStatus.SCHEDULE_CONFIRMED):
    group = OrderGroup(
        id=str(uuid4()), customer_token=f"t-{uuid4()}", customer_name="C",
        customer_phone="01000000000", customer_address="A", customer_visible_payment=False,
    )
    db.add(group)
    db.flush()
    o = Order(
        id=str(uuid4()), group_id=group.id, status=status, received_date=date(2026, 1, 1),
        scheduled_date=scheduled, service_name="S", payment_status=payment_status,
        customer_token=group.customer_token, customer_name="C", customer_phone="01000000000",
        customer_address="A",
    )
    db.add(o)
    db.flush()
    return o


def test_payment_check_count_excludes_future_visit(db_session):
    # 시드 주문이 있을 수 있어 신규 4건의 델타(미래 1건 제외 → +3)로 단언한다.
    service = DashboardService(db_session)
    today = business_today()
    baseline = service.summary().payment_check_needed
    _order(db_session, scheduled=today + timedelta(days=7))   # 미래 → 제외
    _order(db_session, scheduled=today)                        # 오늘 → 포함
    _order(db_session, scheduled=today - timedelta(days=3))    # 과거 → 포함
    _order(db_session, scheduled=None)                         # 미배정 → 포함
    db_session.commit()
    after = service.summary().payment_check_needed
    assert after - baseline == 3  # 미래 1건만 빠지고 3건 카운트


def test_order_page_payment_check_filter_matches_count_definition(db_session):
    # 주문목록 payment_check 탭 필터가 대시보드 카운트와 동일 기준(미래 제외·미배정 유지)인지.
    today = business_today()
    future = _order(db_session, scheduled=today + timedelta(days=7))
    today_order = _order(db_session, scheduled=today)
    past = _order(db_session, scheduled=today - timedelta(days=3))
    unassigned = _order(db_session, scheduled=None)
    cancelled = _order(db_session, scheduled=today, status=OrderStatus.CANCELLED)
    db_session.commit()

    match = OrderPageService._matches_status_tab
    assert match(future, "payment_check") is False       # 미래 → 제외
    assert match(today_order, "payment_check") is True    # 오늘 → 포함
    assert match(past, "payment_check") is True           # 과거 → 포함
    assert match(unassigned, "payment_check") is True     # 미배정 → 포함
    assert match(cancelled, "payment_check") is False     # 취소 → 제외
