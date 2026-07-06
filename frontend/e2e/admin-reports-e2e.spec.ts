import { expect, test } from '@playwright/test';

import { adminLogin } from './helpers';

test('admin can open reports page and see 5 tabs', async ({ browser }) => {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await adminLogin(page);
  await page.getByTestId('admin-nav-reports').click();
  await expect(page.getByTestId('admin-reports-page')).toBeVisible();
  for (const key of ['revenue', 'partners', 'services', 'source_channels', 'settlements']) {
    await expect(page.getByTestId(`reports-tab-${key}`)).toBeVisible();
  }
  await ctx.close();
});

test('admin can switch to partner tab and see table or empty state', async ({ browser }) => {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await adminLogin(page);
  await page.getByTestId('admin-nav-reports').click();
  await page.getByTestId('reports-tab-partners').click();
  await expect(page.getByTestId('reports-partners-export-csv')).toBeVisible();
  await ctx.close();
});

test('revenue tab shows partner and service filters', async ({ browser }) => {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await adminLogin(page);
  await page.getByTestId('admin-nav-reports').click();
  await expect(page.getByTestId('reports-tab-revenue')).toBeVisible();
  await expect(page.getByTestId('reports-revenue-partner-filter')).toBeVisible();
  await expect(page.getByTestId('reports-revenue-service-filter')).toBeVisible();
  await ctx.close();
});

test('source channel tab shows report export controls', async ({ browser }) => {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await adminLogin(page);
  await page.getByTestId('admin-nav-reports').click();
  await page.getByTestId('reports-tab-source_channels').click();
  await expect(page.getByTestId('reports-source-channels-export-csv')).toBeVisible();
  await ctx.close();
});

test('admin can open import dialog from orders page', async ({ browser }) => {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await adminLogin(page);
  await page.getByTestId('admin-nav-orders').click();
  await page.getByTestId('admin-orders-import').click();
  await expect(page.getByTestId('order-import-dialog')).toBeVisible();
  await ctx.close();
});
