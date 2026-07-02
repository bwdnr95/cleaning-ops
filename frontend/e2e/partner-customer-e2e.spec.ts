import { expect, test } from '@playwright/test';
import { createAssignedOrder } from './helpers';

const backendPort = Number(process.env.E2E_BACKEND_PORT ?? 8003);
const backendUrl = `http://127.0.0.1:${backendPort}`;

const ADMIN_EMAIL = 'admin@cleanops.kr';
const ADMIN_PASSWORD = 'AdminPass123!';
const PARTNER_PHONE = '01012345678';
const PARTNER_PASSWORD = 'PartnerPass123!';
const ONE_PIXEL_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=',
  'base64',
);

test('partner uploads job photos and customer sees auto-published photos except revoked ones', async ({ browser, request }) => {
  const flow = await createAssignedOrder(request);

  const partnerContext = await browser.newContext();
  const partnerPage = await partnerContext.newPage();
  await loginAsPartner(partnerPage);
  await partnerPage.getByTestId(`partner-job-row-${flow.orderId}`).click();
  await expect(partnerPage.getByTestId('partner-job-detail-page')).toBeVisible();

  await expect(partnerPage.getByText('partner_payment_amount')).toHaveCount(0);
  await expect(partnerPage.getByText('Internal payment memo')).toHaveCount(0);
  await expect(partnerPage.getByText('010-8899-7766')).toBeVisible();

  await partnerPage.getByTestId('partner-start-job').click();
  await expect(partnerPage.getByText('작업 중')).toBeVisible();
  await partnerPage.getByTestId('partner-before-photo-input').setInputFiles([
    {
      name: 'before-partner-r2.png',
      mimeType: 'image/png',
      buffer: ONE_PIXEL_PNG,
    },
    {
      name: 'before-extra-partner-r2.png',
      mimeType: 'image/png',
      buffer: ONE_PIXEL_PNG,
    },
  ]);
  await expect(partnerPage.getByText('비포 사진 2장이 업로드되었습니다.')).toBeVisible();
  await expect(partnerPage.getByRole('img', { name: 'before-partner-r2.png' })).toBeVisible();
  await expect(partnerPage.getByRole('img', { name: 'before-extra-partner-r2.png' })).toBeVisible();
  await partnerPage.getByTestId('partner-after-photo-input').setInputFiles({
    name: 'after-partner-r2.png',
    mimeType: 'image/png',
    buffer: ONE_PIXEL_PNG,
  });
  await expect(partnerPage.getByRole('img', { name: 'after-partner-r2.png' })).toBeVisible();
  await partnerPage.getByTestId('partner-complete-job').click();
  await expect(partnerPage.getByTestId('partner-status-locked')).toContainText('작업 완료 처리됨');
  await expect(partnerPage.getByTestId('partner-start-job')).toHaveCount(0);
  await expect(partnerPage.getByTestId('partner-complete-job')).toHaveCount(0);

  await partnerPage.reload();
  await expect(partnerPage.getByTestId('partner-jobs-page')).toBeVisible();
  // 작업 완료 후 잡은 '완료' 버킷으로 이동한다(협력사 목록 기본 필터는 '예정'이라 완료건이 숨겨진다).
  // 전체 보기로 전환해 완료된 잡을 다시 연다.
  await partnerPage.getByRole('button', { name: '전체 보기' }).click();
  await partnerPage.getByTestId(`partner-job-row-${flow.orderId}`).click();
  await expect(partnerPage.getByRole('img', { name: 'before-partner-r2.png' })).toBeVisible();
  await expect(partnerPage.getByRole('img', { name: 'after-partner-r2.png' })).toBeVisible();

  await partnerPage.getByTestId('partner-etc-photo-input').setInputFiles({
    name: 'field-note.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('not an image'),
  });
  await expect(partnerPage.getByText('JPG/PNG/WebP만 업로드 가능합니다.')).toBeVisible();
  await expect(partnerPage.getByTestId('partner-status-locked')).toContainText('작업 완료 처리됨');
  await expect(partnerPage.getByTestId('partner-start-job')).toHaveCount(0);
  await expect(partnerPage.getByTestId('partner-complete-job')).toHaveCount(0);

  const autoVisible = await customerVerifyInNewContext(browser, flow.customerToken, flow.phoneSuffix);
  await expect(autoVisible.page.getByTestId('customer-order-page')).toBeVisible();
  await expect(autoVisible.page.getByTestId('customer-visible-phone')).toHaveText('010-8899-7766');
  await expect(autoVisible.page.getByTestId('customer-photo-pending')).toHaveCount(0);
  await expect(
    autoVisible.page.locator('[data-testid^="customer-photo-"]:not([data-testid="customer-photo-pending"])'),
  ).toHaveCount(3);
  await expect(autoVisible.page.getByText('Internal payment memo')).toHaveCount(0);
  await expect(autoVisible.page.getByText('partner_payment_amount')).toHaveCount(0);
  await autoVisible.context.close();

  const adminContext = await browser.newContext();
  const adminPage = await adminContext.newPage();
  await loginAsAdmin(adminPage);
  await adminPage.getByTestId('admin-nav-photos').click();
  await expect(adminPage.getByTestId('admin-photo-review-page')).toBeVisible();
  await expect(adminPage.getByTestId(`photo-review-item-${flow.orderId}`)).toBeVisible();
  await adminPage.getByTestId(`photo-review-item-${flow.orderId}`).click();
  await expect(adminPage.getByRole('img', { name: 'after-partner-r2.png' }).first()).toBeVisible();
  await expect(adminPage.getByTestId('photo-send-customer-link')).toBeEnabled();
  const firstThumb = adminPage.locator('[data-testid^="photo-thumb-"]').first();
  await firstThumb.click();
  await adminPage.getByTestId('photo-revoke-selected').click();
  await expect(firstThumb.getByText('비공개')).toBeVisible();

  await expect.poll(async () => {
    const detail = await getAdminOrder(request, flow.orderId);
    return {
      status: detail.status,
      visiblePhotos: detail.photos.filter((photo) => photo.is_customer_visible).length,
      timeline: detail.timeline.map((event) => event.event_type),
    };
  }).toEqual(expect.objectContaining({
    visiblePhotos: 2,
    timeline: expect.arrayContaining([
      'photo_uploaded',
      'photo_approved',
      'photo_revoked',
    ]),
  }));
  await adminContext.close();

  const afterRevoke = await customerVerifyInNewContext(browser, flow.customerToken, flow.phoneSuffix);
  await expect(afterRevoke.page.getByTestId('customer-order-page')).toBeVisible();
  await expect(afterRevoke.page.getByTestId('customer-photo-pending')).toHaveCount(0);
  await expect(
    afterRevoke.page.locator('[data-testid^="customer-photo-"]:not([data-testid="customer-photo-pending"])'),
  ).toHaveCount(2);
  await expect(afterRevoke.page.getByText('Internal payment memo')).toHaveCount(0);
  await expect(afterRevoke.page.getByText('partner_payment_amount')).toHaveCount(0);
  await afterRevoke.context.close();

  await partnerContext.close();
});

async function loginAsPartner(page) {
  await page.goto('/partner');
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
