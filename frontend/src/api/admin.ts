import { apiBlobRequest, apiRequest } from './client';

export type MessageChannelInput = 'kakao' | 'sms' | 'lms';
export type SettlementStatusFilter = 'unpaid' | 'paid' | 'all';
export type AdminOrderSort = 'visit_asc' | 'visit_desc' | 'received_asc' | 'received_desc';

export interface AdminOrderLineInput {
  status?: string;
  received_date?: string;
  scheduled_date?: string | null;
  requested_time?: string | null;
  partner_id?: string | null;
  team_name?: string | null;
  broker_id?: string | null;
  service_category_id?: string | null;
  service_item_id?: string | null;
  service_name: string;
  size_or_quantity?: string | null;
  service_detail?: string | null;
  special_request?: string | null;
  total_amount?: number | null;
  discount_amount?: number;
  deposit_amount?: number | null;
  balance_amount?: number | null;
  onsite_extra_amount?: number | null;
  vat_type?: string | null;
  payment_status?: string | null;
  payment_memo?: string | null;
  evidence_memo?: string | null;
  receipt_type?: string | null;
  receipt_status?: string | null;
  partner_payment_amount?: number | null;
  partner_payment_status?: string | null;
}

export interface CreateOrderInput extends AdminOrderLineInput {
  customer_name: string;
  customer_phone: string;
  customer_address: string;
  customer_address_detail?: string | null;
  source_channel?: string | null;
  customer_visible_payment?: boolean;
}

export type UpdateOrderInput = Partial<AdminOrderLineInput>;

export interface OrderGroupCreateInput {
  customer_name: string;
  customer_phone: string;
  customer_address: string;
  customer_address_detail?: string | null;
  source_channel?: string | null;
  customer_visible_payment?: boolean;
  notes?: string | null;
  lines: AdminOrderLineInput[];
}

export interface OrderGroupUpdateInput {
  customer_name?: string;
  customer_phone?: string;
  customer_address?: string;
  customer_address_detail?: string | null;
  source_channel?: string | null;
  customer_visible_payment?: boolean;
  notes?: string | null;
}

export interface AdminOrder extends AdminOrderLineInput {
  id: string;
  group_id: string;
  customer_name: string;
  customer_phone: string;
  customer_address: string;
  customer_address_detail?: string | null;
  customer_token: string;
  consumer_price?: number | null;
  partner_price?: number | null;
  partner_settled_at?: string | null;
  recurring_contract_id?: string | null;
}

export interface AdminOrderGroup {
  id: string;
  customer_token: string;
  lines: AdminOrder[];
}

export interface AdminCalendarOrder {
  id: string;
  status: string;
  scheduled_date: string;
  requested_time?: string | null;
  partner_id?: string | null;
  team_name?: string | null;
  service_name: string;
  size_or_quantity?: string | null;
  customer_name: string;
  customer_phone?: string | null;
  customer_address: string;
  customer_address_detail?: string | null;
}

export interface MessageLog {
  id: string;
  order_id: string;
  message_type: string;
  recipient_type: string;
  channel: string;
  status: string;
  content: string;
}

export interface PartnerSettlementItem {
  order_id: string;
  status: string;
  scheduled_date: string | null;
  service_name: string;
  customer_name: string;
  address_short: string;
  address_detail?: string | null;
  consumer_price: number | null;
  partner_price: number | null;
  partner_payment_status: string | null;
  settled_at: string | null;
  // 이 라인이 속한 그룹(고객)의 합계. 0원 라인 보조표시용.
  group_consumer_total: number;
  group_partner_total: number;
}

export interface PartnerSettlementListParams {
  status?: SettlementStatusFilter;
  from?: string;
  to?: string;
}

export interface PartnerSettlementListResponse {
  items: PartnerSettlementItem[];
  total_partner_price: number;
  total_consumer_price: number;
  count: number;
}

export interface SettleOrdersInput {
  order_ids: string[];
  memo?: string | null;
}

export interface PartnerSettlementActionResult {
  updated_order_ids: string[];
  skipped_order_ids: string[];
}

