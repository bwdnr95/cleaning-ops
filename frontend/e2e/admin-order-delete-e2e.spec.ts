import { expect, test } from '@playwright/test';
import { adminLogin, createAssignedOrder } from './helpers';

test('admin can delete a single order from detail page', async ({ browser, request }) => {
  const flow = await createAssignedOrder(request);
  const context = await browser.newContext();
  const page = await context.newPage();
  await adminLogin(page);

  await page.getByTestId('admin-nav-orders').click();
  await expect(page.getByTestId('admin-orders-page')).toBeVisible();
  await page.getByTestId(`admin-order-row-${flow.orderId}`).click();

  await expect(page.getByTestId('admin-order-detail-page')).toBeVisible();

  page.on('dialog', (dialog) => dialog.accept());
  await page.getByTestId('order-detail-delete').click();

  await expect(page.getByTestId('admin-orders-page')).toBeVisible();
  await expect(page.getByText(flow.orderId)).toHaveCount(0);

  await context.close();
});

test('admin can bulk-delete selected orders from list page', async ({ browser, request }) => {
  const flow1 = await createAssignedOrder(request);
  const flow2 = await createAssignedOrder(request);
  const context = await browser.newContext();
  const page = await context.newPage();
  await adminLogin(page);

  await page.getByTestId('admin-nav-orders').click();
  await expect(page.getByTestId('admin-orders-page')).toBeVisible();

  await page.locator(`[data-testid="admin-order-row-${flow1.orderId}"] input[type="checkbox"]`).check();
  await page.locator(`[data-testid="admin-order-row-${flow2.orderId}"] input[type="checkbox"]`).check();

  await expect(page.getByText('2건 선택')).toBeVisible();
  page.on('dialog', (dialog) => dialog.accept());
  await page.getByTestId('orders-bulk-delete').click();

  await expect(page.getByText(flow1.orderId)).toHaveCount(0);
  await expect(page.getByText(flow2.orderId)).toHaveCount(0);

  await context.close();
});
