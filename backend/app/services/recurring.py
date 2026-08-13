from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.time import business_today, utc_now
from app.domain.constants import (
    OrderStatus,
    RecurrenceMode,
    RecurringBillingMode,
    RecurringContractStatus,
    TimelineEventType,
)
from app.domain.order_metrics import WORK_DONE_STATUSES
from app.domain.payment_status import PartnerPaymentStatus
from app.domain.phone import normalize_phone
from app.domain.recurrence import (
    ScheduleSpec,
    format_weekdays_csv,
    iter_due_dates,
    parse_weekdays_csv,
    validate_recurrence_fields,
)
from app.models.order import Order
from app.models.photo import OrderPhoto
from app.models.recurring_contract import RecurringContract
from app.models.recurring_monthly_status import RecurringMonthlyStatus
from app.models.recurring_partner_billing_period import RecurringPartnerBillingPeriod
from app.repositories.order_groups import OrderGroupRepository
from app.repositories.partners import PartnerRepository
from app.repositories.recurring import RecurringContractRepository
from app.schemas.order import AdminOrderRead, OrderGroupCreate, OrderLineCreate
from app.schemas.recurring import (
    RecurringContractCreate,
    RecurringContractRead,
    RecurringContractSummaryRead,
    RecurringContractUpdate,
)
from app.services.orders import OrderService, collect_payment_changes, to_admin_order_dto
from app.services.recurring_generation import (
    RecurringOrderGenerationService,
    recurring_schedule_spec,
)
from app.services.recurring_partner_billing import (
    BASELINE_EFFECTIVE_MONTH,
    RecurringPartnerBillingService,
    billing_month,
    incurred_billing_months,
    money_decimal,
)
from app.services.recurring_validation import validate_recurring_service_catalog
from app.services.timeline import TimelineService


def _month_bounds(month: str) -> tuple[date, date]:
    year, mon = int(month[:4]), int(month[5:7])
    return date(year, mon, 1), date(year, mon, monthrange(year, mon)[1])

# 그룹에 보관되는 고객 필드(계약 수정 시 그룹으로 라우팅)
_GROUP_FIELDS = {
    "customer_name", "customer_phone", "customer_address",
    "customer_address_detail", "customer_visible_payment", "notes",
}


