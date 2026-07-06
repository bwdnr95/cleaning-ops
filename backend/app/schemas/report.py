from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

class RevenueBucket(BaseModel):
    period: date
    completed_count: int = Field(..., ge=0)
    revenue: Decimal


class RevenueReport(BaseModel):
    granularity: str
    start_date: date
    end_date: date
    partner_id: str | None = None
    service_item_id: str | None = None
    buckets: list[RevenueBucket]
    total_revenue: Decimal
    total_completed: int


class PartnerPerformanceRow(BaseModel):
    partner_id: str
    partner_name: str
    job_count: int
    avg_unit_price: Decimal
    pending_settlement_count: int
    expected_settlement_amount: Decimal


class PartnerPerformanceReport(BaseModel):
    start_date: date
    end_date: date
    rows: list[PartnerPerformanceRow]


class ServicePopularityRow(BaseModel):
    service_item_id: str | None = None
    service_name: str
    job_count: int
    revenue: Decimal
    revenue_share_pct: float


class ServicePopularityReport(BaseModel):
    start_date: date
    end_date: date
    rows: list[ServicePopularityRow]


class SourceChannelRow(BaseModel):
    source_channel: str
    order_count: int = Field(..., ge=0)
    completed_count: int = Field(..., ge=0)
    revenue: Decimal
    revenue_share_pct: float


class SourceChannelReport(BaseModel):
    start_date: date
    end_date: date
    rows: list[SourceChannelRow]
    total_orders: int = Field(..., ge=0)
    total_completed: int = Field(..., ge=0)
    total_revenue: Decimal


class SettlementBacklogRow(BaseModel):
    order_id: str
    scheduled_date: date | None
    service_name: str
    partner_id: str | None
    partner_name: str | None
    total_amount: Decimal
    expected_settlement_amount: Decimal
    status: str
    source: str = "order"


class SettlementBacklogReport(BaseModel):
    rows: list[SettlementBacklogRow]


class OrderImportFailure(BaseModel):
    row_index: int
    reason: str


class OrderImportResult(BaseModel):
    succeeded_groups: int
    succeeded_lines: int
    failed: list[OrderImportFailure]
