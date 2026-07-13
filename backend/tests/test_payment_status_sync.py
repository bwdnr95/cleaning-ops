from datetime import date
from uuid import uuid4

from app.domain.constants import OrderStatus
from app.domain.payment_status import PaymentStatus
from app.models.order import Order
from app.models.order_group import OrderGroup
from app.schemas.order import OrderUpdate
from app.services.orders import OrderService


def _order(db, *, status, payment_status=None):
    group = OrderGroup(
        id=str(uuid4()), customer_token=f"t-{uuid4()}", customer_name="C",
        customer_phone="01000000000", customer_address="A", customer_visible_payment=False,
    )
    db.add(group)
    db.flush()
    o = Order(
        id=str(uuid4()), group_id=group.id, status=status, received_date=date(2026, 6, 1),
        service_name="S", payment_status=payment_status, customer_token=group.customer_token,
        customer_name="C", customer_phone="01000000000", customer_address="A",
    )
    db.add(o)
    db.flush()
    return o


def test_paid_auto_completes_from_scheduled(db_session):
    o = _order(db_session, status=OrderStatus.SCHEDULE_CONFIRMED, payment_status=PaymentStatus.UNPAID)
    OrderService(db_session).update(o.id, OrderUpdate(payment_status=PaymentStatus.PAID), actor_user_id="admin")
    db_session.refresh(o)
    assert o.status == OrderStatus.COMPLETED


def test_paid_respects_explicit_status_in_same_request(db_session):
    o = _order(db_session, status=OrderStatus.SCHEDULE_CONFIRMED, payment_status=PaymentStatus.UNPAID)
    OrderService(db_session).update(
        o.id, OrderUpdate(payment_status=PaymentStatus.PAID, status=OrderStatus.SCHEDULE_CONFIRMED),
        actor_user_id="admin",
    )
    db_session.refresh(o)
    assert o.status == OrderStatus.SCHEDULE_CONFIRMED  # #2 미발동


def test_paid_does_not_resurrect_cancelled(db_session):
    o = _order(db_session, status=OrderStatus.CANCELLED, payment_status=PaymentStatus.UNPAID)
    OrderService(db_session).update(o.id, OrderUpdate(payment_status=PaymentStatus.PAID), actor_user_id="admin")
    db_session.refresh(o)
    assert o.status == OrderStatus.CANCELLED


def test_paid_does_not_complete_order_while_as_intake_is_pending(db_session):
    o = _order(
        db_session,
        status=OrderStatus.CUSTOMER_DELIVERY_DONE,
        payment_status=PaymentStatus.UNPAID,
    )
    o.as_intake_pending = True
    db_session.commit()

    OrderService(db_session).update(
        o.id,
        OrderUpdate(payment_status=PaymentStatus.PAID),
        actor_user_id="admin",
    )

    db_session.refresh(o)
    assert o.status == OrderStatus.CUSTOMER_DELIVERY_DONE
    assert o.payment_status == PaymentStatus.PAID


def test_completed_auto_marks_paid(db_session):
    o = _order(db_session, status=OrderStatus.CUSTOMER_DELIVERY_DONE, payment_status=PaymentStatus.UNPAID)
    OrderService(db_session).update(o.id, OrderUpdate(status=OrderStatus.COMPLETED), actor_user_id="admin")
    db_session.refresh(o)
    assert o.payment_status == PaymentStatus.PAID


def test_completed_respects_explicit_payment_in_same_request(db_session):
    o = _order(db_session, status=OrderStatus.CUSTOMER_DELIVERY_DONE, payment_status=PaymentStatus.UNPAID)
    OrderService(db_session).update(
        o.id, OrderUpdate(status=OrderStatus.COMPLETED, payment_status=PaymentStatus.UNPAID),
        actor_user_id="admin",
    )
    db_session.refresh(o)
    assert o.payment_status == PaymentStatus.UNPAID  # #3 미발동


def test_completed_does_not_override_refunded(db_session):
    o = _order(db_session, status=OrderStatus.CUSTOMER_DELIVERY_DONE, payment_status=PaymentStatus.REFUNDED)
    OrderService(db_session).update(o.id, OrderUpdate(status=OrderStatus.COMPLETED), actor_user_id="admin")
    db_session.refresh(o)
    assert o.payment_status == PaymentStatus.REFUNDED
