export class ApiError extends Error {
  status;
  detail;
  issues;
  requestId;

  constructor(payload) {
    super(payload.message);
    this.name = 'ApiError';
    this.status = payload.status;
    this.detail = payload.detail;
    this.issues = payload.issues;
    this.requestId = payload.requestId;
  }
}

let authHandlers = null;
let refreshPromise = null;

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/$/, '');

type FetchOptions = NonNullable<Parameters<typeof fetch>[1]>;
type ApiRequestOptions = Omit<FetchOptions, 'body'> & {
  body?: unknown;
  retryOnUnauthorized?: boolean;
  skipAuth?: boolean;
};

export function setApiAuthHandlers(handlers) {
  authHandlers = handlers;
}

export function toApiAssetUrl(path) {
  if (!path || /^(https?:|data:|blob:)/.test(path)) {
    return path;
  }

  if (!path.startsWith('/')) {
    return path;
  }

  try {
    const apiUrl = new URL(API_BASE_URL, window.location.origin);
    return new URL(path, apiUrl.origin).toString();
  } catch {
    return path;
  }
}

export async function apiRequest(path, requestOptions = undefined) {
  const options = requestOptions ?? {};
  const response = await request(path, options);

  if (
    response.status === 401 &&
    options.skipAuth !== true &&
    options.retryOnUnauthorized !== false &&
    authHandlers?.getRefreshToken()
  ) {
    let session;
    try {
      session = await refreshWithRotation(authHandlers.getRefreshToken() ?? '');
    } catch (error) {
      console.warn('[auth] refresh_failed - session will be cleared', error);
      authHandlers.onUnauthorized();
      throw error;
    }

    authHandlers.onRefresh(session);
    const retryResponse = await request(path, options);
    if (retryResponse.status === 401) {
      console.warn('[auth] retry_still_unauthorized - clearing session');
      authHandlers.onUnauthorized();
    }
    return parseResponse(retryResponse);
  }

  return parseResponse(response);
}

export async function downloadBlob(path: string, suggestedFilename: string): Promise<void> {
  const blob = await apiBlobRequest(path);
  const url = URL.createObjectURL(blob);
  try {
    const a = document.createElement('a');
    a.href = url;
    a.download = suggestedFilename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
}

export async function apiBlobRequest(
  path: string,
  requestOptions: ApiRequestOptions | undefined = undefined,
): Promise<Blob> {
  const response = await fetchBlobWithRefresh(path, requestOptions);
  return response.blob();
}

async function fetchBlobWithRefresh(
  path: string,
  requestOptions: ApiRequestOptions | undefined = undefined,
): Promise<Response> {
  const options = requestOptions ?? {};
  let response = await blobRequest(path, options);
  if (
    response.status === 401 &&
    options.skipAuth !== true &&
    options.retryOnUnauthorized !== false &&
    authHandlers?.getRefreshToken()
  ) {
    try {
      const session = await refreshWithRotation(authHandlers.getRefreshToken() ?? '');
      authHandlers.onRefresh(session);
      response = await blobRequest(path, options);
      if (response.status === 401) {
        authHandlers.onUnauthorized();
        throw await toApiError(response);
      }
    } catch (error) {
      authHandlers?.onUnauthorized();
      throw error;
    }
  }

  if (!response.ok) {
    throw await toApiError(response);
  }
  return response;
}

async function blobRequest(path: string, options: ApiRequestOptions = {}): Promise<Response> {
  const headers = new Headers(options.headers);
  headers.set('X-Request-ID', createRequestId());
  const { body, retryOnUnauthorized, skipAuth, ...fetchOptions } = options;
  void retryOnUnauthorized;
  const isFormData = typeof FormData !== 'undefined' && body instanceof FormData;

  if (body !== undefined && !headers.has('Content-Type') && !isFormData) {
    headers.set('Content-Type', 'application/json');
  }

  const accessToken = authHandlers?.getAccessToken();
  if (skipAuth !== true && accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`);
  }
  const requestBody = body === undefined || isFormData ? (body as FetchOptions['body']) : JSON.stringify(body);
  return fetch(toApiUrl(path), {
    ...fetchOptions,
    headers,
    body: requestBody,
    credentials: 'include',
  });
}

async function request(path, options) {
  const headers = new Headers(options.headers);
  const requestId = createRequestId();

  headers.set('X-Request-ID', requestId);

  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;

  if (options.body !== undefined && !headers.has('Content-Type') && !isFormData) {
    headers.set('Content-Type', 'application/json');
  }

  const accessToken = authHandlers?.getAccessToken();
  if (options.skipAuth !== true && accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`);
  }

  return fetch(toApiUrl(path), {
    ...options,
    headers,
    body: options.body === undefined || isFormData ? options.body : JSON.stringify(options.body),
  });
}

async function parseResponse(response) {
  if (response.ok) {
    if (response.status === 204) {
      return undefined;
    }
    return await response.json();
  }

  throw await toApiError(response);
}

async function toApiError(response) {
  const requestId = response.headers.get('X-Request-ID') ?? '';
  const payload = await readErrorPayload(response);
  const issues = normalizeValidationIssues(payload?.detail);
  const message = issues[0]?.message ?? normalizeErrorMessage(payload?.detail) ?? response.statusText;

  return new ApiError({
    status: response.status,
    message,
    detail: payload?.detail,
    issues,
    requestId,
  });
}

async function readErrorPayload(response) {
  const contentType = response.headers.get('content-type') ?? '';
  if (!contentType.includes('application/json')) {
    return null;
  }

  try {
    return await response.json();
  } catch {
    return null;
  }
}

function normalizeValidationIssues(detail) {
  if (!Array.isArray(detail)) {
    return [];
  }

  return detail.map((issue) => {
    if (!issue || typeof issue !== 'object') {
      return { path: '', message: '입력값을 확인해주세요.' };
    }

    const item = issue;
    const loc = Array.isArray(item.loc) ? item.loc.join('.') : '';
    const message = typeof item.msg === 'string' ? item.msg : '입력값을 확인해주세요.';
    return { path: loc, message };
  });
}

function normalizeErrorMessage(detail) {
  if (typeof detail === 'string') {
    return detail;
  }

  if (detail && typeof detail === 'object' && 'message' in detail) {
    const message = detail.message;
    return typeof message === 'string' ? message : null;
  }

  return null;
}

function refreshWithRotation(refreshToken) {
  refreshPromise ??= apiRequest('/auth/refresh', {
    method: 'POST',
    skipAuth: true,
    retryOnUnauthorized: false,
    body: { refresh_token: refreshToken },
  }).finally(() => {
    refreshPromise = null;
  });

  return refreshPromise;
}

function toApiUrl(path) {
  if (/^https?:\/\//.test(path)) {
    return path;
  }

  return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
}

function createRequestId() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }

  return `req_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}
