import { apiRequest } from './client';

export type RecurrenceMode = 'monthly' | 'weekly';
export type RecurringContractStatus = 'active' | 'paused' | 'ended';

export interface RecurringContractInput {
  label: string;
  customer_name: string;
  customer_phone: string;
  customer_address: string;
  customer_address_detail?: string | null;
  customer_visible_payment?: boolean;
  notes?: string | null;
  recurrence_mode: RecurrenceMode;
  day_of_month?: number | null;
  interval_weeks?: number | null;
  weekday?: number | null;
  start_date: string;
  end_date?: string | null;
  max_occurrences?: number | null;
  default_partner_id?: string | null;
  team_name?: string | null;
  service_category_id?: string | null;
  service_item_id?: string | null;
  service_name: string;
  size_or_quantity?: string | null;
  service_detail?: string | null;
  special_request?: string | null;
  requested_time?: string | null;
  total_amount?: number | null;
  discount_amount?: number;
  deposit_amount?: number | null;
  balance_amount?: number | null;
  vat_type?: string | null;
  partner_payment_amount?: number | null;
}

export interface RecurringContractSummary {
  id: string;
  label: string;
  customer_name: string;
  status: RecurringContractStatus;
  schedule_text: string;
  next_due_date: string | null;
  pending_count: number;
  this_month_count: number;
  this_month_amount: number;
}

export interface RecurringContract extends RecurringContractInput {
  id: string;
  order_group_id: string;
  customer_token: string;
  status: RecurringContractStatus;
  next_due_date: string | null;
}

export interface PendingOccurrence {
  occurrence_id: string;
  contract_id: string;
  contract_label: string;
  customer_name: string;
  sequence_no: number;
  due_date: string;
  service_name: string;
  total_amount: number | null;
  default_partner_id: string | null;
  default_partner_name: string | null;
  is_overdue: boolean;
}

export interface ApproveItemInput {
  occurrence_id: string;
  partner_id?: string | null;
  scheduled_date?: string | null;
  total_amount?: number | null;
}

export interface ApproveOccurrencesResult {
  generated_order_ids: string[];
  skipped_occurrence_ids: string[];
}

export interface SkipItemInput {
  occurrence_id: string;
  reason?: string;
}

export interface SkipOccurrencesResult {
  skipped_occurrence_ids: string[];
}

export function listRecurringContracts(): Promise<RecurringContractSummary[]> {
  return apiRequest('/admin/recurring/contracts') as Promise<RecurringContractSummary[]>;
}

export function getRecurringContract(id: string): Promise<RecurringContract> {
  return apiRequest(`/admin/recurring/contracts/${encodeURIComponent(id)}`) as Promise<RecurringContract>;
}

export function createRecurringContract(input: RecurringContractInput): Promise<RecurringContract> {
  return apiRequest('/admin/recurring/contracts', { method: 'POST', body: input }) as Promise<RecurringContract>;
}

export function updateRecurringContract(
  id: string,
  input: Partial<RecurringContractInput>,
): Promise<RecurringContract> {
  return apiRequest(`/admin/recurring/contracts/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: input,
  }) as Promise<RecurringContract>;
}

export function pauseRecurringContract(id: string): Promise<RecurringContract> {
  return apiRequest(`/admin/recurring/contracts/${encodeURIComponent(id)}/pause`, {
    method: 'POST',
  }) as Promise<RecurringContract>;
}

export function resumeRecurringContract(id: string): Promise<RecurringContract> {
  return apiRequest(`/admin/recurring/contracts/${encodeURIComponent(id)}/resume`, {
    method: 'POST',
  }) as Promise<RecurringContract>;
}

export function endRecurringContract(id: string): Promise<RecurringContract> {
  return apiRequest(`/admin/recurring/contracts/${encodeURIComponent(id)}/end`, {
    method: 'POST',
  }) as Promise<RecurringContract>;
}

export function deleteRecurringContract(id: string): Promise<void> {
  return apiRequest(`/admin/recurring/contracts/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  }) as Promise<void>;
}

export function syncRecurringOccurrences(): Promise<PendingOccurrence[]> {
  return apiRequest('/admin/recurring/occurrences/sync', { method: 'POST' }) as Promise<PendingOccurrence[]>;
}

export function listPendingOccurrences(): Promise<PendingOccurrence[]> {
  return apiRequest('/admin/recurring/occurrences/pending') as Promise<PendingOccurrence[]>;
}

export function approveOccurrences(items: ApproveItemInput[]): Promise<ApproveOccurrencesResult> {
  return apiRequest('/admin/recurring/occurrences/approve', {
    method: 'POST',
    body: { items },
  }) as Promise<ApproveOccurrencesResult>;
}

export function skipOccurrences(items: SkipItemInput[]): Promise<SkipOccurrencesResult> {
  return apiRequest('/admin/recurring/occurrences/skip', {
    method: 'POST',
    body: { items },
  }) as Promise<SkipOccurrencesResult>;
}
