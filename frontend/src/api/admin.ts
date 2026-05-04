import { apiRequest } from './client';

export function getDashboardSummary() {
  return apiRequest('/admin/dashboard/summary');
}

export function getDashboardRecentActivity() {
  return apiRequest('/admin/dashboard/recent-activity');
}

export function listAdminCalendarOrders({ year, month, partnerId = '' }) {
  const params = new URLSearchParams({
    year: String(year),
    month: String(month),
  });
  if (partnerId) {
    params.set('partner_id', partnerId);
  }
  return apiRequest(`/admin/calendar?${params.toString()}`);
}

export function listAdminOrders() {
  return apiRequest('/admin/orders');
}

export function createAdminOrder(input) {
  return apiRequest('/admin/orders', {
    method: 'POST',
    body: input,
  });
}

export function getAdminOrder(orderId) {
  return apiRequest(`/admin/orders/${encodeURIComponent(orderId)}`);
}

export function updateAdminOrder(orderId, input) {
  return apiRequest(`/admin/orders/${encodeURIComponent(orderId)}`, {
    method: 'PATCH',
    body: input,
  });
}

export function listPartners() {
  return apiRequest('/admin/partners');
}
