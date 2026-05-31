import { expect, test } from '@playwright/test';

import { adminLogin } from './helpers';

test('R14 order form calculates consumer price, partner price, VAT, and sends quote', async ({ page }) => {
  await adminLogin(page);
  await page.getByTestId('admin-nav-create-order').click();
  await expect(page.getByTestId('admin-order-form')).toBeVisible();

  await page.getByTestId('order-customer-name').fill('R14 견적 E2E');
  await page.getByTestId('order-customer-phone').fill('010-1414-2525');
  await page.getByTestId('order-customer-address').fill('서울시 R14 견적로 1');
  await page.getByTestId('order-customer-address-detail').fill('101동 1401호');

  await page.getByTestId('order-line-0-service-category').selectOption('seed-service-category-cleaning');
  await page.getByTestId('order-line-0-service-item').selectOption('seed-service-item-move-in');
  await page.getByLabel('수량/규격').fill('2');
  await page.getByTestId('order-line-0-discount-amount').fill('60000');
  await page.getByTestId('order-line-0-onsite-extra-amount').fill('20000');
  await page.getByTestId('order-line-0-vat-type').selectOption('excluded');

  await expect(page.getByTestId('order-line-0-total-amount')).toHaveValue('520,000');
  await expect(page.getByTestId('order-line-0-partner-payment-amount')).toHaveValue('392,000');

  await page.getByTestId('order-send-quote').click();
  await expect(page.getByTestId('admin-order-detail-page')).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/견적서 · R14 견적 E2E · Mock/)).toBeVisible();
  await expect(page.getByText('₩520,000')).toBeVisible();
  await expect(page.getByText(/도급가 ₩392,000/)).toBeVisible();
});
