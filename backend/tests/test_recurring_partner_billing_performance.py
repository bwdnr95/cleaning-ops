from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.domain.constants import RecurrenceMode, RecurringContractStatus
from app.models.order_group import OrderGroup
from app.models.recurring_contract import RecurringContract
from app.models.recurring_monthly_status import RecurringMonthlyStatus
from app.models.recurring_partner_billing_period import RecurringPartnerBillingPeriod
from app.schemas.partner import PartnerCreate
from app.schemas.recurring_monthly import RecurringMonthlyRowRead
from app.services.partner_settlements import PartnerSettlementService
from app.services.partners import PartnerService
from app.services.recurring_monthly import RecurringMonthlyService
from app.services.recurring_partner_billing import RecurringPartnerBillingService


def _partner(db: Session) -> str:
    return PartnerService(db).create(
        PartnerCreate(name="기간해석 테스트", phone="01097979797")
    ).id


def _contract(
    db: Session,
    partner_id: str,
    *,
    label: str,
    partner_payment_amount: int,
    partner_billing_mode: str = "monthly",
) -> RecurringContract:
    group = OrderGroup(
        id=str(uuid4()),
        customer_token=f"t-{uuid4()}",
        customer_name="정기고객",
        customer_phone="01011112222",
        customer_address="기간해석 테스트 주소",
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
        start_date=date(2026, 7, 1),
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


def test_monthly_row_builder_bulk_loads_periods_and_preserves_effective_month_resolution(
    db_session: Session,
) -> None:
    partner_id = _partner(db_session)
    first = _contract(
        db_session,
        partner_id,
        label="기간 일괄 A",
        partner_payment_amount=110000,
    )
    second = _contract(
        db_session,
        partner_id,
        label="기간 일괄 B",
        partner_payment_amount=210000,
    )
    contracts = (
        (first, Decimal("110000"), Decimal("120000")),
        (second, Decimal("210000"), Decimal("220000")),
    )
    for contract, baseline_amount, changed_amount in contracts:
        db_session.add_all(
            [
                RecurringPartnerBillingPeriod(
                    contract_id=contract.id,
                    effective_month="0001-01",
                    partner_id=partner_id,
                    billing_mode="monthly",
                    partner_payment_amount=baseline_amount,
                ),
                RecurringPartnerBillingPeriod(
                    contract_id=contract.id,
                    effective_month="2026-08",
                    partner_id=partner_id,
                    billing_mode="monthly",
                    partner_payment_amount=changed_amount,
                ),
                *(
                    RecurringMonthlyStatus(
                        id=str(uuid4()),
                        contract_id=contract.id,
                        billing_month=month,
                        partner_payment_paid=False,
                    )
                    for month in ("2026-07", "2026-08", "2026-09")
                ),
            ]
        )
    db_session.commit()

    select_statements: list[str] = []

    def count_selects(*args) -> None:
        statement = args[2]
        if statement.lstrip().upper().startswith("SELECT"):
            select_statements.append(statement)

    bind = db_session.get_bind()
    event.listen(bind, "before_cursor_execute", count_selects)
    try:
        rows = RecurringPartnerBillingService(
            db_session
        ).list_monthly_settlement_rows(today=date(2026, 9, 4))
    finally:
        event.remove(bind, "before_cursor_execute", count_selects)

    own_rows = {
        (row.contract_id, row.month): row.amount
        for row in rows
        if row.contract_id in {first.id, second.id}
    }
    assert own_rows == {
        (first.id, "2026-07"): Decimal("110000"),
        (first.id, "2026-08"): Decimal("120000"),
        (first.id, "2026-09"): Decimal("120000"),
        (second.id, "2026-07"): Decimal("210000"),
        (second.id, "2026-08"): Decimal("220000"),
        (second.id, "2026-09"): Decimal("220000"),
    }
    assert len(select_statements) == 3


def test_revert_response_uses_monthly_row_amount_not_per_visit_projection(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_today = date(2026, 9, 4)
    monkeypatch.setattr(
        "app.services.partner_settlements.business_today", lambda: fixed_today
    )
    monkeypatch.setattr("app.services.recurring_monthly.business_today", lambda: fixed_today)
    partner_id = _partner(db_session)
    contract = _contract(
        db_session,
        partner_id,
        label="회당 응답 금액",
        partner_billing_mode="per_visit",
        partner_payment_amount=660000,
    )
    contract.recurrence_mode = RecurrenceMode.WEEKLY
    contract.day_of_month = None
    contract.interval_weeks = 1
    contract.weekday = 1
    contract.start_date = date(2026, 9, 1)
    month = "2026-09"
    db_session.add(
        RecurringMonthlyStatus(
            id=str(uuid4()),
            contract_id=contract.id,
            billing_month=month,
            partner_payment_paid=True,
        )
    )
    db_session.commit()

    projected = next(
        row
        for row in RecurringMonthlyService(db_session).list_month(month)
        if row.contract_id == contract.id
    )
    assert projected.partner_amount is not None and projected.partner_amount > 660000

    reverted = PartnerSettlementService(db_session).set_recurring_monthly_paid(
        partner_id=partner_id,
        contract_id=contract.id,
        month=month,
        paid=False,
    )

    assert reverted.paid is False
    assert reverted.partner_price == 660000


def test_settle_response_uses_terms_refreshed_inside_status_lock(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    partner_id = _partner(db_session)
    contract = _contract(
        db_session,
        partner_id,
        label="동시변경 응답 금액",
        partner_payment_amount=100000,
    )
    month = "2026-09"
    db_session.add(
        RecurringMonthlyStatus(
            id=str(uuid4()),
            contract_id=contract.id,
            billing_month=month,
            partner_payment_paid=False,
        )
    )
    db_session.commit()

    original_set_status = RecurringMonthlyService._set_status

    def change_terms_before_lock(
        self: RecurringMonthlyService,
        contract_id: str,
        billing_month: str,
        *,
        tax_invoice_issued: bool | None = None,
        balance_paid: bool | None = None,
        partner_payment_paid: bool | None = None,
        expected_partner_id: str | None = None,
    ) -> tuple[RecurringMonthlyRowRead, Decimal | None]:
        current = self.contracts.get(contract_id, include_deleted=True)
        assert current is not None
        current.partner_payment_amount = Decimal("200000")
        self.db.flush()
        return original_set_status(
            self,
            contract_id,
            billing_month,
            tax_invoice_issued=tax_invoice_issued,
            balance_paid=balance_paid,
            partner_payment_paid=partner_payment_paid,
            expected_partner_id=expected_partner_id,
        )

    monkeypatch.setattr(RecurringMonthlyService, "_set_status", change_terms_before_lock)

    did_commit = False
    post_commit_selects: list[str] = []

    def mark_committed(session: Session) -> None:
        nonlocal did_commit
        if session is db_session:
            did_commit = True

    def record_post_commit_selects(*args) -> None:
        statement = args[2]
        if did_commit and statement.lstrip().upper().startswith("SELECT"):
            post_commit_selects.append(statement)

    bind = db_session.get_bind()
    event.listen(db_session, "after_commit", mark_committed)
    event.listen(bind, "before_cursor_execute", record_post_commit_selects)
    try:
        settled = PartnerSettlementService(db_session).set_recurring_monthly_paid(
            partner_id=partner_id,
            contract_id=contract.id,
            month=month,
            paid=True,
        )
    finally:
        event.remove(db_session, "after_commit", mark_committed)
        event.remove(bind, "before_cursor_execute", record_post_commit_selects)

    listed = next(
        row
        for row in RecurringPartnerBillingService(
            db_session
        ).list_monthly_settlement_rows(today=date(2026, 9, 4))
        if row.contract_id == contract.id and row.month == month
    )

    assert settled.partner_price == 200000
    assert post_commit_selects == []
    assert listed.amount == Decimal("200000")
