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

export function resetAdminPartnerPassword(partnerId, input = {}) {
  return apiRequest(`/admin/partners/${encodeURIComponent(partnerId)}/reset-password`, {
    method: 'POST',
    body: input,
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
