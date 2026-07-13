import { apiRequest } from './client';

export function verifyCustomerOrder(customerToken, phoneSuffix) {
  return apiRequest(`/customer/orders/${encodeURIComponent(customerToken)}/verify`, {
    method: 'POST',
    skipAuth: true,
    retryOnUnauthorized: false,
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

  return apiRequest(`/customer/orders/${encodeURIComponent(customerToken)}/as-request`, {
    method: 'POST',
    skipAuth: true,
    retryOnUnauthorized: false,
    body: formData,
  });
}
