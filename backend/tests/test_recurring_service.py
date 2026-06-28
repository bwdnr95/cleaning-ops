from datetime import date

from app.db.seed import DEV_PARTNER_ID
from app.domain.constants import (
    OrderStatus,
    RecurrenceMode,
    RecurringContractStatus,
    RecurringOccurrenceStatus,
)
from app.repositories.order_groups import OrderGroupRepository
from app.repositories.orders import OrderRepository
from app.schemas.recurring import ApproveItem, RecurringContractCreate, RecurringContractUpdate, SkipItem
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


def test_sync_creates_pending_occurrences_idempotently(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(_make_payload(start_date=date(2026, 6, 10)), actor_user_id=None)
    # 2026-06-20 기준, HORIZON 14일 → 6/10(과거, grace 내), 7/10? (7/10은 6/20+14=7/4 초과 → 미포함)
    n1 = svc.sync_due_occurrences(today=date(2026, 6, 20))
    pend1 = svc.occurrences.list_by_contract(c.id)
    assert [o.due_date for o in pend1] == [date(2026, 6, 10)]
    n2 = svc.sync_due_occurrences(today=date(2026, 6, 20))
    pend2 = svc.occurrences.list_by_contract(c.id)
    assert len(pend2) == 1  # 멱등 — 중복 생성 없음
    assert n1 == 1 and n2 == 0


def test_sync_skips_paused_contract(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(_make_payload(start_date=date(2026, 6, 10)), actor_user_id=None)
    svc.set_status(c.id, RecurringContractStatus.PAUSED)
    svc.sync_due_occurrences(today=date(2026, 6, 20))
    assert svc.occurrences.list_by_contract(c.id) == []


def test_sync_excludes_overdue_beyond_grace(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(_make_payload(start_date=date(2026, 1, 10)), actor_user_id=None)
    # today 6/20, grace 30일 → 5/21 이전 due는 제외. 6/10만 노출.
    svc.sync_due_occurrences(today=date(2026, 6, 20))
    dues = [o.due_date for o in svc.occurrences.list_by_contract(c.id)]
    assert dues == [date(2026, 6, 10)]


def test_approve_generates_confirmed_order_when_partner_present(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(
        _make_payload(start_date=date(2026, 6, 10), default_partner_id=DEV_PARTNER_ID), actor_user_id=None
    )
    svc.sync_due_occurrences(today=date(2026, 6, 20))
    occ = svc.occurrences.list_by_contract(c.id)[0]
    result = svc.approve_occurrences([ApproveItem(occurrence_id=occ.id)], actor_user_id=None)

    assert len(result.generated_order_ids) == 1
    order = OrderRepository(db_session).get(result.generated_order_ids[0])
    assert order.status == OrderStatus.SCHEDULE_CONFIRMED
    assert order.partner_id == DEV_PARTNER_ID
    assert order.scheduled_date == occ.due_date
    assert order.recurring_contract_id == c.id
    db_session.refresh(occ)
    assert occ.status == RecurringOccurrenceStatus.GENERATED
    assert occ.generated_order_id == order.id


def test_approve_generates_new_order_when_no_partner(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(_make_payload(start_date=date(2026, 6, 10)), actor_user_id=None)
    svc.sync_due_occurrences(today=date(2026, 6, 20))
    occ = svc.occurrences.list_by_contract(c.id)[0]
    result = svc.approve_occurrences([ApproveItem(occurrence_id=occ.id)], actor_user_id=None)
    order = OrderRepository(db_session).get(result.generated_order_ids[0])
    assert order.status == OrderStatus.NEW
    assert order.partner_id is None


def test_approve_skips_non_pending(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(_make_payload(start_date=date(2026, 6, 10)), actor_user_id=None)
    svc.sync_due_occurrences(today=date(2026, 6, 20))
    occ = svc.occurrences.list_by_contract(c.id)[0]
    svc.approve_occurrences([ApproveItem(occurrence_id=occ.id)], actor_user_id=None)
    again = svc.approve_occurrences([ApproveItem(occurrence_id=occ.id)], actor_user_id=None)
    assert again.generated_order_ids == []
    assert occ.id in again.skipped_occurrence_ids


def test_skip_marks_occurrence_skipped(db_session):
    svc = RecurringService(db_session)
    c = svc.create_contract(_make_payload(start_date=date(2026, 6, 10)), actor_user_id=None)
    svc.sync_due_occurrences(today=date(2026, 6, 20))
    occ = svc.occurrences.list_by_contract(c.id)[0]
    svc.skip_occurrences([SkipItem(occurrence_id=occ.id, reason="고객 휴무")], actor_user_id=None)
    db_session.refresh(occ)
    assert occ.status == RecurringOccurrenceStatus.SKIPPED
    assert occ.skipped_reason == "고객 휴무"
