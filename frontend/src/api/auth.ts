import { apiRequest } from './client';

export function adminLogin(input) {
  return apiRequest('/auth/admin/login', {
    method: 'POST',
    skipAuth: true,
    body: {
      identifier: input.identifier,
      password: input.password,
    },
  });
}

export function partnerLogin(input) {
  return apiRequest('/auth/partner/login', {
    method: 'POST',
    skipAuth: true,
    body: {
      identifier: input.identifier,
      password: input.password,
    },
  });
}

export function refreshToken(refreshTokenValue) {
  return apiRequest('/auth/refresh', {
    method: 'POST',
    skipAuth: true,
    retryOnUnauthorized: false,
    body: {
      refresh_token: refreshTokenValue,
    },
  });
}

export function logout(refreshTokenValue) {
  return apiRequest('/auth/logout', {
    method: 'POST',
    skipAuth: true,
    retryOnUnauthorized: false,
    body: {
      refresh_token: refreshTokenValue,
    },
  });
}

export function adminChangePassword(input) {
  return apiRequest('/auth/admin/change-password', {
    method: 'POST',
    body: {
      current_password: input.currentPassword,
      new_password: input.newPassword,
    },
  });
}

export function partnerChangePassword(input) {
  return apiRequest('/auth/partner/change-password', {
    method: 'POST',
    body: {
      current_password: input.currentPassword,
      new_password: input.newPassword,
    },
  });
}
