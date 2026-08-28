from __future__ import annotations

from calendar import monthrange
from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import business_today, utc_now
from app.domain.constants import OrderStatus, TimelineEventType
from app.domain.order_pricing import order_consumer_total
from app.domain.payment_status import PARTNER_SETTLEMENT_PENDING_STATUSES, PartnerPaymentStatus
from app.models.order import Order
from app.models.order_group import OrderGroup
from app.repositories.order_groups import OrderGroupRepository
from app.repositories.partners import PartnerRepository
from app.repositories.recurring import (
    RecurringContractRepository,
    RecurringMonthlyStatusRepository,
)
from app.schemas.partner import (
    PartnerRecurringMonthlySettlementRead,
    PartnerSettlementActionResult,
    PartnerSettlementItemRead,
    PartnerSettlementListRead,
)
from app.services.recurring_monthly import RecurringMonthlyService
from app.services.recurring_partner_billing import (
    RecurringMonthlySettlementRow,
    RecurringPartnerBillingService,
    billing_month,
)
from app.services.timeline import TimelineService


def unpaid_partner_condition():
    """미정산 SQL 조건(전 화면 공통).

    1-1 정책: 서비스완료가 아니어도 정산할 수 있게, '도급가가 0보다 크고 아직 지급완료가 아닌'
    취소 아닌 주문을 미정산으로 본다(완료 요건 제거). 미정산 목록/합계/정산가능 집합 +
    프론트 canSettle(>0)까지 일치. 도급가 미입력(NULL·0)은 정산할 것이 없으므로 제외.
    """
    return (
        (Order.status != OrderStatus.CANCELLED)
        & (Order.partner_payment_amount > 0)
        & (
            Order.partner_payment_status.is_(None)
            | Order.partner_payment_status.in_(PARTNER_SETTLEMENT_PENDING_STATUSES)
        )
    )


