import { apiRequest } from './client';

// 계약×월 단위 세금계산서/잔금 토글 트래커. (계약, 월) 파생 행 — 새 테이블은 상태 토글만 보존.
// 백엔드 스키마: app/schemas/recurring_monthly.py (snake_case 그대로 수신).

export interface RecurringMonthlyRow {
  contract_id: string;
  label: string;
  customer_name: string;
  schedule_text: string;
  month: string;
  amount: number | null;
  partner_amount: number | null;
  partner_billing_mode: 'per_visit' | 'monthly';
  tax_invoice_issued: boolean;
  balance_paid: boolean;
  partner_payment_paid: boolean;
}

// month: "YYYY-MM".
export function getRecurringMonthly(month: string): Promise<RecurringMonthlyRow[]> {
  return apiRequest(
    `/admin/recurring/monthly?month=${encodeURIComponent(month)}`,
  ) as Promise<RecurringMonthlyRow[]>;
}

// 세금계산서 발행/잔금 입금 토글을 부분 갱신한다(전달한 필드만 변경, 나머지는 유지).
export function setRecurringMonthlyStatus(
  contractId: string,
  month: string,
  patch: {
    tax_invoice_issued?: boolean;
    balance_paid?: boolean;
    partner_payment_paid?: boolean;
  },
): Promise<RecurringMonthlyRow> {
  return apiRequest('/admin/recurring/monthly/set', {
    method: 'POST',
    body: { contract_id: contractId, month, ...patch },
  }) as Promise<RecurringMonthlyRow>;
}
