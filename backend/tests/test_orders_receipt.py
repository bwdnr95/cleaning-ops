"""증빙자료(receipt_type/receipt_status) 정규화 + 역할별 DTO 노출/차단 테스트."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.domain.constants import OrderStatus, ReceiptStatus, ReceiptType
from app.repositories.order_groups import OrderGroupRepository
from app.schemas.order import OrderGroupCreate, OrderLineCreate, OrderUpdate
from app.services.orders import (
    OrderService,
    to_admin_order_dto,
    to_customer_order_dto,
    to_partner_job_dto,
)
from tests.test_role_dtos import make_order


def _line(**over) -> OrderLineCreate:
    base = dict(
        status=OrderStatus.NEW,
        received_date=date(2026, 6, 1),
        service_name="입주청소",
    )
    base.update(over)
    return OrderLineCreate(**base)


def _new_group(svc: OrderService, line: OrderLineCreate):
    group = svc.create_group(
        OrderGroupCreate(
            customer_name="홍길동",
            customer_phone="01011112222",
            customer_address="서울특별시 강남구 테스트로 1",
            lines=[line],
        )
    )
    return OrderGroupRepository(svc.db).list_lines(group.id)[0]


def test_create_normalizes_none_receipt_to_not_applicable(db_session: Session) -> None:
    svc = OrderService(db_session)
    line = _new_group(
        svc,
        _line(receipt_type=ReceiptType.NONE, receipt_status=ReceiptStatus.ISSUED),
    )
    assert line.receipt_type == ReceiptType.NONE
    # 발급X면 발급 상태는 '해당없음'으로 강제된다.
    assert line.receipt_status == ReceiptStatus.NOT_APPLICABLE


def test_create_keeps_receipt_status_for_real_type(db_session: Session) -> None:
    svc = OrderService(db_session)
    line = _new_group(
        svc,
        _line(receipt_type=ReceiptType.CASH_RECEIPT, receipt_status=ReceiptStatus.PENDING),
    )
    assert line.receipt_type == ReceiptType.CASH_RECEIPT
    assert line.receipt_status == ReceiptStatus.PENDING


def test_update_forces_not_applicable_when_type_none(db_session: Session) -> None:
    svc = OrderService(db_session)
    line = _new_group(svc, _line())
    updated = svc.update(
        line.id,
        OrderUpdate(receipt_type=ReceiptType.NONE, receipt_status=ReceiptStatus.PENDING),
    )
    assert updated.receipt_type == ReceiptType.NONE
    assert updated.receipt_status == ReceiptStatus.NOT_APPLICABLE


def test_update_sets_receipt_for_real_type(db_session: Session) -> None:
    svc = OrderService(db_session)
    line = _new_group(svc, _line())
    updated = svc.update(
        line.id,
        OrderUpdate(receipt_type=ReceiptType.TAX_INVOICE, receipt_status=ReceiptStatus.ISSUED),
    )
    assert updated.receipt_type == ReceiptType.TAX_INVOICE
    assert updated.receipt_status == ReceiptStatus.ISSUED


def test_admin_dto_exposes_receipt_fields() -> None:
    order = make_order()
    order.vat_type = "included"  # make_order의 한글 기본값은 admin DTO enum에 부적합.
    order.receipt_type = "tax_invoice"
    order.receipt_status = "issued"
    payload = to_admin_order_dto(order).model_dump()
    assert payload["receipt_type"] == ReceiptType.TAX_INVOICE
    assert payload["receipt_status"] == ReceiptStatus.ISSUED


def test_partner_dto_hides_receipt_fields() -> None:
    order = make_order()
    order.receipt_type = "tax_invoice"
    order.receipt_status = "issued"
    payload = to_partner_job_dto(order).model_dump()
    assert "receipt_type" not in payload
    assert "receipt_status" not in payload


def test_customer_dto_hides_receipt_fields() -> None:
    order = make_order(customer_visible_payment=True)
    order.receipt_type = "tax_invoice"
    order.receipt_status = "issued"
    line = to_customer_order_dto(order).model_dump()["lines"][0]
    assert "receipt_type" not in line
    assert "receipt_status" not in line
