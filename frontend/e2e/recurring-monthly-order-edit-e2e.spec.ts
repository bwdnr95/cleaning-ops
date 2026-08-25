import { expect, test } from '@playwright/test';

import { adminLogin } from './helpers';

/**
 * 정기청소 > 주문관리에서 월 청구 계약 주문을 수정하는 흐름.
 *
 * 회귀 대상: 금액을 건드리지 않았는데도 저장이 400(recurring_customer_payment_not_per_visit)으로
 * 막히던 문제. 월 청구 계약은 금액을 계약에서 관리하므로 주문 수정 화면은 금액 입력을 잠그고,
 * 상세상품 선택으로 단가가 자동 계산되지도 않아야 한다.
 */
test('월 청구 정기 주문은 금액이 잠기고 나머지 수정은 저장된다', async ({ page }) => {
  const suffix = Date.now();
  const label = `E2E 월청구 수정 ${suffix}`;
  const customerName = `월청구 수정 고객 ${suffix}`;

  await adminLogin(page);
  await page.getByTestId('admin-nav-recurring').click();
  await expect(page.getByTestId('admin-recurring-page')).toBeVisible();

  await page.getByTestId('recurring-create').click();
  await page.getByTestId('rc-label').fill(label);
  await page.getByTestId('rc-customer-name').fill(customerName);
  await page.getByTestId('rc-customer-phone').fill('01012347777');
  await page.getByTestId('rc-customer-address').fill('서울 정기구 월청구로 2');
  await page.getByTestId('rc-start-date').fill('2020-01-10');
  await page.getByTestId('rc-service-name').fill('사무실 정기청소');
  await page.getByTestId('rc-billing-mode').selectOption('monthly');
  await page.getByTestId('rc-amount').fill('770000');
  await page.getByTestId('rc-partner-billing-mode').selectOption('monthly');
  await page.getByTestId('rc-partner-payment-amount').fill('660000');
  await page.getByTestId('rc-default-partner').selectOption({ index: 1 });
  await page.getByTestId('rc-submit').click();
  await expect(page.getByText(label)).toBeVisible();

  await page.getByTestId('recurring-tab-orders').click();
  await expect(page.getByTestId('admin-recurring-orders-list')).toBeVisible();
  await page.getByRole('textbox', { name: '주문 검색' }).fill(customerName);
  const row = page.locator('tbody tr').filter({ hasText: customerName }).first();
  await expect(row).toBeVisible();
  await row.getByRole('button', { name: '수정' }).click();
  await expect(page.getByTestId('admin-order-form')).toBeVisible();

  // 금액 입력은 잠기고 이유가 화면에 보인다.
  const totalAmount = page.getByTestId('order-line-0-total-amount');
  const partnerAmount = page.getByTestId('order-line-0-partner-payment-amount');
  await expect(totalAmount).toBeDisabled();
  await expect(totalAmount).toHaveValue('');
  await expect(partnerAmount).toBeDisabled();
  await expect(page.getByText('월 청구 정기계약 — 금액은 계약에서 관리')).toBeVisible();

  // 상세상품을 고르면 단가가 자동 계산되지만, 잠긴 주문에서는 금액이 채워지면 안 된다.
  // (소비자가에서 파생되는 계약금·잔금도 마찬가지 — 자동 계산 결과가 남으면 안 된다.)
  await page.getByTestId('order-line-0-service-category').selectOption({ index: 1 });
  await page.getByTestId('order-line-0-service-item').selectOption({ index: 1 });
  await expect(totalAmount).toHaveValue('');
  await expect(partnerAmount).toHaveValue('');
  await expect(page.getByTestId('order-line-0-deposit-amount')).toHaveValue('');
  await expect(page.getByTestId('order-line-0-grand-total')).toHaveText('₩0');

  await page.getByRole('textbox', { name: '요청사항' }).fill('현관 비밀번호 확인 필요');
  await page.getByTestId('order-save').click();

  // 저장 성공 시 주문 상세로 이동한다(400 이면 폼에 머물며 오류 배너가 뜬다).
  await expect(page.getByTestId('admin-order-detail-page')).toBeVisible();
  await expect(page.getByText('현관 비밀번호 확인 필요')).toBeVisible();
});
