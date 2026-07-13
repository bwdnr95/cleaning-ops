import { expect, test } from '@playwright/test';

import {
  redactCustomerTokensFromText,
  scrubCustomerTokensFromTelemetry,
} from '../src/domain/customerTokenPrivacy';

test('redacts every supported customer link and API token form', () => {
  const secret = 'customer-secret-token';
  const values = [
    `https://ops.example/c/${secret}`,
    `https://ops.example/customer/${secret}`,
    `https://ops.example/c?t=${secret}`,
    `https://ops.example/customer?token=${secret}`,
    `https://ops.example/c?customer_token=${secret}`,
    `https://ops.example/c#token=${secret}`,
    `https://ops.example/customer#customer_token=${secret}`,
    `https://ops.example/api/customer/orders/${secret}/verify`,
    `POST /api/customer/orders/${secret}/as-requests`,
    `t=${secret}`,
    `token=${secret}&x=1`,
    `customer_token=${secret}`,
  ];

  for (const value of values) {
    const redacted = redactCustomerTokensFromText(value);
    expect(redacted).not.toContain(secret);
    expect(redacted).toContain('[redacted]');
  }
});

test('recursively scrubs request, breadcrumb, span, and transaction values', () => {
  const secret = 'nested-customer-secret';
  const event = {
    request: { url: `https://ops.example/api/customer/orders/${secret}/verify` },
    transaction: `POST /api/customer/orders/${secret}/verify`,
    breadcrumbs: [{ data: { url: `https://ops.example/c/${secret}` } }],
    spans: [
      {
        description: `GET /api/customer/orders/${secret}/verify`,
        data: { url: `https://ops.example/customer?token=${secret}` },
      },
    ],
    history: {
      state: {
        __cleaning_ops_customer_token: secret,
      },
    },
    auth: {
      authorization: secret,
    },
    headers: {
      'x-customer-token': secret,
    },
  };

  const scrubbed = scrubCustomerTokensFromTelemetry(event);
  const serialized = JSON.stringify(scrubbed);
  expect(serialized).not.toContain(secret);
  expect(serialized.match(/\[redacted\]/g)?.length).toBeGreaterThanOrEqual(8);
});

test('customer token stays out of browser and API request URLs', async ({ page }) => {
  const secret = 'fragment-only-customer-token';
  let observedRequest: { url: string; tokenHeader: string | undefined } | null = null;

  await page.route('**/api/customer/orders/verify', async (route) => {
    observedRequest = {
      url: route.request().url(),
      tokenHeader: route.request().headers()['x-customer-token'],
    };
    await route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'order_not_found' }),
    });
  });

  await page.goto(`/c#token=${encodeURIComponent(secret)}`);
  await expect(page).toHaveURL(/\/c$/);
  expect(page.url()).not.toContain(secret);

  await page.getByTestId('customer-phone-suffix').fill('5432');
  await page.getByTestId('customer-verify-submit').click();
  await expect(page.getByTestId('customer-verify-error')).toBeVisible();

  expect(observedRequest).toEqual({
    url: expect.stringMatching(/\/api\/customer\/orders\/verify$/),
    tokenHeader: secret,
  });
  expect(observedRequest?.url).not.toContain(secret);
});

test('legacy path and query tokens are captured before URL redaction', async ({ page }) => {
  const legacySecret = 'legacy-customer-token';
  const observedHeaders: string[] = [];
  await page.route('**/api/customer/orders/verify', async (route) => {
    observedHeaders.push(route.request().headers()['x-customer-token'] || '');
    await route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'order_not_found' }),
    });
  });

  for (const legacyUrl of [
    `/c/${legacySecret}`,
    `/c?token=${legacySecret}`,
  ]) {
    await page.goto(legacyUrl);
    await expect(page).toHaveURL(/\/c$/);
    await page.getByTestId('customer-phone-suffix').fill('5432');
    await page.getByTestId('customer-verify-submit').click();
    await expect(page.getByTestId('customer-verify-error')).toBeVisible();
    expect(page.url()).not.toContain(legacySecret);
  }

  expect(observedHeaders).toEqual([legacySecret, legacySecret]);
});
