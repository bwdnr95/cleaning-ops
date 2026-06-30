from pydantic import Field

from app.schemas.common import ApiModel


class RecurringMonthlyRowRead(ApiModel):
    contract_id: str
    label: str
    customer_name: str
    schedule_text: str
    month: str
    amount: float | None = None
    tax_invoice_issued: bool
    balance_paid: bool


class SetMonthlyStatusRequest(ApiModel):
    contract_id: str
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    tax_invoice_issued: bool | None = None
    balance_paid: bool | None = None
