from datetime import date

import pytest
from sqlalchemy import func, select

from app.core.time import business_today
from app.db.seed import DEV_PARTNER_ID
from app.domain.constants import RecurrenceMode, RecurringContractStatus
from app.models import OrderGroup
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


def test_create_contract_creates_group_and_current_month_order(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(_make_payload(), actor_user_id=None)
    today = business_today()

    assert c.status == RecurringContractStatus.ACTIVE
    assert c.order_group_id
    lines = OrderGroupRepository(db_session).list_lines(c.order_group_id)
    assert len(lines) == 1
    assert lines[0].recurring_contract_id == c.id
    assert lines[0].recurring_planned_date == date(today.year, today.month, 10)


def test_update_contract_changes_future_template(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(_make_payload(), actor_user_id=None)
    svc.update_contract(c.id, RecurringContractUpdate(total_amount=200000), actor_user_id=None)
    assert svc.get_contract(c.id).total_amount == 200000


def test_update_contract_rejects_invalid_mode_switch(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(_make_payload(), actor_user_id=None)  # monthly, day_of_month=10
    # weekly로 전환하는데 interval_weeks를 주지 않으면 거부되어야 한다.
    with pytest.raises(ValueError, match="invalid_recurrence_fields"):
        svc.update_contract(
            c.id, RecurringContractUpdate(recurrence_mode=RecurrenceMode.WEEKLY), actor_user_id=None
        )
    # 잘못된 전환이 저장되지 않았는지(롤백) 확인
    again = svc.get_contract(c.id)
    assert again.recurrence_mode == RecurrenceMode.MONTHLY
    assert again.day_of_month == 10


def test_update_contract_allows_valid_mode_switch(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(_make_payload(), actor_user_id=None)
    svc.update_contract(
        c.id,
        RecurringContractUpdate(recurrence_mode=RecurrenceMode.WEEKLY, interval_weeks=2),
        actor_user_id=None,
    )
    again = svc.get_contract(c.id)
    assert again.recurrence_mode == RecurrenceMode.WEEKLY
    assert again.interval_weeks == 2


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


def test_create_contract_unknown_partner_no_orphan_group(db_session):
    svc = RecurringService(db_session)
    before = db_session.scalar(select(func.count()).select_from(OrderGroup))
    with pytest.raises(ValueError, match="partner_not_found"):
        svc.create_contract(_make_payload(default_partner_id="no-such-partner"), actor_user_id=None)
    db_session.rollback()
    after = db_session.scalar(select(func.count()).select_from(OrderGroup))
    assert after == before  # 고아 그룹이 생성되지 않아야 한다


def test_update_contract_unknown_partner_raises(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(_make_payload(), actor_user_id=None)
    with pytest.raises(ValueError, match="partner_not_found"):
        svc.update_contract(
            c.id, RecurringContractUpdate(default_partner_id="nonexistent"), actor_user_id=None
        )


def test_update_contract_valid_partner_ok(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(_make_payload(), actor_user_id=None)
    svc.update_contract(
        c.id, RecurringContractUpdate(default_partner_id=DEV_PARTNER_ID), actor_user_id=None
    )
    assert svc.get_contract(c.id).default_partner_id == DEV_PARTNER_ID


def test_update_contract_normalizes_customer_phone(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(_make_payload(), actor_user_id=None)
    svc.update_contract(
        c.id, RecurringContractUpdate(customer_phone="010-1111-3333"), actor_user_id=None
    )
    group = OrderGroupRepository(db_session).get(c.order_group_id)
    assert group.customer_phone == "01011113333"


def test_create_weekly_contract_with_weekdays_stores_and_restores_csv(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(
        RecurringContractCreate(
            label="다중요일", customer_name="강남", customer_phone="01011112222",
            customer_address="A", recurrence_mode=RecurrenceMode.WEEKLY, interval_weeks=1,
            weekdays=[0, 2, 4], start_date=date(2026, 6, 1), service_name="청소",
            total_amount=100000,
        ),
        actor_user_id=None,
    )
    assert svc.get_contract(c.id).weekdays == "0,2,4"  # CSV로 저장
    read = svc.to_contract_read(c)
    assert read.weekdays == [0, 2, 4]                  # list로 복원


def test_schedule_text_weekly_multiple(db_session):
    svc = RecurringService(db_session)
    svc.create_contract(
        RecurringContractCreate(
            label="x", customer_name="c", customer_phone="01000000000", customer_address="A",
            recurrence_mode=RecurrenceMode.WEEKLY, interval_weeks=1, weekdays=[0, 2, 4],
            start_date=date(2026, 6, 1), service_name="청소",
        ),
        actor_user_id=None,
    )
    assert svc.list_contract_summaries()[0].schedule_text == "매주 월·수·금"
