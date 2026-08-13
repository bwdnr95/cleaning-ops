from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.time import business_today, utc_now
from app.domain.constants import (
    OrderStatus,
    RecurringBillingMode,
    RecurringContractStatus,
    VatType,
)
from app.domain.recurrence import ScheduleSpec, iter_due_dates, parse_weekdays_csv
from app.models.order import Order
from app.models.recurring_contract import RecurringContract
from app.repositories.order_groups import OrderGroupRepository
from app.repositories.partners import PartnerRepository
from app.repositories.recurring import RecurringContractRepository
from app.schemas.order import OrderLineCreate
from app.services.orders import OrderService
from app.services.recurring_partner_billing import (
    RecurringPartnerBillingService,
    billing_month,
)


@dataclass(frozen=True, slots=True)
class GenerationWindow:
    first: date
    last: date


class RecurringOrderGenerationError(RuntimeError):
    def __init__(self, *, created_count: int, failed_contract_ids: tuple[str, ...]) -> None:
        super().__init__("recurring_order_generation_failed")
        self.created_count = created_count
        self.failed_contract_ids = failed_contract_ids


def recurring_schedule_spec(contract: RecurringContract) -> ScheduleSpec:
    return ScheduleSpec(
        mode=contract.recurrence_mode,
        start_date=contract.start_date,
        day_of_month=contract.day_of_month,
        interval_weeks=contract.interval_weeks,
        weekday=contract.weekday,
        weekdays=parse_weekdays_csv(contract.weekdays) or None,
        end_date=contract.end_date,
        max_occurrences=contract.max_occurrences,
    )


class RecurringOrderGenerationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.contracts = RecurringContractRepository(db)
        self.groups = OrderGroupRepository(db)
        self.orders = OrderService(db)
        self.partner_billing = RecurringPartnerBillingService(db)

    def generate_current_month(
        self,
        *,
        actor_user_id: str | None,
        raise_on_error: bool = True,
    ) -> int:
        today = business_today()
        window = GenerationWindow(
            first=date(today.year, today.month, 1),
            last=date(today.year, today.month, monthrange(today.year, today.month)[1]),
        )
        return self.generate_month(
            window.first,
            window.last,
            actor_user_id=actor_user_id,
            raise_on_error=raise_on_error,
        )

    def generate_current_month_for_contract(
        self,
        contract: RecurringContract,
        *,
        actor_user_id: str | None,
    ) -> int:
        today = business_today()
        window = GenerationWindow(
            first=date(today.year, today.month, 1),
            last=date(today.year, today.month, monthrange(today.year, today.month)[1]),
        )
        if contract.start_date > window.last:
            return 0
        if contract.end_date is not None and contract.end_date < window.first:
            return 0
        created_count = self._generate_contract_month(contract, window, actor_user_id=actor_user_id)
        if created_count > 0:
            self.db.commit()
        return created_count

    def generate_month(
        self,
        first: date,
        last: date,
        *,
        actor_user_id: str | None,
        raise_on_error: bool = True,
    ) -> int:
        window = GenerationWindow(first=first, last=last)
        created_count = 0
        failed_contract_ids: list[str] = []
        contract_ids = [contract.id for contract in self.contracts.list_active()]
        for contract_id in contract_ids:
            contract = self.contracts.get(contract_id)
            if contract is None or contract.status != RecurringContractStatus.ACTIVE:
                continue
            if contract.start_date > window.last:
                continue
            if contract.end_date is not None and contract.end_date < window.first:
                continue
            try:
                created_count += self._generate_contract_month(
                    contract,
                    window,
                    actor_user_id=actor_user_id,
                )
            except (SQLAlchemyError, ValueError):
                failed_contract_ids.append(contract.id)
                self.db.rollback()
                continue
            self.db.commit()
        if failed_contract_ids and raise_on_error:
            raise RecurringOrderGenerationError(
                created_count=created_count,
                failed_contract_ids=tuple(failed_contract_ids),
            )
        return created_count

    def discard_failed_contract_setup(self, contract_id: str, group_id: str) -> None:
        self.db.rollback()
        now = utc_now()
        contract = self.contracts.get(contract_id, include_deleted=True)
        if contract is not None:
            contract.deleted_at = now
        group = self.groups.get(group_id, include_deleted=True)
        if group is not None:
            group.deleted_at = now
        self.db.commit()

    def _generate_contract_month(
        self,
        contract: RecurringContract,
        window: GenerationWindow,
        *,
        actor_user_id: str | None,
    ) -> int:
        locked_contract = self._lock_generation_contract(
            contract.id,
            billing_month(window.first),
        )
        if locked_contract is None:
            return 0
        contract = locked_contract
        group = self.groups.get(contract.order_group_id)
        if group is None:
            raise ValueError("recurring_order_group_not_found")
        existing = self._existing_slot_dates(contract.id, window)
        created_count = 0
        active_from = max(
            contract.start_date,
            contract.active_segment_start_date or contract.start_date,
        )
        with self.db.begin_nested():
            for _seq, due in iter_due_dates(recurring_schedule_spec(contract), until=window.last):
                if (
                    due < window.first
                    or due < active_from
                    or due > window.last
                    or due in existing
                ):
                    continue
                order = self.orders.add_recurring_line(
                    group,
                    self._contract_line_payload(contract, due),
                    recurring_contract_id=contract.id,
                    actor_user_id=actor_user_id,
                )
                order.recurring_planned_date = due
                existing.add(due)
                created_count += 1
        return created_count

    def _lock_generation_contract(
        self,
        contract_id: str,
        month: str,
    ) -> RecurringContract | None:
        observed = self.contracts.get(contract_id)
        if observed is None or observed.status != RecurringContractStatus.ACTIVE:
            return None
        observed_terms = self.partner_billing.resolve(observed, month)
        locked_partner_id = observed_terms.partner_id
        partner = None
        if locked_partner_id is not None:
            partner = PartnerRepository(self.db).get_for_update(
                locked_partner_id,
                include_deleted=True,
            )
        contract = self.contracts.get_for_update(contract_id)
        if contract is None or contract.status != RecurringContractStatus.ACTIVE:
            return None
        current_terms = self.partner_billing.resolve(contract, month, refresh=True)
        if current_terms.partner_id != locked_partner_id:
            raise ValueError("recurring_partner_changed_concurrently")
        if locked_partner_id is not None:
            if partner is None or partner.deleted_at is not None:
                raise ValueError("partner_not_found")
            if not partner.is_active:
                raise ValueError("partner_inactive")
        return contract

    def _existing_slot_dates(self, contract_id: str, window: GenerationWindow) -> set[date]:
        planned_dates = set(
            self.db.scalars(
                select(Order.recurring_planned_date).where(
                    Order.recurring_contract_id == contract_id,
                    Order.recurring_planned_date >= window.first,
                    Order.recurring_planned_date <= window.last,
                )
            )
        )
        legacy_scheduled_dates = set(
            self.db.scalars(
                select(Order.scheduled_date).where(
                    Order.recurring_contract_id == contract_id,
                    Order.recurring_planned_date.is_(None),
                    Order.scheduled_date >= window.first,
                    Order.scheduled_date <= window.last,
                )
            )
        )
        return planned_dates | legacy_scheduled_dates

    def _contract_line_payload(self, contract: RecurringContract, due: date) -> OrderLineCreate:
        def to_float(value: Decimal | None) -> float | None:
            return float(value) if value is not None else None

        partner_terms = self.partner_billing.resolve(contract, billing_month(due))
        is_partner_per_visit = (
            partner_terms.billing_mode == RecurringBillingMode.PER_VISIT
        )

        return OrderLineCreate(
            status=(
                OrderStatus.PARTNER_CONFIRMING
                if partner_terms.partner_id
                else OrderStatus.SCHEDULE_CONFIRMED
            ),
            received_date=business_today(),
            scheduled_date=due,
            requested_time=contract.requested_time,
            partner_id=partner_terms.partner_id,
            team_name=contract.team_name,
            service_category_id=contract.service_category_id,
            service_item_id=contract.service_item_id,
            service_name=contract.service_name,
            size_or_quantity=contract.size_or_quantity,
            service_detail=contract.service_detail,
            special_request=contract.special_request,
            total_amount=(
                None
                if contract.billing_mode == RecurringBillingMode.MONTHLY
                else to_float(contract.total_amount)
            ),
            discount_amount=to_float(contract.discount_amount) or 0,
            deposit_amount=to_float(contract.deposit_amount),
            balance_amount=to_float(contract.balance_amount),
            vat_type=contract.vat_type or VatType.INCLUDED,
            partner_payment_amount=(
                to_float(partner_terms.partner_payment_amount)
                if is_partner_per_visit
                else None
            ),
        )