export function getDashboardSummary() {
  return apiRequest('/admin/dashboard/summary');
}

export function getDashboardRecentActivity() {
  return apiRequest('/admin/dashboard/recent-activity');
}

export function listAdminCalendarOrders({ year, month, partnerId = '' }): Promise<AdminCalendarOrder[]> {
  const params = new URLSearchParams({
    year: String(year),
    month: String(month),
  });
  if (partnerId) {
    params.set('partner_id', partnerId);
  }
  return apiRequest(`/admin/calendar?${params.toString()}`) as Promise<AdminCalendarOrder[]>;
}

export function listAdminOrders(
  { sort = 'visit_asc', includePastPaid = false }: { sort?: AdminOrderSort; includePastPaid?: boolean } = {},
): Promise<AdminOrder[]> {
  const params = new URLSearchParams();
  params.set('sort', sort);
  if (includePastPaid) {
    params.set('include_past_paid', 'true');
  }
  return apiRequest(`/admin/orders?${params.toString()}`) as Promise<AdminOrder[]>;
}

export interface AdminOrderPageParams {
  page?: number;
  page_size?: number;
  sort?: AdminOrderSort;
  status?: string;
  visit_preset?: string;
  visit_from?: string;
  visit_to?: string;
  received_preset?: string;
  received_from?: string;
  received_to?: string;
  partner_id?: string;
  broker_id?: string;
  q?: string;
}

export interface AdminOrderPageSummary {
  count: number;
  consumer_total: number;
  partner_total: number;
  profit: number;
}

export interface AdminOrderPageInsight {
  today_jobs: number;
  unassigned: number;
  schedule_confirmed: number;
  work_done: number;
  unpaid_total: number;
  month_total: number;
}

export interface AdminOrderPageResponse {
  items: AdminOrder[];
  total: number;
  status_counts: Record<string, number>;
  summary: AdminOrderPageSummary;
  insight: AdminOrderPageInsight;
}

export function listAdminOrdersPage(params: AdminOrderPageParams = {}): Promise<AdminOrderPageResponse> {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') {
      continue;
    }
    search.set(key, String(value));
  }
  const query = search.toString();
  return apiRequest(`/admin/orders/page${query ? `?${query}` : ''}`) as Promise<AdminOrderPageResponse>;
}

export interface ImportFailure {
  row_index: number;
  reason: string;
}

export interface ImportResult {
  succeeded_groups: number;
  succeeded_lines: number;
  failed: ImportFailure[];
}

export function importOrders(file: File): Promise<ImportResult> {
  const form = new FormData();
  form.append('file', file);
  return apiRequest('/admin/orders/import', { method: 'POST', body: form });
}

export function exportAdminOrders(orderIds: string[]): Promise<Blob> {
  return apiBlobRequest('/admin/orders/export', {
    method: 'POST',
    body: { order_ids: orderIds },
  });
}

export function createAdminOrder(input: CreateOrderInput): Promise<AdminOrder> {
  return apiRequest('/admin/orders', {
    method: 'POST',
    body: input,
  }) as Promise<AdminOrder>;
}

export function getAdminOrder(orderId: string): Promise<AdminOrder> {
  return apiRequest(`/admin/orders/${encodeURIComponent(orderId)}`) as Promise<AdminOrder>;
}

export function updateAdminOrder(orderId: string, input: UpdateOrderInput): Promise<AdminOrder> {
  return apiRequest(`/admin/orders/${encodeURIComponent(orderId)}`, {
    method: 'PATCH',
    body: input,
  }) as Promise<AdminOrder>;
}

export function sendOrderQuote(
  orderId: string,
  channel: MessageChannelInput = 'kakao',
): Promise<MessageLog> {
  return apiRequest(`/admin/orders/${encodeURIComponent(orderId)}/quote/send`, {
    method: 'POST',
    body: { channel },
  }) as Promise<MessageLog>;
}

