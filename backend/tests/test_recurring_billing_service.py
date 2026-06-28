from datetime import date

from app.db.seed import DEV_PARTNER_ID
from app.domain.constants import OrderStatus
from app.domain.payment_status import PartnerPaymentStatus, PaymentStatus
from app.repositories.orders import OrderRepository
from app.schemas.recurring import RecurringContractCreate
from app.services.recurring import RecurringService
from app.services.recurring_billing import RecurringBillingService


def _contract_with_order(db, *, status, payment_status, partner_payment_status, partner_id=DEV_PARTNER_ID):
    rsvc = RecurringService(db)
    c = rsvc.create_contract(
        RecurringContractCreate(
            label="L", customer_name="강남", customer_phone="01011112222", customer_address="A",
            recurrence_mode="monthly", day_of_month=10, start_date=date(2026, 6, 10),
            service_name="청소", total_amount=100000, partner_payment_amount=60000,
        ),
        actor_user_id=None,
    )
    rsvc.sync_due_occurrences(today=date(2026, 6, 20))
    occ = rsvc.occurrences.list_by_contract(c.id)[0]
    from app.schemas.recurring import ApproveItem
    res = rsvc.approve_occurrences([ApproveItem(occurrence_id=occ.id)], actor_user_id=None)
    order = OrderRepository(db).get(res.generated_order_ids[0])
    order.status = status
    order.payment_status = payment_status
    order.partner_payment_status = partner_payment_status
    order.partner_id = partner_id
    db.commit()
    return c, order


def test_month_summary_aggregates_per_contract(db_session):
    c, order = _contract_with_order(
        db_session, status=OrderStatus.COMPLETED, payment_status=PaymentStatus.PAID,
        partner_payment_status=PartnerPaymentStatus.UNPAID,
    )
    rows = RecurringBillingService(db_session).month_summary("2026-06")
    row = next(r for r in rows if r.contract_id == c.id)
    assert row.visit_count == 1
    assert row.billed_total == 100000
    assert row.confirmed_revenue == 100000
    assert row.partner_total == 60000
    assert row.unpaid_partner_count == 1  # COMPLETED + UNPAID


def test_mark_month_paid_sets_unpaid_orders_to_paid(db_session):
    c, order = _contract_with_order(
        db_session, status=OrderStatus.COMPLETED, payment_status=PaymentStatus.UNPAID,
        partner_payment_status=PartnerPaymentStatus.PAID,
    )
    res = RecurringBillingService(db_session).mark_month_paid(c.id, "2026-06", actor_user_id="admin")
    assert order.id in res.updated_order_ids
    db_session.refresh(order)
    assert order.payment_status == PaymentStatus.PAID


def test_settle_month_only_completed_unpaid(db_session):
    c, order = _contract_with_order(
        db_session, status=OrderStatus.COMPLETED, payment_status=PaymentStatus.PAID,
        partner_payment_status=PartnerPaymentStatus.UNPAID,
    )
    res = RecurringBillingService(db_session).settle_month(c.id, "2026-06", actor_user_id="admin")
    assert order.id in res.settled_order_ids
    db_session.refresh(order)
    assert order.partner_payment_status == PartnerPaymentStatus.PAID
    assert order.partner_settled_at is not None


def test_settle_month_skips_incomplete(db_session):
    c, order = _contract_with_order(
        db_session, status=OrderStatus.IN_PROGRESS, payment_status=PaymentStatus.PAID,
        partner_payment_status=PartnerPaymentStatus.UNPAID,
    )
    res = RecurringBillingService(db_session).settle_month(c.id, "2026-06", actor_user_id="admin")
    assert res.settled_order_ids == []
    assert res.skipped_count == 1