class RecurringService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.contracts = RecurringContractRepository(db)
        self.groups = OrderGroupRepository(db)
        self.orders = OrderService(db)
        self.order_generation = RecurringOrderGenerationService(db)
        self.partner_billing = RecurringPartnerBillingService(db)
        self.timeline = TimelineService(db)

    # --- 계약 CRUD ---
    def create_contract(self, payload: RecurringContractCreate, *, actor_user_id: str | None) -> RecurringContract:
        partner_repo = PartnerRepository(self.db)
        if payload.default_partner_id is not None:
            partner = partner_repo.get_for_update(
                payload.default_partner_id,
                include_deleted=True,
            )
            if partner is None or partner.deleted_at is not None:
                raise ValueError("partner_not_found")
            if not partner.is_active:
                raise ValueError("partner_inactive")
        self._validate_service_catalog(payload)
        group = self.orders.create_empty_group(
            OrderGroupCreate(
                customer_name=payload.customer_name,
                customer_phone=payload.customer_phone,
                customer_address=payload.customer_address,
                customer_address_detail=payload.customer_address_detail,
                customer_visible_payment=payload.customer_visible_payment,
                notes=payload.notes,
                # lines는 create_empty_group이 무시한다. OrderLineCreate가 received_date를
                # 필수로 요구하므로 검증 통과용 더미 라인을 채워준다.
                lines=[OrderLineCreate(service_name=payload.service_name, received_date=business_today())],
            ),
            actor_user_id=actor_user_id,
            commit=False,
        )
        data = payload.model_dump()
        # 다중요일은 list[int] → CSV "0,2,4"로 직렬화해 컬럼에 저장한다.
        if data.get("weekdays") is not None:
            data["weekdays"] = format_weekdays_csv(data["weekdays"])
        for field in _GROUP_FIELDS:
            data.pop(field, None)
        contract = RecurringContract(
            id=str(uuid4()),
            order_group_id=group.id,
            status=RecurringContractStatus.ACTIVE,
            active_segment_start_date=payload.start_date,
            **data,
        )
        self.db.add(contract)
        self.db.flush()
        self.partner_billing.ensure_baseline(contract)
        self.db.commit()
        self.db.refresh(contract)
        try:
            self.order_generation.generate_current_month_for_contract(contract, actor_user_id=actor_user_id)
        except (SQLAlchemyError, ValueError):
            self.order_generation.discard_failed_contract_setup(contract.id, group.id)
            raise
        self.db.refresh(contract)
        return contract

    def _validate_service_catalog(self, payload: RecurringContractCreate) -> None:
        validate_recurring_service_catalog(
            self.db,
            service_item_id=payload.service_item_id,
            service_category_id=payload.service_category_id,
        )

    def get_contract(self, contract_id: str) -> RecurringContract | None:
        return self.contracts.get(contract_id)

    def update_contract(
        self, contract_id: str, payload: RecurringContractUpdate, *, actor_user_id: str | None
    ) -> RecurringContract:
        changes = payload.model_dump(exclude_unset=True)
        observed = self.contracts.get(contract_id)
        if observed is None:
            raise ValueError("recurring_contract_not_found")
        billing_terms_changed = self._partner_billing_terms_changed(observed, changes)
        partner_ids = (
            [observed.default_partner_id]
            if observed.default_partner_id is not None
            else []
        )
        if changes.get("default_partner_id") is not None:
            partner_ids.append(changes["default_partner_id"])
        if billing_terms_changed:
            first = business_today().replace(day=1)
            partner_ids.extend(
                partner_id
                for partner_id in self.db.scalars(
                    select(Order.partner_id).where(
                        Order.recurring_contract_id == contract_id,
                        Order.deleted_at.is_(None),
                        Order.status != OrderStatus.CANCELLED,
                        or_(
                            Order.recurring_planned_date >= first,
                            and_(
                                Order.recurring_planned_date.is_(None),
                                or_(
                                    Order.scheduled_date >= first,
                                    Order.scheduled_date.is_(None),
                                ),
                            ),
                        ),
                        Order.partner_id.is_not(None),
                    )
                )
                if partner_id is not None
            )
        locked_partners = {
            partner.id: partner
            for partner in PartnerRepository(self.db).lock_ids(partner_ids)
        }
        contract = self.contracts.get_for_update(contract_id)
        if contract is None:
            raise ValueError("recurring_contract_not_found")
        if (
            contract.default_partner_id is not None
            and contract.default_partner_id not in locked_partners
        ):
            raise ValueError("recurring_partner_changed_concurrently")
        locked_billing_terms_changed = self._partner_billing_terms_changed(contract, changes)
        if locked_billing_terms_changed != billing_terms_changed:
            raise ValueError("recurring_partner_changed_concurrently")
        self._prepare_start_date_change(contract, changes)

        if "default_partner_id" in changes and changes["default_partner_id"] is not None:
            partner = locked_partners.get(changes["default_partner_id"])
            if partner is None or partner.deleted_at is not None:
                raise ValueError("partner_not_found")
            if not partner.is_active:
                raise ValueError("partner_inactive")
        service_item_id = changes.get("service_item_id")
        service_category_id = changes.get("service_category_id")
        validate_recurring_service_catalog(
            self.db,
            service_item_id=service_item_id if isinstance(service_item_id, str) else None,
            service_category_id=service_category_id if isinstance(service_category_id, str) else None,
        )
        if locked_billing_terms_changed:
            self._apply_partner_billing_change(
                contract,
                changes,
                locked_partners=locked_partners,
                actor_user_id=actor_user_id,
            )

        group = self.groups.get(contract.order_group_id)
        for field in list(changes.keys()):
            if field in _GROUP_FIELDS:
                value = changes.pop(field)
                if group is not None and value is not None:
                    if field == "customer_phone":
                        value = normalize_phone(value)
                    setattr(group, field, value)
        # 다중요일은 list[int] → CSV로 직렬화(None이면 미선택으로 초기화).
        if "weekdays" in changes:
            changes["weekdays"] = format_weekdays_csv(changes["weekdays"])
        for key, value in changes.items():
            setattr(contract, key, value)
        # 머지 결과(모드+짝 필드)를 commit 전에 재검증한다. weekly↔monthly 모드만
        # 바꾸고 짝 필드를 빠뜨린 PATCH가 저장되면 이후 iter_due_dates가 연쇄 고장한다.
        try:
            validate_recurrence_fields(
                contract.recurrence_mode, contract.day_of_month, contract.interval_weeks
            )
        except ValueError:
            self.db.rollback()  # 잘못된 전환이 저장되지 않도록 변경을 되돌린다
            raise
        self.db.commit()
        self.db.refresh(contract)
        return contract

    def _prepare_start_date_change(
        self,
        contract: RecurringContract,
        changes: dict,
    ) -> None:
        next_start = changes.get("start_date")
        if next_start is None or next_start == contract.start_date:
            return
        has_orders = self.db.scalar(
            select(Order.id)
            .where(Order.recurring_contract_id == contract.id)
            .limit(1)
        )
        has_monthly_status = self.db.scalar(
            select(RecurringMonthlyStatus.id)
            .where(RecurringMonthlyStatus.contract_id == contract.id)
            .limit(1)
        )
        has_effective_history = self.db.scalar(
            select(RecurringPartnerBillingPeriod.contract_id)
            .where(
                RecurringPartnerBillingPeriod.contract_id == contract.id,
                RecurringPartnerBillingPeriod.effective_month != BASELINE_EFFECTIVE_MONTH,
            )
            .limit(1)
        )
        initial_segment_start = contract.active_segment_start_date or contract.start_date
        if (
            contract.status != RecurringContractStatus.ACTIVE
            or contract.start_date <= business_today()
            or initial_segment_start != contract.start_date
            or has_orders is not None
            or has_monthly_status is not None
            or has_effective_history is not None
        ):
            raise ValueError("recurring_start_date_locked")
        contract.active_segment_start_date = next_start

    def _partner_billing_terms_changed(
        self,
        contract: RecurringContract,
        changes: dict,
    ) -> bool:
        current_mode = RecurringBillingMode(
            contract.partner_billing_mode or RecurringBillingMode.PER_VISIT
        )
        next_mode = RecurringBillingMode(
            changes.get("partner_billing_mode", current_mode)
        )
        current_amount = money_decimal(contract.partner_payment_amount)
        next_amount = money_decimal(
            changes.get("partner_payment_amount", current_amount)
        )
        next_partner_id = changes.get("default_partner_id", contract.default_partner_id)
        return (
            next_mode != current_mode
            or next_amount != current_amount
            or next_partner_id != contract.default_partner_id
        )

    def _apply_partner_billing_change(
        self,
        contract: RecurringContract,
        changes: dict,
        *,
        locked_partners: dict,
        actor_user_id: str | None,
    ) -> None:
        today = business_today()
        effective_month = billing_month(today)
        first = today.replace(day=1)
        affected_orders = list(
            self.db.scalars(
                select(Order)
                .where(
                    Order.recurring_contract_id == contract.id,
                    Order.deleted_at.is_(None),
                    Order.status != OrderStatus.CANCELLED,
                    or_(
                        Order.recurring_planned_date >= first,
                        and_(
                            Order.recurring_planned_date.is_(None),
                            or_(
                                Order.scheduled_date >= first,
                                Order.scheduled_date.is_(None),
                            ),
                        ),
                    ),
                )
                .order_by(Order.scheduled_date.asc(), Order.id.asc())
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )
        if any(
            order.partner_id is not None and order.partner_id not in locked_partners
            for order in affected_orders
        ):
            raise ValueError("recurring_partner_changed_concurrently")
        affected_order_ids = [order.id for order in affected_orders]
        photo_order_ids = (
            set(
                self.db.scalars(
                    select(OrderPhoto.order_id).where(
                        OrderPhoto.order_id.in_(affected_order_ids)
                    )
                )
            )
            if affected_order_ids
            else set()
        )
        locked_order_ids = {
            order.id
            for order in affected_orders
            if (
                order.partner_payment_status
                in (PartnerPaymentStatus.PAID, PartnerPaymentStatus.HOLD)
                or order.partner_settled_at is not None
                or order.status in WORK_DONE_STATUSES
                or order.work_completed_at is not None
                or order.id in photo_order_ids
            )
        }
        mutable_orders = [
            order for order in affected_orders if order.id not in locked_order_ids
        ]
        if any(
            order.recurring_planned_date is None and order.scheduled_date is None
            for order in mutable_orders
        ):
            raise ValueError("recurring_partner_billing_change_unscheduled")
        current_mode = RecurringBillingMode(
            contract.partner_billing_mode or RecurringBillingMode.PER_VISIT
        )
        if (
            current_mode == RecurringBillingMode.MONTHLY
            and any(
                order.id in locked_order_ids
                and order.recurring_planned_date is None
                and order.scheduled_date is None
                for order in affected_orders
            )
        ):
            raise ValueError("recurring_partner_billing_change_unscheduled")
        future_month_statuses = list(
            self.db.scalars(
                select(RecurringMonthlyStatus)
                .where(
                    RecurringMonthlyStatus.contract_id == contract.id,
                    RecurringMonthlyStatus.billing_month >= effective_month,
                )
                .order_by(RecurringMonthlyStatus.billing_month.asc())
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )
        if any(status.partner_payment_paid for status in future_month_statuses):
            raise ValueError("recurring_partner_billing_change_paid")

        next_mode = RecurringBillingMode(
            changes.get(
                "partner_billing_mode",
                contract.partner_billing_mode or RecurringBillingMode.PER_VISIT,
            )
        )
        next_amount = money_decimal(
            changes.get("partner_payment_amount", contract.partner_payment_amount)
        )
        next_partner_id = changes.get("default_partner_id", contract.default_partner_id)
        is_partner_change = next_partner_id != contract.default_partner_id
        is_payable_per_visit = (
            next_mode == RecurringBillingMode.PER_VISIT
            and next_amount is not None
            and next_amount > 0
        )
        target_amount = next_amount if next_mode == RecurringBillingMode.PER_VISIT else None
        target_status = PartnerPaymentStatus.UNPAID if is_payable_per_visit else None
        target = {
            "partner_payment_amount": target_amount,
            "partner_payment_status": target_status,
            "partner_settled_at": None,
        }
        if next_partner_id is not None and next_amount is not None and next_amount > 0:
            target_partner = locked_partners.get(next_partner_id)
            if target_partner is None:
                raise ValueError("recurring_partner_changed_concurrently")
            if target_partner.deleted_at is not None:
                raise ValueError("partner_not_found")
            if not target_partner.is_active:
                raise ValueError("partner_inactive")
        for order in mutable_orders:
            target_partner_id = next_partner_id if is_partner_change else order.partner_id
            if target_status is not None and target_partner_id is not None:
                target_partner = locked_partners.get(target_partner_id)
                if target_partner is None:
                    raise ValueError("recurring_partner_changed_concurrently")
                if target_partner.deleted_at is not None:
                    raise ValueError("partner_not_found")
                if not target_partner.is_active:
                    raise ValueError("partner_inactive")
        self.partner_billing.set_effective(
            contract,
            month=effective_month,
            partner_id=next_partner_id,
            billing_mode=next_mode,
            partner_payment_amount=next_amount,
        )

        statuses_by_month = {
            status.billing_month: status for status in future_month_statuses
        }
        if (
            current_mode == RecurringBillingMode.MONTHLY
            and contract.partner_payment_amount is not None
            and contract.partner_payment_amount > 0
        ):
            locked_months = {
                billing_month(order.recurring_planned_date or order.scheduled_date)
                for order in affected_orders
                if order.id in locked_order_ids
                and (order.recurring_planned_date or order.scheduled_date) is not None
            }
            for locked_month in sorted(locked_months):
                status = statuses_by_month.get(locked_month)
                if status is None:
                    status = RecurringMonthlyStatus(
                        id=str(uuid4()),
                        contract_id=contract.id,
                        billing_month=locked_month,
                        tax_invoice_issued=False,
                        balance_paid=False,
                        partner_payment_paid=False,
                    )
                    self.db.add(status)
                    statuses_by_month[locked_month] = status
                if status.retained_partner_payment_amount is None:
                    status.retained_partner_id = contract.default_partner_id
                    status.retained_partner_payment_amount = money_decimal(
                        contract.partner_payment_amount
                    )

        if (
            current_mode == RecurringBillingMode.PER_VISIT
            and next_mode == RecurringBillingMode.MONTHLY
        ):
            for order in affected_orders:
                if (
                    order.id in locked_order_ids
                    and order.partner_payment_amount is not None
                    and order.partner_payment_amount > 0
                ):
                    order.recurring_partner_settlement_retained = True

        for order in mutable_orders:
            old_partner_id = order.partner_id
            partner_changed = is_partner_change and old_partner_id != next_partner_id
            payment_changes = collect_payment_changes(order, target)
            if not payment_changes and not partner_changed:
                continue
            if partner_changed:
                order.partner_id = next_partner_id
                self.timeline.record(
                    order_id=order.id,
                    actor_user_id=actor_user_id,
                    event_type=TimelineEventType.PARTNER_ASSIGNED,
                    title="협력사 배정",
                    description="정기계약 기본 협력사 변경을 해당 월부터 반영했습니다.",
                    metadata={
                        "partner_id": next_partner_id,
                        "from_partner_id": old_partner_id,
                        "effective_month": effective_month,
                        "recurring_contract_id": contract.id,
                    },
                )
            if not payment_changes:
                continue
            for key, value in target.items():
                setattr(order, key, value)
            self.timeline.record(
                order_id=order.id,
                actor_user_id=actor_user_id,
                event_type=TimelineEventType.MEMO_ADDED,
                title="결제/정산 변경",
                description="정기계약 협력사 정산 방식 변경을 해당 월부터 반영했습니다.",
                metadata={
                    "effective_month": effective_month,
                    "partner_billing_mode": next_mode.value,
                    "changes": payment_changes,
                },
            )

    def _lifecycle_partner_ids(
        self,
        contract: RecurringContract,
        *,
        target_status: RecurringContractStatus,
        today: date,
        refresh: bool = False,
    ) -> tuple[str, ...]:
        if target_status == RecurringContractStatus.ACTIVE:
            months = (billing_month(today),)
        elif contract.status == RecurringContractStatus.ACTIVE:
            months = incurred_billing_months(contract, through_date=today)
        else:
            months = ()
        return tuple(
            sorted(
                {
                    terms.partner_id
                    for month in months
                    if (
                        terms := self.partner_billing.resolve(
                            contract,
                            month,
                            refresh=refresh,
                        )
                    ).partner_id
                    is not None
                }
            )
        )

    def set_status(self, contract_id: str, status: RecurringContractStatus) -> RecurringContract:
        observed = self.contracts.get(contract_id)
        if observed is None:
            raise ValueError("recurring_contract_not_found")
        today = business_today()
        observed_partner_ids = self._lifecycle_partner_ids(
            observed,
            target_status=status,
            today=today,
        )
        locked_partners = {
            partner.id: partner
            for partner in PartnerRepository(self.db).lock_ids(list(observed_partner_ids))
        }
        contract = self.contracts.get_for_update(contract_id)
        if contract is None:
            raise ValueError("recurring_contract_not_found")
        current_partner_ids = self._lifecycle_partner_ids(
            contract,
            target_status=status,
            today=today,
            refresh=True,
        )
        if current_partner_ids != observed_partner_ids:
            raise ValueError("recurring_partner_changed_concurrently")
        previous_status = RecurringContractStatus(contract.status)
        if status == RecurringContractStatus.ACTIVE:
            if (
                previous_status != RecurringContractStatus.ACTIVE
                and contract.end_date is not None
                and contract.end_date < today
            ):
                raise ValueError("recurring_contract_end_date_passed")
            for partner_id in current_partner_ids:
                partner = locked_partners.get(partner_id)
                if partner is None or partner.deleted_at is not None:
                    raise ValueError("partner_not_found")
                if not partner.is_active:
                    raise ValueError("partner_inactive")
            if previous_status != RecurringContractStatus.ACTIVE:
                contract.active_segment_start_date = today
                if previous_status == RecurringContractStatus.ENDED:
                    contract.end_date = None
            elif contract.active_segment_start_date is None:
                contract.active_segment_start_date = contract.start_date
        elif previous_status == RecurringContractStatus.ACTIVE:
            if contract.active_segment_start_date is None:
                contract.active_segment_start_date = contract.start_date
            self.partner_billing.materialize_incurred_statuses(
                contract,
                through_date=today,
            )
        if status == RecurringContractStatus.ENDED and previous_status != status:
            contract.end_date = today
        contract.status = status
        self.db.commit()
        self.db.refresh(contract)
        return contract

    def delete_contract(self, contract_id: str, *, actor_user_id: str | None) -> None:
        observed = self.contracts.get(contract_id)
        if observed is None:
            raise ValueError("recurring_contract_not_found")
        today = business_today()
        observed_partner_ids = self._lifecycle_partner_ids(
            observed,
            target_status=RecurringContractStatus.ENDED,
            today=today,
        )
        PartnerRepository(self.db).lock_ids(list(observed_partner_ids))
        contract = self.contracts.get_for_update(contract_id)
        if contract is None:
            raise ValueError("recurring_contract_not_found")
        current_partner_ids = self._lifecycle_partner_ids(
            contract,
            target_status=RecurringContractStatus.ENDED,
            today=today,
            refresh=True,
        )
        if current_partner_ids != observed_partner_ids:
            raise ValueError("recurring_partner_changed_concurrently")
        if contract.status == RecurringContractStatus.ACTIVE:
            if contract.active_segment_start_date is None:
                contract.active_segment_start_date = contract.start_date
            self.partner_billing.materialize_incurred_statuses(
                contract,
                through_date=today,
            )
        if self._has_unpaid_monthly_obligation(contract):
            raise ValueError("recurring_contract_has_unpaid_settlements")
        if contract.status == RecurringContractStatus.ACTIVE:
            contract.status = RecurringContractStatus.ENDED
            contract.end_date = today
        contract.deleted_at = utc_now()
        self.db.commit()

    def _has_unpaid_monthly_obligation(self, contract: RecurringContract) -> bool:
        statuses = list(
            self.db.scalars(
                select(RecurringMonthlyStatus)
                .where(RecurringMonthlyStatus.contract_id == contract.id)
                .order_by(RecurringMonthlyStatus.billing_month.asc())
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )
        statuses_by_month = {status.billing_month: status for status in statuses}
        months = set(statuses_by_month)
        months.update(incurred_billing_months(contract))
        current_month = billing_month(business_today())
        for month in sorted(months):
            if month > current_month:
                continue
            status = statuses_by_month.get(month)
            if status is not None and status.partner_payment_paid:
                continue
            terms = self.partner_billing.resolve(contract, month)
            retained_amount = (
                status.retained_partner_payment_amount if status is not None else None
            )
            if (
                retained_amount is not None
                and retained_amount > 0
            ) or (
                retained_amount is None
                and terms.billing_mode == RecurringBillingMode.MONTHLY
                and terms.partner_payment_amount is not None
                and terms.partner_payment_amount > 0
            ):
                return True
        return False

    # --- 스케줄 헬퍼 ---
    def _spec(self, contract: RecurringContract) -> ScheduleSpec:
        return recurring_schedule_spec(contract)

    # --- DTO 매핑 (라우트용) ---
    def _next_due(self, contract: RecurringContract) -> date | None:
        today = business_today()
        for _seq, due in iter_due_dates(self._spec(contract), until=today + timedelta(days=365)):
            if due >= today:
                return due
        return None

    def _schedule_text(self, contract: RecurringContract) -> str:
        if contract.recurrence_mode == RecurrenceMode.MONTHLY:
            return f"매월 {contract.day_of_month}일"
        weekday_ko = ["월", "화", "수", "목", "금", "토", "일"]
        every = {1: "매주", 2: "격주"}.get(contract.interval_weeks, f"{contract.interval_weeks}주마다")
        # 폴백 체인(도메인과 동일): weekdays → weekday → start_date 요일
        wds = parse_weekdays_csv(contract.weekdays)
        if not wds:
            wds = (contract.weekday,) if contract.weekday is not None else (contract.start_date.weekday(),)
        days = "·".join(weekday_ko[w] for w in sorted(set(wds)))
        return f"{every} {days}"

    def to_contract_read(self, contract: RecurringContract) -> RecurringContractRead:
        group = self.groups.get(contract.order_group_id)
        data = {
            **{c.name: getattr(contract, c.name) for c in contract.__table__.columns},
            # 컬럼은 CSV이지만 Read DTO는 list[int]을 기대하므로 덮어쓴다.
            "weekdays": list(parse_weekdays_csv(contract.weekdays)) or None,
            "customer_name": group.customer_name if group else "",
            "customer_phone": group.customer_phone if group else "",
            "customer_address": group.customer_address if group else "",
            "customer_address_detail": group.customer_address_detail if group else None,
            "customer_visible_payment": group.customer_visible_payment if group else False,
            "notes": group.notes if group else None,
            "customer_token": group.customer_token if group else "",
            "next_due_date": self._next_due(contract),
        }
        return RecurringContractRead.model_validate(data)

    def list_contract_summaries(self) -> list[RecurringContractSummaryRead]:
        out: list[RecurringContractSummaryRead] = []
        for contract in self.contracts.list_all():
            group = self.groups.get(contract.order_group_id)
            out.append(
                RecurringContractSummaryRead(
                    id=contract.id,
                    label=contract.label,
                    customer_name=group.customer_name if group else "",
                    status=contract.status,
                    schedule_text=self._schedule_text(contract),
                    next_due_date=self._next_due(contract),
                )
            )
        return out

    # --- 정기 주문 자동생성 + 월별 조회 (2-3 / 2-4 / 2-5) ---
    def list_month_orders(self, month: str, *, actor_user_id: str | None) -> list[AdminOrderRead]:
        first, last = _month_bounds(month)
        today = business_today()
        if (today.year, today.month) == (first.year, first.month):
            self.order_generation.generate_month(
                first,
                last,
                actor_user_id=actor_user_id,
                raise_on_error=False,
            )
        orders = list(
            self.db.scalars(
                select(Order)
                .where(
                    Order.deleted_at.is_(None),
                    Order.recurring_contract_id.is_not(None),
                    Order.scheduled_date >= first,
                    Order.scheduled_date <= last,
                )
                .order_by(Order.scheduled_date.asc(), Order.id.asc())
            )
        )
        groups = self.groups.list_by_ids(order.group_id for order in orders)
        return [to_admin_order_dto(order, group=groups.get(order.group_id)) for order in orders]

    def generate_current_month_orders(self, *, actor_user_id: str | None) -> int:
        return self.order_generation.generate_current_month(actor_user_id=actor_user_id)
