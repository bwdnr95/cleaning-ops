from datetime import date

from app.domain.constants import RecurrenceMode, RecurringContractStatus
from app.repositories.order_groups import OrderGroupRepository
from app.schemas.recurring import RecurringContractCreate, RecurringContractUpdate
from app.services.recurring import RecurringService


def _make_payload(**over):
    base = dict(
        label="강남빌딩 정기청소", customer_name="강남빌딩", customer_phone="01011112222",
        customer_address="서울 강남구 1", recurrence_mode=RecurrenceMode.MONTHLY, day_of_month=10,
        start_date=date(2026, 6, 10), service_name="사무실 정기청소", total_amount=150000,
    )
    base.update(over)
    return RecurringContractCreate(**base)


def test_create_contract_creates_empty_group(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(_make_payload(), actor_user_id=None)
    assert c.status == RecurringContractStatus.ACTIVE
    assert c.order_group_id
    assert OrderGroupRepository(db_session).list_lines(c.order_group_id) == []


def test_update_contract_changes_future_template(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(_make_payload(), actor_user_id=None)
    svc.update_contract(c.id, RecurringContractUpdate(total_amount=200000), actor_user_id=None)
    assert svc.get_contract(c.id).total_amount == 200000


def test_pause_and_resume_and_end(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(_make_payload(), actor_user_id=None)
    svc.set_status(c.id, RecurringContractStatus.PAUSED)
    assert svc.get_contract(c.id).status == RecurringContractStatus.PAUSED
    svc.set_status(c.id, RecurringContractStatus.ACTIVE)
    assert svc.get_contract(c.id).status == RecurringContractStatus.ACTIVE


def test_soft_delete_hides_contract_but_keeps_group(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(_make_payload(), actor_user_id=None)
    gid = c.order_group_id
    svc.delete_contract(c.id, actor_user_id=None)
    assert svc.get_contract(c.id) is None
    assert OrderGroupRepository(db_session).get(gid) is not None
