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

test('dashboard KPI cards open the matching operational filters', async ({ page }) => {
  await loginAsAdmin(page);

  for (const item of [
    ['dashboard-kpi-today_jobs', 'orders-tab-today'],
    ['dashboard-kpi-tomorrow_notice', 'orders-tab-tomorrow_notice'],
    ['dashboard-kpi-payment_check', 'orders-tab-payment_check'],
  ]) {
    await page.getByTestId(item[0]).click();
    await expect(page.getByTestId('admin-orders-page')).toBeVisible();
    await expect(page.getByTestId(item[1])).toHaveAttribute('aria-pressed', 'true');
    await page.getByTestId('admin-nav-dashboard').click();
    await expect(page.getByTestId('admin-dashboard-page')).toBeVisible();
  }

  await page.getByTestId('dashboard-kpi-photo_review').click();
  await expect(page.getByTestId('admin-photo-review-page')).toBeVisible();
});

test('calendar more link opens the selected day order list', async ({ page, request }) => {
  const orders = await createCalendarDayOrders(request);

  await loginAsAdmin(page);
  await page.getByTestId('admin-nav-calendar').click();
  await expect(page.getByTestId('admin-calendar-page')).toBeVisible();

  await expect(page.getByTestId('calendar-more-20')).toBeVisible();
  await page.getByTestId('calendar-more-20').click();

  const panel = page.getByTestId('calendar-day-panel');
  await expect(panel).toContainText('2026.05.20');
  await expect(panel).toContainText('4건');
  for (const order of orders) {
    await expect(page.getByTestId(`calendar-panel-order-${order.id}`)).toBeVisible();
  }

  await page.getByTestId(`calendar-panel-order-${orders[3].id}`).click();
  await expect(page.getByTestId('admin-order-detail-page')).toBeVisible();
});

test('admin can filter orders by visit date with the custom date picker', async ({ page, request }) => {
  const { targetOrder, outsideOrder } = await createDateFilterOrders(request);

  await loginAsAdmin(page);
  await page.getByTestId('admin-nav-orders').click();
  await expect(page.getByTestId('admin-orders-page')).toBeVisible();
  await expect(page.getByTestId('orders-date-preset-today')).toHaveAttribute('aria-pressed', 'true');
  await page.getByTestId('orders-date-clear').click();
  await expect(page.getByTestId(`admin-order-row-${targetOrder.id}`)).toBeVisible();
  await expect(page.getByTestId(`admin-order-row-${outsideOrder.id}`)).toBeVisible();

  await pickDate(page, 'orders-date-start', '2026-05-21');
  await pickDate(page, 'orders-date-end', '2026-05-21');

  await expect(page.getByTestId(`admin-order-row-${targetOrder.id}`)).toBeVisible();
  await expect(page.getByTestId(`admin-order-row-${outsideOrder.id}`)).toHaveCount(0);

  await page.getByTestId('orders-date-clear').click();
  await expect(page.getByTestId(`admin-order-row-${outsideOrder.id}`)).toBeVisible();
});

test('admin can run selected order bulk operations from the order list', async ({ page, request }) => {
  const orders = await createBulkActionOrders(request);

  await loginAsAdmin(page);
  await page.getByTestId('admin-nav-orders').click();
  await expect(page.getByTestId('admin-orders-page')).toBeVisible();

  await selectOrderRows(page, orders);
  await page.getByTestId('orders-bulk-status-open').click();
  await page.getByTestId('orders-bulk-status-select').selectOption('상담중');
  await page.getByTestId('orders-bulk-status-apply').click();
  await expect(page.getByTestId('orders-bulk-notice')).toContainText('2건 상담중 상태로 변경했습니다.');
  await expect.poll(() => getOrderStatuses(request, orders)).toEqual(['상담중', '상담중']);

  await selectOrderRows(page, orders);
  await page.getByTestId('orders-bulk-partner-open').click();
  await page.getByTestId('orders-bulk-partner-select').selectOption(SEED_PARTNER_ID);
  await page.getByTestId('orders-bulk-partner-apply').click();
  await expect(page.getByTestId('orders-bulk-notice')).toContainText('2건');
  await expect.poll(() => getOrderPartnerIds(request, orders)).toEqual([SEED_PARTNER_ID, SEED_PARTNER_ID]);

  await selectOrderRows(page, orders);
  await page.getByTestId('orders-bulk-message-open').click();
  await page.getByTestId('orders-bulk-message-type').selectOption('customer_schedule_confirmed');
  await page.getByTestId('orders-bulk-message-apply').click();
  await expect(page.getByTestId('orders-bulk-notice')).toContainText('2건 고객 일정확정 안내를 발송했습니다.');
  await expect.poll(() => getOrderMessageTypes(request, orders)).toEqual([
    ['customer_schedule_confirmed'],
    ['customer_schedule_confirmed'],
  ]);
});

