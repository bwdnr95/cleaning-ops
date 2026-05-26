/**
 * Cleanjob Demo Handoff — Screenshot Capture
 *
 * Auto-captures all key screens for the static demo handoff HTML.
 * Run via: npx playwright test e2e/capture-demo.spec.ts
 *
 * Outputs to: ../.master/cleanjob_demo_handoff/images/
 */
import { expect, test, type Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const ADMIN_EMAIL = 'admin@cleanops.kr';
const ADMIN_PASSWORD = 'AdminPass123!';
const PARTNER_PHONE = '01012345678';
const PARTNER_PASSWORD = 'PartnerPass123!';
const SEED_ORDER_ID = 'seed-order-2450';
const SEED_CUSTOMER_TOKEN = 'seed-customer-token-2450';
const SEED_PHONE_SUFFIX = '5432';

// Playwright runs from frontend/, so go up one to repo root and into .master/
const OUT_DIR = path.resolve(process.cwd(), '../.master/cleanjob_demo_handoff/images');

test.use({
  viewport: { width: 1600, height: 1000 },
});

test.beforeAll(async () => {
  fs.mkdirSync(OUT_DIR, { recursive: true });
});

test('capture all demo screens', async ({ page }) => {
  test.setTimeout(180_000);

  // Suppress all motion for stable, snappy screenshots
  await page.addInitScript(() => {
    const style = document.createElement('style');
    style.innerHTML = `
      *, *::before, *::after {
        animation-duration: 0ms !important;
        transition-duration: 0ms !important;
      }
    `;
    document.documentElement.appendChild(style);
  });

  // ───────────────────────── ADMIN ─────────────────────────
  await loginAsAdmin(page);

  // 1. Dashboard
  await page.getByTestId('admin-nav-dashboard').click();
  await expect(page.getByTestId('admin-dashboard-page')).toBeVisible();
  await page.waitForTimeout(400);
  await captureFrame(page, 'desktop', '01-admin-dashboard.png');

  // 2. Orders list (clear default "today" filter so seed order is visible)
  await page.getByTestId('admin-nav-orders').click();
  await expect(page.getByTestId('admin-orders-page')).toBeVisible();
  await page.getByTestId('orders-date-preset-all').click();
  await expect(page.getByTestId(`admin-order-row-${SEED_ORDER_ID}`)).toBeVisible();
  await page.waitForTimeout(300);
  await captureFrame(page, 'desktop', '02-admin-orders-list.png');

  // 3. Order create form
  await page.getByTestId('admin-orders-create').click();
  await expect(page.getByTestId('admin-order-form')).toBeVisible();
  await page.waitForTimeout(300);
  await captureFrame(page, 'desktop', '03-admin-order-create.png');

  // Cancel form, go back to orders list (filter resets — re-clear it)
  await page.getByRole('button', { name: '취소' }).first().click();
  await expect(page.getByTestId('admin-orders-page')).toBeVisible();
  await page.getByTestId('orders-date-preset-all').click();
  await expect(page.getByTestId(`admin-order-row-${SEED_ORDER_ID}`)).toBeVisible();

  // 4. Order detail (seed order)
  await page.getByTestId(`admin-order-row-${SEED_ORDER_ID}`).click();
  await page.waitForTimeout(700);
  await captureFrame(page, 'desktop', '04-admin-order-detail.png');

  // 5. Photo review (likely empty queue — annotated)
  await page.getByTestId('admin-nav-photos').click();
  await expect(page.getByTestId('admin-photo-review-page')).toBeVisible();
  await page.waitForTimeout(300);
  await captureFrame(page, 'desktop', '07-admin-photo-review.png');

  // 6. Calendar
  await page.getByTestId('admin-nav-calendar').click();
  await expect(page.getByTestId('admin-calendar-page')).toBeVisible();
  await page.waitForTimeout(400);
  await captureFrame(page, 'desktop', '10-admin-calendar.png');

  // 7. Messages history
  await page.getByTestId('admin-nav-sends').click();
  await expect(page.getByTestId('admin-messages-page')).toBeVisible();
  await page.waitForTimeout(300);
  await captureFrame(page, 'desktop', '11-admin-messages.png');

  // ───────────────────────── PARTNER ─────────────────────────
  await page.goto('/partner');
  await expect(page.getByTestId('partner-login-form')).toBeVisible();
  await page.getByTestId('partner-login-identifier').fill(PARTNER_PHONE);
  await page.getByTestId('partner-login-password').fill(PARTNER_PASSWORD);
  await page.getByTestId('partner-login-submit').click();
  await expect(page.getByTestId('partner-jobs-page')).toBeVisible();
  await page.waitForTimeout(400);

  // 8. Partner job list (mobile)
  await captureFrame(page, 'phone', '05-partner-jobs.png');

  // 9. Partner job detail (mobile)
  await page.getByTestId(`partner-job-row-${SEED_ORDER_ID}`).click();
  await expect(page.getByTestId('partner-job-detail-page')).toBeVisible();
  await page.waitForTimeout(400);
  await captureFrame(page, 'phone', '06-partner-job-detail.png');

  // ───────────────────────── CUSTOMER ─────────────────────────
  await page.goto(`/c/${SEED_CUSTOMER_TOKEN}`);
  await expect(page.getByTestId('customer-verify-form')).toBeVisible();
  await page.waitForTimeout(300);

  // 10. Customer verify gate (mobile)
  await captureFrame(page, 'phone', '08-customer-verify.png');

  // Submit verification
  const tokenInput = page.getByTestId('customer-token-input');
  if (await tokenInput.isVisible().catch(() => false)) {
    await tokenInput.fill(SEED_CUSTOMER_TOKEN);
  }
  await page.getByTestId('customer-phone-suffix').fill(SEED_PHONE_SUFFIX);
  await page.getByTestId('customer-verify-submit').click();
  await expect(page.getByTestId('customer-order-page')).toBeVisible();
  await page.waitForTimeout(500);

  // 11. Customer reservation page (mobile)
  await captureFrame(page, 'phone', '09-customer-reservation.png');

  console.log(`\n✓ Captured screenshots → ${OUT_DIR}`);
});

async function loginAsAdmin(page: Page) {
  await page.goto('/');
  if (await page.getByTestId('admin-login-form').isVisible().catch(() => false)) {
    await page.getByTestId('admin-login-identifier').fill(ADMIN_EMAIL);
    await page.getByTestId('admin-login-password').fill(ADMIN_PASSWORD);
    await page.getByTestId('admin-login-submit').click();
  }
  await expect(page.getByTestId('admin-shell')).toBeVisible();
}

async function captureFrame(page: Page, kind: 'desktop' | 'phone', filename: string) {
  await page.setViewportSize(kind === 'desktop' ? { width: 1600, height: 1000 } : { width: 390, height: 844 });
  const main = page.locator('main').first();
  await expect(main).toBeVisible();
  await main.screenshot({ path: path.join(OUT_DIR, filename) });
  console.log(`  · ${filename}`);
}
