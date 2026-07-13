const CUSTOMER_TOKEN_HISTORY_KEY = '__cleaning_ops_customer_token';
const CUSTOMER_API_TOKEN_PATH = /(\/api\/customer\/orders\/)[^/?#\s]+/g;
const CUSTOMER_PAGE_TOKEN_PATH = /(^|\s|https?:\/\/[^/?#\s]+)(\/(?:c|customer)\/)[^/?#\s]+/g;
const CUSTOMER_TOKEN_QUERY = /(^|[?&])((?:t|token|customer_token)=)[^&#\s]+/g;
const CUSTOMER_TOKEN_FRAGMENT = /(^|#|&)((?:t|token|customer_token)=)[^&#\s]+/g;
const SENSITIVE_TELEMETRY_KEYS = new Set([
  '--cleaning-ops-customer-token',
  'customer-token',
  'token',
  't',
  'authorization',
  'cookie',
  'x-customer-token',
]);

export function captureAndRedactCustomerToken(): void {
  const url = new URL(window.location.href);
  if (!/^\/(?:c|customer)(?:\/|$)/.test(url.pathname)) {
    return;
  }
  const pathMatch = url.pathname.match(/^\/(?:c|customer)\/([^/?#]+)/);
  const queryToken =
    url.searchParams.get('t') ||
    url.searchParams.get('token') ||
    url.searchParams.get('customer_token');
  const fragmentParams = new URLSearchParams(url.hash.replace(/^#/, ''));
  const fragmentToken =
    fragmentParams.get('t') ||
    fragmentParams.get('token') ||
    fragmentParams.get('customer_token');
  const hasLegacyToken = Boolean(pathMatch || queryToken);
  const pathToken = pathMatch ? safelyDecodeToken(pathMatch[1]) : '';
  const legacyToken = queryToken || pathToken;
  const token =
    fragmentToken && fragmentToken !== '[redacted]'
      ? fragmentToken
      : legacyToken && legacyToken !== '[redacted]' && !legacyToken.startsWith('ct2_')
        ? legacyToken
        : '';
  if (!token && !hasLegacyToken) {
    return;
  }

  const currentState = isRecord(window.history.state) ? window.history.state : {};
  const nextState = { ...currentState };
  if (token) {
    nextState[CUSTOMER_TOKEN_HISTORY_KEY] = token;
  } else {
    delete nextState[CUSTOMER_TOKEN_HISTORY_KEY];
  }
  if (pathMatch) {
    url.pathname = url.pathname.replace(/^\/(c|customer)\/[^/?#]+/, '/$1');
  }
  url.searchParams.delete('t');
  url.searchParams.delete('token');
  url.searchParams.delete('customer_token');
  if (fragmentToken) {
    url.hash = '';
  }
  window.history.replaceState(
    nextState,
    '',
    `${url.pathname}${url.search}${url.hash}`,
  );
}

export function readCapturedCustomerToken(): string {
  if (!isRecord(window.history.state)) {
    return '';
  }
  const token = window.history.state[CUSTOMER_TOKEN_HISTORY_KEY];
  return typeof token === 'string' ? token : '';
}

export function redactCustomerTokensFromText(value: string): string {
  let redacted = value.replace(CUSTOMER_API_TOKEN_PATH, '$1[redacted]');
  redacted = redacted.replace(CUSTOMER_PAGE_TOKEN_PATH, '$1$2[redacted]');
  redacted = redacted.replace(CUSTOMER_TOKEN_QUERY, '$1$2[redacted]');
  redacted = redacted.replace(CUSTOMER_TOKEN_FRAGMENT, '$1$2[redacted]');
  return redacted;
}

export function scrubCustomerTokensFromTelemetry<T>(value: T): T {
  return scrubTelemetryValue(value) as T;
}

function scrubTelemetryValue(value: unknown): unknown {
  if (typeof value === 'string') {
    return redactCustomerTokensFromText(value);
  }
  if (Array.isArray(value)) {
    return value.map(scrubTelemetryValue);
  }
  if (isRecord(value)) {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [
        key,
        SENSITIVE_TELEMETRY_KEYS.has(key.toLowerCase().replaceAll('_', '-'))
          ? '[redacted]'
          : scrubTelemetryValue(item),
      ]),
    );
  }
  return value;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function safelyDecodeToken(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return '';
  }
}