export function notifyPartnerUnpaid(
  orderId: string,
  channel: MessageChannelInput = 'kakao',
  memo = '',
): Promise<MessageLog> {
  return apiRequest(`/admin/orders/${encodeURIComponent(orderId)}/notify-partner-unpaid`, {
    method: 'POST',
    body: { channel, memo },
  }) as Promise<MessageLog>;
}

export function deleteAdminOrder(orderId) {
  return apiRequest(`/admin/orders/${encodeURIComponent(orderId)}`, {
    method: 'DELETE',
  });
}

export function bulkDeleteAdminOrders(orderIds) {
  return apiRequest('/admin/orders/bulk-delete', {
    method: 'POST',
    body: { order_ids: orderIds },
  });
}

export function createOrderGroup(input: OrderGroupCreateInput): Promise<AdminOrderGroup> {
  return apiRequest('/admin/orders/groups', {
    method: 'POST',
    body: input,
  }) as Promise<AdminOrderGroup>;
}

export function getAdminOrderGroup(groupId: string): Promise<AdminOrderGroup> {
  return apiRequest(`/admin/orders/groups/${encodeURIComponent(groupId)}`) as Promise<AdminOrderGroup>;
}

export function addLineToGroup(groupId: string, input: AdminOrderLineInput): Promise<AdminOrder> {
  return apiRequest(`/admin/orders/groups/${encodeURIComponent(groupId)}/lines`, {
    method: 'POST',
    body: input,
  }) as Promise<AdminOrder>;
}

export function updateAdminOrderGroup(
  groupId: string,
  input: OrderGroupUpdateInput,
): Promise<AdminOrderGroup> {
  return apiRequest(`/admin/orders/groups/${encodeURIComponent(groupId)}`, {
    method: 'PATCH',
    body: input,
  }) as Promise<AdminOrderGroup>;
}

export function listPartners() {
  return apiRequest('/admin/partners');
}

export function listAdminPartners({ includeInactive = true } = {}) {
  const params = new URLSearchParams();
  if (includeInactive) {
    params.set('include_inactive', 'true');
  }
  const query = params.toString();
  return apiRequest(`/admin/partners${query ? `?${query}` : ''}`);
}

export function createAdminPartner(input) {
  return apiRequest('/admin/partners', {
    method: 'POST',
    body: input,
  });
}

export function getAdminPartner(partnerId) {
  return apiRequest(`/admin/partners/${encodeURIComponent(partnerId)}`);
}

export function updateAdminPartner(partnerId, input) {
  return apiRequest(`/admin/partners/${encodeURIComponent(partnerId)}`, {
    method: 'PATCH',
    body: input,
  });
}

export function deleteAdminPartner(partnerId) {
  return apiRequest(`/admin/partners/${encodeURIComponent(partnerId)}`, {
    method: 'DELETE',
  });
}

export function resetAdminPartnerPassword(partnerId, input = {}) {
  return apiRequest(`/admin/partners/${encodeURIComponent(partnerId)}/reset-password`, {
    method: 'POST',
    body: input,
  });
}

export function listPartnerSettlements(
  partnerId: string,
  { status = 'unpaid', from = '', to = '' }: PartnerSettlementListParams = {},
): Promise<PartnerSettlementListResponse> {
  const params = new URLSearchParams({ status });
  if (from) params.set('from', from);
  if (to) params.set('to', to);
  return apiRequest(
    `/admin/partners/${encodeURIComponent(partnerId)}/settlements?${params.toString()}`,
  ) as Promise<PartnerSettlementListResponse>;
}

export function settlePartnerOrders(
  partnerId: string,
  orderIds: string[],
  memo = '',
): Promise<PartnerSettlementActionResult> {
  const input: SettleOrdersInput = { order_ids: orderIds, memo };
  return apiRequest(`/admin/partners/${encodeURIComponent(partnerId)}/settlements/settle`, {
    method: 'POST',
    body: input,
  }) as Promise<PartnerSettlementActionResult>;
}

