import { expect, test, type Route } from '@playwright/test';

import { adminLogin } from './helpers';

function currentMonth(): string {
  const date = new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
}

test('admin can manage recurring partner monthly payout', async ({ page }) => {
  const suffix = Date.now();
  const label = `E2E 월도급 ${suffix}`;
  const updatedLabel = `${label} 수정`;
  const customerName = `정기 월도급 고객 ${suffix}`;

  await adminLogin(page);
  await page.getByTestId('admin-nav-recurring').click();
  await expect(page.getByTestId('admin-recurring-page')).toBeVisible();

  await page.getByTestId('recurring-create').click();
  await page.getByTestId('rc-label').fill(label);
  await page.getByTestId('rc-customer-name').fill(customerName);
  await page.getByTestId('rc-customer-phone').fill('01012349999');
  await page.getByTestId('rc-customer-address').fill('서울 정기구 월도급로 1');
  await page.getByTestId('rc-start-date').fill('2020-01-10');
  await page.getByTestId('rc-service-name').fill('사무실 정기청소');
  await page.getByTestId('rc-billing-mode').selectOption('monthly');
  await page.getByTestId('rc-amount').fill('600000');
  await page.getByTestId('rc-partner-billing-mode').selectOption('monthly');
  await page.getByTestId('rc-partner-payment-amount').fill('250000');
  await page.getByTestId('rc-default-partner').selectOption({ index: 1 });
  const originalPartnerId = await page.getByTestId('rc-default-partner').inputValue();
  await page.getByTestId('rc-submit').click();

  await expect(page.getByText(label)).toBeVisible();
  await page.getByText(label).click();
  await expect(page.getByTestId('rc-detail-label')).toHaveText(label);
  await expect(page.getByText('협력사 정산 방식')).toBeVisible();
  await expect(page.getByText('월결제')).toHaveCount(2);
  await expect(page.getByText('협력사 도급가')).toBeVisible();
  await expect(page.getByText('250,000원')).toBeVisible();
  await page.getByTestId('rc-detail-edit').click();
  await expect(page.getByTestId('rc-partner-billing-effective-note')).toContainText(
    '이전 달 정산 이력과 기존 주문·사진은 그대로 유지됩니다.',
  );
  const rejectConcurrentChange = async (route: Route) => {
    if (route.request().method() === 'PATCH') {
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'recurring_partner_changed_concurrently' }),
      });
      return;
    }
    await route.continue();
  };
  await page.route('**/api/admin/recurring/contracts/*', rejectConcurrentChange);
  await page.setViewportSize({ width: 375, height: 812 });
  await expect(page.getByTestId('admin-mobile-create-order')).toHaveCount(0);
  for (const control of [page.getByTestId('rc-submit'), page.getByTestId('rc-default-partner')]) {
    const box = await control.boundingBox();
    expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
  }
  await page.getByTestId('rc-submit').click();
  const formError = page.getByTestId('rc-form-error');
  await expect(formError).toBeFocused();
  await expect(formError).toContainText('최신 정보를 다시 불러온 뒤 시도하세요.');
  await page.unroute('**/api/admin/recurring/contracts/*', rejectConcurrentChange);
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.getByRole('button', { name: '취소' }).click();

  const emptyPartnerList = async (route: Route) => {
    await route.fulfill({ json: [] });
  };
  let editPayload: Record<string, unknown> | null = null;
  const captureUnrelatedEdit = async (route: Route) => {
    if (route.request().method() === 'PATCH') {
      editPayload = route.request().postDataJSON() as Record<string, unknown>;
    }
    await route.continue();
  };
  await page.route('**/api/admin/partners', emptyPartnerList);
  await page.route('**/api/admin/recurring/contracts/*', captureUnrelatedEdit);
  await page.getByTestId('rc-detail-edit').click();
  const archivedPartner = page.getByTestId('rc-default-partner');
  await expect(archivedPartner).toHaveValue(originalPartnerId);
  await expect(archivedPartner.locator('option:checked')).toHaveText('보관된 협력사 (기존 배정)');
  await page.getByTestId('rc-label').fill(updatedLabel);
  await page.getByTestId('rc-submit').click();
  await expect(page.getByTestId('rc-detail-label')).toHaveText(updatedLabel);
  expect(editPayload).toEqual({ label: updatedLabel });
  await page.unroute('**/api/admin/partners', emptyPartnerList);
  await page.unroute('**/api/admin/recurring/contracts/*', captureUnrelatedEdit);

  await page.getByRole('button', { name: '목록' }).click();
  await page.getByTestId('recurring-tab-orders').click();
  await expect(page.getByTestId('admin-recurring-orders-list')).toBeVisible();
  await page.getByRole('textbox', { name: '주문 검색' }).fill(customerName);
  await expect(page.locator('tbody').getByText(customerName, { exact: true })).toBeVisible();

  await page.getByTestId('admin-nav-orders').click();
  await page.getByRole('textbox', { name: '주문 검색' }).fill(customerName);
  await expect(page.locator('tbody').getByText(customerName, { exact: true })).toHaveCount(0);

  await page.getByTestId('admin-nav-recurring').click();
  await page.getByTestId('recurring-tab-monthly').click();
  await page.getByTestId('monthly-month').fill(currentMonth());
  const row = page.locator('tr').filter({ hasText: updatedLabel });
  await expect(row).toContainText('250,000원');
  const partnerPaid = row.getByRole('checkbox', { name: new RegExp(`${updatedLabel} .* 협력사 지급`) });
  await expect(partnerPaid).not.toBeChecked();
  await partnerPaid.click();
  await expect(partnerPaid).toBeChecked();

  await page.setViewportSize({ width: 375, height: 812 });
  const mockedSettlements = async (route: Route) => {
    if (route.request().method() !== 'GET') {
      await route.continue();
      return;
    }
    await route.fulfill({
      json: {
        items: [
          {
            order_id: 'e2e-unpaid-in-progress',
            status: '작업진행',
            scheduled_date: '2026-08-12',
            service_name: '진행 중 정산 가능 주문',
            customer_name: '선택 테스트',
            address_short: '서울',
            address_detail: null,
            consumer_price: 100000,
            partner_price: 70000,
            partner_payment_status: 'unpaid',
            settled_at: null,
            group_consumer_total: 100000,
            group_partner_total: 70000,
          },
          {
            order_id: 'e2e-cancelled-unpaid',
            status: '취소',
            scheduled_date: '2026-08-12',
            service_name: '취소 주문',
            customer_name: '선택 테스트',
            address_short: '서울',
            address_detail: null,
            consumer_price: 100000,
            partner_price: 70000,
            partner_payment_status: 'unpaid',
            settled_at: null,
            group_consumer_total: 100000,
            group_partner_total: 70000,
          },
        ],
        total_partner_price: 140000,
        total_consumer_price: 200000,
        count: 2,
      },
    });
  };
  await page.route('**/api/admin/partners/*/settlements**', mockedSettlements);
  await page.getByTestId('admin-mobile-nav-partners').click();
  await expect(page.getByTestId('partner-settlement-row-e2e-unpaid-in-progress')).toBeVisible();
  await page.getByTestId('partner-settlement-select-all').check();
  await expect(page.getByTestId('partner-settlement-select-e2e-unpaid-in-progress')).toBeChecked();
  await expect(page.getByTestId('partner-settlement-select-e2e-cancelled-unpaid')).toBeDisabled();
  for (const control of [
    page.getByTestId('partner-search-input').locator('..'),
    page.getByTestId('partner-category-filter-all'),
  ]) {
    const box = await control.boundingBox();
    expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
  }
  await page.getByTestId('partner-settlement-from').click();
  const popup = page.locator('.date-picker-popup');
  await expect(popup).toBeVisible();
  const focusedDay = popup.locator('[data-date-value][tabindex="0"]');
  await expect(focusedDay).toBeFocused();
  await expect(focusedDay).toHaveAccessibleName(/\d{4}년 \d{1,2}월 \d{1,2}일/);
  await expect(focusedDay).toHaveAttribute('aria-pressed', /true|false/);
  await expect(focusedDay).not.toHaveAttribute('aria-selected', /.+/);
  const focusedValue = await focusedDay.getAttribute('data-date-value');
  await page.keyboard.press('ArrowRight');
  const movedValue = await page.locator(':focus').getAttribute('data-date-value');
  expect(movedValue).not.toBe(focusedValue);
  await page.keyboard.press('Escape');
  await expect(popup).toBeHidden();
  await expect(page.getByTestId('partner-settlement-from')).toBeFocused();
  await page.getByTestId('partner-settlement-from').click();
  await expect(popup).toBeVisible();
  for (const control of [
    popup.getByRole('button', { name: '이전 달' }),
    popup.getByRole('button', { name: '다음 달' }),
    popup.locator('.date-picker-popup__day').first(),
    popup.getByRole('button', { name: '오늘' }),
    popup.getByRole('button', { name: '지우기' }),
  ]) {
    const box = await control.boundingBox();
    expect(box?.width ?? 0).toBeGreaterThanOrEqual(44);
    expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
  }
  const dayToSelect = popup.locator('.date-picker-popup__day').first();
  const selectedDateName = await dayToSelect.getAttribute('aria-label');
  await dayToSelect.click();
  await expect(popup).toBeHidden();
  await page.getByTestId('partner-settlement-from').click();
  const selectedDay = popup.locator('[aria-pressed="true"]');
  await expect(selectedDay).toHaveCount(1);
  await expect(selectedDay).toHaveAccessibleName(selectedDateName ?? '');
  await page.keyboard.press('Escape');
  await page.unroute('**/api/admin/partners/*/settlements**', mockedSettlements);

  const createOrderFab = page.getByTestId('admin-mobile-create-order');
  await expect(createOrderFab).toHaveAccessibleName('신규 주문 등록');
  await createOrderFab.click();
  await expect(page.getByTestId('admin-order-form')).toBeVisible();
  await expect(page.getByTestId('admin-mobile-create-order')).toHaveCount(0);
  const customerNameBox = await page.getByTestId('order-customer-name').boundingBox();
  const customerPhoneBox = await page.getByTestId('order-customer-phone').boundingBox();
  expect(customerNameBox?.width ?? 0).toBeLessThanOrEqual(351);
  expect(customerPhoneBox?.y ?? 0).toBeGreaterThan(
    (customerNameBox?.y ?? 0) + (customerNameBox?.height ?? 0),
  );
  expect(customerNameBox?.height ?? 0).toBeGreaterThanOrEqual(44);
});
