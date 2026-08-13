from datetime import date, datetime
from typing import Annotated

from pydantic import Field, model_validator

from app.domain.constants import (
    RecurrenceMode,
    RecurringBillingMode,
    RecurringContractStatus,
    VatType,
)
from app.domain.recurrence import validate_recurrence_fields
from app.schemas.common import ApiModel


class RecurringContractBase(ApiModel):
    label: str = Field(min_length=1, max_length=160)
    # 고객정보(공유 그룹에 저장)
    customer_name: str
    customer_phone: str
    customer_address: str
    customer_address_detail: str | None = None
    customer_visible_payment: bool = False
    notes: str | None = None
    # 스케줄
    recurrence_mode: RecurrenceMode
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    interval_weeks: int | None = Field(default=None, ge=1, le=12)
    weekday: int | None = Field(default=None, ge=0, le=6)
    weekdays: list[Annotated[int, Field(ge=0, le=6)]] | None = None
    start_date: date
    end_date: date | None = None
    max_occurrences: int | None = Field(default=None, ge=1)
    # 회차 템플릿
    default_partner_id: str | None = None
    team_name: str | None = None
    team_phone: str | None = None
    service_category_id: str | None = None
    service_item_id: str | None = None
    service_name: str
    size_or_quantity: str | None = None
    service_detail: str | None = None
    special_request: str | None = None
    requested_time: str | None = None
    # per_visit: total_amount=회당 금액(월 합산=회당×방문횟수). monthly: total_amount=월 고정 금액.
    billing_mode: RecurringBillingMode = RecurringBillingMode.PER_VISIT
    partner_billing_mode: RecurringBillingMode = RecurringBillingMode.PER_VISIT
    total_amount: float | None = Field(default=None, ge=0)
    discount_amount: float = Field(default=0, ge=0)
    deposit_amount: float | None = Field(default=None, ge=0)
    balance_amount: float | None = Field(default=None, ge=0)
    vat_type: VatType | None = None
    partner_payment_amount: float | None = Field(default=None, ge=0)


class RecurringContractCreate(RecurringContractBase):
    @model_validator(mode="after")
    def _check_recurrence_fields(self) -> "RecurringContractCreate":
        validate_recurrence_fields(self.recurrence_mode, self.day_of_month, self.interval_weeks)
        return self


class RecurringContractUpdate(ApiModel):
    label: str | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    customer_address: str | None = None
    customer_address_detail: str | None = None
    customer_visible_payment: bool | None = None
    notes: str | None = None
    recurrence_mode: RecurrenceMode | None = None
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    interval_weeks: int | None = Field(default=None, ge=1, le=12)
    weekday: int | None = Field(default=None, ge=0, le=6)
    weekdays: list[Annotated[int, Field(ge=0, le=6)]] | None = None
    start_date: date | None = None
    end_date: date | None = None
    max_occurrences: int | None = Field(default=None, ge=1)
    default_partner_id: str | None = None
    team_name: str | None = None
    team_phone: str | None = None
    service_category_id: str | None = None
    service_item_id: str | None = None
    service_name: str | None = None
    size_or_quantity: str | None = None
    service_detail: str | None = None
    special_request: str | None = None
    requested_time: str | None = None
    billing_mode: RecurringBillingMode | None = None
    partner_billing_mode: RecurringBillingMode | None = None
    total_amount: float | None = Field(default=None, ge=0)
    discount_amount: float | None = Field(default=None, ge=0)
    deposit_amount: float | None = Field(default=None, ge=0)
    balance_amount: float | None = Field(default=None, ge=0)
    vat_type: VatType | None = None
    partner_payment_amount: float | None = Field(default=None, ge=0)


class RecurringContractRead(RecurringContractBase):
    id: str
    order_group_id: str
    customer_token: str
    status: RecurringContractStatus
    next_due_date: date | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RecurringContractSummaryRead(ApiModel):
    id: str
    label: str
    customer_name: str
    status: RecurringContractStatus
    schedule_text: str
    next_due_date: date | None = None
