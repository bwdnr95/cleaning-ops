from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import business_today, utc_now
from app.domain.constants import (
    OrderStatus,
    RecurrenceMode,
    RecurringBillingMode,
    RecurringContractStatus,
    VatType,
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
        if (
            "partner_billing_mode" in changes
            and changes["partner_billing_mode"] != contract.partner_billing_mode
            and self._has_partner_billing_history(contract.id)
        ):
            raise ValueError("recurring_partner_billing_mode_locked")

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
        """해당 월의 정기 주문을 (없으면) 멱등 생성한 뒤 목록으로 반환한다.

        스케줄러가 없으므로 월 트래커(list_month)와 동일하게 '조회 시 생성' 방식을 쓴다.
        생성된 주문은 recurring_contract_id로 스탬프되어 일반 주문 파이프라인을 그대로
        타므로 협력사링크에도 다른 주문과 동일하게 노출된다(2-5).
        """
        first, last = _month_bounds(month)
        today = business_today()
        # '매월 1일 생성' 스펙: 생성은 현재 달을 조회할 때만 수행한다. 과거/미래 달은 읽기 전용이라
        # 임의의 달을 넘겨봐도 운영 큐(주문목록/캘린더/대시보드/협력사링크)가 미리 오염되지 않는다.
        if (today.year, today.month) == (first.year, first.month):
            self._generate_month(first, last, actor_user_id=actor_user_id)
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

    def _generate_month(self, first: date, last: date, *, actor_user_id: str | None) -> None:
        """활성 계약의 해당 월 예정일마다 주문을 멱등 생성한다.

        (recurring_contract_id, scheduled_date)가 이미 있으면 건너뛴다. 월/주간 다중요일
        모두 iter_due_dates가 처리하므로 매주 특정 요일(2-3)도 그대로 생성된다.
        """
        created = False
        for contract in self.contracts.list_active():
            if contract.start_date > last:
                continue
            if contract.end_date is not None and contract.end_date < first:
                continue
            group = self.groups.get(contract.order_group_id)
            if group is None:
                continue
            # 멱등 키 = '생성 당시 예정일'(recurring_planned_date, 불변)이며 soft-delete분까지
            # 포함해 조회한다 → 방문일을 옮기거나 회차를 삭제해도 그 슬롯을 재생성하지 않는다.
            existing = set(
                self.db.scalars(
                    select(Order.recurring_planned_date).where(
                        Order.recurring_contract_id == contract.id,
                        Order.recurring_planned_date >= first,
                        Order.recurring_planned_date <= last,
                    )
                )
            )
            try:
                # 계약 단위 savepoint: 한 계약의 설정 오류(비활성 서비스 항목 등)나 동시 생성
                # 충돌(유니크 위반)이 그 달 전체 조회를 막지 않도록 격리한다(이 계약만 건너뜀).
                with self.db.begin_nested():
                    for _seq, due in iter_due_dates(self._spec(contract), until=last):
                        if due < first or due > last or due in existing:
                            continue
                        order = self.orders.add_recurring_line(
                            group,
                            self._contract_line_payload(contract, due),
                            recurring_contract_id=contract.id,
                            actor_user_id=actor_user_id,
                        )
                        order.recurring_planned_date = due
                        existing.add(due)
                        created = True
            except Exception:
                continue
        if created:
            self.db.commit()

    def _contract_line_payload(self, contract: RecurringContract, due: date) -> OrderLineCreate:
        # 계약 템플릿 → 주문 라인. 방문일이 계약 예정일이므로 '일정확정'으로 생성해
        # 배정 협력사의 링크/일정에 바로 노출한다(협력사 미지정이면 미배정 상태로 확정).
        def _f(value: Decimal | None) -> float | None:
            return float(value) if value is not None else None
        is_partner_per_visit = (
            contract.partner_billing_mode or RecurringBillingMode.PER_VISIT
        ) == RecurringBillingMode.PER_VISIT

        return OrderLineCreate(
            status=OrderStatus.SCHEDULE_CONFIRMED,
            received_date=business_today(),
            scheduled_date=due,
            requested_time=contract.requested_time,
            partner_id=contract.default_partner_id,
            team_name=contract.team_name,
            service_category_id=contract.service_category_id,
            service_item_id=contract.service_item_id,
            service_name=contract.service_name,
            size_or_quantity=contract.size_or_quantity,
            service_detail=contract.service_detail,
            special_request=contract.special_request,
            # 회당(per_visit): 각 회차 = 회당 금액 → 회차 주문이 정상적으로 매출 집계(월합 = 회당×방문수)에 반영된다.
            # 월 고정(monthly): 회차별 금액 없음(None). 월 고정 청구는 회차 수와 무관하므로 회차마다 금액을
            # 실으면 N배 과대계상된다. 그래서 회차에는 금액을 두지 않고, 월 고정 청구/매출은 '월 트래커'
            # (RecurringMonthlyStatus, 세금계산서/잔금)에서 계약×월 단위로 관리한다. 결과적으로 월 고정 정기분은
            # 주문 단위 매출 대시보드(dashboard.monthly_revenue)에는 잡히지 않는다 — 의도된 경계(과대계상 방지).
            # 월 고정 정기 매출을 대시보드로 롤업하려면 월 트래커를 매출 소스로 합류시키는 별도 작업이 필요하다.
            total_amount=(
                None
                if contract.billing_mode == RecurringBillingMode.MONTHLY
                else _f(contract.total_amount)
            ),
            discount_amount=_f(contract.discount_amount) or 0,
            deposit_amount=_f(contract.deposit_amount),
            balance_amount=_f(contract.balance_amount),
            vat_type=contract.vat_type or VatType.INCLUDED,
            partner_payment_amount=(
                _f(contract.partner_payment_amount) if is_partner_per_visit else None
            ),
        )
