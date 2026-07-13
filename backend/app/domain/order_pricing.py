from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.order import Order


def order_consumer_total(order: Order) -> Decimal:
    """소비자가 총금액(VAT 포함) = total_amount + onsite_extra_amount.

    total_amount 는 현장추가를 제외한 소비자 기본가이고,
    onsite_extra_amount 는 현장에서 추가된 금액이다.
    고객 노출/내보내기/정산의 '소비자가/총금액'은 둘의 합을 사용한다.

    주의: 관리자 주문 DTO(`to_admin_order_dto`)의 consumer_price 는
    프론트가 onsite_extra 를 따로 더하므로 여기서 합치면 이중 계산된다.
    그 경로에는 적용하지 않는다.
    """
    base = order.total_amount or Decimal("0")
    extra = order.onsite_extra_amount or Decimal("0")
    return Decimal(str(base)) + Decimal(str(extra))
