import { apiRequest, downloadBlob } from './client';

export interface RevenueBucket {
  period: string;
  completed_count: number;
  revenue: string;
}

export interface RevenueReport {
  granularity: string;
  start_date: string;
  end_date: string;
  partner_id: string | null;
  service_item_id: string | null;
  buckets: RevenueBucket[];
  total_revenue: string;
  total_completed: number;
}

export interface PartnerPerformanceRow {
  partner_id: string;
  partner_name: string;
  job_count: number;
  avg_unit_price: string;
  pending_settlement_count: number;
  expected_settlement_amount: string;
}

export interface PartnerPerformanceReport {
  start_date: string;
  end_date: string;
  rows: PartnerPerformanceRow[];
}

export interface ServicePopularityRow {
  service_item_id: string | null;
  service_name: string;
  job_count: number;
  revenue: string;
  revenue_share_pct: number;
}

export interface ServicePopularityReport {
  start_date: string;
  end_date: string;
  rows: ServicePopularityRow[];
}

export interface SourceChannelRow {
  source_channel: string;
  order_count: number;
  completed_count: number;
  revenue: string;
  revenue_share_pct: number;
}

export interface SourceChannelReport {
  start_date: string;
  end_date: string;
  rows: SourceChannelRow[];
  total_orders: number;
  total_completed: number;
  total_revenue: string;
}

export interface SettlementBacklogRow {
  order_id: string;
  scheduled_date: string | null;
  service_name: string;
  partner_id: string | null;
  partner_name: string | null;
  total_amount: string;
  expected_settlement_amount: string;
  status: string;
  source: 'order' | 'recurring_monthly';
}

export interface SettlementBacklogReport {
  rows: SettlementBacklogRow[];
}

export function fetchRevenue(params: Record<string, string>): Promise<RevenueReport> {
  const qs = new URLSearchParams(params).toString();
  return apiRequest(`/admin/reports/revenue?${qs}`);
}

export function fetchPartners(params: Record<string, string>): Promise<PartnerPerformanceReport> {
  const qs = new URLSearchParams(params).toString();
  return apiRequest(`/admin/reports/partners?${qs}`);
}

export function fetchServices(params: Record<string, string>): Promise<ServicePopularityReport> {
  const qs = new URLSearchParams(params).toString();
  return apiRequest(`/admin/reports/services?${qs}`);
}

export function fetchSourceChannels(params: Record<string, string>): Promise<SourceChannelReport> {
  const qs = new URLSearchParams(params).toString();
  return apiRequest(`/admin/reports/source-channels?${qs}`);
}

export function fetchSettlements(): Promise<SettlementBacklogReport> {
  return apiRequest('/admin/reports/settlements');
}

export function exportReport(
  name: 'revenue' | 'partners' | 'services' | 'source-channels' | 'settlements',
  params: Record<string, string>,
  format: 'csv' | 'xlsx',
): Promise<void> {
  const qs = new URLSearchParams({ ...params, format }).toString();
  return downloadBlob(`/admin/reports/${name}/export?${qs}`, `${name}.${format}`);
}
