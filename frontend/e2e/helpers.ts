import { expect, type APIRequestContext, type APIResponse, type Browser, type Page } from '@playwright/test';

const ONE_PIXEL_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=',
  'base64',
);

const backendPort = Number(process.env.E2E_BACKEND_PORT ?? 8003);
const backendUrl = `http://127.0.0.1:${backendPort}`;
const ADMIN_EMAIL = 'admin@cleanops.kr';
const ADMIN_PASSWORD = 'AdminPass123!';
const PARTNER_PHONE = '01012345678';
const PARTNER_PASSWORD = 'PartnerPass123!';
const SEED_PARTNER_ID = 'seed-partner-01';
const SEED_SERVICE_ITEM_ID = 'seed-service-item-move-in';

type AuthSession = {
  access_token: string;
};

type CreatedOrderGroup = {
  id: string;
  customer_token: string;
  lines: Array<{ id: string }>;
};

export async function adminLogin(page: Page) {
  await page.goto('/');
  await page.getByTestId('app-mode-admin').click();
  await page.getByTestId('admin-login-identifier').fill(ADMIN_EMAIL);
  await page.getByTestId('admin-login-password').fill(ADMIN_PASSWORD);
  await page.getByTestId('admin-login-submit').click();
  await expect(page.getByTestId('admin-shell')).toBeVisible();
  await expect(page.getByTestId('admin-dashboard-page')).toBeVisible();
}

export async function partnerLogin(page: Page) {
  await page.goto('/');
  await page.getByTestId('app-mode-partner').click();
  await page.getByTestId('partner-login-identifier').fill(PARTNER_PHONE);
  await page.getByTestId('partner-login-password').fill(PARTNER_PASSWORD);
  await page.getByTestId('partner-login-submit').click();
  await expect(page.getByTestId('partner-jobs-page')).toBeVisible();
}

export async function partnerUploadPhoto(
  browser: Browser,
  { orderId, photoType }: { orderId: string; photoType: 'before' | 'after' | 'etc' },
) {
  const context = await browser.newContext();
  const page = await context.newPage();
  try {
    await partnerLogin(page);
    await page.getByTestId(`partner-job-row-${orderId}`).click();
    await expect(page.getByTestId('partner-job-detail-page')).toBeVisible();

    const startButton = page.getByTestId('partner-start-job');
    if ((await startButton.count()) > 0) {
      await startButton.click();
      await expect(page.getByText('작업 중')).toBeVisible();
    }

    await page.getByTestId(`partner-${photoType}-photo-input`).setInputFiles({
      name: `${photoType}-e2e.png`,
      mimeType: 'image/png',
      buffer: ONE_PIXEL_PNG,
    });
    const labelMap = { before: '비포', after: '애프터', etc: '기타' } as const;
    await expect(page.getByText(`${labelMap[photoType]} 사진 1장이 업로드되었습니다.`)).toBeVisible({ timeout: 5_000 });

    await expect(page.getByTestId('partner-complete-job')).toBeVisible();
    await page.getByTestId('partner-complete-job').click();
    await expect(page.getByTestId('partner-status-locked')).toContainText('작업 완료 처리됨', { timeout: 10_000 });
  } finally {
    await context.close();
  }
}

export async function createAssignedOrder(request: APIRequestContext) {
  const adminSession = await loginViaApi(request, 'admin');
  const created = await checkedJson<CreatedOrderGroup>(await request.post(`${backendUrl}/api/admin/orders/groups`, {
    headers: authHeaders(adminSession.access_token),
    data: {
      source_channel: 'E2E internal source',
      customer_name: 'R6 Photo Review',
      customer_phone: '010-8899-7766',
      customer_address: 'Seoul R6 Photo Review E2E 1',
      customer_visible_payment: false,
      lines: [
        {
          status: '일정확정',
          received_date: '2026-05-05',
          scheduled_date: '2026-05-14',
          requested_time: '09:30',
          partner_id: SEED_PARTNER_ID,
          team_name: 'R6 Photo Review E2E Team',
          service_item_id: SEED_SERVICE_ITEM_ID,
          service_name: 'R6 Photo Review E2E',
          size_or_quantity: '32py',
          service_detail: 'R6 auto-publish + revoke flow',
          special_request: 'Use only approved photos for customer view',
          total_amount: 360000,
          payment_status: 'deposit_paid',
          payment_memo: 'Internal payment memo',
          evidence_memo: 'Internal evidence memo',
          partner_payment_amount: 210000,
          partner_payment_status: 'unpaid',
        },
      ],
    },
  }));
  return {
    orderId: created.lines[0].id,
    groupId: created.id,
    customerToken: created.customer_token,
    phoneSuffix: '7766',
  };
}

export async function createMultiLineOrder(
  request: APIRequestContext,
  lines: Array<{
    service_name: string;
    partner_id?: string | null;
    total_amount?: number;
    scheduled_date?: string;
    requested_time?: string;
    size_or_quantity?: string;
  }>,
): Promise<{ groupId: string; lineIds: string[]; customerToken: string; phoneSuffix: string }> {
  const adminSession = await loginViaApi(request, 'admin');
  const created = await checkedJson<CreatedOrderGroup>(await request.post(`${backendUrl}/api/admin/orders/groups`, {
    headers: authHeaders(adminSession.access_token),
    data: {
      customer_name: 'R7 Multi-line Customer',
      customer_phone: '010-2222-3333',
      customer_address: 'Seoul R7 Multi-line E2E',
      source_channel: 'E2E',
      customer_visible_payment: false,
      lines: lines.map((line) => ({
        status: '일정확정',
        received_date: '2026-05-05',
        scheduled_date: line.scheduled_date ?? '2026-05-14',
        requested_time: line.requested_time ?? '09:30',
        partner_id: line.partner_id ?? null,
        team_name: line.partner_id ? 'R7 Multi-line E2E Team' : null,
        service_item_id: SEED_SERVICE_ITEM_ID,
        service_name: line.service_name,
        size_or_quantity: line.size_or_quantity ?? '32py',
        total_amount: line.total_amount ?? 100000,
      })),
    },
  }));
  return {
    groupId: created.id,
    lineIds: created.lines.map((line) => line.id),
    customerToken: created.customer_token,
    phoneSuffix: '3333',
  };
}

export async function openAdminPhotoReview(page: Page, orderId: string) {
  await page.getByTestId('admin-nav-photos').click();
  await expect(page.getByTestId('admin-photo-review-page')).toBeVisible();
  await expect(page.getByTestId(`photo-review-item-${orderId}`)).toBeVisible();
  await page.getByTestId(`photo-review-item-${orderId}`).click();
}

async function loginViaApi(request: APIRequestContext, role: 'admin' | 'partner') {
  const endpoint = role === 'admin' ? 'admin/login' : 'partner/login';
  const identifier = role === 'admin' ? ADMIN_EMAIL : PARTNER_PHONE;
  const password = role === 'admin' ? ADMIN_PASSWORD : PARTNER_PASSWORD;
  return checkedJson<AuthSession>(await request.post(`${backendUrl}/api/auth/${endpoint}`, {
    data: { identifier, password },
  }));
}

async function checkedJson<T>(response: APIResponse) {
  expect(response.ok(), await response.text()).toBe(true);
  return response.json() as Promise<T>;
}

function authHeaders(accessToken: string) {
  return { Authorization: `Bearer ${accessToken}` };
}
