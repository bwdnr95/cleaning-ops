import { expect, test } from '@playwright/test';
import { adminLogin } from './helpers';

test('admin can open address search modal and edit detail address', async ({ browser }) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  await adminLogin(page);

  await page.getByTestId('admin-nav-orders').click();
  await page.getByTestId('admin-orders-create').click();

  await expect(page.getByTestId('order-customer-address-search')).toBeVisible();
  await page.getByTestId('order-customer-address-search').click();
  await expect(page.getByTestId('order-customer-address-modal')).toBeVisible();
  await page.getByTestId('order-customer-address-modal-close').click();
  await expect(page.getByTestId('order-customer-address-modal')).toHaveCount(0);

  await page.getByTestId('order-customer-address-detail').fill('101동 1001호');
  await expect(page.getByTestId('order-customer-address-detail')).toHaveValue('101동 1001호');

  await context.close();
});
