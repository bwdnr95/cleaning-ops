from datetime import date
from uuid import uuid4

from app.domain.constants import RecurrenceMode, RecurringContractStatus
from app.models.order_group import OrderGroup
from app.models.recurring_contract import RecurringContract
from app.models.recurring_monthly_status import RecurringMonthlyStatus
from app.repositories.recurring import RecurringMonthlyStatusRepository


def _contract(db):
    g = OrderGroup(id=str(uuid4()), customer_token=f"t-{uuid4()}", customer_name="강남",
                   customer_phone="01011112222", customer_address="A", customer_visible_payment=False)
    db.add(g); db.flush()
    c = RecurringContract(id=str(uuid4()), label="L", order_group_id=g.id,
                          recurrence_mode=RecurrenceMode.MONTHLY, day_of_month=10, start_date=date(2026, 6, 10),
                          status=RecurringContractStatus.ACTIVE, service_name="청소", total_amount=150000)
    db.add(c); db.flush()
    return c


def test_monthly_status_persists_and_lookup(db_session):
    repo = RecurringMonthlyStatusRepository(db_session)
    c = _contract(db_session)
    repo.add(RecurringMonthlyStatus(id=str(uuid4()), contract_id=c.id, billing_month="2026-06"))
    db_session.flush()
    found = repo.get_by_contract_and_month(c.id, "2026-06")
    assert found is not None and found.tax_invoice_issued is False and found.balance_paid is False
    assert repo.get_by_contract_and_month(c.id, "2026-07") is None
