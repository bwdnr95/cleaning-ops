from datetime import date
from uuid import uuid4

from app.domain.constants import RecurrenceMode, RecurringContractStatus, RecurringOccurrenceStatus
from app.models.order_group import OrderGroup
from app.models.recurring_contract import RecurringContract
from app.models.recurring_occurrence import RecurringOccurrence


def test_models_persist_and_relate(db_session):
    group = OrderGroup(
        id=str(uuid4()), customer_token=f"tok-{uuid4()}", customer_name="강남빌딩",
        customer_phone="01011112222", customer_address="서울 강남구 1", customer_visible_payment=False,
    )
    db_session.add(group)
    db_session.flush()

    contract = RecurringContract(
        id=str(uuid4()), label="강남빌딩 정기청소", order_group_id=group.id,
        recurrence_mode=RecurrenceMode.MONTHLY, day_of_month=10, start_date=date(2026, 6, 10),
        status=RecurringContractStatus.ACTIVE, service_name="사무실 정기청소", total_amount=150000,
    )
    db_session.add(contract)
    db_session.flush()

    occ = RecurringOccurrence(
        id=str(uuid4()), contract_id=contract.id, sequence_no=1, due_date=date(2026, 6, 10),
        billing_month="2026-06", status=RecurringOccurrenceStatus.PENDING,
    )
    db_session.add(occ)
    db_session.flush()

    assert contract.deleted_at is None
    assert occ.contract_id == contract.id
