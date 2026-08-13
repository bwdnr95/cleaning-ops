import { expect, test } from '@playwright/test';
import { adminLogin } from './helpers';

test('관리자가 신규 등록과 주문 수정 화면에서 증빙자료를 선택하고 저장한다', async ({ page }) => {
  await adminLogin(page);
  await page.getByTestId('admin-nav-orders').click();
  await page.getByTestId('admin-orders-create').click();
  await expect(page.getByTestId('admin-order-form')).toBeVisible();

  await page.getByTestId('order-customer-name').fill('증빙자료 폼 고객');
  await page.getByTestId('order-customer-phone').fill('010-9284-6153');
  await page.getByTestId('order-customer-address').fill('서울특별시 중구 증빙로 13');
  await page.getByTestId('order-line-0-service-name').fill('증빙자료 선택 테스트');

  await page.getByTestId('order-line-0-receipt-type').selectOption('tax_invoice');
  await page.getByTestId('order-line-0-receipt-status').selectOption('pending');
  await page.getByTestId('order-save').click();

  await expect(page.getByTestId('admin-order-detail-page')).toBeVisible();
  await expect(page.getByTestId('detail-receipt-type')).toHaveValue('tax_invoice');
  await expect(page.getByTestId('detail-receipt-status')).toHaveValue('pending');

  await page.getByTestId('order-detail-edit').click();
  await expect(page.getByTestId('order-line-0-receipt-type')).toHaveValue('tax_invoice');
  await expect(page.getByTestId('order-line-0-receipt-status')).toHaveValue('pending');

  await page.getByTestId('order-line-0-receipt-type').selectOption('');
  await expect(page.getByTestId('order-line-0-receipt-status')).toBeDisabled();
  await expect(page.getByTestId('order-line-0-receipt-status')).toHaveValue('');
  await page.getByTestId('order-save').click();
  await expect(page.getByTestId('detail-receipt-type')).toHaveValue('');
  await expect(page.getByTestId('detail-receipt-status')).toHaveValue('');

  await page.getByTestId('order-detail-edit').click();
  await page.getByTestId('order-line-0-receipt-type').selectOption('none');
  await expect(page.getByTestId('order-line-0-receipt-status')).toBeDisabled();
  await expect(page.getByTestId('order-line-0-receipt-status')).toHaveValue('not_applicable');
  await page.getByTestId('order-save').click();

  await expect(page.getByTestId('admin-order-detail-page')).toBeVisible();
  await expect(page.getByTestId('detail-receipt-type')).toHaveValue('none');
  await expect(page.getByTestId('detail-receipt-status')).toHaveValue('not_applicable');
});

test('관리자가 증빙만 수정해도 주소와 금액과 다중 라인을 보존한다', async ({ page }) => {
  // Given: 상세주소와 서로 다른 금액을 가진 두 라인 주문이 저장되어 있다.
  await adminLogin(page);
  await page.getByTestId('admin-nav-orders').click();
  await page.getByTestId('admin-orders-create').click();
  await expect(page.getByTestId('admin-order-form')).toBeVisible();

  await page.getByTestId('order-customer-name').fill('증빙 수정 보존 고객');
  await page.getByTestId('order-customer-phone').fill('010-8432-7651');
  await page.getByTestId('order-customer-address').fill('서울특별시 종로구 보존로 24');
  await page.getByTestId('order-customer-address-detail').fill('202동 1304호');
  await page.getByTestId('order-line-0-service-name').fill('증빙 보존 라인 A');
  await page.getByTestId('order-line-0-total-amount').fill('345000');
  await page.getByTestId('order-line-0-discount-amount').fill('25000');
  await page.getByTestId('order-line-0-deposit-amount').fill('120000');
  await page.getByTestId('order-line-0-onsite-extra-amount').fill('10000');

  await page.getByTestId('order-add-line').click();
  await page.getByTestId('order-line-1-service-name').fill('증빙 보존 라인 B');
  await page.getByTestId('order-line-1-total-amount').fill('210000');
  await page.getByTestId('order-line-1-discount-amount').fill('10000');
  await page.getByTestId('order-line-1-deposit-amount').fill('50000');
  await page.getByTestId('order-line-1-onsite-extra-amount').fill('5000');
  await page.getByTestId('order-save').click();

  await expect(page.getByTestId('admin-order-detail-page')).toBeVisible();
  const initialSibling = page.locator('[data-testid^="order-sibling-"]');
  await expect(initialSibling).toHaveCount(1);
  if ((await initialSibling.textContent())?.includes('증빙 보존 라인 A')) {
    await initialSibling.click();
    await expect(page.getByTestId('admin-order-detail-page')).toBeVisible();
  }
  const targetDetailUrl = page.url();
  const siblingBefore = page.locator('[data-testid^="order-sibling-"]');
  await expect(siblingBefore).toHaveCount(1);
  const siblingTestId = await siblingBefore.getAttribute('data-testid');
  await expect(siblingBefore).toContainText('증빙 보존 라인 B');
  await expect(siblingBefore).toContainText('₩200,000');

  // When: 첫 번째 라인의 증빙 종류와 상태만 수정한다.
  await page.getByTestId('order-detail-edit').click();
  await page.getByTestId('order-line-0-receipt-type').selectOption('cash_receipt');
  await page.getByTestId('order-line-0-receipt-status').selectOption('issued');
  await page.getByTestId('order-save').click();

  // Then: 대상과 형제 라인의 식별자 및 기존 고객·금액 정보가 그대로 유지된다.
  await expect(page.getByTestId('admin-order-detail-page')).toBeVisible();
  await expect(page).toHaveURL(targetDetailUrl);
  await expect(page.getByTestId('detail-receipt-type')).toHaveValue('cash_receipt');
  await expect(page.getByTestId('detail-receipt-status')).toHaveValue('issued');

  const siblingAfter = page.locator('[data-testid^="order-sibling-"]');
  await expect(siblingAfter).toHaveCount(1);
  expect(await siblingAfter.getAttribute('data-testid')).toBe(siblingTestId);
  await expect(siblingAfter).toContainText('증빙 보존 라인 B');
  await expect(siblingAfter).toContainText('₩200,000');

  await page.getByTestId('order-detail-edit').click();
  await expect(page.getByTestId('order-customer-address')).toHaveValue('서울특별시 종로구 보존로 24');
  await expect(page.getByTestId('order-customer-address-detail')).toHaveValue('202동 1304호');
  await expect(page.getByTestId('order-line-0-total-amount')).toHaveValue('345,000');
  await expect(page.getByTestId('order-line-0-discount-amount')).toHaveValue('25,000');
  await expect(page.getByTestId('order-line-0-deposit-amount')).toHaveValue('120,000');
  await expect(page.getByTestId('order-line-0-onsite-extra-amount')).toHaveValue('10,000');
});
