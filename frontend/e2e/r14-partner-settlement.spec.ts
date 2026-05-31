import { expect, test } from '@playwright/test';

import { adminLogin, createAssignedOrder } from './helpers';

test('R14 partner settlement can settle, notify, and revert from partner detail', async ({ page, request }) => {
  const flow = await createAssignedOrder(request, { status: '서비스완료' });
  page.on('dialog', (dialog) => dialog.accept());

  await adminLogin(page);
  await page.getByTestId('admin-nav-partners').click();
  await expect(page.getByTestId('admin-partners-page')).toBeVisible();

  await page.getByTestId('partner-settlement-status').selectOption('all');
  await expect(page.getByTestId(`partner-settlement-row-${flow.orderId}`)).toBeVisible();
  await expect(page.getByText('R6 Photo Review').first()).toBeVisible();

  await page.getByTestId(`partner-settlement-settle-${flow.orderId}`).click();
  await expect(page.getByTestId(`partner-settlement-revert-${flow.orderId}`)).toBeVisible({ timeout: 15_000 });

  await page.getByTestId(`partner-settlement-notify-${flow.orderId}`).click();
  await expect(page.getByTestId('partner-notify-modal')).toBeVisible();
  await page.getByTestId('partner-notify-send').click();
  await expect(page.getByTestId('partner-notify-modal')).toBeHidden({ timeout: 15_000 });

  await page.getByTestId(`partner-settlement-revert-${flow.orderId}`).click();
  await expect(page.getByTestId(`partner-settlement-settle-${flow.orderId}`)).toBeVisible({ timeout: 15_000 });
});
