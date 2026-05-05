import { expect, test } from '@playwright/test';

const backendPort = Number(process.env.E2E_BACKEND_PORT ?? 8003);
const backendUrl = `http://127.0.0.1:${backendPort}`;

const ADMIN_EMAIL = 'admin@cleanops.kr';
const ADMIN_PASSWORD = 'AdminPass123!';
const PARTNER_PHONE = '01012345678';
const PARTNER_PASSWORD = 'PartnerPass123!';
const SEED_PARTNER_ID = 'seed-partner-01';
const SEED_SERVICE_ITEM_ID = 'seed-service-item-move-in';

test('admin can log in, navigate operational pages, and open order creation from the dashboard', async ({ page }) => {
  await loginAsAdmin(page);

  const pages = [
    ['orders', 'admin-orders-page'],
    ['calendar', 'admin-calendar-page'],
    ['photos', 'admin-photo-review-page'],
    ['products', 'admin-products-page'],
    ['partners', 'admin-partners-page'],
    ['sends', 'admin-messages-page'],
  ];

  for (const [navKey, pageTestId] of pages) {
    await page.getByTestId(`admin-nav-${navKey}`).click();
    await expect(page.getByTestId(pageTestId)).toBeVisible();
  }

  await page.getByTestId('admin-nav-dashboard').click();
  await expect(page.getByTestId('admin-dashboard-page')).toBeVisible();
  await page.getByTestId('dashboard-create-order').click();
  await expect(page.getByTestId('admin-order-form')).toBeVisible();
});

test('admin can add a catalog item in product ops and use it in an order', async ({ page }) => {
  const itemName = `E2E Admin QA Item ${Date.now()}`;

  await loginAsAdmin(page);
  await page.getByTestId('admin-nav-products').click();
  await expect(page.getByTestId('admin-products-page')).toBeVisible();
  await expect(page.getByTestId('products-item-name')).toBeVisible();

  await page.getByTestId('products-item-name').fill(itemName);
  await page.getByTestId('products-item-base-price').fill('412000');
  await page.getByTestId('products-save-item').click();
  await expect(page.getByText(itemName)).toBeVisible();

  await page.getByTestId('admin-nav-orders').click();
  await page.getByTestId('admin-orders-create').click();
  await expect(page.getByTestId('admin-order-form')).toBeVisible();

  const serviceSelect = page.getByTestId('order-service-item');
  const itemValue = await serviceSelect.locator('option', { hasText: itemName }).getAttribute('value');
  expect(itemValue).toBeTruthy();

  await serviceSelect.selectOption(itemValue ?? '');
  await expect(page.getByTestId('order-service-name')).toHaveValue(itemName);
  await expect(page.getByTestId('order-total-amount')).toHaveValue('412000');

  await page.getByTestId('order-customer-name').fill('E2E Admin Customer');
  await page.getByTestId('order-customer-phone').fill('010-4444-8899');
  await page.getByTestId('order-customer-address').fill('Seoul E2E Admin QA 1');
  await page.getByTestId('order-scheduled-date').fill('2026-05-12');
  await page.getByTestId('order-requested-time').fill('10:30');
  await page.getByTestId('order-partner').selectOption(SEED_PARTNER_ID);
  await page.getByTestId('order-payment-status').selectOption('deposit_paid');
  await page.getByTestId('order-partner-payment-status').selectOption('unpaid');
  await page.getByTestId('order-save').click();

  await expect(page.getByTestId('admin-order-detail-page')).toBeVisible();
  await expect(page.getByText(itemName).first()).toBeVisible();
});

test('admin photo review keeps customer send disabled until a photo is approved', async ({ page, request }) => {
  const orderId = await createPhotoReviewJob(request);

  await loginAsAdmin(page);
  await page.getByTestId('admin-nav-photos').click();
  await expect(page.getByTestId('admin-photo-review-page')).toBeVisible();
  await expect(page.getByText(orderId).first()).toBeVisible();
  await expect(page.getByTestId('photo-send-customer-link')).toBeDisabled();

  await page.getByTestId('photo-approve-selected').click();
  await expect(page.getByTestId('photo-send-customer-link')).toBeEnabled();
  await page.getByTestId('photo-send-customer-link').click();

  await expect.poll(async () => {
    const adminSession = await loginViaApi(request, 'admin');
    const response = await request.get(`${backendUrl}/api/admin/orders/${orderId}`, {
      headers: authHeaders(adminSession.access_token),
    });
    const detail = await response.json();
    return {
      status: detail.status,
      messages: detail.message_logs.length,
      timeline: detail.timeline.map((event) => event.event_type),
    };
  }).toEqual(expect.objectContaining({
    messages: 1,
    timeline: expect.arrayContaining(['photo_approved', 'message_sent', 'customer_link_sent']),
  }));
});

async function loginAsAdmin(page) {
  await page.goto('/');
  await page.getByTestId('admin-login-identifier').fill(ADMIN_EMAIL);
  await page.getByTestId('admin-login-password').fill(ADMIN_PASSWORD);
  await page.getByTestId('admin-login-submit').click();
  await expect(page.getByTestId('admin-shell')).toBeVisible();
  await expect(page.getByTestId('admin-dashboard-page')).toBeVisible();
}

async function createPhotoReviewJob(request) {
  const adminSession = await loginViaApi(request, 'admin');
  const adminHeaders = authHeaders(adminSession.access_token);
  const created = await checkedJson(await request.post(`${backendUrl}/api/admin/orders`, {
    headers: adminHeaders,
    data: {
      received_date: '2026-05-05',
      scheduled_date: '2026-05-13',
      requested_time: '15:00',
      partner_id: SEED_PARTNER_ID,
      team_name: 'E2E QA Team',
      service_item_id: SEED_SERVICE_ITEM_ID,
      service_name: 'E2E Photo Review',
      customer_name: 'E2E Photo Customer',
      customer_phone: '010-5555-4455',
      customer_address: 'Seoul E2E Photo QA 1',
      customer_visible_payment: false,
    },
  }));

  const partnerSession = await loginViaApi(request, 'partner');
  const partnerHeaders = authHeaders(partnerSession.access_token);
  await checkedJson(await request.post(`${backendUrl}/api/partner/jobs/${created.id}/start`, {
    headers: partnerHeaders,
  }));
  await checkedJson(await request.post(`${backendUrl}/api/partner/jobs/${created.id}/photos`, {
    headers: partnerHeaders,
    multipart: {
      photo_type: 'after',
      file: {
        name: 'e2e-after.jpg',
        mimeType: 'image/jpeg',
        buffer: Buffer.from('fake-jpeg-bytes'),
      },
    },
  }));
  await checkedJson(await request.post(`${backendUrl}/api/partner/jobs/${created.id}/complete`, {
    headers: partnerHeaders,
  }));

  return created.id;
}

async function loginViaApi(request, role) {
  const endpoint = role === 'admin' ? 'admin/login' : 'partner/login';
  const identifier = role === 'admin' ? ADMIN_EMAIL : PARTNER_PHONE;
  const password = role === 'admin' ? ADMIN_PASSWORD : PARTNER_PASSWORD;
  return checkedJson(await request.post(`${backendUrl}/api/auth/${endpoint}`, {
    data: { identifier, password },
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
