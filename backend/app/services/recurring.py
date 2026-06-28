from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.time import business_today, utc_now
from app.domain.constants import RecurringContractStatus
from app.models.order_group import OrderGroup
from app.models.recurring_contract import RecurringContract
from app.repositories.order_groups import OrderGroupRepository
from app.repositories.recurring import RecurringContractRepository, RecurringOccurrenceRepository
from app.schemas.order import OrderGroupCreate, OrderLineCreate
from app.schemas.recurring import RecurringContractCreate, RecurringContractUpdate
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
