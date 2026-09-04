import { expect, test, type Page } from '@playwright/test';
import { adminLogin, createAssignedOrder, updateAdminOrder } from './helpers';
import { addDays, formatDateValue, getAppTodayDate } from '../src/domain/time';

test('admin can delete a single order from detail page', async ({ browser, request }) => {
  const flow = await createAssignedOrder(request);
  const context = await browser.newContext();
  const page = await context.newPage();
  await adminLogin(page);

  await page.getByTestId('admin-nav-orders').click();
  await expect(page.getByTestId('admin-orders-page')).toBeVisible();
  await page.getByTestId('orders-date-preset-all').click();
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
  await page.getByTestId('orders-date-preset-all').click();

  await page.locator(`[data-testid="admin-order-row-${flow1.orderId}"] input[type="checkbox"]`).check();
  await page.locator(`[data-testid="admin-order-row-${flow2.orderId}"] input[type="checkbox"]`).check();

  await expect(page.getByText('2건 선택')).toBeVisible();
  page.on('dialog', async (dialog) => {
    expect(dialog.message()).toBe('선택한 2건의 주문을 삭제하시겠습니까? 삭제된 주문은 목록에서 사라지지만 운영 기록(타임라인)은 보존됩니다.');
    await dialog.accept();
  });
  await page.getByTestId('orders-bulk-delete').click();

  await expect(page.getByText(flow1.orderId)).toHaveCount(0);
  await expect(page.getByText(flow2.orderId)).toHaveCount(0);

  await context.close();
});

test('bulk delete warning describes an ordinary past visit without claiming recurring impact', async ({ browser, request }) => {
  const pastVisit = relativeDateValue(-1);
  const flow = await createAssignedOrder(request, { visitDates: [pastVisit] });
  const context = await browser.newContext();
  const page = await context.newPage();
  await adminLogin(page);

  await page.getByTestId('admin-nav-orders').click();
  await page.getByTestId('orders-date-preset-all').click();
  await page.locator(`[data-testid="admin-order-row-${flow.orderId}"] input[type="checkbox"]`).check();

  const message = await dismissBulkDeleteDialog(page);
  expect(message).toBe(
    '선택한 1건의 주문을 삭제하시겠습니까? 과거 방문 1건 포함 — 삭제하면 과거 작업 내역에서 사라집니다. 삭제된 주문은 목록에서 사라지지만 운영 기록(타임라인)은 보존됩니다.',
  );

  await expect(page.getByTestId(`admin-order-row-${flow.orderId}`)).toBeVisible();
  await context.close();
});

test('bulk delete warns for a real recurring order with a past visit', async ({ page, request }) => {
  const suffix = Date.now();
  const label = `삭제 경고 정기계약 ${suffix}`;
  const customerName = `삭제 경고 정기고객 ${suffix}`;
  const pastVisit = relativeDateValue(-1);
  await adminLogin(page);

  await page.getByTestId('admin-nav-recurring').click();
  await page.getByTestId('recurring-create').click();
  await page.getByTestId('rc-label').fill(label);
  await page.getByTestId('rc-customer-name').fill(customerName);
  await page.getByTestId('rc-customer-phone').fill('01012346666');
  await page.getByTestId('rc-customer-address').fill('서울 정기구 삭제경고로 1');
  await page.getByTestId('rc-start-date').fill('2020-01-10');
  await page.getByTestId('rc-service-name').fill('정기청소 삭제 경고 검증');
  await page.getByTestId('rc-amount').fill('150000');
  await page.getByTestId('rc-submit').click();
  await expect(page.getByText(label)).toBeVisible();

  await page.getByTestId('recurring-tab-orders').click();
  await page.getByRole('textbox', { name: '주문 검색' }).fill(customerName);
  const recurringRow = page.locator('tbody tr').filter({ hasText: customerName }).first();
  await expect(recurringRow).toBeVisible();
  const rowTestId = await recurringRow.getAttribute('data-testid');
  const orderId = rowTestId?.replace('admin-order-row-', '');
  if (!orderId) {
    throw new Error('정기계약 회차 주문 ID를 찾지 못했습니다.');
  }

  await updateAdminOrder(request, orderId, {
    scheduled_date: pastVisit,
    visit_dates: [pastVisit],
  });
  await page.reload();
  await expect(page.getByTestId('admin-recurring-page')).toBeVisible();
  await page.getByTestId('recurring-tab-orders').click();
  await page.getByRole('textbox', { name: '주문 검색' }).fill(customerName);
  const updatedRow = page.getByTestId(`admin-order-row-${orderId}`);
  await expect(updatedRow).toBeVisible();
  await updatedRow.locator('input[type="checkbox"]').check();

  const message = await dismissBulkDeleteDialog(page);
  expect(message).toBe(
    '선택한 1건의 주문을 삭제하시겠습니까? 정기계약 회차 1건·과거 방문 1건 포함 — 삭제하면 정기청소 내역/협력사 정산 목록에서도 사라집니다. 삭제된 주문은 목록에서 사라지지만 운영 기록(타임라인)은 보존됩니다.',
  );
  await expect(updatedRow).toBeVisible();
});

async function dismissBulkDeleteDialog(page: Page): Promise<string> {
  const dialogPromise = page.waitForEvent('dialog');
  const clickPromise = page.getByTestId('orders-bulk-delete').click();
  const dialog = await dialogPromise;
  const message = dialog.message();
  await dialog.dismiss();
  await clickPromise;
  return message;
}

function relativeDateValue(offsetDays: number): string {
  return formatDateValue(addDays(getAppTodayDate(), offsetDays));
}
