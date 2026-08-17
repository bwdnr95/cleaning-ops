import { expect, test } from '@playwright/test';

import {
  adminLogin,
  confirmPartnerJob,
  createAssignedOrder,
  createMultiLineOrder,
  getAdminOrderGroup,
  partnerLogin,
  updateAdminOrder,
} from './helpers';

test('multi-visit dates stay visible across admin, calendar, partner, and customer surfaces', async ({ browser, request }, testInfo) => {
  const visitDates = [currentMonthDate(9), currentMonthDate(13)];
  const flow = await createAssignedOrder(request, { visitDates });

  const adminContext = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const adminPage = await adminContext.newPage();
  try {
    await adminLogin(adminPage);
    await adminPage.goto(`/#orders/${flow.orderId}`);
    await expect(adminPage.getByTestId('admin-order-detail-page')).toBeVisible();
    await expect(adminPage.getByText(visitDates.join(' · '))).toBeVisible();
    await adminPage.screenshot({ path: testInfo.outputPath('admin-detail-1280.png'), fullPage: true });

    await adminPage.setViewportSize({ width: 768, height: 900 });
    await adminPage.goto('/#calendar');
    await expect(adminPage.getByTestId('admin-calendar-page')).toBeVisible();
    for (const visitDate of visitDates) {
      const day = Number(visitDate.slice(-2));
      const dayCell = adminPage.getByTestId(`calendar-day-${day}`);
      await expect(dayCell).toContainText('R6 Photo Review E2E');
      await adminPage.getByTestId(`calendar-day-select-${day}`).click();
      await expect(adminPage.getByTestId('calendar-day-panel')).toContainText('R6 Photo Review E2E');
    }
    const selectedDayButton = adminPage.getByTestId(`calendar-day-select-${Number(visitDates[1].slice(-2))}`);
    await selectedDayButton.focus();
    await expect(selectedDayButton).toBeFocused();
    await adminPage.screenshot({ path: testInfo.outputPath('admin-calendar-768.png'), fullPage: true });

    await adminPage.setViewportSize({ width: 375, height: 812 });
    await adminPage.goto('/#orders/new');
    await expect(adminPage.getByTestId('admin-order-form')).toBeVisible();
    await adminPage.getByTestId('order-line-0-visit-dates').click();
    const picker = adminPage.getByRole('dialog', { name: '방문 예정일 선택 달력' });
    await expect(picker).toBeVisible();
    await expect(picker.locator('[data-date-value][tabindex="0"]')).toHaveCount(1);
    for (const visitDate of visitDates) {
      await adminPage.getByTestId(`order-line-0-visit-dates-day-${visitDate}`).click();
      await expect(adminPage.getByTestId(`order-line-0-visit-dates-day-${visitDate}`)).toHaveAttribute('aria-pressed', 'true');
    }
    const firstFocusable = picker.getByRole('button', { name: '이전 달' });
    const lastFocusable = picker.getByRole('button', { name: '선택 완료' });
    await lastFocusable.focus();
    await adminPage.keyboard.press('Tab');
    await expect(firstFocusable).toBeFocused();
    await adminPage.keyboard.press('Shift+Tab');
    await expect(lastFocusable).toBeFocused();
    await adminPage.getByTestId(`order-line-0-visit-dates-day-${visitDates[0]}`).focus();
    await expect(adminPage.getByTestId(`order-line-0-visit-dates-day-${visitDates[0]}`)).toBeFocused();
    await adminPage.screenshot({ path: testInfo.outputPath('admin-picker-375.png'), fullPage: true });
  } finally {
    await adminContext.close();
  }

  const partnerContext = await browser.newContext({ viewport: { width: 375, height: 812 } });
  const partnerPage = await partnerContext.newPage();
  try {
    await partnerLogin(partnerPage);
    await partnerPage.getByTestId(`partner-job-row-${flow.orderId}`).click();
    const detail = partnerPage.getByTestId('partner-job-detail-page');
    await expect(detail).toBeVisible();
    await expect(detail.getByText(/^1차 ·/)).toBeVisible();
    await expect(detail.getByText(/^2차 ·/)).toBeVisible();
    await partnerPage.screenshot({ path: testInfo.outputPath('partner-detail-375.png'), fullPage: true });
  } finally {
    await partnerContext.close();
  }

  const customerContext = await browser.newContext({ viewport: { width: 375, height: 812 } });
  const customerPage = await customerContext.newPage();
  try {
    await customerPage.goto(`/c#token=${encodeURIComponent(flow.customerToken)}`);
    await customerPage.getByTestId('customer-phone-suffix').fill(flow.phoneSuffix);
    await customerPage.getByTestId('customer-verify-submit').click();
    const line = customerPage.getByTestId(`customer-line-${flow.orderId}`);
    await expect(line).toBeVisible();
    await expect(customerPage.getByText('총 2회 방문 예정입니다')).toBeVisible();
    await expect(line.getByText(/^1차 ·/)).toBeVisible();
    await expect(line.getByText(/^2차 ·/)).toBeVisible();
    await customerPage.screenshot({ path: testInfo.outputPath('customer-reservation-375.png'), fullPage: true });
  } finally {
    await customerContext.close();
  }
});

