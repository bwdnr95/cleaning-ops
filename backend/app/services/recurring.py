from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.time import business_today, utc_now
from app.domain.constants import OrderStatus, RecurringContractStatus, RecurringOccurrenceStatus
from app.domain.recurrence import (
    HORIZON_DAYS,
    OVERDUE_GRACE_DAYS,
    ScheduleSpec,
    billing_month_of,
    iter_due_dates,
)
from app.models.order_group import OrderGroup
from app.models.recurring_contract import RecurringContract
from app.models.recurring_occurrence import RecurringOccurrence
from app.repositories.order_groups import OrderGroupRepository
from app.repositories.recurring import RecurringContractRepository, RecurringOccurrenceRepository
from app.schemas.order import OrderGroupCreate, OrderLineCreate
from app.schemas.recurring import (
    ApproveItem,
    ApproveOccurrencesResult,
    RecurringContractCreate,
    RecurringContractUpdate,
    SkipItem,
    SkipOccurrencesResult,
)
from app.services.orders import OrderService

# 그룹에 보관되는 고객 필드(계약 수정 시 그룹으로 라우팅)
_GROUP_FIELDS = {
    "customer_name", "customer_phone", "customer_address",
    "customer_address_detail", "customer_visible_payment", "notes",
}


class RecurringService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.contracts = RecurringContractRepository(db)
        self.occurrences = RecurringOccurrenceRepository(db)
        self.groups = OrderGroupRepository(db)
        self.orders = OrderService(db)

    # --- 계약 CRUD ---
    def create_contract(self, payload: RecurringContractCreate, *, actor_user_id: str | None) -> RecurringContract:
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
        )
        data = payload.model_dump()
        for field in _GROUP_FIELDS:
            data.pop(field, None)
        contract = RecurringContract(
            id=str(uuid4()),
            order_group_id=group.id,
            status=RecurringContractStatus.ACTIVE,
            **data,
        )
        self.db.add(contract)
        self.db.commit()
        self.db.refresh(contract)
        return contract

    def get_contract(self, contract_id: str) -> RecurringContract | None:
        return self.contracts.get(contract_id)

    def update_contract(
        self, contract_id: str, payload: RecurringContractUpdate, *, actor_user_id: str | None
    ) -> RecurringContract:
        contract = self.contracts.get(contract_id)
        if contract is None:
            raise ValueError("recurring_contract_not_found")
        changes = payload.model_dump(exclude_unset=True)

        group = self.groups.get(contract.order_group_id)
        for field in list(changes.keys()):
            if field in _GROUP_FIELDS:
                value = changes.pop(field)
                if group is not None and value is not None:
                    setattr(group, field, value)
        for key, value in changes.items():
            setattr(contract, key, value)
        self.db.commit()
        self.db.refresh(contract)
        return contract

    def set_status(self, contract_id: str, status: RecurringContractStatus) -> RecurringContract:
        contract = self.contracts.get(contract_id)
        if contract is None:
            raise ValueError("recurring_contract_not_found")
        contract.status = status
        self.db.commit()
        self.db.refresh(contract)
        return contract

    def delete_contract(self, contract_id: str, *, actor_user_id: str | None) -> None:
        contract = self.contracts.get(contract_id)
        if contract is None:
            raise ValueError("recurring_contract_not_found")
        contract.deleted_at = utc_now()
        self.db.commit()

    # --- 회차 sync / 조회 ---
    def _spec(self, contract: RecurringContract) -> ScheduleSpec:
        return ScheduleSpec(
            mode=contract.recurrence_mode,
            start_date=contract.start_date,
            day_of_month=contract.day_of_month,
            interval_weeks=contract.interval_weeks,
            weekday=contract.weekday,
            end_date=contract.end_date,
            max_occurrences=contract.max_occurrences,
        )

    def sync_due_occurrences(self, *, today: date | None = None) -> int:
        """ACTIVE 계약의 도래분을 PENDING으로 upsert. 생성 건수 반환. 멱등."""
        today = today or business_today()
        horizon = today + timedelta(days=HORIZON_DAYS)
        floor = today - timedelta(days=OVERDUE_GRACE_DAYS)
        created = 0
        for contract in self.contracts.list_active():
            for seq, due in iter_due_dates(self._spec(contract), until=horizon):
                if due < floor:
                    continue
                if self.occurrences.get_by_contract_and_due(contract.id, due) is not None:
                    continue
                self.occurrences.add(
                    RecurringOccurrence(
                        id=str(uuid4()),
                        contract_id=contract.id,
                        sequence_no=seq,
                        due_date=due,
                        billing_month=billing_month_of(due),
                        status=RecurringOccurrenceStatus.PENDING,
                    )
                )
                created += 1
        if created:
            self.db.commit()
        return created

    def list_pending(self) -> list[RecurringOccurrence]:
        return self.occurrences.list_pending()

    # --- 승인 / 건너뛰기 ---
    def approve_occurrences(
        self, items: list[ApproveItem], *, actor_user_id: str | None
    ) -> ApproveOccurrencesResult:
        generated: list[str] = []
        skipped: list[str] = []
        for item in items:
            occ = self.occurrences.get(item.occurrence_id)
            if occ is None or occ.status != RecurringOccurrenceStatus.PENDING:
                if occ is not None:
                    skipped.append(occ.id)
                continue
            contract = self.contracts.get(occ.contract_id)
            if contract is None:
                skipped.append(occ.id)
                continue
            group = self.groups.get(contract.order_group_id)
            if group is None:
                skipped.append(occ.id)
                continue

            partner_id = item.partner_id or contract.default_partner_id
            status = OrderStatus.SCHEDULE_CONFIRMED if partner_id else OrderStatus.NEW
            scheduled = item.scheduled_date or occ.due_date
            total = item.total_amount if item.total_amount is not None else (
                float(contract.total_amount) if contract.total_amount is not None else None
            )

            line = OrderLineCreate(
                status=status,
                received_date=business_today(),
                scheduled_date=scheduled,
                requested_time=contract.requested_time,
                partner_id=partner_id,
                team_name=contract.team_name,
                service_category_id=contract.service_category_id,
                service_item_id=contract.service_item_id,
                service_name=contract.service_name,
                size_or_quantity=contract.size_or_quantity,
                service_detail=contract.service_detail,
                special_request=contract.special_request,
                total_amount=total,
                discount_amount=float(contract.discount_amount or 0),
                deposit_amount=float(contract.deposit_amount) if contract.deposit_amount is not None else None,
                balance_amount=float(contract.balance_amount) if contract.balance_amount is not None else None,
                vat_type=contract.vat_type,
                partner_payment_amount=(
                    float(contract.partner_payment_amount)
                    if contract.partner_payment_amount is not None else None
                ),
            )
            order = self.orders.add_recurring_line(
                group, line, recurring_contract_id=contract.id, actor_user_id=actor_user_id
            )
            self.db.flush()  # order.id 확보
            occ.status = RecurringOccurrenceStatus.GENERATED
            occ.generated_order_id = order.id
            occ.generated_at = utc_now()
            generated.append(order.id)
        self.db.commit()
        return ApproveOccurrencesResult(generated_order_ids=generated, skipped_occurrence_ids=skipped)

    def skip_occurrences(
        self, items: list[SkipItem], *, actor_user_id: str | None
    ) -> SkipOccurrencesResult:
        skipped: list[str] = []
        for item in items:
            occ = self.occurrences.get(item.occurrence_id)
            if occ is None or occ.status != RecurringOccurrenceStatus.PENDING:
                continue
            occ.status = RecurringOccurrenceStatus.SKIPPED
            occ.skipped_reason = item.reason
            skipped.append(occ.id)
        self.db.commit()
        return SkipOccurrencesResult(skipped_occurrence_ids=skipped)