test('admin can add a catalog item in product ops and use it in an order', async ({ page }) => {
  const itemName = `E2E Admin QA Item ${Date.now()}`;
  const updatedItemName = `${itemName} Updated`;
  const deleteItemName = `${itemName} Delete`;

  await loginAsAdmin(page);
  await page.getByTestId('admin-nav-products').click();
  await expect(page.getByTestId('admin-products-page')).toBeVisible();
  await expect(page.getByTestId('products-item-name')).toBeVisible();

  await page.getByTestId('products-item-name').fill(itemName);
  await page.getByTestId('products-item-base-price').fill('412000');
  await page.getByTestId('products-save-item').click();
  await expect(page.getByText(itemName)).toBeVisible();

  await page.getByRole('button', { name: `${itemName} 수정` }).click();
  await page.getByTestId('products-item-name').fill(updatedItemName);
  await page.getByTestId('products-item-base-price').fill('425000');
  await page.getByTestId('products-save-item').click();
  await expect(page.getByRole('button', { name: updatedItemName, exact: true })).toBeVisible();

  await page.getByRole('button', { name: '새 상품' }).click();
  await page.getByTestId('products-item-name').fill(deleteItemName);
  await page.getByTestId('products-item-base-price').fill('10000');
  await page.getByTestId('products-save-item').click();
  await expect(page.getByText(deleteItemName)).toBeVisible();
  page.once('dialog', async (dialog) => {
    await dialog.accept();
  });
  await page.getByRole('button', { name: `${deleteItemName} 삭제` }).click();
  await expect(page.getByText(deleteItemName)).toHaveCount(0);

  await page.getByTestId('admin-nav-orders').click();
  await page.getByTestId('admin-orders-create').click();
  await expect(page.getByTestId('admin-order-form')).toBeVisible();

  const serviceSelect = page.getByTestId('order-service-item');
  const itemValue = await serviceSelect.locator('option', { hasText: updatedItemName }).getAttribute('value');
  expect(itemValue).toBeTruthy();

  await serviceSelect.selectOption(itemValue ?? '');
  await expect(page.getByTestId('order-service-name')).toHaveValue(updatedItemName);
  await expect(page.getByTestId('order-total-amount')).toHaveValue('425,000');

  await page.getByTestId('order-deposit-amount').fill('125000');
  await expect(page.getByTestId('order-deposit-amount')).toHaveValue('125,000');
  await expect(page.getByTestId('order-balance-amount')).toHaveValue('300,000');

  await page.getByTestId('order-customer-name').fill('E2E Admin Customer');
  await page.getByTestId('order-customer-phone').fill('010-4444-8899');
  await page.getByTestId('order-customer-address').fill('Seoul E2E Admin QA 1');
  await pickDate(page, 'order-scheduled-date', '2026-05-12');
  await page.getByTestId('order-requested-time').fill('10:30');
  await page.getByTestId('order-partner').selectOption(SEED_PARTNER_ID);
  await page.getByTestId('order-payment-status').selectOption('deposit_paid');
  await page.getByTestId('order-partner-payment-status').selectOption('unpaid');
  await page.getByTestId('order-save').click();

  await expect(page.getByTestId('admin-order-detail-page')).toBeVisible();
  await expect(page.getByText(updatedItemName).first()).toBeVisible();
});

