import { expect, test } from '@playwright/test';

const backendPort = Number(process.env.E2E_BACKEND_PORT ?? 8003);
const backendUrl = `http://127.0.0.1:${backendPort}`;

const ADMIN_EMAIL = 'admin@cleanops.kr';
const ADMIN_PASSWORD = 'AdminPass123!';

test('admin sees blocked message actions clearly on orders without partner or customer-visible photos', async ({ page, request }) => {
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
  await expect(page.getByTestId('send-customer-photo-ready')).toBeDisabled();
  await expect(page.getByTestId('send-customer-photo-ready')).toHaveAttribute('title', '공개 사진이 1장 이상 필요합니다.');
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
  await expect(page.getByTestId('message-preview-channel-alimtalk')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByTestId('message-preview-template-id')).toBeVisible();
  await expect(page.getByTestId('message-preview-content')).toContainText('/c/seed-customer-token-2450');

  await page.getByTestId('message-preview-channel-sms').click();
  await expect(page.getByTestId('message-preview-channel-sms')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByTestId('message-preview-content')).toContainText('/c/seed-customer-token-2450');

  await page.getByTestId('message-preview-send').click();
  await expect(page.getByTestId('message-preview-modal')).toHaveCount(0);
  await expect(page.getByTestId('admin-action-notice')).toContainText('SMS');
});

test('admin sends AS request from explicit review modal', async ({ page, request }) => {
  const preWorkOrder = await createAdminOrder(request, {
    service_name: 'AS Modal Pre Work QA',
    customer_name: 'AS Modal Pre Customer',
    customer_phone: '010-4444-1111',
    customer_address: 'Seoul AS Modal Pre QA 1',
    partner_id: 'seed-partner-01',
    team_name: 'AS Modal Partner',
    status: '협력사확인중',
    scheduled_date: '2026-05-15',
    requested_time: '09:30',
    customer_visible_payment: false,
  });
  const order = await createAdminOrder(request, {
    service_name: 'AS Modal QA',
    customer_name: 'AS Modal Customer',
    customer_phone: '010-4444-5555',
    customer_address: 'Seoul AS Modal QA 1',
    partner_id: 'seed-partner-01',
    team_name: 'AS Modal Partner',
    status: '고객전달완료',
    scheduled_date: '2026-05-15',
    requested_time: '10:30',
    customer_visible_payment: false,
  });

  await loginAsAdmin(page);

  await openAdminOrder(page, preWorkOrder.id);
  await expect(page.getByTestId('send-order-as-request')).toBeDisabled();
  await expect(page.getByTestId('send-order-as-request')).toHaveAttribute(
    'title',
    '작업완료 이후 또는 고객확인필요 상태에서 AS 요청을 보낼 수 있습니다.',
  );

  await openAdminOrder(page, order.id);
  await expect(page.getByTestId('order-workflow-guide')).toBeVisible();

  await page.getByTestId('send-order-as-request').click();
  await expect(page.getByTestId('as-request-modal')).toBeVisible();
  await expect(page.getByTestId('as-request-submit')).toBeDisabled();

  await page.getByTestId('as-request-template-partial').click();
  await expect(page.getByTestId('as-request-template-partial')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByTestId('as-request-memo')).toHaveValue(/비포\/애프터 사진/);
  await page.getByTestId('as-request-submit').click();

  await expect(page.getByTestId('as-request-modal')).toHaveCount(0);
  await expect(page.getByTestId('admin-action-notice')).toContainText('AS 요청 상태로 전환');
  await expect(page.getByTestId('order-workflow-guide')).toContainText('AS 요청');

  const adminSession = await loginViaApi(request);
  const refreshedOrder = await checkedJson(await request.get(`${backendUrl}/api/admin/orders/${order.id}`, {
    headers: authHeaders(adminSession.access_token),
  }));
  expect(refreshedOrder.status).toBe('고객확인필요');
  expect(refreshedOrder.as_requested).toBe(true);
  expect(refreshedOrder.as_memo).toContain('비포/애프터 사진');
  expect(refreshedOrder.message_logs).toEqual(expect.arrayContaining([
    expect.objectContaining({ message_type: 'partner_as_request' }),
    expect.objectContaining({ message_type: 'customer_as_notice' }),
  ]));
});