export function revertPartnerOrders(
  partnerId: string,
  orderIds: string[],
): Promise<PartnerSettlementActionResult> {
  const input: SettleOrdersInput = { order_ids: orderIds };
  return apiRequest(`/admin/partners/${encodeURIComponent(partnerId)}/settlements/revert`, {
    method: 'POST',
    body: input,
  }) as Promise<PartnerSettlementActionResult>;
}

export function listPartnerCategories({ includeInactive = true } = {}) {
  const params = new URLSearchParams();
  if (includeInactive) {
    params.set('include_inactive', 'true');
  }
  const query = params.toString();
  return apiRequest(`/admin/partners/categories${query ? `?${query}` : ''}`);
}

export function createPartnerCategory(input) {
  return apiRequest('/admin/partners/categories', {
    method: 'POST',
    body: input,
  });
}

export function updatePartnerCategory(categoryId, input) {
  return apiRequest(`/admin/partners/categories/${encodeURIComponent(categoryId)}`, {
    method: 'PATCH',
    body: input,
  });
}

export function deletePartnerCategory(categoryId) {
  return apiRequest(`/admin/partners/categories/${encodeURIComponent(categoryId)}`, {
    method: 'DELETE',
  });
}

// 중개사(broker) — 협력사와 동일 패턴. listBrokers=활성만(드롭다운용), listAdminBrokers=전체(관리 화면용).
export function listBrokers() {
  return apiRequest('/admin/brokers');
}

export function listAdminBrokers({ includeInactive = true } = {}) {
  const params = new URLSearchParams();
  if (includeInactive) {
    params.set('include_inactive', 'true');
  }
  const query = params.toString();
  return apiRequest(`/admin/brokers${query ? `?${query}` : ''}`);
}

export function createAdminBroker(input) {
  return apiRequest('/admin/brokers', {
    method: 'POST',
    body: input,
  });
}

export function getAdminBroker(brokerId) {
  return apiRequest(`/admin/brokers/${encodeURIComponent(brokerId)}`);
}

export function updateAdminBroker(brokerId, input) {
  return apiRequest(`/admin/brokers/${encodeURIComponent(brokerId)}`, {
    method: 'PATCH',
    body: input,
  });
}

export function deleteAdminBroker(brokerId) {
  return apiRequest(`/admin/brokers/${encodeURIComponent(brokerId)}`, {
    method: 'DELETE',
  });
}

export function listServiceCatalog({ includeInactive = false } = {}) {
  const params = new URLSearchParams();
  if (includeInactive) {
    params.set('include_inactive', 'true');
  }
  const query = params.toString();
  return apiRequest(`/admin/services${query ? `?${query}` : ''}`);
}

export interface ServiceItemSummary {
  id: string;
  name: string;
}

interface ServiceCategoryWithItems {
  id: string;
  name: string;
  items?: ServiceItemSummary[];
}

export function listServiceItems(): Promise<ServiceItemSummary[]> {
  return (listServiceCatalog() as Promise<ServiceCategoryWithItems[]>).then((categories) =>
    categories.flatMap((category) =>
      (category.items ?? []).map((item) => ({ id: item.id, name: item.name })),
    ),
  );
}

export function createServiceCategory(input) {
  return apiRequest('/admin/services/categories', {
    method: 'POST',
    body: input,
  });
}

export function updateServiceCategory(categoryId, input) {
  return apiRequest(`/admin/services/categories/${encodeURIComponent(categoryId)}`, {
    method: 'PATCH',
    body: input,
  });
}

export function deleteServiceCategory(categoryId) {
  return apiRequest(`/admin/services/categories/${encodeURIComponent(categoryId)}`, {
    method: 'DELETE',
  });
}

export function createServiceItem(input) {
  return apiRequest('/admin/services/items', {
    method: 'POST',
    body: input,
  });
}

export function updateServiceItem(itemId, input) {
  return apiRequest(`/admin/services/items/${encodeURIComponent(itemId)}`, {
    method: 'PATCH',
    body: input,
  });
}

export function deleteServiceItem(itemId) {
  return apiRequest(`/admin/services/items/${encodeURIComponent(itemId)}`, {
    method: 'DELETE',
  });
}
