import { apiRequest } from './client';

export function listAdminMessages() {
  return apiRequest('/admin/messages');
}

export function getAdminMessageSettings() {
  return apiRequest('/admin/messages/settings');
}

export function sendCustomerScheduleConfirmed(orderId) {
  return sendAdminMessage(orderId, 'customer_schedule_confirmed', 'customer');
}

export function sendCustomerDayBefore(orderId) {
  return sendAdminMessage(orderId, 'customer_day_before', 'customer');
}

export function sendPartnerAssignment(orderId) {
  return sendAdminMessage(orderId, 'partner_assignment', 'partner');
}

export function sendCustomerPhotoReady(orderId) {
  return sendAdminMessage(orderId, 'customer_photo_ready', 'customer');
}

export function previewAdminMessage(orderId, messageType, recipientType, channel = 'sms') {
  return apiRequest('/admin/messages/preview', {
    method: 'POST',
    body: {
      order_id: orderId,
      message_type: messageType,
      recipient_type: recipientType,
      channel,
    },
  });
}

export function sendAdminMessage(orderId, messageType, recipientType, channel = 'sms') {
  return apiRequest('/admin/messages/send', {
    method: 'POST',
    body: {
      order_id: orderId,
      message_type: messageType,
      recipient_type: recipientType,
      channel,
    },
  });
}
