"""Codex CTO 리뷰(커밋 494b11c) 후속 수정에 대한 회귀 테스트.

- P1-1: STATUS_ORDER 에 신규 상태 누락 시 발송 후처리 KeyError → 골든/방어 테스트로 고정.
- P1-3: 고객확인필요 탭이 기본 '오늘부터' 방문일 프리셋에서 과거 방문건을 숨기지 않도록 보장.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.time import business_today
from app.domain.constants import OrderStatus
from app.services.messages import STATUS_ORDER, should_advance_status
from app.services.order_page import OrderPageService

from tests.test_batch_2026_06_23 import _add, _clean_universe


# --------------------------------------------------------------------------
# P1-1: 상태 순서표 누락으로 인한 발송 후처리 크래시 방지
# --------------------------------------------------------------------------


def test_status_order_covers_every_order_status() -> None:
    """모든 OrderStatus 는 STATUS_ORDER 에 등록돼야 한다.

    누락되면 should_advance_status() 의 직접 인덱싱이 KeyError 를 내고,
    이는 provider 발송 직후/최종 commit 직전에 터져 운영 기록을 깨뜨린다.
    """
    missing = [status for status in OrderStatus if status not in STATUS_ORDER]
    assert missing == []


def test_should_advance_status_handles_customer_check_needed() -> None:
    # 고객확인필요는 보류 상태 → 앞 단계 메시지를 보내도 뒤로 전진(역행)하지 않는다.
    assert should_advance_status(OrderStatus.CUSTOMER_CHECK_NEEDED, OrderStatus.PARTNER_CONFIRMING) is False
    assert should_advance_status(OrderStatus.CUSTOMER_CHECK_NEEDED, OrderStatus.SCHEDULE_CONFIRMED) is False
    # 앞 단계에서 고객확인필요로는 전진할 수 있다.
    assert should_advance_status(OrderStatus.IN_PROGRESS, OrderStatus.CUSTOMER_CHECK_NEEDED) is True


def test_should_advance_status_unknown_status_does_not_crash() -> None:
    # enum 에 없는 값이 들어와도 KeyError 없이 안전하게 False 를 돌려준다(미래 회귀 방어).
    assert should_advance_status("없는상태", OrderStatus.COMPLETED) is False
    assert should_advance_status(OrderStatus.IN_PROGRESS, "없는상태") is False


# --------------------------------------------------------------------------
# P1-3: 고객확인필요 탭은 기본 '오늘부터' 필터에서도 과거 방문건을 노출
# --------------------------------------------------------------------------


def test_customer_check_needed_tab_shows_past_visits_under_upcoming(db_session: Session) -> None:
    _clean_universe(db_session)
    past = business_today() - timedelta(days=10)
    # 과거에 방문했고 완납이라도, 컴플레인/확인 큐는 숨기면 안 된다.
    _add(
        db_session,
        status=OrderStatus.CUSTOMER_CHECK_NEEDED,
        scheduled_date=past,
        payment_status="paid",
    )
    db_session.flush()

    page = OrderPageService(db_session).list_page(
        status="customer_check_needed", visit_preset="upcoming", page_size=200
    )
    # _PAST_PAID_VISIBLE_TABS 에 customer_check_needed 가 포함돼야 1건이 잡힌다.
    assert page.total == 1
