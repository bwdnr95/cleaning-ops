from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.time import business_today
from app.domain.constants import RecurrenceMode, RecurringContractStatus
from app.models.order_group import OrderGroup
from app.models.recurring_contract import RecurringContract
from app.models.recurring_monthly_status import RecurringMonthlyStatus
from app.schemas.partner import PartnerCreate
from app.services.partner_settlements import PartnerSettlementService
from app.services.partners import PartnerService
from app.services.recurring_monthly import RecurringMonthlyService
from app.services.recurring_partner_billing import (
    RecurringPartnerBillingService,
    billing_month,
)
from app.services.reports import ReportService


def _partner(db: Session) -> str:
    return PartnerService(db).create(
        PartnerCreate(name="삭제계약 테스트", phone="01098989898")
    ).id


def _monthly_contract(
    db: Session,
    partner_id: str,
    *,
    label: str,
    partner_billing_mode: str = "monthly",
    partner_payment_amount: int = 660000,
) -> RecurringContract:
    start = business_today().replace(day=1)
    group = OrderGroup(
        id=str(uuid4()),
        customer_token=f"t-{uuid4()}",
        customer_name="정기고객",
        customer_phone="01011112222",
        customer_address="삭제계약 테스트 주소",
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


@pytest.mark.parametrize(
    ("tax_invoice_issued", "balance_paid"),
    [(False, False), (True, False), (False, True)],
)
def test_deleted_contract_without_partner_history_is_hidden_from_all_monthly_surfaces(
    db_session: Session,
    tax_invoice_issued: bool,
    balance_paid: bool,
) -> None:
    partner_id = _partner(db_session)
    contract = _monthly_contract(db_session, partner_id, label="삭제 빈 계약")
    month = billing_month(business_today())
    contract.deleted_at = datetime.now(UTC)
    db_session.add(
        RecurringMonthlyStatus(
            id=str(uuid4()),
            contract_id=contract.id,
            billing_month=month,
            tax_invoice_issued=tax_invoice_issued,
            balance_paid=balance_paid,
            partner_payment_paid=False,
        )
    )
    db_session.commit()

    tracker = RecurringMonthlyService(db_session).list_month(month)
    settlement_rows = RecurringPartnerBillingService(
        db_session
    ).list_monthly_settlement_rows()
    partner_list = PartnerSettlementService(db_session).list_settlements(
        partner_id=partner_id,
        status="unpaid",
    )
    backlog = ReportService(db_session).settlements().rows

    assert all(row.contract_id != contract.id for row in tracker)
    assert all(row.contract_id != contract.id for row in settlement_rows)
    assert all(row.contract_id != contract.id for row in partner_list.monthly_items)
    assert all(
        row.order_id != f"recurring-monthly:{contract.id}:{month}" for row in backlog
    )
    assert (
        PartnerService(db_session).get_detail(partner_id).unpaid_partner_amount_total
        == 0
    )


def test_deleted_contract_paid_history_remains_visible_without_reopening_backlog(
    db_session: Session,
) -> None:
    partner_id = _partner(db_session)
    contract = _monthly_contract(db_session, partner_id, label="삭제 지급 계약")
    month = billing_month(business_today())
    contract.deleted_at = datetime.now(UTC)
    db_session.add(
        RecurringMonthlyStatus(
            id=str(uuid4()),
            contract_id=contract.id,
            billing_month=month,
            partner_payment_paid=True,
        )
    )
    db_session.commit()

    tracker = RecurringMonthlyService(db_session).list_month(month)
    settlement_rows = RecurringPartnerBillingService(
        db_session
    ).list_monthly_settlement_rows()
    paid_list = PartnerSettlementService(db_session).list_settlements(
        partner_id=partner_id,
        status="paid",
        from_date=business_today().replace(day=1),
        to_date=business_today(),
    )
    backlog = ReportService(db_session).settlements().rows

    assert any(row.contract_id == contract.id for row in tracker)
    assert any(
        row.contract_id == contract.id and row.paid is True for row in settlement_rows
    )
    assert any(row.contract_id == contract.id for row in paid_list.monthly_items)
    assert all(
        row.order_id != f"recurring-monthly:{contract.id}:{month}" for row in backlog
    )


def test_deleted_contract_retained_unpaid_history_remains_on_all_monthly_surfaces(
    db_session: Session,
) -> None:
    partner_id = _partner(db_session)
    contract = _monthly_contract(
        db_session,
        partner_id,
        label="삭제 retained 계약",
        partner_billing_mode="per_visit",
        partner_payment_amount=90000,
    )
    month = billing_month(business_today())
    contract.deleted_at = datetime.now(UTC)
    db_session.add(
        RecurringMonthlyStatus(
            id=str(uuid4()),
            contract_id=contract.id,
            billing_month=month,
            partner_payment_paid=False,
            retained_partner_id=partner_id,
            retained_partner_payment_amount=Decimal("720000"),
        )
    )
    db_session.commit()

    tracker = RecurringMonthlyService(db_session).list_month(month)
    settlement_rows = RecurringPartnerBillingService(
        db_session
    ).list_monthly_settlement_rows()
    partner_list = PartnerSettlementService(db_session).list_settlements(
        partner_id=partner_id,
        status="unpaid",
    )
    backlog = ReportService(db_session).settlements().rows

    assert any(
        row.contract_id == contract.id and row.partner_amount == 720000
        for row in tracker
    )
    assert any(
        row.contract_id == contract.id and row.amount == Decimal("720000")
        for row in settlement_rows
    )
    assert any(
        row.contract_id == contract.id and row.partner_price == 720000
        for row in partner_list.monthly_items
    )
    assert any(
        row.order_id == f"recurring-monthly:{contract.id}:{month}"
        and row.expected_settlement_amount == Decimal("720000")
        for row in backlog
    )
    assert (
        PartnerService(db_session).get_detail(partner_id).unpaid_partner_amount_total
        == 720000
    )
