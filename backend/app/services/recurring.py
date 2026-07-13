from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.time import business_today, utc_now
from app.domain.constants import (
    RecurrenceMode,
    RecurringContractStatus,
)
from app.domain.phone import normalize_phone
from app.domain.recurrence import (
    ScheduleSpec,
    format_weekdays_csv,
    iter_due_dates,
    parse_weekdays_csv,
    validate_recurrence_fields,
)
from app.models.order import Order
from app.models.recurring_contract import RecurringContract
from app.models.recurring_monthly_status import RecurringMonthlyStatus
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
from app.services.orders import OrderService, to_admin_order_dto
from app.services.recurring_generation import (
    RecurringOrderGenerationService,
    recurring_schedule_spec,
)
from app.services.recurring_validation import validate_recurring_service_catalog


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

    # --- 계약 CRUD ---
    def create_contract(self, payload: RecurringContractCreate, *, actor_user_id: str | None) -> RecurringContract:
        # 그룹 생성(commit) 전에 FK 대상을 검증한다. 잘못된 partner_id면 그룹만 남는
        # 고아 그룹이 발생하므로(create_empty_group이 즉시 commit) 미리 막는다.
        if payload.default_partner_id is not None:
            if PartnerRepository(self.db).get(payload.default_partner_id) is None:
                raise ValueError("partner_not_found")
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
            **data,
        )
        self.db.add(contract)
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
        contract = self.contracts.get(contract_id)
        if contract is None:
            raise ValueError("recurring_contract_not_found")
        changes = payload.model_dump(exclude_unset=True)

        # 생성 경로와 동일하게 default_partner_id 존재를 검증한다(잘못된 FK PATCH로
        # Postgres IntegrityError가 나기 전에 막는다 — SQLite 테스트는 FK 미강제).
        if changes.get("default_partner_id") is not None:
            if PartnerRepository(self.db).get(changes["default_partner_id"]) is None:
                raise ValueError("partner_not_found")
        if (
            "partner_billing_mode" in changes
            and changes["partner_billing_mode"] != contract.partner_billing_mode
            and self._has_partner_billing_history(contract.id)
        ):
            raise ValueError("recurring_partner_billing_mode_locked")
        service_item_id = changes.get("service_item_id")
        service_category_id = changes.get("service_category_id")
        validate_recurring_service_catalog(
            self.db,
            service_item_id=service_item_id if isinstance(service_item_id, str) else None,
            service_category_id=service_category_id if isinstance(service_category_id, str) else None,
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

    def _has_partner_billing_history(self, contract_id: str) -> bool:
        generated_order_id = self.db.scalar(
            select(Order.id).where(Order.recurring_contract_id == contract_id).limit(1)
        )
        if generated_order_id is not None:
            return True
        monthly_status_id = self.db.scalar(
            select(RecurringMonthlyStatus.id)
            .where(RecurringMonthlyStatus.contract_id == contract_id)
            .limit(1)
        )
        return monthly_status_id is not None

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
