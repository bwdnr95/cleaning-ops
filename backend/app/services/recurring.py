from __future__ import annotations

import logging
from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.time import business_today, utc_now
from app.domain.constants import (
    OrderStatus,
    RecurrenceMode,
    RecurringContractStatus,
    RecurringOccurrenceStatus,
)
from app.domain.phone import normalize_phone
from app.domain.recurrence import (
    HORIZON_DAYS,
    OVERDUE_GRACE_DAYS,
    ScheduleSpec,
    billing_month_of,
    iter_due_dates,
    validate_recurrence_fields,
)
from app.models.recurring_contract import RecurringContract
from app.models.recurring_occurrence import RecurringOccurrence
from app.repositories.order_groups import OrderGroupRepository
from app.repositories.orders import OrderRepository
from app.repositories.partners import PartnerRepository
from app.repositories.recurring import RecurringContractRepository, RecurringOccurrenceRepository
from app.schemas.order import OrderGroupCreate, OrderLineCreate
from app.schemas.recurring import (
    ApproveItem,
    ApproveOccurrencesResult,
    PendingOccurrenceRead,
    RecurringContractCreate,
    RecurringContractRead,
    RecurringContractSummaryRead,
    RecurringContractUpdate,
    SkipItem,
    SkipOccurrencesResult,
)
from app.services.orders import OrderService

logger = logging.getLogger(__name__)

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
        # 그룹 생성(commit) 전에 FK 대상을 검증한다. 잘못된 partner_id면 그룹만 남는
        # 고아 그룹이 발생하므로(create_empty_group이 즉시 commit) 미리 막는다.
        if payload.default_partner_id is not None:
            if PartnerRepository(self.db).get(payload.default_partner_id) is None:
                raise ValueError("partner_not_found")
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

        # 생성 경로와 동일하게 default_partner_id 존재를 검증한다(잘못된 FK PATCH로
        # Postgres IntegrityError가 나기 전에 막는다 — SQLite 테스트는 FK 미강제).
        if changes.get("default_partner_id") is not None:
            if PartnerRepository(self.db).get(changes["default_partner_id"]) is None:
                raise ValueError("partner_not_found")

        group = self.groups.get(contract.order_group_id)
        for field in list(changes.keys()):
            if field in _GROUP_FIELDS:
                value = changes.pop(field)
                if group is not None and value is not None:
                    if field == "customer_phone":
                        value = normalize_phone(value)
                    setattr(group, field, value)
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
            # 한 계약의 불량 스케줄(예: 짝 필드 누락으로 iter_due_dates가 ValueError)이
            # 전체 배치를 죽이지 않도록 계약별로 격리한다. 정상 유입은 검증으로 막지만,
            # 기존에 저장된 잘못된 데이터를 방어한다.
            try:
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
            except ValueError as exc:
                # 잘못 저장된 스케줄(짝 필드 누락 등)로 iter_due_dates가 ValueError를
                # 던지면 그 계약만 건너뛰고 경고를 남긴다. DB 오류 등 다른 예외는
                # 삼키지 않고 전파한다 — 운영자가 알 수 있어야 한다.
                logger.warning("recurring_sync_skipped_contract %s: %s", contract.id, exc)
                continue
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

            line_data = dict(
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
                partner_payment_amount=(
                    float(contract.partner_payment_amount)
                    if contract.partner_payment_amount is not None else None
                ),
            )
            # 계약에 vat_type이 없으면 키를 생략해 OrderLineCreate 기본값을 유지한다.
            # (None으로 덮어쓰면 정기 생성 주문만 vat_type이 달라진다.)
            if contract.vat_type is not None:
                line_data["vat_type"] = contract.vat_type
            line = OrderLineCreate(**line_data)
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
        every = "매주" if contract.interval_weeks == 1 else f"{contract.interval_weeks}주마다"
        wd = (
            weekday_ko[contract.weekday]
            if contract.weekday is not None
            else weekday_ko[contract.start_date.weekday()]
        )
        return f"{every} {wd}요일"

    def to_contract_read(self, contract: RecurringContract) -> RecurringContractRead:
        group = self.groups.get(contract.order_group_id)
        data = {
            **{c.name: getattr(contract, c.name) for c in contract.__table__.columns},
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
        pend_by_contract: dict[str, int] = {}
        for occ in self.occurrences.list_pending():
            pend_by_contract[occ.contract_id] = pend_by_contract.get(occ.contract_id, 0) + 1
        order_repo = OrderRepository(self.db)
        month = billing_month_of(business_today())
        out: list[RecurringContractSummaryRead] = []
        for contract in self.contracts.list_all():
            group = self.groups.get(contract.order_group_id)
            this_month = order_repo.list_recurring_orders_in_month(contract.id, month)
            out.append(
                RecurringContractSummaryRead(
                    id=contract.id,
                    label=contract.label,
                    customer_name=group.customer_name if group else "",
                    status=contract.status,
                    schedule_text=self._schedule_text(contract),
                    next_due_date=self._next_due(contract),
                    pending_count=pend_by_contract.get(contract.id, 0),
                    this_month_count=len(this_month),
                    this_month_amount=float(sum((o.total_amount or 0) for o in this_month)),
                )
            )
        return out

    def list_pending_views(self) -> list[PendingOccurrenceRead]:
        partner_repo = PartnerRepository(self.db)
        today = business_today()
        views: list[PendingOccurrenceRead] = []
        for occ in self.occurrences.list_pending():
            contract = self.contracts.get(occ.contract_id)
            if contract is None:
                continue
            group = self.groups.get(contract.order_group_id)
            partner = partner_repo.get(contract.default_partner_id) if contract.default_partner_id else None
            views.append(
                PendingOccurrenceRead(
                    occurrence_id=occ.id,
                    contract_id=contract.id,
                    contract_label=contract.label,
                    customer_name=group.customer_name if group else "",
                    sequence_no=occ.sequence_no,
                    due_date=occ.due_date,
                    service_name=contract.service_name,
                    total_amount=float(contract.total_amount) if contract.total_amount is not None else None,
                    default_partner_id=contract.default_partner_id,
                    default_partner_name=partner.name if partner else None,
                    is_overdue=occ.due_date < today,
                )
            )
        return views
