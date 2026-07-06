import { apiRequest } from './client';

export type AdminMessageType =
  | 'customer_schedule_confirmed'
  | 'customer_day_before'
  | 'partner_assignment'
  | 'customer_photo_ready'
  | 'customer_balance_due'
  | 'customer_quote'
  | 'partner_customer_info'
  | 'partner_as_request'
  | 'customer_as_notice';

export type AdminMessageRecipient = 'customer' | 'partner';
export type AdminMessageChannel = 'sms' | 'lms' | 'alimtalk';

type AdminMessageBody = {
  readonly order_id: string;
  readonly message_type: AdminMessageType;
  readonly recipient_type: AdminMessageRecipient;
  readonly channel?: AdminMessageChannel;
};

export function listAdminMessages() {
  return apiRequest('/admin/messages');
}

export function getAdminMessageSettings() {
  return apiRequest('/admin/messages/settings');
}

export function sendCustomerScheduleConfirmed(orderId: string) {
  return sendAdminMessage(orderId, 'customer_schedule_confirmed', 'customer');
}

export function sendCustomerDayBefore(orderId: string) {
  return sendAdminMessage(orderId, 'customer_day_before', 'customer');
}

export function sendPartnerAssignment(orderId: string) {
  return sendAdminMessage(orderId, 'partner_assignment', 'partner');
}

export function sendCustomerPhotoReady(orderId: string) {
  return sendAdminMessage(orderId, 'customer_photo_ready', 'customer');
}

function buildMessageBody(
  orderId: string,
  messageType: AdminMessageType,
  recipientType: AdminMessageRecipient,
  channel: AdminMessageChannel | undefined,
): AdminMessageBody {
  if (channel) {
    return {
      order_id: orderId,
      message_type: messageType,
      recipient_type: recipientType,
      channel,
    };
  }
  return {
    order_id: orderId,
    message_type: messageType,
    recipient_type: recipientType,
  };
}

export function previewAdminMessage(
  orderId: string,
  messageType: AdminMessageType,
  recipientType: AdminMessageRecipient,
  channel?: AdminMessageChannel,
) {
  return apiRequest('/admin/messages/preview', {
    method: 'POST',
    body: buildMessageBody(orderId, messageType, recipientType, channel),
  });
}

export function sendAdminMessage(
  orderId: string,
  messageType: AdminMessageType,
  recipientType: AdminMessageRecipient,
  channel?: AdminMessageChannel,
) {
  return apiRequest('/admin/messages/send', {
    method: 'POST',
    body: buildMessageBody(orderId, messageType, recipientType, channel),
  });
}
