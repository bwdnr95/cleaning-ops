"""협력사 담당자 연락처(manager_phone) 정규화 + 정산 안내 수신처 정책 테스트."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.domain.constants import MessageType, RecipientType
from app.repositories.order_groups import OrderGroupRepository
from app.schemas.message import MessageSendRequest
from app.schemas.order import OrderGroupCreate, OrderLineCreate
from app.schemas.partner import PartnerCreate, PartnerUpdate
from app.services.messages import MessageService
from app.services.orders import OrderService
from app.services.partners import PartnerService


def _partner(svc: PartnerService, **over):
    base = dict(name="청소왕", phone="010-1111-2222")
    base.update(over)
    return svc.create(PartnerCreate(**base))


def _order_for_partner(db_session: Session, partner_id: str):
    osvc = OrderService(db_session)
    group = osvc.create_group(
        OrderGroupCreate(
            customer_name="홍길동",
            customer_phone="01055556666",
            customer_address="서울특별시 강남구 테스트로 1",
            lines=[
                OrderLineCreate(
                    received_date=date(2026, 6, 1),
                    service_name="입주청소",
                    partner_id=partner_id,
                )
            ],
        )
    )
    return OrderGroupRepository(db_session).list_lines(group.id)[0]


def _recipient(db_session: Session, order, message_type):
    msvc = MessageService(db_session)
    return msvc._resolve_recipient(
        order,
        MessageSendRequest(order_id=order.id, message_type=message_type, recipient_type=RecipientType.PARTNER),
    )


def test_create_normalizes_manager_phone(db_session: Session) -> None:
    detail = _partner(PartnerService(db_session), manager_phone="010-3333-4444")
    assert detail.manager_phone == "01033334444"


def test_create_without_manager_phone_is_none(db_session: Session) -> None:
    detail = _partner(PartnerService(db_session))
    assert detail.manager_phone is None


def test_update_sets_manager_phone(db_session: Session) -> None:
    svc = PartnerService(db_session)
    detail = _partner(svc)
    updated = svc.update(detail.id, PartnerUpdate(manager_phone="010-9999-8888"))
    assert updated.manager_phone == "01099998888"


def test_customer_info_prefers_manager_phone(db_session: Session) -> None:
    detail = _partner(PartnerService(db_session), manager_phone="010-3333-4444")
    order = _order_for_partner(db_session, detail.id)
    _, _, phone = _recipient(db_session, order, MessageType.PARTNER_CUSTOMER_INFO)
    assert phone == "01033334444"


def test_customer_info_falls_back_to_rep_phone(db_session: Session) -> None:
    detail = _partner(PartnerService(db_session))  # 담당자 연락처 없음
    order = _order_for_partner(db_session, detail.id)
    _, _, phone = _recipient(db_session, order, MessageType.PARTNER_CUSTOMER_INFO)
    assert phone == "01011112222"


def test_assignment_uses_rep_phone(db_session: Session) -> None:
    detail = _partner(PartnerService(db_session), manager_phone="010-3333-4444")
    order = _order_for_partner(db_session, detail.id)
    _, _, phone = _recipient(db_session, order, MessageType.PARTNER_ASSIGNMENT)
    # 배정 안내는 담당자 연락처가 있어도 대표 연락처로 발송.
    assert phone == "01011112222"
