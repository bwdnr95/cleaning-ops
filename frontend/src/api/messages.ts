import { apiRequest } from './client';

export function sendCustomerPhotoReady(orderId) {
  return apiRequest('/admin/messages/send', {
    method: 'POST',
    body: {
      order_id: orderId,
      message_type: 'customer_photo_ready',
      recipient_type: 'customer',
      channel: 'sms',
    },
  });
}
