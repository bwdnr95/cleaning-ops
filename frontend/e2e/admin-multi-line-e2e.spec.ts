import { expect, test } from '@playwright/test';
import { adminLogin, createMultiLineOrder, getAdminOrderGroup } from './helpers';

test('관리자가 라인 2개 주문을 생성하고 같은 그룹에 묶여 표시된다', async ({ page, request }) => {
  const flow = await createMultiLineOrder(request, [
    { service_name: 'line A', partner_id: 'seed-partner-01', total_amount: 200000 },
    { service_name: 'line B', partner_id: null, total_amount: 100000 },
  ]);

  await adminLogin(page);
  await page.getByTestId('admin-nav-orders').click();
  await page.getByTestId('admin-orders-page').waitFor();
  await page.getByTestId('orders-date-clear').click();

  const lineARow = page.getByTestId(`admin-order-row-${flow.lineIds[0]}`);
  const lineBRow = page.getByTestId(`admin-order-row-${flow.lineIds[1]}`);
  await expect(lineARow).toBeVisible();
  await expect(lineBRow).toBeVisible();

  await lineARow.click();
  await expect(page.getByTestId(`order-sibling-${flow.lineIds[1]}`)).toBeVisible();
});

test('고객이 같은 링크로 두 라인 카드를 모두 본다', async ({ page, request }) => {
  const flow = await createMultiLineOrder(request, [
    { service_name: 'line A', partner_id: 'seed-partner-01', total_amount: 200000 },
    { service_name: 'line B', partner_id: null, total_amount: 100000 },
  ]);

  await page.goto(`/c/${flow.customerToken}`);
  await page.getByTestId('customer-phone-suffix').fill(flow.phoneSuffix);
  await page.getByTestId('customer-verify-submit').click();

  await expect(page.getByTestId(`customer-line-${flow.lineIds[0]}`)).toBeVisible();
  await expect(page.getByTestId(`customer-line-${flow.lineIds[1]}`)).toBeVisible();
});

test('admin edit preserves existing group notes', async ({ page, request }) => {
  const groupNotes = `Preserve group memo ${Date.now()}`;
  const flow = await createMultiLineOrder(
    request,
    [{ service_name: 'line with memo', partner_id: 'seed-partner-01', total_amount: 200000 }],
    { notes: groupNotes },
  );

  await adminLogin(page);
  await page.getByTestId('admin-nav-orders').click();
  await page.getByTestId('admin-orders-page').waitFor();
  await page.getByTestId('orders-date-clear').click();
  await page.getByTestId(`admin-order-row-${flow.lineIds[0]}`).click();
  await expect(page.getByTestId('admin-order-detail-page')).toBeVisible();

  await page.getByTestId('order-detail-edit').click();
  await expect(page.getByTestId('admin-order-form')).toBeVisible();
  await expect(page.getByTestId('order-group-notes')).toHaveValue(groupNotes);
  await page.getByTestId('order-line-0-service-name').fill('line with memo edited');
  await page.getByTestId('order-save').click();
  await expect(page.getByTestId('admin-order-detail-page')).toBeVisible();

  const group = await getAdminOrderGroup(request, flow.groupId);
  expect(group.notes).toBe(groupNotes);
});
