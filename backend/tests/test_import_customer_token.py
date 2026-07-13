from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.constants import OrderStatus
from app.models.order import Order
from app.models.order_group import OrderGroup
from scripts.import_cleanjob_spreadsheet import ParsedOrder, apply_rows


def test_legacy_import_uses_current_customer_token_generator(db_session: Session) -> None:
    row = ParsedOrder(
        sheet="SERVICE ORDERS",
        sheet_slug="svc",
        row_index=999,
        order_id="legacy-token-import-order",
        preferred_group_id="legacy-token-import-group",
        status=OrderStatus.NEW,
        received_date=date(2030, 1, 1),
        scheduled_date=None,
        requested_time=None,
        team_name=None,
        service_name="입주청소",
        size_or_quantity=None,
        service_detail=None,
        special_request=None,
        source_channel="legacy",
        customer_name="토큰 고객",
        customer_phone="01012345678",
        customer_address="서울",
        total_amount=Decimal("100000"),
        discount_amount=Decimal("0"),
        deposit_amount=None,
        balance_amount=Decimal("100000"),
        onsite_extra_amount=None,
        vat_type=None,
        payment_status=None,
        payment_memo=None,
        evidence_memo=None,
        partner_name=None,
        partner_payment_amount=None,
        partner_payment_status=None,
        partner_settled_at=None,
    )

    apply_rows(db_session, [row])
    db_session.flush()

    group = db_session.get(OrderGroup, row.preferred_group_id)
    order = db_session.get(Order, row.order_id)
    assert group is not None
    assert order is not None
    assert group.customer_token.startswith("ct2_")
    assert order.customer_token == group.customer_token