test('admin balance due action is gated by work phase, unpaid balance, and saved payment state', async ({ page, request }) => {
  const preWorkOrder = await createAdminOrder(request, {
    service_name: 'Balance Gate Pre Work',
    customer_name: 'Balance Gate Pre Customer',
    customer_phone: '010-5555-1111',
    customer_address: 'Seoul Balance Gate Pre 1',
    partner_id: 'seed-partner-01',
    team_name: 'Balance Gate Partner',
    status: '협력사확인중',
    scheduled_date: '2026-05-15',
    requested_time: '09:30',
    total_amount: 100000,
    deposit_amount: 20000,
    balance_amount: 80000,
    payment_status: 'balance_pending',
    customer_visible_payment: false,
  });
  const postWorkOrder = await createAdminOrder(request, {
    service_name: 'Balance Gate Post Work',
    customer_name: 'Balance Gate Post Customer',
    customer_phone: '010-5555-2222',
    customer_address: 'Seoul Balance Gate Post 1',
    partner_id: 'seed-partner-01',
    team_name: 'Balance Gate Partner',
    status: '고객전달완료',
    scheduled_date: '2026-05-15',
    requested_time: '10:30',
    total_amount: 100000,
    deposit_amount: 20000,
    balance_amount: 80000,
    payment_status: 'balance_pending',
    customer_visible_payment: false,
  });
  const paidOrder = await createAdminOrder(request, {
    service_name: 'Balance Gate Paid',
    customer_name: 'Balance Gate Paid Customer',
    customer_phone: '010-5555-3333',
    customer_address: 'Seoul Balance Gate Paid 1',
    partner_id: 'seed-partner-01',
    team_name: 'Balance Gate Partner',
    status: '고객전달완료',
    scheduled_date: '2026-05-15',
    requested_time: '11:30',
    total_amount: 100000,
    deposit_amount: 100000,
    balance_amount: 0,
    payment_status: 'paid',
    customer_visible_payment: false,
  });

  await loginAsAdmin(page);

  await openAdminOrder(page, preWorkOrder.id);
  await expect(page.getByTestId('send-customer-balance-due')).toBeDisabled();
  await expect(page.getByTestId('send-customer-balance-due')).toHaveAttribute('title', '작업완료 이후 상태에서만 잔금 안내를 보낼 수 있습니다.');

  await openAdminOrder(page, postWorkOrder.id);
  await expect(page.getByTestId('send-customer-balance-due')).toBeEnabled();

  await page.getByTestId('detail-onsite-extra').fill('10000');
  await expect(page.getByTestId('send-customer-balance-due')).toBeDisabled();
  await expect(page.getByTestId('send-customer-balance-due')).toHaveAttribute('title', '결제/정산 변경을 먼저 저장하세요.');
  await expect(page.getByTestId('order-workflow-guide')).toContainText('먼저 변경사항을 저장하세요');
  await expect(page.getByTestId('order-workflow-guide')).not.toContainText('미수 잔금이 없으면');

  await page.getByTestId('detail-onsite-extra').fill('');
  await openAdminOrder(page, paidOrder.id);
  await expect(page.getByTestId('send-customer-balance-due')).toBeDisabled();
  await expect(page.getByTestId('send-customer-balance-due')).toHaveAttribute('title', '미수 잔금이 있는 주문에서만 발송합니다.');

  await page.getByTestId('detail-onsite-extra').fill('10000');
  await expect(page.getByTestId('send-customer-balance-due')).toBeDisabled();
  await expect(page.getByTestId('send-customer-balance-due')).toHaveAttribute('title', '결제/정산 변경을 먼저 저장하세요.');
  await expect(page.getByTestId('order-workflow-guide')).toContainText('먼저 변경사항을 저장하세요');
  await expect(page.getByTestId('order-workflow-guide')).not.toContainText('미수 잔금이 없으면');
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

async function openAdminOrder(page, orderId) {
  await page.getByTestId('admin-nav-orders').click();
  await expect(page.getByTestId('orders-date-preset-upcoming')).toHaveAttribute('aria-pressed', 'true');
  await page.getByTestId('orders-date-preset-all').click();
  await page.getByTestId(`admin-order-row-${orderId}`).click();
  await expect(page.getByTestId('admin-order-detail-page')).toBeVisible();
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
