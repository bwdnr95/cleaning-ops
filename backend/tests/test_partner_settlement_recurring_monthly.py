"""월 청구 정기 도급비 ↔ 협력사관리 정산 동기화 테스트.

2026-08 대표 보고: 월 트래커에서 지급을 체크해도 협력사관리에는 월 도급비가
어디에도 보이지 않고, 미정산 배지에는 잡히는데 정산 목록에는 정산할 행이 없어
"정산 체크가 불가"한 모순이 있었다.

핵심 검증:
- 정산 목록 monthly_items에 계약×월 행이 표시된다(미지급은 날짜 필터 무관).
- 배지(미정산 합계)와 목록(미지급 monthly_items 합계)이 항상 일치한다(같은 행 빌더).
- 협력사관리의 지급/되돌리기가 월 트래커(list_month)와 같은 행을 토글한다.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.time import business_today
from app.domain.constants import RecurrenceMode, RecurringContractStatus
from app.models.order_group import OrderGroup
from app.models.recurring_contract import RecurringContract
from app.repositories.recurring import RecurringMonthlyStatusRepository
from app.schemas.partner import PartnerCreate
from app.services.partner_settlements import PartnerSettlementService
from app.services.partners import PartnerService
from app.services.recurring_monthly import RecurringMonthlyService
from app.services.recurring_partner_billing import billing_month


def _partner(db: Session, *, name: str = "치움테스트", phone: str = "01099998888") -> str:
    return PartnerService(db).create(PartnerCreate(name=name, phone=phone)).id


def _monthly_contract(
    db: Session,
    partner_id: str,
    *,
    partner_billing_mode: str = "monthly",
    partner_payment_amount: int | None = 660000,
    label: str = "김해테스트1차",
) -> RecurringContract:
    # 시작일을 당월 1일로 둬서 발생 월(incurred)이 정확히 현재 월 1개가 되게 한다.
    start = business_today().replace(day=1)
    group = OrderGroup(
        id=str(uuid4()),
        customer_token=f"t-{uuid4()}",
        customer_name="정기고객",
        customer_phone="01011112222",
        customer_address="김해시 테스트로 1",
        customer_visible_payment=False,
    )
    db.add(group)
    db.flush()
    contract = RecurringContract(
        id=str(uuid4()),
        label=label,
        order_group_id=group.id,
        recurrence_mode=RecurrenceMode.MONTHLY,
        day_of_month=10,
        start_date=start,
        status=RecurringContractStatus.ACTIVE,
        service_name="정기청소",
        total_amount=770000,
        billing_mode="monthly",
        default_partner_id=partner_id,
        partner_billing_mode=partner_billing_mode,
        partner_payment_amount=partner_payment_amount,
    )
    db.add(contract)
    db.commit()
    return contract


def test_unpaid_monthly_row_listed_regardless_of_date_filter(db_session: Session) -> None:
    pid = _partner(db_session)
    contract = _monthly_contract(db_session, pid)
    month = billing_month(business_today())
    service = PartnerSettlementService(db_session)

    result = service.list_settlements(partner_id=pid, status="unpaid")
    assert [(row.contract_id, row.month, row.paid) for row in result.monthly_items] == [
        (contract.id, month, False)
    ]
    assert result.monthly_items[0].partner_price == 660000
    assert result.count == 1
    assert result.total_partner_price == 660000

    # 미지급 월정산은 배지(날짜 무관)와 일치해야 하므로 기간 밖이어도 항상 보인다.
    out_of_range = service.list_settlements(
        partner_id=pid,
        status="unpaid",
        from_date=date(2020, 1, 1),
        to_date=date(2020, 1, 31),
    )
    assert len(out_of_range.monthly_items) == 1


def test_badge_and_list_agree_on_unpaid_monthly(db_session: Session) -> None:
    # ⭐ 숫자 cross-check: 미정산 배지 합계 == 정산 목록 미지급 합계 (독립 화면 2곳).
    pid = _partner(db_session)
    _monthly_contract(db_session, pid)

    detail = PartnerService(db_session).get_detail(pid)
    listing = PartnerSettlementService(db_session).list_settlements(
        partner_id=pid, status="unpaid"
    )
    monthly_total = sum(row.partner_price for row in listing.monthly_items)

    assert detail.unpaid_partner_order_count == 1
    assert detail.unpaid_partner_amount_total == 660000
    assert monthly_total + sum(
        item.partner_price or 0
        for item in listing.items
        if item.partner_payment_status != "paid"
    ) == detail.unpaid_partner_amount_total


def test_settle_and_revert_sync_with_monthly_tracker(db_session: Session) -> None:
    pid = _partner(db_session)
    contract = _monthly_contract(db_session, pid)
    month = billing_month(business_today())
    service = PartnerSettlementService(db_session)

    settled = service.set_recurring_monthly_paid(
        partner_id=pid, contract_id=contract.id, month=month, paid=True
    )
    assert settled.paid is True

    status = RecurringMonthlyStatusRepository(db_session).get_by_contract_and_month(
        contract.id, month
    )
    assert status is not None and status.partner_payment_paid is True

    # 월 트래커(정기청소 탭) 화면도 같은 행을 읽으므로 즉시 동기화된다.
    tracker_row = next(
        row
        for row in RecurringMonthlyService(db_session).list_month(month)
        if row.contract_id == contract.id
    )
    assert tracker_row.partner_payment_paid is True

    # 미지급 목록/배지에서 사라지고 정산완료 목록(기간 포함)에 나타난다.
    unpaid = service.list_settlements(partner_id=pid, status="unpaid")
    assert unpaid.monthly_items == []
    assert PartnerService(db_session).get_detail(pid).unpaid_partner_amount_total == 0
    today = business_today()
    paid = service.list_settlements(
        partner_id=pid,
        status="paid",
        from_date=today.replace(day=1),
        to_date=today,
    )
    assert [(row.month, row.paid) for row in paid.monthly_items] == [(month, True)]
    assert paid.total_partner_price == 660000

    reverted = service.set_recurring_monthly_paid(
        partner_id=pid, contract_id=contract.id, month=month, paid=False
    )
    assert reverted.paid is False
    assert PartnerService(db_session).get_detail(pid).unpaid_partner_amount_total == 660000


def test_paid_monthly_row_respects_date_filter(db_session: Session) -> None:
    pid = _partner(db_session)
    contract = _monthly_contract(db_session, pid)
    month = billing_month(business_today())
    service = PartnerSettlementService(db_session)
    service.set_recurring_monthly_paid(
        partner_id=pid, contract_id=contract.id, month=month, paid=True
    )

    out_of_range = service.list_settlements(
        partner_id=pid,
        status="paid",
        from_date=date(2020, 1, 1),
        to_date=date(2020, 1, 31),
    )
    assert out_of_range.monthly_items == []


def test_settle_monthly_rejects_other_partner(db_session: Session) -> None:
    pid = _partner(db_session)
    other_pid = _partner(db_session, name="다른업체", phone="01097776666")
    contract = _monthly_contract(db_session, pid)
    month = billing_month(business_today())

    with pytest.raises(ValueError, match="settlement_month_partner_mismatch"):
        PartnerSettlementService(db_session).set_recurring_monthly_paid(
            partner_id=other_pid, contract_id=contract.id, month=month, paid=True
        )


def test_per_visit_contract_has_no_monthly_rows(db_session: Session) -> None:
    pid = _partner(db_session)
    _monthly_contract(db_session, pid, partner_billing_mode="per_visit")

    result = PartnerSettlementService(db_session).list_settlements(
        partner_id=pid, status="unpaid"
    )
    assert result.monthly_items == []
    assert PartnerService(db_session).get_detail(pid).unpaid_partner_amount_total == 0


def test_contract_without_partner_amount_not_listed(db_session: Session) -> None:
    pid = _partner(db_session)
    _monthly_contract(db_session, pid, partner_payment_amount=None)

    result = PartnerSettlementService(db_session).list_settlements(
        partner_id=pid, status="unpaid"
    )
    assert result.monthly_items == []


def test_set_status_expected_partner_guard_inside_lock(db_session: Session) -> None:
    # H1(TOCTOU): 락 밖 사전 검사 사이에 담당 협력사가 바뀌어도, 락 획득 후
    # expected_partner_id 재검증이 엉뚱한 협력사 월의 지급 마킹을 거부해야 한다.
    pid = _partner(db_session)
    other_pid = _partner(db_session, name="바뀐업체", phone="01096665555")
    contract = _monthly_contract(db_session, pid)
    month = billing_month(business_today())

    with pytest.raises(ValueError, match="settlement_month_partner_mismatch"):
        RecurringMonthlyService(db_session).set_status(
            contract.id, month, partner_payment_paid=True, expected_partner_id=other_pid
        )
    status = RecurringMonthlyStatusRepository(db_session).get_by_contract_and_month(
        contract.id, month
    )
    assert status is None or status.partner_payment_paid is False

    row = RecurringMonthlyService(db_session).set_status(
        contract.id, month, partner_payment_paid=True, expected_partner_id=pid
    )
    assert row.partner_payment_paid is True


def test_revert_without_paid_state_is_noop_without_status_row(db_session: Session) -> None:
    # M5: 되돌릴 지급이 없으면 빈 status 행을 만들지 않는다(멱등 no-op).
    pid = _partner(db_session)
    contract = _monthly_contract(db_session, pid)
    month = billing_month(business_today())

    result = PartnerSettlementService(db_session).set_recurring_monthly_paid(
        partner_id=pid, contract_id=contract.id, month=month, paid=False
    )
    assert result.paid is False
    assert result.partner_price == 660000
    assert RecurringMonthlyStatusRepository(db_session).get_by_contract_and_month(
        contract.id, month
    ) is None


def test_future_month_rejected_even_as_noop_revert(db_session: Session) -> None:
    # L6: no-op revert 분기가 set_status의 미래월 가드를 우회하면 안 된다.
    pid = _partner(db_session)
    contract = _monthly_contract(db_session, pid)
    today = business_today()
    next_month = (
        date(today.year + 1, 1, 1) if today.month == 12 else date(today.year, today.month + 1, 1)
    )
    future = billing_month(next_month)

    with pytest.raises(ValueError, match="recurring_month_not_editable"):
        PartnerSettlementService(db_session).set_recurring_monthly_paid(
            partner_id=pid, contract_id=contract.id, month=future, paid=False
        )


def test_report_backlog_and_partner_screen_derive_same_unpaid_set(db_session: Session) -> None:
    # H3(§4 독립 신호): 정산 백로그 리포트는 _partner_month_amount 경유의 **다른 계산
    # 경로**다. 협력사 화면 행 빌더의 미지급 집합과 (계약, 월, 협력사, 금액)이 완전히
    # 일치해야 한다. (실 운영 DB 감사 S3와 같은 대조를 CI에 박제.)
    from app.services.recurring_partner_billing import RecurringPartnerBillingService
    from app.services.reports import ReportService

    pid = _partner(db_session)
    unpaid_contract = _monthly_contract(db_session, pid, label="미지급계약")
    paid_contract = _monthly_contract(db_session, pid, label="지급계약")
    month = billing_month(business_today())
    PartnerSettlementService(db_session).set_recurring_monthly_paid(
        partner_id=pid, contract_id=paid_contract.id, month=month, paid=True
    )

    builder_unpaid = {
        (row.contract_id, row.month, row.partner_id, float(row.amount))
        for row in RecurringPartnerBillingService(db_session).list_monthly_settlement_rows()
        if not row.paid
    }
    report_pending = {
        (item.contract.id, item.month, item.partner_id, float(item.amount))
        for item in ReportService(db_session)._pending_recurring_monthly_settlements()
        if item.partner_id is not None
    }
    assert builder_unpaid == report_pending
    assert (unpaid_contract.id, month, pid, 660000.0) in builder_unpaid
    assert all(key[0] != paid_contract.id for key in builder_unpaid)
