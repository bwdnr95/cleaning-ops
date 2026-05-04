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