class PartnerSettlementService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.partners = PartnerRepository(db)
        self.groups = OrderGroupRepository(db)
        self.recurring_contracts = RecurringContractRepository(db)
        self.partner_billing = RecurringPartnerBillingService(db)
        self.timeline = TimelineService(db)

    def list_settlements(
        self,
        *,
        partner_id: str,
        status: str = "unpaid",
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> PartnerSettlementListRead:
        self._require_partner(partner_id)
        orders = self._list_orders(
            partner_id=partner_id,
            status=status,
            from_date=from_date,
            to_date=to_date,
        )
        monthly_items = self._list_monthly_items(
            partner_id=partner_id,
            status=status,
            from_date=from_date,
            to_date=to_date,
        )
        groups_by_id = self.groups.list_by_ids(order.group_id for order in orders)
        group_totals = self._group_totals(order.group_id for order in orders)
        # 취소건은 목록(items)에는 남겨 기록을 보존하되, 건수/금액 집계에선 제외한다.
        countable = [order for order in orders if order.status != OrderStatus.CANCELLED]
        total_partner_price = sum(
            (money_decimal(order.partner_payment_amount) for order in countable),
            Decimal("0"),
        ) + sum((Decimal(str(item.partner_price)) for item in monthly_items), Decimal("0"))
        total_consumer_price = sum(
            (order_consumer_total(order) for order in countable),
            Decimal("0"),
        )
        items = [
            to_settlement_item(
                order,
                group=groups_by_id.get(order.group_id),
                group_totals=group_totals.get(order.group_id, (0.0, 0.0)),
            )
            for order in orders
        ]
        return PartnerSettlementListRead(
            items=items,
            monthly_items=monthly_items,
            total_partner_price=float(total_partner_price),
            total_consumer_price=float(total_consumer_price),
            count=len(countable) + len(monthly_items),
        )

    def _list_monthly_items(
        self,
        *,
        partner_id: str,
        status: str,
        from_date: date | None,
        to_date: date | None,
    ) -> list[PartnerRecurringMonthlySettlementRead]:
        """월 청구 정기계약의 계약×월 도급 지급 행.

        미지급 월은 **날짜 필터와 무관하게 항상 표시**한다 — 협력사 목록/상세의 미정산
        배지가 날짜 필터 없이 합산되므로, 여기서 기간으로 숨기면 "배지에는 있는데
        목록에는 없는" 모순이 재발한다(방문일 NULL 미정산 건과 같은 정책).
        지급 완료 월만 조회 기간(월 겹침 기준)을 적용한다.
        """
        # today는 이 모듈 경계에서 주입한다(배지 partners.py와 같은 시계 규율).
        rows = self.partner_billing.list_monthly_settlement_rows(
            partner_ids={partner_id}, today=business_today()
        )

        def in_range(row: RecurringMonthlySettlementRow) -> bool:
            month_end = row.month_start.replace(
                day=monthrange(row.month_start.year, row.month_start.month)[1]
            )
            if from_date is not None and month_end < from_date:
                return False
            if to_date is not None and row.month_start > to_date:
                return False
            return True

        if status == "unpaid":
            visible = [row for row in rows if not row.paid]
        elif status == "paid":
            visible = [row for row in rows if row.paid and in_range(row)]
        else:  # "all" — 상위에서 이미 검증됨
            visible = [row for row in rows if (not row.paid) or in_range(row)]
        # 최신 월 우선, 같은 월 안에서는 계약명 가나다순.
        visible.sort(key=lambda row: row.contract_label)
        visible.sort(key=lambda row: row.month_start, reverse=True)
        return [
            PartnerRecurringMonthlySettlementRead(
                contract_id=row.contract_id,
                contract_label=row.contract_label,
                month=row.month,
                month_start=row.month_start,
                partner_price=float(row.amount),
                paid=row.paid,
            )
            for row in visible
        ]

    def set_recurring_monthly_paid(
        self,
        *,
        partner_id: str,
        contract_id: str,
        month: str,
        paid: bool,
    ) -> PartnerRecurringMonthlySettlementRead:
        """협력사관리 화면에서 월정산 지급/되돌리기.

        월 트래커(정기청소 탭)와 같은 `RecurringMonthlyStatus.partner_payment_paid`
        행을 토글하므로 두 화면은 자동으로 동기화된다. 가드/락/동시성 검증은
        `RecurringMonthlyService.set_status`를 그대로 재사용한다(내부 commit 포함).
        """
        self._require_partner(partner_id)
        # 미래월은 set_status와 동일하게 거부한다(no-op 분기가 가드를 우회하지 않도록).
        if month > billing_month(business_today()):
            raise ValueError("recurring_month_not_editable")
        contract = self.recurring_contracts.get(contract_id, include_deleted=True)
        if contract is None:
            raise ValueError("recurring_contract_not_found")
        status_row = RecurringMonthlyStatusRepository(self.db).get_by_contract_and_month(
            contract_id, month
        )
        has_retained = (
            status_row is not None
            and status_row.retained_partner_payment_amount is not None
        )
        terms = self.partner_billing.resolve(contract, month)
        payable_partner_id = (
            status_row.retained_partner_id
            if has_retained and status_row is not None
            else terms.partner_id
        )
        if payable_partner_id != partner_id:
            raise ValueError("settlement_month_partner_mismatch")
        month_start = date(int(month[:4]), int(month[5:7]), 1)
        if not paid and (status_row is None or not status_row.partner_payment_paid):
            # 되돌릴 지급이 없으면 빈 status 행을 만들지 않고 그대로 반환(멱등 no-op).
            amount = (
                status_row.retained_partner_payment_amount
                if has_retained and status_row is not None
                else terms.partner_payment_amount
            )
            return PartnerRecurringMonthlySettlementRead(
                contract_id=contract_id,
                contract_label=contract.label,
                month=month,
                month_start=month_start,
                partner_price=float(amount or 0),
                paid=False,
            )
        # expected_partner_id: 락 획득 후 지급 대상을 재검증한다(위 사전 검사만으로는
        # 그 사이 담당 협력사가 바뀌는 TOCTOU를 못 막는다).
        row = RecurringMonthlyService(self.db).set_status(
            contract_id,
            month,
            partner_payment_paid=paid,
            expected_partner_id=partner_id,
        )
        return PartnerRecurringMonthlySettlementRead(
            contract_id=contract_id,
            contract_label=contract.label,
            month=month,
            month_start=month_start,
            partner_price=float(row.partner_amount or 0),
            paid=bool(row.partner_payment_paid),
        )

    def settle(
        self,
        *,
        partner_id: str,
        order_ids: list[str],
        actor_user_id: str,
        memo: str | None = None,
    ) -> PartnerSettlementActionResult:
        self._require_partner(partner_id, for_update=True)
        orders = self._lock_orders(
            partner_id=partner_id,
            order_ids=order_ids,
            action="settle",
        )
        now = utc_now()
        for order in orders:
            order.partner_payment_status = PartnerPaymentStatus.PAID
            order.partner_settled_at = now
            self.timeline.record(
                order_id=order.id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.PARTNER_SETTLED,
                title="협력사 정산 완료",
                description=memo,
                metadata={"partner_id": partner_id, "settled_at": now.isoformat()},
            )
        return PartnerSettlementActionResult(
            updated_order_ids=[order.id for order in orders],
            skipped_order_ids=[],
        )

    def revert(
        self,
        *,
        partner_id: str,
        order_ids: list[str],
        actor_user_id: str,
    ) -> PartnerSettlementActionResult:
        self._require_partner(partner_id, for_update=True)
        orders = self._lock_orders(
            partner_id=partner_id,
            order_ids=order_ids,
            action="revert",
        )
        for order in orders:
            order.partner_payment_status = PartnerPaymentStatus.UNPAID
            order.partner_settled_at = None
            self.timeline.record(
                order_id=order.id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.PARTNER_SETTLEMENT_REVERTED,
                title="협력사 정산 되돌리기",
                metadata={"partner_id": partner_id},
            )
        return PartnerSettlementActionResult(
            updated_order_ids=[order.id for order in orders],
            skipped_order_ids=[],
        )

    def _group_totals(self, group_ids: Iterable[str]) -> dict[str, tuple[float, float]]:
        """결과에 포함된 각 그룹(고객)의 합계(취소·삭제 제외)를 (소비자가, 도급가)로 계산.

        0원 라인 보조표시용 — 한 그룹에 금액이 한 라인에만 입력돼 다른 라인이
        0원으로 보일 때, 그 라인이 속한 그룹 총액을 함께 노출하기 위함이다.
        """
        totals: dict[str, tuple[float, float]] = {}
        for group_id in {gid for gid in group_ids if gid}:
            lines = self.groups.list_lines(group_id)  # 삭제 제외
            settleable = [line for line in lines if line.status != OrderStatus.CANCELLED]
            consumer = sum((order_consumer_total(line) for line in settleable), Decimal("0"))
            partner = sum(
                (money_decimal(line.partner_payment_amount) for line in settleable),
                Decimal("0"),
            )
            totals[group_id] = (float(consumer), float(partner))
        return totals

    def _require_partner(self, partner_id: str, *, for_update: bool = False) -> None:
        partner = (
            self.partners.get_for_update(partner_id)
            if for_update
            else self.partners.get(partner_id)
        )
        if partner is None:
            raise ValueError("partner_not_found")
        if not partner.is_active:
            raise ValueError("partner_inactive")

    def _list_orders(
        self,
        *,
        partner_id: str,
        status: str,
        from_date: date | None,
        to_date: date | None,
    ) -> list[Order]:
        stmt = (
            select(Order)
            .where(
                Order.partner_id == partner_id,
                Order.deleted_at.is_(None),
            )
            .order_by(Order.scheduled_date.desc().nulls_last(), Order.id.desc())
        )
        if from_date is not None:
            stmt = stmt.where(Order.scheduled_date >= from_date)
        if to_date is not None:
            stmt = stmt.where(Order.scheduled_date <= to_date)
        if status == "unpaid":
            stmt = stmt.where(unpaid_partner_condition())
        elif status == "paid":
            stmt = stmt.where(
                Order.status != OrderStatus.CANCELLED,
                Order.partner_payment_status == PartnerPaymentStatus.PAID,
            )
        elif status == "all":
            # '전체'는 이 협력사에 배정된 모든 작업(상태 무관, 취소 포함)을 보여준다.
            # 운영자가 "배정 작업이 있는데 안 뜬다"고 한 문제(완료-미지급만 보이던 것) 해결.
            pass
        else:
            raise ValueError("invalid_settlement_status")
        orders = list(self.db.scalars(stmt))
        if status in {"unpaid", "paid"}:
            orders = [
                order
                for order in orders
                if self.partner_billing.allows_order_settlement(order)
            ]
        return orders

    def _lock_orders(self, *, partner_id: str, order_ids: list[str], action: str) -> list[Order]:
        if not order_ids:
            return []
        requested_ids = list(dict.fromkeys(order_ids))
        order_contract_rows = self.db.execute(
            select(Order.id, Order.recurring_contract_id).where(
                Order.id.in_(requested_ids),
                Order.deleted_at.is_(None),
            )
        ).all()
        contract_by_order_id = {
            order_id: recurring_contract_id
            for order_id, recurring_contract_id in order_contract_rows
        }
        if any(order_id not in contract_by_order_id for order_id in requested_ids):
            raise ValueError("settlement_order_not_found")
        self.recurring_contracts.lock_ids(
            [
                contract_id
                for contract_id in contract_by_order_id.values()
                if contract_id is not None
            ]
        )
        stmt = (
            select(Order)
            .where(
                Order.id.in_(requested_ids),
                Order.deleted_at.is_(None),
            )
            .order_by(Order.id.asc())
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        orders = list(self.db.scalars(stmt))
        by_id = {order.id: order for order in orders}
        if any(order_id not in by_id for order_id in requested_ids):
            raise ValueError("settlement_order_not_found")
        if any(order.partner_id != partner_id for order in orders):
            raise ValueError("settlement_order_partner_mismatch")
        if action in {"settle", "revert"} and any(
            not self.partner_billing.allows_order_settlement(order)
            for order in orders
        ):
            raise ValueError("invalid_settlement_order")
        if action == "settle" and any(not is_unpaid_partner_order(order) for order in orders):
            raise ValueError("invalid_settlement_order")
        if action == "revert" and any(not is_revertible_partner_order(order) for order in orders):
            raise ValueError("invalid_settlement_order")
        if action not in {"settle", "revert"}:
            raise ValueError("invalid_settlement_action")
        return [by_id[order_id] for order_id in requested_ids]


def to_settlement_item(
    order: Order,
    *,
    group: OrderGroup | None = None,
    group_totals: tuple[float, float] = (0.0, 0.0),
) -> PartnerSettlementItemRead:
    # 정산 확인을 쉽게 하려고 기본주소 + 상세주소까지 모두 노출한다.
    base_address = (group.customer_address if group else None) or order.customer_address or ""
    address_detail = group.customer_address_detail if group else None
    return PartnerSettlementItemRead(
        order_id=order.id,
        status=order.status,
        scheduled_date=order.scheduled_date,
        service_name=order.service_name,
        customer_name=order.customer_name or "",
        address_short=base_address,
        address_detail=address_detail,
        consumer_price=float(order_consumer_total(order)),
        partner_price=float(order.partner_payment_amount or 0),
        partner_payment_status=order.partner_payment_status,
        settled_at=order.partner_settled_at,
        group_consumer_total=group_totals[0],
        group_partner_total=group_totals[1],
    )


def is_unpaid_partner_order(order: Order) -> bool:
    # 1-1: 미정산 가시성(unpaid_partner_condition)과 동일 기준. 서비스완료 요건 없이
    # 도급가 > 0 + 미지급 + 취소 아님이면 정산 실행 가능.
    return (
        order.deleted_at is None
        and order.status != OrderStatus.CANCELLED
        and (order.partner_payment_amount or 0) > 0
        and (
            order.partner_payment_status is None
            or order.partner_payment_status in PARTNER_SETTLEMENT_PENDING_STATUSES
        )
    )


def is_revertible_partner_order(order: Order) -> bool:
    return (
        order.deleted_at is None
        and order.status != OrderStatus.CANCELLED
        and order.partner_payment_status == PartnerPaymentStatus.PAID
    )


def money_decimal(value: object) -> Decimal:
    return Decimal(str(value or 0))