test('admin can edit and delete an unused partner explicitly', async ({ page }) => {
  const suffix = String(Date.now()).slice(-6);
  const partnerName = `E2E Partner ${suffix}`;
  const updatedPartnerName = `${partnerName} Updated`;
  const phone = `010-77${suffix.slice(0, 2)}-${suffix.slice(2)}`;

  await loginAsAdmin(page);
  await page.getByTestId('admin-nav-partners').click();
  await expect(page.getByTestId('admin-partners-page')).toBeVisible();

  await page.getByTestId('partner-create-name').fill(partnerName);
  await page.getByTestId('partner-create-phone').fill(phone);
  await page.getByTestId('partner-create-submit').click();
  await expect(page.getByRole('button', { name: `${partnerName} 수정` })).toBeVisible();
  await page.getByRole('button', { name: `${partnerName} 수정` }).click();
  await expect(page.getByTestId('partner-detail-name')).toHaveValue(partnerName);

  await page.getByTestId('partner-detail-name').fill(updatedPartnerName);
  await page.getByTestId('partner-save').click();
  await expect(page.getByRole('button', { name: `${updatedPartnerName} 수정` })).toBeVisible();

  page.once('dialog', async (dialog) => {
    await dialog.accept();
  });
  await page.getByTestId('partner-delete').click();
  await expect(page.getByRole('button', { name: `${updatedPartnerName} 수정` })).toHaveCount(0);
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

async function createCalendarDayOrders(request) {
  const adminSession = await loginViaApi(request, 'admin');
  const adminHeaders = authHeaders(adminSession.access_token);
  const created = [];

  for (let index = 0; index < 4; index += 1) {
    created.push(await checkedJson(await request.post(`${backendUrl}/api/admin/orders`, {
      headers: adminHeaders,
      data: {
        received_date: '2026-05-05',
        scheduled_date: '2026-05-20',
        requested_time: `${String(9 + index).padStart(2, '0')}:00`,
        partner_id: SEED_PARTNER_ID,
        team_name: 'E2E QA Team',
        service_name: `Calendar Overflow QA ${index + 1}`,
        customer_name: `Calendar Customer ${index + 1}`,
        customer_phone: `010-3333-10${index}${index}`,
        customer_address: `Seoul Calendar QA ${index + 1}`,
        customer_visible_payment: false,
      },
    })));
  }

  return created;
}

async function createDateFilterOrders(request) {
  const adminSession = await loginViaApi(request, 'admin');
  const adminHeaders = authHeaders(adminSession.access_token);
  const targetOrder = await checkedJson(await request.post(`${backendUrl}/api/admin/orders`, {
    headers: adminHeaders,
    data: {
      received_date: '2026-05-05',
      scheduled_date: '2026-05-21',
      requested_time: '11:00',
      service_name: 'Date Filter Target QA',
      customer_name: 'Date Filter Target',
      customer_phone: '010-7000-2100',
      customer_address: 'Seoul Date Filter Target',
      customer_visible_payment: false,
    },
  }));
  const outsideOrder = await checkedJson(await request.post(`${backendUrl}/api/admin/orders`, {
    headers: adminHeaders,
    data: {
      received_date: '2026-05-05',
      scheduled_date: '2026-05-22',
      requested_time: '11:00',
      service_name: 'Date Filter Outside QA',
      customer_name: 'Date Filter Outside',
      customer_phone: '010-7000-2200',
      customer_address: 'Seoul Date Filter Outside',
      customer_visible_payment: false,
    },
  }));

  return { targetOrder, outsideOrder };
}

async function createBulkActionOrders(request) {
  const adminSession = await loginViaApi(request, 'admin');
  const adminHeaders = authHeaders(adminSession.access_token);
  const created = [];

  for (let index = 0; index < 2; index += 1) {
    created.push(await checkedJson(await request.post(`${backendUrl}/api/admin/orders`, {
      headers: adminHeaders,
      data: {
        received_date: '2026-05-05',
        scheduled_date: '2026-05-05',
        requested_time: `${String(10 + index).padStart(2, '0')}:30`,
        service_name: `Bulk Action QA ${index + 1}`,
        customer_name: `Bulk Customer ${index + 1}`,
        customer_phone: `010-8000-24${index}${index}`,
        customer_address: `Seoul Bulk QA ${index + 1}`,
        customer_visible_payment: false,
      },
    })));
  }

  return created;
}

async function pickDate(page, pickerTestId, dateValue) {
  await page.getByTestId(pickerTestId).click();
  await page.getByTestId(`date-picker-day-${dateValue}`).click();
}

async function selectOrderRows(page, orders) {
  for (const order of orders) {
    const checkbox = page.getByTestId(`admin-order-row-${order.id}`).locator('input[type="checkbox"]');
    await expect(checkbox).toBeVisible();
    await checkbox.check();
  }
}

async function getOrderStatuses(request, orders) {
  const details = await getOrderDetails(request, orders);
  return details.map((detail) => detail.status);
}

async function getOrderPartnerIds(request, orders) {
  const details = await getOrderDetails(request, orders);
  return details.map((detail) => detail.partner_id);
}

async function getOrderMessageTypes(request, orders) {
  const details = await getOrderDetails(request, orders);
  return details.map((detail) => detail.message_logs.map((message) => message.message_type));
}

async function getOrderDetails(request, orders) {
  const adminSession = await loginViaApi(request, 'admin');
  const adminHeaders = authHeaders(adminSession.access_token);
  const details = [];
  for (const order of orders) {
    details.push(await checkedJson(await request.get(`${backendUrl}/api/admin/orders/${order.id}`, {
      headers: adminHeaders,
    })));
  }
  return details;
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
