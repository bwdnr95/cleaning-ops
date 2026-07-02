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


def test_settlement_item_includes_group_totals(db_session):
    # 한 그룹(고객)에 2라인: 금액은 라인1에만. 둘 다 DEV_PARTNER에 배정·서비스완료.
    # 1-1로 도급가 0원 라인은 '미정산' 목록에선 빠지므로, 그룹 합계 보조표시는 '전체' 뷰로 검증한다.
    group = OrderGroup(
        id=str(uuid4()), customer_token=f"t-{uuid4()}", customer_name="강남",
        customer_phone="01011112222", customer_address="A", customer_visible_payment=False,
    )
    db_session.add(group)
    db_session.flush()
    common = dict(
        group_id=group.id, status=OrderStatus.COMPLETED, received_date=date(2026, 1, 1),
        service_name="청소", partner_id=DEV_PARTNER_ID, partner_payment_status="unpaid",
        customer_token=group.customer_token, customer_name="강남", customer_phone="01011112222",
        customer_address="A",
    )
    db_session.add(Order(id=str(uuid4()), total_amount=120000, partner_payment_amount=80000, **common))
    db_session.add(Order(id=str(uuid4()), total_amount=0, partner_payment_amount=0, **common))
    db_session.commit()

    result = PartnerSettlementService(db_session).list_settlements(partner_id=DEV_PARTNER_ID, status="all")
    items = [i for i in result.items if i.customer_name == "강남"]
    assert len(items) == 2
    for it in items:
        assert it.group_consumer_total == 120000  # 그룹 합계가 두 라인 모두에 실림
        assert it.group_partner_total == 80000


def test_settlement_group_totals_exclude_cancelled_line(db_session):
    # 같은 그룹에 취소 라인이 섞이면 그 금액은 그룹 합계에서 제외된다.
    group = OrderGroup(
        id=str(uuid4()), customer_token=f"t-{uuid4()}", customer_name="서초",
        customer_phone="01033334444", customer_address="A", customer_visible_payment=False,
    )
    db_session.add(group)
    db_session.flush()
    common = dict(
        group_id=group.id, received_date=date(2026, 1, 1), service_name="청소",
        partner_id=DEV_PARTNER_ID, partner_payment_status="unpaid",
        customer_token=group.customer_token, customer_name="서초", customer_phone="01033334444",
        customer_address="A",
    )
    db_session.add(Order(
        id=str(uuid4()), status=OrderStatus.COMPLETED,
        total_amount=100000, partner_payment_amount=70000, **common,
    ))
    db_session.add(Order(
        id=str(uuid4()), status=OrderStatus.CANCELLED,
        total_amount=50000, partner_payment_amount=30000, **common,
    ))
    db_session.commit()

    result = PartnerSettlementService(db_session).list_settlements(partner_id=DEV_PARTNER_ID, status="unpaid")
    items = [i for i in result.items if i.customer_name == "서초"]
    # 미정산 목록엔 서비스완료 라인만 뜬다(취소는 unpaid 조건 밖).
    assert len(items) == 1
    assert items[0].group_consumer_total == 100000  # 취소 50000 제외
    assert items[0].group_partner_total == 70000     # 취소 30000 제외
