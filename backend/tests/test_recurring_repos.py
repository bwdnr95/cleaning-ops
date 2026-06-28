from datetime import date
from uuid import uuid4

from app.domain.constants import RecurrenceMode, RecurringContractStatus, RecurringOccurrenceStatus
from app.models.order_group import OrderGroup
from app.models.recurring_contract import RecurringContract
from app.models.recurring_occurrence import RecurringOccurrence
from app.repositories.recurring import RecurringContractRepository, RecurringOccurrenceRepository


def _contract(db, *, status=RecurringContractStatus.ACTIVE, deleted=False):
    group = OrderGroup(
        id=str(uuid4()), customer_token=f"tok-{uuid4()}", customer_name="C",
        customer_phone="01000000000", customer_address="A", customer_visible_payment=False,
    )
    db.add(group)
    db.flush()
    c = RecurringContract(
        id=str(uuid4()), label="L", order_group_id=group.id, recurrence_mode=RecurrenceMode.MONTHLY,
        day_of_month=10, start_date=date(2026, 6, 10), status=status, service_name="S",
        deleted_at=(date(2026, 1, 1) and None),
    )
    if deleted:
        from app.core.time import utc_now
        c.deleted_at = utc_now()
    db.add(c)
    db.flush()
    return c


def test_contract_get_hides_soft_deleted(db_session):
    repo = RecurringContractRepository(db_session)
    c = _contract(db_session, deleted=True)
    assert repo.get(c.id) is None
    assert repo.get(c.id, include_deleted=True) is not None


def test_list_active_excludes_paused_and_deleted(db_session):
    repo = RecurringContractRepository(db_session)
    active = _contract(db_session)
    _contract(db_session, status=RecurringContractStatus.PAUSED)
    _contract(db_session, deleted=True)
    ids = [c.id for c in repo.list_active()]
    assert active.id in ids
    assert len(ids) == 1


def test_occurrence_get_by_contract_and_due(db_session):
    orepo = RecurringOccurrenceRepository(db_session)
    c = _contract(db_session)
    occ = RecurringOccurrence(
        id=str(uuid4()), contract_id=c.id, sequence_no=1, due_date=date(2026, 6, 10),
        billing_month="2026-06", status=RecurringOccurrenceStatus.PENDING,
    )
    orepo.add(occ)
    db_session.flush()
    found = orepo.get_by_contract_and_due(c.id, date(2026, 6, 10))
    assert found is not None and found.id == occ.id
    assert orepo.get_by_contract_and_due(c.id, date(2026, 7, 10)) is None