test('manual day-before notice stays available for later-visit recovery statuses', async ({ page, request }) => {
  const flow = await createAssignedOrder(request, {
    visitDates: [koreaDateOffset(-2), koreaDateOffset(1)],
  });
  await confirmPartnerJob(request, flow.orderId);
  await updateAdminOrder(request, flow.orderId, { status: '전날안내완료' });
  await adminLogin(page);
  await page.goto(`/#orders/${flow.orderId}`);
  await expect(page.getByTestId('admin-order-detail-page')).toBeVisible();

  const action = page.getByTestId('send-customer-day-before');
  await expect(action).toBeEnabled();
  await updateAdminOrder(request, flow.orderId, { status: '작업진행' });
  await page.reload();
  await expect(action).toBeEnabled();
  await action.click();
  await expect(page.getByTestId('message-preview-modal')).toBeVisible();
});

test('multi-date picker keeps tablet touch targets at least 44 pixels', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 700, height: 900 });
  await adminLogin(page);
  await page.goto('/#orders/new');
  await expect(page.getByTestId('admin-order-form')).toBeVisible();

  const trigger = page.getByTestId('order-line-0-visit-dates');
  await trigger.click();
  const picker = page.getByRole('dialog', { name: '방문 예정일 선택 달력' });
  const visitDate = currentMonthDate(9);
  const day = page.getByTestId(`order-line-0-visit-dates-day-${visitDate}`);
  await day.click();

  const targets = [
    trigger,
    day,
    page.getByRole('button', { name: '이전 달' }),
    page.getByRole('button', { name: '선택 완료' }),
    page.getByRole('button', { name: /9일 삭제$/ }),
  ];
  for (const target of targets) {
    const box = await target.boundingBox();
    expect(box).not.toBeNull();
    expect(box?.width).toBeGreaterThanOrEqual(44);
    expect(box?.height).toBeGreaterThanOrEqual(44);
  }

  const pickerOverflow = await picker.evaluate((element) => ({
    clientWidth: element.clientWidth,
    scrollWidth: element.scrollWidth,
  }));
  const gridOverflow = await picker.locator('.multi-date-picker__grid').evaluate((element) => ({
    clientWidth: element.clientWidth,
    scrollWidth: element.scrollWidth,
  }));
  expect(pickerOverflow.scrollWidth).toBeLessThanOrEqual(pickerOverflow.clientWidth);
  expect(gridOverflow.scrollWidth).toBeLessThanOrEqual(gridOverflow.clientWidth);

  const pickerBox = await picker.boundingBox();
  expect(pickerBox).not.toBeNull();
  expect(pickerBox?.x).toBeGreaterThanOrEqual(0);
  expect((pickerBox?.x || 0) + (pickerBox?.width || 0)).toBeLessThanOrEqual(700);
  await page.screenshot({ path: testInfo.outputPath('admin-picker-700.png'), fullPage: true });

  const firstDay = picker.locator('[data-date-value]').nth(0);
  const secondDay = picker.locator('[data-date-value]').nth(1);
  const expectedHitDate = await firstDay.getAttribute('data-date-value');
  for (const viewportWidth of [320, 360, 361]) {
    await page.setViewportSize({ width: viewportWidth, height: 900 });
    const narrowGridOverflow = await picker.locator('.multi-date-picker__grid').evaluate((element) => ({
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
    }));
    expect(narrowGridOverflow.scrollWidth).toBeLessThanOrEqual(narrowGridOverflow.clientWidth);

    const firstDayBox = await firstDay.boundingBox();
    const secondDayBox = await secondDay.boundingBox();
    expect(firstDayBox).not.toBeNull();
    expect(secondDayBox).not.toBeNull();
    expect((firstDayBox?.x || 0) + (firstDayBox?.width || 0)).toBeLessThanOrEqual(secondDayBox?.x || 0);

    const actualHitDate = await page.evaluate(({ x, y }) => (
      document.elementFromPoint(x, y)
        ?.closest<HTMLElement>('[data-date-value]')
        ?.dataset.dateValue || null
    ), {
      x: Math.floor((firstDayBox?.x || 0) + (firstDayBox?.width || 0) - 1),
      y: Math.floor((firstDayBox?.y || 0) + (firstDayBox?.height || 0) / 2),
    });
    expect(actualHitDate).toBe(expectedHitDate);

    const narrowPickerBox = await picker.boundingBox();
    expect(narrowPickerBox).not.toBeNull();
    expect(narrowPickerBox?.x).toBeGreaterThanOrEqual(0);
    expect((narrowPickerBox?.x || 0) + (narrowPickerBox?.width || 0)).toBeLessThanOrEqual(viewportWidth);
    if (viewportWidth === 320) {
      await page.screenshot({ path: testInfo.outputPath('admin-picker-320.png'), fullPage: true });
    }
  }
});

