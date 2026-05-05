import { expect, test } from '@playwright/test';

const backendPort = Number(process.env.E2E_BACKEND_PORT ?? 8003);
const backendUrl = `http://127.0.0.1:${backendPort}`;

const ADMIN_EMAIL = 'admin@cleanops.kr';
const ADMIN_PASSWORD = 'AdminPass123!';
const PARTNER_PHONE = '01012345678';
const PARTNER_PASSWORD = 'PartnerPass123!';
const SEED_PARTNER_ID = 'seed-partner-01';
const SEED_SERVICE_ITEM_ID = 'seed-service-item-move-in';

test('partner uploads job photos and customer sees only admin-approved photos', async ({ browser, request }) => {
  const flow = await createAssignedOrder(request);

  const partnerContext = await browser.newContext();
  const partnerPage = await partnerContext.newPage();
  await loginAsPartner(partnerPage);
  await partnerPage.getByTestId(`partner-job-row-${flow.orderId}`).click();
  await expect(partnerPage.getByTestId('partner-job-detail-page')).toBeVisible();

  await expect(partnerPage.getByText('partner_payment_amount')).toHaveCount(0);
  await expect(partnerPage.getByText('Internal payment memo')).toHaveCount(0);

  await partnerPage.getByTestId('partner-start-job').click();
  await partnerPage.getByTestId('partner-before-photo-input').setInputFiles({
    name: 'before-partner-r1.jpg',
    mimeType: 'image/jpeg',
    buffer: Buffer.from('fake-before-jpeg-bytes'),
  });
  await partnerPage.getByTestId('partner-after-photo-input').setInputFiles({
    name: 'after-partner-r1.jpg',
    mimeType: 'image/jpeg',
    buffer: Buffer.from('fake-after-jpeg-bytes'),
  });
  await expect(partnerPage.getByText('B-1')).toBeVisible();
  await expect(partnerPage.getByText('A-1')).toBeVisible();
  await partnerPage.getByTestId('partner-complete-job').click();

  const beforeApproval = await customerVerifyInNewContext(browser, flow.customerToken, flow.phoneSuffix);
  await expect(beforeApproval.page.getByTestId('customer-order-page')).toBeVisible();
  await expect(beforeApproval.page.getByTestId('customer-photo-pending')).toBeVisible();
  await expect(beforeApproval.page.getByText('Internal payment memo')).toHaveCount(0);
  await expect(beforeApproval.page.getByText('partner_payment_amount')).toHaveCount(0);
  await beforeApproval.context.close();

  const adminContext = await browser.newContext();
  const adminPage = await adminContext.newPage();
  await loginAsAdmin(adminPage);
  await adminPage.getByTestId('admin-nav-photos').click();
  await expect(adminPage.getByTestId('admin-photo-review-page')).toBeVisible();
  await expect(adminPage.getByText(flow.orderId).first()).toBeVisible();
  await expect(adminPage.getByTestId('photo-send-customer-link')).toBeDisabled();

  await adminPage.getByTestId('photo-approve-selected').click();
  await expect(adminPage.getByTestId('photo-send-customer-link')).toBeEnabled();
  await adminPage.getByTestId('photo-send-customer-link').click();

  await expect.poll(async () => {
    const detail = await getAdminOrder(request, flow.orderId);
    return {
      status: detail.status,
      visiblePhotos: detail.photos.filter((photo) => photo.is_customer_visible).length,
      timeline: detail.timeline.map((event) => event.event_type),
    };
  }).toEqual(expect.objectContaining({
    visiblePhotos: 1,
    timeline: expect.arrayContaining([
      'photo_uploaded',
      'photo_approved',
      'message_sent',
      'customer_link_sent',
    ]),
  }));
  await adminContext.close();

  const afterApproval = await customerVerifyInNewContext(browser, flow.customerToken, flow.phoneSuffix);
  await expect(afterApproval.page.getByTestId('customer-order-page')).toBeVisible();
  await expect(afterApproval.page.getByTestId('customer-photo-pending')).toHaveCount(0);
  await expect(afterApproval.page.getByText('after-partner-r1.jpg')).toBeVisible();
  await expect(afterApproval.page.getByText('before-partner-r1.jpg')).toHaveCount(0);
  await expect(afterApproval.page.getByText('Internal payment memo')).toHaveCount(0);
  await expect(afterApproval.page.getByText('partner_payment_amount')).toHaveCount(0);
  await afterApproval.context.close();

  await partnerContext.close();
});

async function loginAsPartner(page) {
  await page.goto('/');
  await page.getByTestId('app-mode-partner').click();
  await page.getByTestId('partner-login-identifier').fill(PARTNER_PHONE);
  await page.getByTestId('partner-login-password').fill(PARTNER_PASSWORD);
  await page.getByTestId('partner-login-submit').click();
  await expect(page.getByTestId('partner-jobs-page')).toBeVisible();
}

async function loginAsAdmin(page) {
  await page.goto('/');
  await page.getByTestId('admin-login-identifier').fill(ADMIN_EMAIL);
  await page.getByTestId('admin-login-password').fill(ADMIN_PASSWORD);
  await page.getByTestId('admin-login-submit').click();
  await expect(page.getByTestId('admin-shell')).toBeVisible();
}

async function customerVerifyInNewContext(browser, customerToken, phoneSuffix) {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(`/c/${customerToken}`);
  await expect(page.getByTestId('customer-verify-form')).toBeVisible();
  await page.getByTestId('customer-phone-suffix').fill(phoneSuffix);
  await page.getByTestId('customer-verify-submit').click();
  return { context, page };
}

async function createAssignedOrder(request) {
  const adminSession = await loginViaApi(request, 'admin');
  const created = await checkedJson(await request.post(`${backendUrl}/api/admin/orders`, {
    headers: authHeaders(adminSession.access_token),
    data: {
      received_date: '2026-05-05',
      scheduled_date: '2026-05-14',
      requested_time: '09:30',
      partner_id: SEED_PARTNER_ID,
      team_name: 'Partner Customer E2E Team',
      service_item_id: SEED_SERVICE_ITEM_ID,
      service_name: 'Partner Customer E2E',
      size_or_quantity: '32py',
      service_detail: 'Partner/customer R1 browser flow',
      special_request: 'Use only approved photos for customer view',
      source_channel: 'E2E internal source',
      customer_name: 'Partner Customer R1',
      customer_phone: '010-8899-7766',
      customer_address: 'Seoul Partner Customer E2E 1',
      total_amount: 360000,
      payment_status: 'deposit_paid',
      payment_memo: 'Internal payment memo',
      evidence_memo: 'Internal evidence memo',
      partner_payment_amount: 210000,
      partner_payment_status: 'unpaid',
      customer_visible_payment: false,
    },
  }));

  return {
    orderId: created.id,
    customerToken: created.customer_token,
    phoneSuffix: '7766',
  };
}

async function getAdminOrder(request, orderId) {
  const adminSession = await loginViaApi(request, 'admin');
  return checkedJson(await request.get(`${backendUrl}/api/admin/orders/${orderId}`, {
    headers: authHeaders(adminSession.access_token),
  }));
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
