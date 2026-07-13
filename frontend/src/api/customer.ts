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

export function submitCustomerAsRequest(customerToken, { orderId, phoneSuffix, memo, files = [] }) {
  const formData = new FormData();
  formData.append('order_id', orderId);
  formData.append('phone_suffix', phoneSuffix);
  formData.append('memo', memo);
  for (const file of files) {
    formData.append('files', file);
  }

  return apiRequest('/customer/orders/as-request', {
    method: 'POST',
    skipAuth: true,
    retryOnUnauthorized: false,
    headers: {
      'X-Customer-Token': customerToken,
    },
    body: formData,
  });
}
