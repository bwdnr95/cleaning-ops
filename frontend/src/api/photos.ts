import { apiRequest } from './client';

export function listPhotoReviewQueue() {
  return apiRequest('/admin/photos/review-queue');
}

export function approvePhoto(photoId) {
  return apiRequest(`/admin/photos/${encodeURIComponent(photoId)}/approve`, {
    method: 'POST',
  });
}

export function revokePhoto(photoId) {
  return apiRequest(`/admin/photos/${encodeURIComponent(photoId)}/revoke`, {
    method: 'POST',
  });
}

export function uploadPartnerJobPhoto(orderId, input) {
  const body = new FormData();
  body.set('photo_type', input.photoType);
  body.set('file', input.file);

  return apiRequest(`/partner/jobs/${encodeURIComponent(orderId)}/photos`, {
    method: 'POST',
    body,
  });
}

export function deletePartnerJobPhoto(orderId, photoId) {
  return apiRequest(`/partner/jobs/${encodeURIComponent(orderId)}/photos/${encodeURIComponent(photoId)}`, {
    method: 'DELETE',
  });
}
