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

export function confirmPartnerJob(orderId) {
  return apiRequest(`/partner/jobs/${encodeURIComponent(orderId)}/confirm`, {
    method: 'POST',
  });
}

export function completePartnerJob(orderId, customerSignatureDataUrl = '') {
  return apiRequest(`/partner/jobs/${encodeURIComponent(orderId)}/complete`, {
    method: 'POST',
    body: { customer_signature_data_url: customerSignatureDataUrl },
  });
}

export function addPartnerJobMemo(orderId, text) {
  return apiRequest(`/partner/jobs/${encodeURIComponent(orderId)}/memo`, {
    method: 'POST',
    body: { text },
  });
}

export function getPartnerJobMessages(orderId) {
  return apiRequest(`/partner/jobs/${encodeURIComponent(orderId)}/messages`);
}
