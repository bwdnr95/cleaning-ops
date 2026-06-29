from datetime import date
from uuid import uuid4

from app.domain.constants import RecurrenceMode, RecurringContractStatus
from app.models.order_group import OrderGroup
from app.models.recurring_contract import RecurringContract


def test_contract_persists_weekdays_csv(db_session):
    group = OrderGroup(
        id=str(uuid4()), customer_token=f"t-{uuid4()}", customer_name="C",
        customer_phone="01000000000", customer_address="A", customer_visible_payment=False,
    )
    db_session.add(group)
    db_session.flush()
    c = RecurringContract(
        id=str(uuid4()), label="L", order_group_id=group.id, recurrence_mode=RecurrenceMode.WEEKLY,
        interval_weeks=1, weekdays="0,2,4", start_date=date(2026, 6, 1),
        status=RecurringContractStatus.ACTIVE, service_name="S",
    )
    db_session.add(c)
    db_session.flush()
    assert c.weekdays == "0,2,4"
