import { apiRequest } from './client';

export function listPartnerJobs() {
  return apiRequest('/partner/jobs');
}

export function getPartnerJob(orderId) {
  return apiRequest(`/partner/jobs/${encodeURIComponent(orderId)}`);
}

export function startPartnerJob(orderId) {
  return apiRequest(`/partner/jobs/${encodeURIComponent(orderId)}/start`, {
    method: 'POST',
  });
}

export function completePartnerJob(orderId) {
  return apiRequest(`/partner/jobs/${encodeURIComponent(orderId)}/complete`, {
    method: 'POST',
  });
}
