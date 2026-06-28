from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.payment_status import PaymentStatus
from app.domain.recurring_billing import aggregate_orders
from app.models.recurring_contract import RecurringContract
from app.repositories.order_groups import OrderGroupRepository
from app.repositories.orders import OrderRepository
from app.repositories.partners import PartnerRepository
from app.repositories.recurring import RecurringContractRepository
from app.schemas.order import OrderUpdate
from app.schemas.recurring_billing import (
    MarkPaidResult,
    PartnerSubtotalRead,
    RecurringBillingRowRead,
    SettleMonthResult,
)
from app.services.order_export import OrderExportService, OrderExportTable
from app.services.orders import OrderService
from app.services.partner_settlements import PartnerSettlementService, is_unpaid_partner_order

_ALREADY_PAID = (PaymentStatus.PAID, PaymentStatus.REFUNDED)


class RecurringBillingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.orders = OrderRepository(db)
        self.contracts = RecurringContractRepository(db)
        self.partners = PartnerRepository(db)
        self.groups = OrderGroupRepository(db)

    def month_summary(self, month: str) -> list[RecurringBillingRowRead]:
        all_orders = self.orders.list_recurring_billing_orders(month=month, contract_id=None)
        by_contract: dict[str, list] = {}
        for o in all_orders:
            by_contract.setdefault(o.recurring_contract_id, []).append(o)

        rows: list[RecurringBillingRowRead] = []
        for contract_id, orders in by_contract.items():
            contract = self.contracts.get(contract_id)
            if contract is None:  # soft-deleted 계약은 제외
                continue
            agg = aggregate_orders(orders)
            rows.append(self._to_row(contract, month, agg))
        rows.sort(key=lambda r: r.label)
        return rows

    def _to_row(self, contract: RecurringContract, month: str, agg) -> RecurringBillingRowRead:
        group = self.groups.get(contract.order_group_id)
        partner_names: dict[str | None, str | None] = {}
        for s in agg.partner_subtotals:
            if s.partner_id:
                partner = self.partners.get(s.partner_id)
                partner_names[s.partner_id] = partner.name if partner else None
            else:
                partner_names[s.partner_id] = None
        return RecurringBillingRowRead(
            contract_id=contract.id,
            label=contract.label,
            customer_name=group.customer_name if group else "",
            month=month,
            visit_count=agg.visit_count,
            billed_total=float(agg.billed_total),
            confirmed_revenue=float(agg.confirmed_revenue),
            unpaid_customer_count=agg.unpaid_customer_count,
            payment_breakdown=agg.payment_breakdown,
            partner_total=float(agg.partner_total),
            unpaid_partner_total=float(agg.unpaid_partner_total),
            unpaid_partner_count=agg.unpaid_partner_count,
            partner_subtotals=[
                PartnerSubtotalRead(
                    partner_id=s.partner_id,
                    partner_name=partner_names.get(s.partner_id),
                    partner_total=float(s.partner_total),
                    unpaid_partner_total=float(s.unpaid_partner_total),
                    settleable_count=s.settleable_count,
                )
                for s in agg.partner_subtotals
            ],
        )

    def mark_month_paid(
        self, contract_id: str, month: str, *, actor_user_id: str
    ) -> MarkPaidResult:
        orders = self.orders.list_recurring_billing_orders(month=month, contract_id=contract_id)
        updated: list[str] = []
        skipped = 0
        order_service = OrderService(self.db)
        for o in orders:
            if o.payment_status in _ALREADY_PAID:
                skipped += 1
                continue
            order_service.update(
                o.id, OrderUpdate(payment_status=PaymentStatus.PAID), actor_user_id=actor_user_id
            )
            updated.append(o.id)
        return MarkPaidResult(updated_order_ids=updated, skipped_count=skipped)

    def settle_month(
        self, contract_id: str, month: str, *, partner_id: str | None = None, actor_user_id: str
    ) -> SettleMonthResult:
        orders = self.orders.list_recurring_billing_orders(month=month, contract_id=contract_id)
        eligible = [
            o
            for o in orders
            if is_unpaid_partner_order(o)
            and o.partner_id is not None
            and (partner_id is None or o.partner_id == partner_id)
        ]
        skipped = len(orders) - len(eligible)
        settled: list[str] = []
        settlement = PartnerSettlementService(self.db)
        by_partner: dict[str, list[str]] = {}
        for o in eligible:
            by_partner.setdefault(o.partner_id, []).append(o.id)
        for pid, order_ids in by_partner.items():
            result = settlement.settle(
                partner_id=pid, order_ids=order_ids, actor_user_id=actor_user_id
            )
            settled.extend(result.updated_order_ids)
        # PartnerSettlementService.settle 는 commit 하지 않으므로 여기서 트랜잭션을 소유한다.
        self.db.commit()
        return SettleMonthResult(settled_order_ids=settled, skipped_count=skipped)

    def export_table(self, month: str, contract_id: str | None = None) -> OrderExportTable:
        orders = self.orders.list_recurring_billing_orders(month=month, contract_id=contract_id)
        return OrderExportService(self.db).build_admin_orders_export([o.id for o in orders])
