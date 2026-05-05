import { apiRequest } from './client';

export function listAdminMessages() {
  return apiRequest('/admin/messages');
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

function sendAdminMessage(orderId, messageType, recipientType) {
  return apiRequest('/admin/messages/send', {
    method: 'POST',
    body: {
      order_id: orderId,
      message_type: messageType,
      recipient_type: recipientType,
      channel: 'sms',
    },
  });
}
