import { expect, test } from '@playwright/test';

import { adminLogin } from './helpers';

function currentMonth(): string {
  const date = new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
}

test('admin can manage recurring partner monthly payout', async ({ page }) => {
  const label = `E2E 월도급 ${Date.now()}`;

  await adminLogin(page);
  await page.getByTestId('admin-nav-recurring').click();
  await expect(page.getByTestId('admin-recurring-page')).toBeVisible();

  await page.getByTestId('recurring-create').click();
  await page.getByTestId('rc-label').fill(label);
  await page.getByTestId('rc-customer-name').fill('정기 월도급 고객');
  await page.getByTestId('rc-customer-phone').fill('01012349999');
  await page.getByTestId('rc-customer-address').fill('서울 정기구 월도급로 1');
  await page.getByTestId('rc-start-date').fill('2020-01-10');
  await page.getByTestId('rc-service-name').fill('사무실 정기청소');
  await page.getByTestId('rc-billing-mode').selectOption('monthly');
  await page.getByTestId('rc-amount').fill('600000');
  await page.getByTestId('rc-partner-billing-mode').selectOption('monthly');
  await page.getByTestId('rc-partner-payment-amount').fill('250000');
  await page.getByTestId('rc-submit').click();

  await expect(page.getByText(label)).toBeVisible();
  await page.getByText(label).click();
  await expect(page.getByTestId('rc-detail-label')).toHaveText(label);
  await expect(page.getByText('협력사 정산 방식')).toBeVisible();
  await expect(page.getByText('월결제')).toHaveCount(2);
  await expect(page.getByText('협력사 도급가')).toBeVisible();
  await expect(page.getByText('250,000원')).toBeVisible();

  await page.getByRole('button', { name: '목록' }).click();
  await page.getByTestId('recurring-tab-orders').click();
  await expect(page.getByTestId('admin-recurring-orders-list')).toBeVisible();
  await page.getByRole('textbox', { name: '주문 검색' }).fill('정기 월도급 고객');
  await expect(page.locator('tbody').getByText('정기 월도급 고객', { exact: true })).toBeVisible();

  await page.getByTestId('admin-nav-orders').click();
  await page.getByRole('textbox', { name: '주문 검색' }).fill('정기 월도급 고객');
  await expect(page.locator('tbody').getByText('정기 월도급 고객', { exact: true })).toHaveCount(0);

  await page.getByTestId('admin-nav-recurring').click();
  await page.getByTestId('recurring-tab-monthly').click();
  await page.getByTestId('monthly-month').fill(currentMonth());
  const row = page.locator('tr').filter({ hasText: label });
  await expect(row).toContainText('250,000원');
  const partnerPaid = row.getByRole('checkbox', { name: new RegExp(`${label} .* 협력사 지급`) });
  await expect(partnerPaid).not.toBeChecked();
  await partnerPaid.click();
  await expect(partnerPaid).toBeChecked();
});
