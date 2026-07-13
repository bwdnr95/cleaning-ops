import { apiRequest } from './client';

export function verifyCustomerOrder(customerToken, phoneSuffix) {
  return apiRequest('/customer/orders/verify', {
    method: 'POST',
    skipAuth: true,
    retryOnUnauthorized: false,
    headers: {
      'X-Customer-Token': customerToken,
    },
    body: {
      phone_suffix: phoneSuffix,
    },
  });
}

export function submitCustomerAsRequest(customerToken, phoneSuffix, orderId, memo) {
  return apiRequest('/customer/orders/as-requests', {
    method: 'POST',
    skipAuth: true,
    retryOnUnauthorized: false,
    headers: {
      'X-Customer-Token': customerToken,
    },
    body: {
      phone_suffix: phoneSuffix,
      order_id: orderId,
      memo,
    },
  });
}
