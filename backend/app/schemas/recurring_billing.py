from pydantic import Field

from app.schemas.common import ApiModel


class PartnerSubtotalRead(ApiModel):
    partner_id: str | None = None
    partner_name: str | None = None
    partner_total: float
    unpaid_partner_total: float
    settleable_count: int


class RecurringBillingRowRead(ApiModel):
    contract_id: str
    label: str
    customer_name: str
    month: str
    visit_count: int
    billed_total: float
    confirmed_revenue: float
    unpaid_customer_count: int
    payment_breakdown: dict[str, int]
    partner_total: float
    unpaid_partner_total: float
    unpaid_partner_count: int
    partner_subtotals: list[PartnerSubtotalRead]


class MarkPaidRequest(ApiModel):
    contract_id: str
    month: str = Field(pattern=r"^\d{4}-\d{2}$")


class MarkPaidResult(ApiModel):
    updated_order_ids: list[str]
    skipped_count: int


class SettleMonthRequest(ApiModel):
    contract_id: str
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    partner_id: str | None = None


class SettleMonthResult(ApiModel):
    settled_order_ids: list[str]
    skipped_count: int