test('customer headline counts unique visit dates across every service line', async ({ page, request }) => {
  const first = koreaDateOffset(2);
  const shared = koreaDateOffset(4);
  const last = koreaDateOffset(7);
  const flow = await createMultiLineOrder(request, [
    { service_name: '다중 방문 A', visit_dates: [first, shared] },
    { service_name: '다중 방문 B', visit_dates: [shared, last] },
  ]);

  await page.goto(`/c#token=${encodeURIComponent(flow.customerToken)}`);
  await page.getByTestId('customer-phone-suffix').fill(flow.phoneSuffix);
  await page.getByTestId('customer-verify-submit').click();
  await expect(page.getByText('총 3회 방문 예정입니다')).toBeVisible();
  await expect(page.getByTestId(`customer-line-${flow.lineIds[0]}`).getByText(/^1차 ·/)).toBeVisible();
  await expect(page.getByTestId(`customer-line-${flow.lineIds[1]}`).getByText(/^2차 ·/)).toBeVisible();
});

test('dashboard includes an order when today is a later visit', async ({ page, request }) => {
  const flow = await createAssignedOrder(request, {
    visitDates: [koreaDateOffset(-1), koreaDateOffset(0)],
  });

  await adminLogin(page);
  await expect(page.getByTestId(`dashboard-job-${flow.orderId}`)).toBeVisible();
});

test('cancelling a bulk schedule replacement preserves every visit date', async ({ page, request }) => {
  const visitDates = [koreaDateOffset(1), koreaDateOffset(3), koreaDateOffset(5)];
  const flow = await createAssignedOrder(request, { visitDates });

  await adminLogin(page);
  await page.goto('/#orders');
  const row = page.getByTestId(`admin-order-row-${flow.orderId}`);
  await expect(row).toBeVisible();
  await row.locator('input[type="checkbox"]').check();
  await page.getByTestId('orders-bulk-schedule-open').click();
  await page.getByTestId('orders-bulk-schedule-date').click();
  await page.getByTestId(`date-picker-day-${koreaDateOffset(0)}`).click();

  let didRequestConfirmation = false;
  page.once('dialog', async (dialog) => {
    expect(dialog.type()).toBe('confirm');
    didRequestConfirmation = true;
    await dialog.dismiss();
  });
  await page.getByTestId('orders-bulk-schedule-apply').click();
  await expect.poll(() => didRequestConfirmation).toBe(true);

  const group = await getAdminOrderGroup(request, flow.groupId);
  expect(group.lines[0].visit_dates).toEqual(visitDates);
});

function currentMonthDate(day: number): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  return `${now.getFullYear()}-${month}-${String(day).padStart(2, '0')}`;
}

function koreaDateOffset(offsetDays: number): string {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Seoul',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date());
  const values = Object.fromEntries(
    parts.filter((part) => part.type !== 'literal').map((part) => [part.type, Number(part.value)]),
  );
  const date = new Date(Date.UTC(values.year, values.month - 1, values.day + offsetDays));
  return date.toISOString().slice(0, 10);
}
