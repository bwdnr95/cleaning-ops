import { expect, test } from '@playwright/test';

const backendPort = Number(process.env.E2E_BACKEND_PORT ?? 8003);
const backendUrl = `http://127.0.0.1:${backendPort}`;

const ADMIN_EMAIL = 'admin@cleanops.kr';
const ADMIN_PASSWORD = 'AdminPass123!';

test('admin sees blocked message actions clearly on orders without partner or approved photos', async ({ page, request }) => {
  const order = await createAdminOrder(request, {
    service_name: 'Message Edge QA',
    customer_name: 'Message Edge Customer',
    customer_phone: '010-1000-2000',
    customer_address: 'Seoul Message Edge QA 1',
    customer_visible_payment: false,
  });

  await loginAsAdmin(page);
  await page.getByTestId('admin-nav-orders').click();
  await expect(page.getByTestId('orders-date-preset-upcoming')).toHaveAttribute('aria-pressed', 'true');
  await page.getByTestId('orders-date-preset-all').click();
  await page.getByTestId(`admin-order-row-${order.id}`).click();
  await expect(page.getByTestId('admin-order-detail-page')).toBeVisible();

  await expect(page.getByTestId('send-partner-assignment')).toBeDisabled();
  await page.getByTestId('send-customer-photo-ready').click();
  await expect(page.getByTestId('admin-action-error')).toBeVisible();
});

test('admin previews message channel readiness before sending', async ({ page }) => {
  await loginAsAdmin(page);
  await page.getByTestId('admin-nav-orders').click();
  await expect(page.getByTestId('orders-date-preset-upcoming')).toHaveAttribute('aria-pressed', 'true');
  await page.getByTestId('orders-date-preset-all').click();
  await page.getByTestId('admin-order-row-seed-order-2450').click();
  await expect(page.getByTestId('admin-order-detail-page')).toBeVisible();

  await page.getByTestId('send-customer-day-before').click();
  await expect(page.getByTestId('message-preview-modal')).toBeVisible();
  await expect(page.getByTestId('message-preview-channel-sms')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByTestId('message-preview-content')).toContainText('/c/seed-customer-token-2450');

  await page.getByTestId('message-preview-channel-alimtalk').click();
  await expect(page.getByTestId('message-preview-channel-alimtalk')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByTestId('message-preview-template-id')).toBeVisible();
  await expect(page.getByTestId('message-preview-content')).toContainText('/c/seed-customer-token-2450');

  await page.getByTestId('message-preview-channel-sms').click();
  await page.getByTestId('message-preview-send').click();
  await expect(page.getByTestId('message-preview-modal')).toHaveCount(0);
  await expect(page.getByTestId('admin-action-notice')).toContainText('SMS');
});

test('customer wrong phone suffix stays behind verification gate', async ({ page }) => {
  await page.goto('/c/seed-customer-token-2450');
  await expect(page.getByTestId('customer-verify-form')).toBeVisible();

  await page.getByTestId('customer-phone-suffix').fill('0000');
  await page.getByTestId('customer-verify-submit').click();

  await expect(page.getByTestId('customer-verify-error')).toBeVisible();
  await expect(page.getByTestId('customer-order-page')).toHaveCount(0);
});

test('admin order list and detail stay usable with long operational text', async ({ page, request }) => {
  const longCustomerName = 'Very Long Customer Name For Admin Polish QA Display';
  const longServiceName = 'Premium Deep Cleaning With Extra Long Catalog Name For Table Stability';
  const longAddress = 'Seoul Gangnam-gu Very Long Apartment Complex Name Building 123 Unit 4501 With Detailed Parking Instructions';

  const order = await createAdminOrder(request, {
    service_name: longServiceName,
    customer_name: longCustomerName,
    customer_phone: '010-2222-3333',
    customer_address: longAddress,
    scheduled_date: '2026-05-15',
    requested_time: '13:30',
    special_request: 'Please keep this long request visible in detail without breaking the admin page layout.',
    customer_visible_payment: false,
  });

  await loginAsAdmin(page);
  await page.getByTestId('admin-nav-orders').click();
  await expect(page.getByTestId('orders-date-preset-upcoming')).toHaveAttribute('aria-pressed', 'true');
  await page.getByTestId('orders-date-preset-all').click();

  const row = page.getByTestId(`admin-order-row-${order.id}`);
  await expect(row).toBeVisible();
  await expect(row).toContainText(longCustomerName);
  await expect(row).toContainText(longServiceName);

  await row.click();
  await expect(page.getByTestId('admin-order-detail-page')).toBeVisible();
  await expect(page.getByText(longCustomerName)).toBeVisible();
  await expect(page.getByText(longAddress)).toBeVisible();
});

async function loginAsAdmin(page) {
  await page.goto('/');
  await page.getByTestId('admin-login-identifier').fill(ADMIN_EMAIL);
  await page.getByTestId('admin-login-password').fill(ADMIN_PASSWORD);
  await page.getByTestId('admin-login-submit').click();
  await expect(page.getByTestId('admin-shell')).toBeVisible();
}

async function createAdminOrder(request, overrides = {}) {
  const adminSession = await loginViaApi(request);
  return checkedJson(await request.post(`${backendUrl}/api/admin/orders`, {
    headers: authHeaders(adminSession.access_token),
    data: {
      received_date: '2026-05-05',
      service_name: 'Edge QA Order',
      customer_name: 'Edge QA Customer',
      customer_phone: '010-1234-5678',
      customer_address: 'Seoul Edge QA 1',
      ...overrides,
    },
  }));
}

async function loginViaApi(request) {
  return checkedJson(await request.post(`${backendUrl}/api/auth/admin/login`, {
    data: {
      identifier: ADMIN_EMAIL,
      password: ADMIN_PASSWORD,
    },
  }));
}

async function checkedJson(response) {
  expect(response.ok(), await response.text()).toBe(true);
  return response.json();
}

function authHeaders(accessToken) {
  return {
    Authorization: `Bearer ${accessToken}`,
  };
}
