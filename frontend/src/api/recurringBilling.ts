import { apiRequest, downloadBlob } from './client';

// 월 합산 청구·정산. (계약, 월) 단위 파생 집계 — 새 테이블 없음.
// 백엔드 스키마: app/schemas/recurring_billing.py (snake_case 그대로 수신).

export interface PartnerSubtotal {
  partner_id: string | null;
  partner_name: string | null;
  partner_total: number;
  unpaid_partner_total: number;
  settleable_count: number;
}

export interface RecurringBillingRow {
  contract_id: string;
  label: string;
  customer_name: string;
  month: string;
  visit_count: number;
  billed_total: number;
  confirmed_revenue: number;
  unpaid_customer_count: number;
  payment_breakdown: Record<string, number>;
  partner_total: number;
  unpaid_partner_total: number;
  unpaid_partner_count: number;
  partner_subtotals: PartnerSubtotal[];
}

export interface MarkPaidResult {
  updated_order_ids: string[];
  skipped_count: number;
}

export interface SettleMonthResult {
  settled_order_ids: string[];
  skipped_count: number;
}

// month: "YYYY-MM".
export function getRecurringBilling(month: string): Promise<RecurringBillingRow[]> {
  return apiRequest(
    `/admin/recurring/billing?month=${encodeURIComponent(month)}`,
  ) as Promise<RecurringBillingRow[]>;
}

// 해당 월 미입금 정기 주문을 일괄 입금완료로 표시한다(이미 입금/환불 건은 skip).
export function markRecurringMonthPaid(
  contractId: string,
  month: string,
): Promise<MarkPaidResult> {
  return apiRequest('/admin/recurring/billing/mark-paid', {
    method: 'POST',
    body: { contract_id: contractId, month },
  }) as Promise<MarkPaidResult>;
}

// 해당 월 정산 가능(서비스완료+미정산) 정기 주문을 일괄 정산완료로 표시한다.
// partnerId 지정 시 해당 협력사분만 정산한다.
export function settleRecurringMonth(
  contractId: string,
  month: string,
  partnerId?: string | null,
): Promise<SettleMonthResult> {
  return apiRequest('/admin/recurring/billing/settle', {
    method: 'POST',
    body: { contract_id: contractId, month, partner_id: partnerId ?? null },
  }) as Promise<SettleMonthResult>;
}

// 월 청구·정산 표를 CSV(utf-8-sig)로 내려받는다.
export function exportRecurringBilling(month: string): Promise<void> {
  return downloadBlob(
    `/admin/recurring/billing/export?month=${encodeURIComponent(month)}`,
    `recurring-billing-${month}.csv`,
  );
}
