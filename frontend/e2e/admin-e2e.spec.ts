import { expect, test } from '@playwright/test';

const backendPort = Number(process.env.E2E_BACKEND_PORT ?? 8003);
const backendUrl = `http://127.0.0.1:${backendPort}`;

const ADMIN_EMAIL = 'admin@cleanops.kr';
const ADMIN_PASSWORD = 'AdminPass123!';
const PARTNER_PHONE = '01012345678';
const PARTNER_PASSWORD = 'PartnerPass123!';
const SEED_PARTNER_ID = 'seed-partner-01';
const SEED_SERVICE_ITEM_ID = 'seed-service-item-move-in';
const ONE_PIXEL_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=',
  'base64',
);

test('admin can log in, navigate operational pages, and open order creation from the dashboard', async ({ page }) => {
  await loginAsAdmin(page);

  const pages = [
    ['orders', 'admin-orders-page'],
    ['calendar', 'admin-calendar-page'],
    ['photos', 'admin-photo-review-page'],
    ['products', 'admin-products-page'],
    ['partners', 'admin-partners-page'],
    ['sends', 'admin-messages-page'],
  ];

  for (const [navKey, pageTestId] of pages) {
    await page.getByTestId(`admin-nav-${navKey}`).click();
    await expect(page.getByTestId(pageTestId)).toBeVisible();
    if (navKey === 'photos') {
      await expect(page.getByTestId('photo-empty-title')).toContainText('사진 모니터링 큐가 비었습니다');
    }
  }

  await page.getByTestId('admin-nav-dashboard').click();
  await expect(page.getByTestId('admin-dashboard-page')).toBeVisible();
  await page.getByTestId('dashboard-create-order').click();
  await expect(page.getByTestId('admin-order-form')).toBeVisible();
});

test('admin and partner sessions stay active across role routes', async ({ page }) => {
  await loginAsAdmin(page);

  await page.goto('/partner');
  await expect(page.getByTestId('partner-login-form')).toBeVisible();
  await page.getByTestId('partner-login-identifier').fill(PARTNER_PHONE);
  await page.getByTestId('partner-login-password').fill(PARTNER_PASSWORD);
  await page.getByTestId('partner-login-submit').click();
  await expect(page.getByTestId('partner-jobs-page')).toBeVisible();

  await page.goto('/');
  await expect(page.getByTestId('admin-dashboard-page')).toBeVisible();
  await expect(page.getByTestId('admin-login-form')).toHaveCount(0);

  await page.goto('/partner');
  await expect(page.getByTestId('partner-jobs-page')).toBeVisible();
  await expect(page.getByTestId('partner-login-form')).toHaveCount(0);
});

test('dashboard KPI cards open the matching operational filters', async ({ page }) => {
  await loginAsAdmin(page);

  for (const item of [
    ['dashboard-kpi-today_jobs', 'orders-date-preset-today'],
    ['dashboard-kpi-tomorrow_notice', 'orders-date-preset-tomorrow'],
    ['dashboard-kpi-photo_review', 'orders-date-preset-all'],
    ['dashboard-kpi-customer_delivery', 'orders-date-preset-all'],
    ['dashboard-kpi-payment_check', 'orders-date-preset-all'],
    ['dashboard-kpi-monthly_done', 'orders-date-preset-month'],
    ['dashboard-kpi-monthly_revenue', 'orders-date-preset-month'],
  ]) {
    await page.getByTestId(item[0]).click();
    await expect(page.getByTestId('admin-orders-page')).toBeVisible();
    await expect(page.getByTestId(item[1])).toHaveAttribute('aria-pressed', 'true');
    await page.getByTestId('admin-nav-dashboard').click();
    await expect(page.getByTestId('admin-dashboard-page')).toBeVisible();
  }
});

test('admin order status tabs use the simplified workflow states only', async ({ page, request }) => {
  const unpaidCompletedOrder = await createUnpaidCompletedOrder(request);

  await loginAsAdmin(page);
  await page.getByTestId('admin-nav-orders').click();
  await expect(page.getByTestId('admin-orders-page')).toBeVisible();

  const expectedTabs = [
    ['orders-tab-all', '전체'],
    ['orders-tab-consulting_unassigned', '상담중/미배정'],
    ['orders-tab-schedule_partner_checking', '일정 및 협력사 확인중'],
    ['orders-tab-schedule_work_confirmed', '일정 및 작업 확정'],
    ['orders-tab-work_done', '작업완료'],
    ['orders-tab-final_payment_complete', '최종결제완료'],
    ['orders-tab-cancel', '취소'],
  ];

  for (const [testId, label] of expectedTabs) {
    await expect(page.getByTestId(testId)).toBeVisible();
    await expect(page.getByTestId(testId)).toContainText(label);
  }

  for (const oldTab of [
    'orders-tab-today',
    'orders-tab-tomorrow_notice',
    'orders-tab-partner_pending',
    'orders-tab-photo_review',
    'orders-tab-payment_check',
    'orders-tab-monthly_done',
    'orders-tab-monthly_revenue',
  ]) {
    await expect(page.getByTestId(oldTab)).toHaveCount(0);
  }

  await page.getByTestId('orders-tab-work_done').click();
  await expect(page.getByTestId(`admin-order-row-${unpaidCompletedOrder.id}`)).toBeVisible();
  await expect(page.getByTestId(`admin-order-row-${unpaidCompletedOrder.id}`)).toContainText('작업완료');

  await page.getByTestId('orders-tab-final_payment_complete').click();
  await expect(page.getByTestId(`admin-order-row-${unpaidCompletedOrder.id}`)).toHaveCount(0);
});

test('dashboard monthly revenue KPI shows current-month completed paid orders', async ({ page, request }) => {
  const order = await createMonthlyRevenueOrder(request);

  await loginAsAdmin(page);
  await page.getByTestId('dashboard-kpi-monthly_revenue').click();

  await expect(page.getByTestId('admin-orders-page')).toBeVisible();
  await expect(page.getByTestId('orders-date-preset-month')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByTestId(`admin-order-row-${order.id}`)).toBeVisible();
  await expect(page.getByTestId(`admin-order-row-${order.id}`)).toContainText(order.customer_name);
});

test('dashboard today and tomorrow work lists open matching order queues', async ({ page }) => {
  await loginAsAdmin(page);

  await page.getByRole('button', { name: '큐 보기' }).first().click();
  await expect(page.getByTestId('admin-orders-page')).toBeVisible();
  await expect(page.getByTestId('orders-tab-schedule_work_confirmed')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByTestId('orders-date-preset-today')).toHaveAttribute('aria-pressed', 'true');

  await page.getByTestId('admin-nav-dashboard').click();
  await expect(page.getByTestId('admin-dashboard-page')).toBeVisible();
  await page.getByRole('button', { name: '큐 보기' }).nth(1).click();
  await expect(page.getByTestId('admin-orders-page')).toBeVisible();
  await expect(page.getByTestId('orders-tab-schedule_work_confirmed')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByTestId('orders-date-preset-tomorrow')).toHaveAttribute('aria-pressed', 'true');
});

test('browser back stays inside admin navigation history', async ({ page }) => {
  await loginAsAdmin(page);

  await page.getByTestId('admin-nav-orders').click();
  await expect(page.getByTestId('admin-orders-page')).toBeVisible();
  await expect(page).toHaveURL(/#orders$/);

  await page.getByTestId('admin-nav-calendar').click();
  await expect(page.getByTestId('admin-calendar-page')).toBeVisible();
  await expect(page).toHaveURL(/#calendar$/);

  await page.goBack();
  await expect(page.getByTestId('admin-orders-page')).toBeVisible();
  await expect(page).toHaveURL(/#orders$/);

  await page.goBack();
  await expect(page.getByTestId('admin-dashboard-page')).toBeVisible();
  await expect(page).toHaveURL(/#dashboard$/);
});

test('dashboard recent photo thumbnails load from backend assets', async ({ page, request }) => {
  const flow = await createPhotoReviewJob(request);

  await loginAsAdmin(page);
  const thumb = page.getByTestId(`dashboard-recent-photo-thumb-${flow.photoId}`);

  await expect(thumb).toBeVisible();
  const src = await thumb.getAttribute('src');
  expect(src?.startsWith(`${backendUrl}/uploads/photos/`)).toBe(true);
  await expect.poll(async () => thumb.evaluate((node) => ({
    complete: node.complete,
    width: node.naturalWidth,
  }))).toEqual({ complete: true, width: 1 });
});

test('calendar more link opens the selected day order list', async ({ page, request }) => {
  const orders = await createCalendarDayOrders(request);

  await loginAsAdmin(page);
  await page.getByTestId('admin-nav-calendar').click();
  await expect(page.getByTestId('admin-calendar-page')).toBeVisible();

  await expect(page.getByTestId('calendar-more-20')).toBeVisible();
  await page.getByTestId('calendar-more-20').click();

  const panel = page.getByTestId('calendar-day-panel');
  await expect(panel).toContainText('2026.06.20');
  await expect(panel).toContainText('4건');
  for (const order of orders) {
    await expect(page.getByTestId(`calendar-panel-order-${order.id}`)).toBeVisible();
  }
  await expect(page.getByTestId(`calendar-panel-order-${orders[3].id}`)).toContainText('Calendar Overflow QA 4 4 | E2E QA Team');
  await expect(page.getByTestId(`calendar-panel-order-${orders[3].id}`)).toContainText(/Calendar Customer 4\s*·\s*010-3333-1033/);

  await page.getByTestId(`calendar-panel-order-${orders[3].id}`).click();
  await expect(page.getByTestId('admin-order-detail-page')).toBeVisible();
});

test('admin can filter orders by visit date with the custom date picker', async ({ page, request }) => {
  const { targetOrder, outsideOrder } = await createDateFilterOrders(request);

  await loginAsAdmin(page);
  await page.getByTestId('admin-nav-orders').click();
  await expect(page.getByTestId('admin-orders-page')).toBeVisible();
  await expect(page.getByTestId('orders-date-preset-upcoming')).toHaveAttribute('aria-pressed', 'true');
  await page.getByTestId('orders-date-preset-all').click();
  await expect(page.getByTestId(`admin-order-row-${targetOrder.id}`)).toBeVisible();
  await expect(page.getByTestId(`admin-order-row-${outsideOrder.id}`)).toBeVisible();

  await pickDate(page, 'orders-date-start', '2026-06-24');
  await pickDate(page, 'orders-date-end', '2026-06-24');

  await expect(page.getByTestId(`admin-order-row-${targetOrder.id}`)).toBeVisible();
  await expect(page.getByTestId(`admin-order-row-${outsideOrder.id}`)).toHaveCount(0);
  const summary = page.getByTestId('orders-filter-summary');
  await expect(summary).toBeVisible();
  await expect(summary).toContainText('1건');
  await expect(summary).toContainText('₩123,000');
  await expect(summary).toContainText('₩45,000');
  await expect(summary).toContainText('₩78,000');

  await page.getByTestId('orders-date-clear').click();
  await expect(page.getByTestId(`admin-order-row-${outsideOrder.id}`)).toBeVisible();
});

test('admin order search finds past fully paid customers hidden from the default queue', async ({ page, request }) => {
  const order = await createPastPaidSearchOrder(request);

  await loginAsAdmin(page);
  await page.getByTestId('admin-nav-orders').click();
  await expect(page.getByTestId('admin-orders-page')).toBeVisible();
  await expect(page.getByTestId('orders-date-preset-upcoming')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByTestId(`admin-order-row-${order.id}`)).toHaveCount(0);

  await page.getByLabel('주문 검색').fill(order.customer_name);
  await expect(page.getByTestId(`admin-order-row-${order.id}`)).toBeVisible();

  await page.getByLabel('주문 검색').fill('01090901234');
  await expect(page.getByTestId(`admin-order-row-${order.id}`)).toBeVisible();
});

test('admin order list fits the desktop viewport and exposes received-date sorting', async ({ page }) => {
  await loginAsAdmin(page);
  await page.getByTestId('admin-nav-orders').click();
  await expect(page.getByTestId('admin-orders-page')).toBeVisible();
  await expect(page.getByRole('button', { name: '접수 내림차순' })).toBeVisible();

  const width = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(width.scrollWidth).toBeLessThanOrEqual(width.clientWidth + 1);

  const tableWidth = await page.getByTestId('orders-table-scroll').evaluate((element) => ({
    scrollWidth: element.scrollWidth,
    clientWidth: element.clientWidth,
  }));
  expect(tableWidth.scrollWidth).toBeLessThanOrEqual(tableWidth.clientWidth + 1);

  const addressBefore = await page.getByTestId('orders-column-address').boundingBox();
  const customerBefore = await page.getByTestId('orders-column-customer').boundingBox();
  const addressResizer = await page.getByTestId('orders-column-resizer-address').boundingBox();
  expect(addressBefore).not.toBeNull();
  expect(customerBefore).not.toBeNull();
  expect(addressResizer).not.toBeNull();

  await page.mouse.move(addressResizer!.x + addressResizer!.width / 2, addressResizer!.y + addressResizer!.height / 2);
  await page.mouse.down();
  await page.mouse.move(addressResizer!.x - 70, addressResizer!.y + addressResizer!.height / 2);
  await page.mouse.up();

  const addressAfter = await page.getByTestId('orders-column-address').boundingBox();
  const customerAfter = await page.getByTestId('orders-column-customer').boundingBox();
  expect(addressAfter!.width).toBeLessThan(addressBefore!.width - 30);
  expect(customerAfter!.width).toBeGreaterThan(customerBefore!.width + 30);
  const resizedTableWidth = await page.getByTestId('orders-table-scroll').evaluate((element) => ({
    scrollWidth: element.scrollWidth,
    clientWidth: element.clientWidth,
  }));
  expect(resizedTableWidth.scrollWidth).toBeLessThanOrEqual(resizedTableWidth.clientWidth + 1);

  const contentInset = await page.getByTestId('orders-table-scroll').evaluate((element) => {
    const page = document.querySelector('[data-testid="admin-orders-page"]');
    if (!page) return 999;
    return element.getBoundingClientRect().left - page.getBoundingClientRect().left;
  });
  expect(contentInset).toBeLessThanOrEqual(6);

  await page.getByRole('button', { name: '접수 내림차순' }).click();
  await expect(page.getByRole('button', { name: '접수 내림차순' })).toBeVisible();
});

test('admin can page through the full order result set', async ({ page, request }) => {
  const orders = await createPaginationOrders(request);
  const lastOrder = orders[orders.length - 1];

  await loginAsAdmin(page);
  await page.getByTestId('admin-nav-orders').click();
  await expect(page.getByTestId('admin-orders-page')).toBeVisible();
  await expect(page.getByTestId('orders-date-preset-upcoming')).toHaveAttribute('aria-pressed', 'true');
  await page.getByTestId('orders-date-preset-all').click();
  await page.getByTestId('orders-pagination-page-size').selectOption('10');
  await expect(page.getByTestId('orders-pagination-next')).toBeEnabled();

  await page.getByTestId('orders-pagination-next').click();
  await expect(page.getByTestId('orders-pagination-page')).toContainText('2 /');

  await page.getByTestId('orders-pagination-page-size').selectOption('100');
  await expect(page.getByTestId(`admin-order-row-${lastOrder.id}`)).toBeVisible();
});

test('admin can run selected order bulk operations from the order list', async ({ page, request }) => {
  const orders = await createBulkActionOrders(request);

  await loginAsAdmin(page);
  await page.getByTestId('admin-nav-orders').click();
  await expect(page.getByTestId('admin-orders-page')).toBeVisible();
  await expect(page.getByTestId('orders-date-preset-upcoming')).toHaveAttribute('aria-pressed', 'true');
  await page.getByTestId('orders-date-preset-all').click();

  await selectOrderRows(page, orders);
  await page.getByTestId('orders-bulk-status-open').click();
  await page.getByTestId('orders-bulk-status-select').selectOption('상담중');
  await page.getByTestId('orders-bulk-status-apply').click();
  await expect(page.getByTestId('orders-bulk-notice')).toContainText('2건 상담중/미배정 상태로 변경했습니다.');
  await expect.poll(() => getOrderStatuses(request, orders)).toEqual(['상담중', '상담중']);

  await selectOrderRows(page, orders);
  await page.getByTestId('orders-bulk-partner-open').click();
  await page.getByTestId('orders-bulk-partner-select').selectOption(SEED_PARTNER_ID);
  await page.getByTestId('orders-bulk-partner-apply').click();
  await expect(page.getByTestId('orders-bulk-notice')).toContainText('2건');
  await expect.poll(() => getOrderPartnerIds(request, orders)).toEqual([SEED_PARTNER_ID, SEED_PARTNER_ID]);

  await selectOrderRows(page, orders);
  await page.getByTestId('orders-bulk-message-open').click();
  await page.getByTestId('orders-bulk-message-type').selectOption('customer_schedule_confirmed');
  await page.getByTestId('orders-bulk-message-apply').click();
  await expect(page.getByTestId('orders-bulk-notice')).toContainText('2건 고객 일정확정 안내를 발송했습니다.');
  await expect.poll(() => getOrderMessageTypes(request, orders)).toEqual([
    ['customer_schedule_confirmed'],
    ['customer_schedule_confirmed'],
  ]);
});

test('admin can adjust schedule from order detail and jump to related ops pages', async ({ page, request }) => {
  const order = await createDetailActionOrder(request);

  await loginAsAdmin(page);
  await page.getByTestId('admin-nav-orders').click();
  await expect(page.getByTestId('admin-orders-page')).toBeVisible();
  await expect(page.getByTestId('orders-date-preset-upcoming')).toHaveAttribute('aria-pressed', 'true');
  await page.getByTestId('orders-date-preset-all').click();
  await page.getByTestId(`admin-order-row-${order.id}`).click();
  await expect(page.getByTestId('admin-order-detail-page')).toBeVisible();

  await pickDate(page, 'detail-scheduled-date', '2026-05-06');
  await page.getByTestId('detail-requested-time').fill('16:30');
  await page.getByTestId('detail-schedule-save').click();
  await expect(page.getByTestId('admin-action-notice')).toContainText('방문 일정 변경');

  await expect.poll(async () => {
    const [detail] = await getOrderDetails(request, [order]);
    return {
      scheduledDate: detail.scheduled_date,
      requestedTime: detail.requested_time,
      hasScheduleTimeline: detail.timeline.some((event) => event.event_type === 'memo_added' && event.title === '방문 일정 변경'),
    };
  }).toEqual({
    scheduledDate: '2026-05-06',
    requestedTime: '16:30',
    hasScheduleTimeline: true,
  });

  await page.getByTestId('detail-status-select').selectOption('고객전달필요');
  await page.getByTestId('detail-status-save').click();
  await expect(page.getByTestId('admin-action-notice')).toContainText('잔금 안내를 발송했습니다');
  await expect.poll(async () => {
    const [detail] = await getOrderDetails(request, [order]);
    return {
      status: detail.status,
      messageTypes: detail.message_logs.map((message) => message.message_type),
    };
  }).toEqual({
    status: '고객전달필요',
    messageTypes: ['customer_balance_due'],
  });

  await page.getByTestId('detail-nav-calendar').click();
  await expect(page.getByTestId('admin-calendar-page')).toBeVisible();
});

test('admin can add a catalog item in product ops and use it in an order', async ({ page }) => {
  const itemName = `E2E Admin QA Item ${Date.now()}`;
  const updatedItemName = `${itemName} Updated`;
  const deleteItemName = `${itemName} Delete`;

  await loginAsAdmin(page);
  await page.getByTestId('admin-nav-products').click();
  await expect(page.getByTestId('admin-products-page')).toBeVisible();
  await expect(page.getByTestId('products-item-name')).toBeVisible();

  await page.getByTestId('products-item-name').fill(itemName);
  await page.getByTestId('products-item-base-price').fill('412000');
  await page.getByTestId('products-save-item').click();
  await expect(page.getByText(itemName)).toBeVisible();

  await page.getByRole('button', { name: `${itemName} 수정` }).click();
  await page.getByTestId('products-item-name').fill(updatedItemName);
  await page.getByTestId('products-item-base-price').fill('425000');
  await page.getByTestId('products-save-item').click();
  await expect(page.getByRole('button', { name: updatedItemName, exact: true })).toBeVisible();

  await page.getByRole('button', { name: '새 상품' }).click();
  await page.getByTestId('products-item-name').fill(deleteItemName);
  await page.getByTestId('products-item-base-price').fill('10000');
  await page.getByTestId('products-save-item').click();
  await expect(page.getByText(deleteItemName)).toBeVisible();
  page.once('dialog', async (dialog) => {
    await dialog.accept();
  });
  await page.getByRole('button', { name: `${deleteItemName} 삭제` }).click();
  await expect(page.getByText(deleteItemName)).toHaveCount(0);

  await page.getByTestId('admin-nav-orders').click();
  await page.getByTestId('admin-orders-create').click();
  await expect(page.getByTestId('admin-order-form')).toBeVisible();

  const categorySelect = page.getByTestId('order-line-0-service-category');
  const categoryValue = await categorySelect.locator('option', { hasText: '청소' }).first().getAttribute('value');
  expect(categoryValue).toBeTruthy();
  await categorySelect.selectOption(categoryValue ?? '');

  const serviceSelect = page.getByTestId('order-line-0-service-item');
  const itemValue = await serviceSelect.locator('option', { hasText: updatedItemName }).getAttribute('value');
  expect(itemValue).toBeTruthy();

  await serviceSelect.selectOption(itemValue ?? '');
  await expect(page.getByTestId('order-line-0-service-name')).toHaveValue(updatedItemName);
  await expect(page.getByTestId('order-line-0-total-amount')).toHaveValue('425,000');

  await page.getByRole('textbox', { name: '계약금' }).fill('125000');
  await expect(page.getByRole('textbox', { name: '계약금' })).toHaveValue('125,000');
  await expect(page.getByRole('textbox', { name: '잔금' })).toHaveValue('300,000');

  await page.getByTestId('order-customer-name').fill('E2E Admin Customer');
  await page.getByTestId('order-customer-phone').fill('010-4444-8899');
  await page.getByTestId('order-customer-address').fill('Seoul E2E Admin QA 1');
  await pickDate(page, 'order-line-0-scheduled-date', '2026-06-12');
  await page.getByTestId('order-line-0-requested-time').fill('10:30');
  await page.getByTestId('order-line-0-partner').selectOption(SEED_PARTNER_ID);
  await page.getByLabel('결제 상태').selectOption('deposit_paid');
  await page.getByLabel('협력사 정산 상태').selectOption('unpaid');
  await page.getByTestId('order-save').click();

  await expect(page.getByTestId('admin-order-detail-page')).toBeVisible();
  await expect(page.getByText(updatedItemName).first()).toBeVisible();
});

test('admin can edit and delete an unused partner explicitly', async ({ page }) => {
  const suffix = String(Date.now()).slice(-6);
  const categoryName = `E2E Category ${suffix}`;
  const partnerName = `E2E Partner ${suffix}`;
  const updatedPartnerName = `${partnerName} Updated`;
  const phone = `010-77${suffix.slice(0, 2)}-${suffix.slice(2)}`;

  await loginAsAdmin(page);
  await page.getByTestId('admin-nav-partners').click();
  await expect(page.getByTestId('admin-partners-page')).toBeVisible();

  await page.getByTestId('partner-category-create').click();
  await expect(page.getByTestId('partner-category-name')).toHaveValue('새 대분류');
  await page.getByTestId('partner-category-name').fill(categoryName);
  await expect(page.getByTestId('partner-category-name')).toHaveValue(categoryName);
  await page.getByTestId('partner-category-save').click();
  await expect(page.getByRole('button', { name: new RegExp(categoryName) }).first()).toBeVisible();

  await page.getByTestId('partner-create-name').fill(partnerName);
  await page.getByTestId('partner-create-category').selectOption({ label: categoryName });
  await page.getByTestId('partner-create-phone').fill(phone);
  await page.getByTestId('partner-create-submit').click();
  await expect(page.getByRole('button', { name: `${partnerName} 수정` })).toBeVisible();

  await page.getByTestId('partner-category-filter-unclassified').click();
  await expect(page.getByRole('button', { name: `${partnerName} 수정` })).toHaveCount(0);
  await page.getByRole('button', { name: new RegExp(categoryName) }).first().click();
  await expect(page.getByRole('button', { name: `${partnerName} 수정` })).toBeVisible();

  await page.getByRole('button', { name: `${partnerName} 수정` }).click();
  await expect(page.getByTestId('partner-detail-name')).toHaveValue(partnerName);
  await page.getByTestId('partner-settlement-from').click();
  const settlementDays = page.locator('[data-testid^="date-picker-day-"]');
  await expect(settlementDays.last()).toBeVisible();
  const popupBounds = await settlementDays.evaluateAll((nodes) => {
    const boxes = nodes.map((node) => node.getBoundingClientRect());
    return {
      top: Math.min(...boxes.map((box) => box.top)),
      bottom: Math.max(...boxes.map((box) => box.bottom)),
      viewportHeight: window.innerHeight,
    };
  });
  expect(popupBounds.top).toBeGreaterThanOrEqual(0);
  expect(popupBounds.bottom).toBeLessThanOrEqual(popupBounds.viewportHeight);
  await settlementDays.last().click();

  await page.getByTestId('partner-detail-name').fill(updatedPartnerName);
  await page.getByTestId('partner-save').click();
  await expect(page.getByRole('button', { name: `${updatedPartnerName} 수정` })).toBeVisible();

  await page.getByTestId('partner-detail-category').selectOption('');
  await page.getByTestId('partner-save').click();
  await page.getByTestId('partner-category-filter-unclassified').click();
  await expect(page.getByRole('button', { name: `${updatedPartnerName} 수정` })).toBeVisible();

  page.once('dialog', async (dialog) => {
    await dialog.accept();
  });
  await page.getByTestId('partner-delete').click();
  await expect(page.getByRole('button', { name: `${updatedPartnerName} 수정` })).toHaveCount(0);

  page.once('dialog', async (dialog) => {
    await dialog.accept();
  });
  await page.getByTestId('partner-category-delete').click();
  await expect(page.getByRole('button', { name: new RegExp(categoryName) })).toHaveCount(0);
});

test('admin photo review sends customer links for automatically published photos', async ({ page, request }) => {
  const { orderId, photoId } = await createPhotoReviewJob(request);

  await loginAsAdmin(page);
  await page.getByTestId('admin-nav-photos').click();
  await expect(page.getByTestId('admin-photo-review-page')).toBeVisible();
  await expect(page.getByText(orderId).first()).toBeVisible();
  await expect(page.getByTestId('photo-filter-pending_link')).toHaveAttribute('aria-pressed', 'false');
  await page.getByTestId('photo-filter-pending_link').click();
  await expect(page.getByTestId(`photo-review-item-${orderId}`)).toBeVisible();
  await page.getByTestId(`photo-review-item-${orderId}`).click();
  await expect(page.getByTestId(`photo-thumb-${photoId}`).getByText('공개')).toBeVisible();

  await page.getByTestId('photo-open-order').click();
  await expect(page.getByTestId('admin-order-detail-page')).toBeVisible();
  await page.getByTestId('admin-nav-photos').click();
  await expect(page.getByTestId('admin-photo-review-page')).toBeVisible();
  await page.getByTestId('photo-filter-pending_link').click();
  await expect(page.getByTestId(`photo-review-item-${orderId}`)).toBeVisible();
  await page.getByTestId(`photo-review-item-${orderId}`).click();
  const sendButton = page.getByTestId('photo-send-customer-link');
  await expect(sendButton).toBeEnabled();
  await sendButton.click();
  await expect(page.getByTestId('photo-send-notice')).toContainText('고객 링크를 발송');

  await expect.poll(async () => {
    const adminSession = await loginViaApi(request, 'admin');
    const response = await request.get(`${backendUrl}/api/admin/orders/${orderId}`, {
      headers: authHeaders(adminSession.access_token),
    });
    const detail = await response.json();
    return {
      status: detail.status,
      messages: detail.message_logs.length,
      timeline: detail.timeline.map((event) => event.event_type),
    };
  }).toEqual(expect.objectContaining({
    status: '고객전달필요',
    messages: 1,
    timeline: expect.arrayContaining(['photo_approved', 'message_sent', 'customer_link_sent']),
  }));

  await page.getByTestId('photo-filter-done').click();
  await expect(page.getByTestId(`photo-review-item-${orderId}`)).toBeVisible();
  await expect(sendButton).toContainText('재전송');
  await expect(sendButton).toBeEnabled();
  await page.getByTestId('photo-open-messages').click();
  await expect(page.getByTestId('admin-messages-page')).toBeVisible();
  await page.getByTestId('messages-type-customer_photo_ready').click();
  await page.getByTestId('messages-search').fill(orderId);
  await expect(page.getByTestId(`message-open-order-${orderId}`).first()).toBeVisible();
  await page.getByRole('button', { name: '재발송' }).first().click();
  await expect(page.getByTestId('messages-action-notice')).toContainText('사진 전달');
  await page.getByTestId(`message-open-order-${orderId}`).first().click();
  await expect(page.getByTestId('admin-order-detail-page')).toBeVisible();
});

async function loginAsAdmin(page) {
  await page.goto('/');
  await page.getByTestId('admin-login-identifier').fill(ADMIN_EMAIL);
  await page.getByTestId('admin-login-password').fill(ADMIN_PASSWORD);
  await page.getByTestId('admin-login-submit').click();
  await expect(page.getByTestId('admin-shell')).toBeVisible();
  await expect(page.getByTestId('admin-dashboard-page')).toBeVisible();
}

async function createPhotoReviewJob(request) {
  const adminSession = await loginViaApi(request, 'admin');
  const adminHeaders = authHeaders(adminSession.access_token);
  const created = await checkedJson(await request.post(`${backendUrl}/api/admin/orders`, {
    headers: adminHeaders,
    data: {
      status: '일정확정',
      received_date: '2026-05-05',
      scheduled_date: '2026-05-13',
      requested_time: '15:00',
      partner_id: SEED_PARTNER_ID,
      team_name: 'E2E QA Team',
      service_item_id: SEED_SERVICE_ITEM_ID,
      service_name: 'E2E Photo Review',
      customer_name: 'E2E Photo Customer',
      customer_phone: '010-5555-4455',
      customer_address: 'Seoul E2E Photo QA 1',
      customer_visible_payment: false,
    },
  }));

  const partnerSession = await loginViaApi(request, 'partner');
  const partnerHeaders = authHeaders(partnerSession.access_token);
  await checkedJson(await request.post(`${backendUrl}/api/partner/jobs/${created.id}/start`, {
    headers: partnerHeaders,
  }));
  const uploaded = await checkedJson(await request.post(`${backendUrl}/api/partner/jobs/${created.id}/photos`, {
    headers: partnerHeaders,
    multipart: {
      photo_type: 'after',
      file: {
        name: 'e2e-after.png',
        mimeType: 'image/png',
        buffer: ONE_PIXEL_PNG,
      },
    },
  }));
  await checkedJson(await request.post(`${backendUrl}/api/partner/jobs/${created.id}/complete`, {
    headers: partnerHeaders,
  }));
  return { orderId: created.id, photoId: uploaded.id };
}

async function createCalendarDayOrders(request) {
  const adminSession = await loginViaApi(request, 'admin');
  const adminHeaders = authHeaders(adminSession.access_token);
  const created = [];

  for (let index = 0; index < 4; index += 1) {
    created.push(await checkedJson(await request.post(`${backendUrl}/api/admin/orders`, {
      headers: adminHeaders,
      data: {
        received_date: '2026-05-05',
        scheduled_date: '2026-06-20',
        requested_time: `${String(9 + index).padStart(2, '0')}:00`,
        partner_id: SEED_PARTNER_ID,
        team_name: 'E2E QA Team',
        service_name: `Calendar Overflow QA ${index + 1}`,
        size_or_quantity: `${index + 1}.0`,
        customer_name: `Calendar Customer ${index + 1}`,
        customer_phone: `010-3333-10${index}${index}`,
        customer_address: `Seoul Calendar QA ${index + 1}`,
        customer_visible_payment: false,
      },
    })));
  }

  return created;
}

async function createDateFilterOrders(request) {
  const adminSession = await loginViaApi(request, 'admin');
  const adminHeaders = authHeaders(adminSession.access_token);
  const targetOrder = await checkedJson(await request.post(`${backendUrl}/api/admin/orders`, {
    headers: adminHeaders,
    data: {
      received_date: '2026-05-05',
      scheduled_date: '2026-06-24',
      requested_time: '11:00',
      service_name: 'Date Filter Target QA',
      customer_name: 'Date Filter Target',
      customer_phone: '010-7000-2100',
      customer_address: 'Seoul Date Filter Target',
      customer_visible_payment: false,
      total_amount: 123000,
      partner_payment_amount: 45000,
    },
  }));
  const outsideOrder = await checkedJson(await request.post(`${backendUrl}/api/admin/orders`, {
    headers: adminHeaders,
    data: {
      received_date: '2026-05-05',
      scheduled_date: '2026-06-25',
      requested_time: '11:00',
      service_name: 'Date Filter Outside QA',
      customer_name: 'Date Filter Outside',
      customer_phone: '010-7000-2200',
      customer_address: 'Seoul Date Filter Outside',
      customer_visible_payment: false,
      total_amount: 999000,
      partner_payment_amount: 111000,
    },
  }));

  return { targetOrder, outsideOrder };
}

async function createPastPaidSearchOrder(request) {
  const adminSession = await loginViaApi(request, 'admin');
  const adminHeaders = authHeaders(adminSession.access_token);
  const suffix = Date.now();
  return checkedJson(await request.post(`${backendUrl}/api/admin/orders`, {
    headers: adminHeaders,
    data: {
      status: '서비스완료',
      received_date: '2024-01-10',
      scheduled_date: '2024-01-15',
      requested_time: '13:00',
      service_name: 'Past Paid Search QA',
      customer_name: `Past Paid Search Customer ${suffix}`,
      customer_phone: '010-9090-1234',
      customer_address: 'Seoul Past Paid Search QA',
      customer_visible_payment: false,
      payment_status: 'paid',
      total_amount: 77000,
      partner_payment_amount: 33000,
    },
  }));
}

async function createMonthlyRevenueOrder(request) {
  const adminSession = await loginViaApi(request, 'admin');
  const adminHeaders = authHeaders(adminSession.access_token);
  const suffix = Date.now();
  return checkedJson(await request.post(`${backendUrl}/api/admin/orders`, {
    headers: adminHeaders,
    data: {
      status: '서비스완료',
      received_date: '2026-06-01',
      scheduled_date: '2026-06-01',
      requested_time: '10:00',
      service_name: 'Monthly Revenue QA',
      customer_name: `Monthly Revenue Customer ${suffix}`,
      customer_phone: '010-9191-0601',
      customer_address: 'Seoul Monthly Revenue QA',
      customer_visible_payment: false,
      payment_status: 'paid',
      total_amount: 88000,
      partner_payment_amount: 33000,
    },
  }));
}

async function createUnpaidCompletedOrder(request) {
  const adminSession = await loginViaApi(request, 'admin');
  const adminHeaders = authHeaders(adminSession.access_token);
  const suffix = Date.now();
  return checkedJson(await request.post(`${backendUrl}/api/admin/orders`, {
    headers: adminHeaders,
    data: {
      status: '서비스완료',
      received_date: '2026-06-01',
      scheduled_date: '2026-06-22',
      requested_time: '14:00',
      service_name: 'Unpaid Completed QA',
      customer_name: `Unpaid Completed Customer ${suffix}`,
      customer_phone: '010-9292-0622',
      customer_address: 'Seoul Unpaid Completed QA',
      customer_visible_payment: false,
      payment_status: 'unpaid',
      total_amount: 99000,
      partner_payment_amount: 44000,
    },
  }));
}

async function createPaginationOrders(request) {
  const adminSession = await loginViaApi(request, 'admin');
  const adminHeaders = authHeaders(adminSession.access_token);
  const created = [];

  for (let index = 0; index < 55; index += 1) {
    created.push(await checkedJson(await request.post(`${backendUrl}/api/admin/orders`, {
      headers: adminHeaders,
      data: {
        received_date: '2026-05-05',
        scheduled_date: '2026-12-31',
        requested_time: `${String(9 + index).padStart(2, '0')}:00`,
        service_name: `Pagination QA ${index + 1}`,
        customer_name: `Pagination Customer ${index + 1}`,
        customer_phone: `010-8100-${String(3000 + index)}`,
        customer_address: `Seoul Pagination QA ${index + 1}`,
        customer_visible_payment: false,
      },
    })));
  }

  return created;
}

async function createBulkActionOrders(request) {
  const adminSession = await loginViaApi(request, 'admin');
  const adminHeaders = authHeaders(adminSession.access_token);
  const created = [];

  for (let index = 0; index < 2; index += 1) {
    created.push(await checkedJson(await request.post(`${backendUrl}/api/admin/orders`, {
      headers: adminHeaders,
      data: {
        received_date: '2026-05-05',
        scheduled_date: '2026-05-05',
        requested_time: `${String(10 + index).padStart(2, '0')}:30`,
        service_name: `Bulk Action QA ${index + 1}`,
        customer_name: `Bulk Customer ${index + 1}`,
        customer_phone: `010-8000-24${index}${index}`,
        customer_address: `Seoul Bulk QA ${index + 1}`,
        customer_visible_payment: false,
      },
    })));
  }

  return created;
}

async function createDetailActionOrder(request) {
  const adminSession = await loginViaApi(request, 'admin');
  const adminHeaders = authHeaders(adminSession.access_token);
  return checkedJson(await request.post(`${backendUrl}/api/admin/orders`, {
    headers: adminHeaders,
    data: {
      received_date: '2026-05-05',
      scheduled_date: '2026-05-05',
      requested_time: '09:00',
      service_name: 'Detail Schedule QA',
      customer_name: 'Detail Schedule Customer',
      customer_phone: '010-9000-0505',
      customer_address: 'Seoul Detail Schedule QA',
      customer_visible_payment: false,
    },
  }));
}

async function pickDate(page, pickerTestId, dateValue) {
  await page.getByTestId(pickerTestId).click();
  await page.getByTestId(`date-picker-day-${dateValue}`).click();
}

async function selectOrderRows(page, orders) {
  for (const order of orders) {
    const checkbox = page.getByTestId(`admin-order-row-${order.id}`).locator('input[type="checkbox"]');
    await expect(checkbox).toBeVisible();
    await checkbox.check();
  }
}

async function getOrderStatuses(request, orders) {
  const details = await getOrderDetails(request, orders);
  return details.map((detail) => detail.status);
}

async function getOrderPartnerIds(request, orders) {
  const details = await getOrderDetails(request, orders);
  return details.map((detail) => detail.partner_id);
}

async function getOrderMessageTypes(request, orders) {
  const details = await getOrderDetails(request, orders);
  return details.map((detail) => detail.message_logs.map((message) => message.message_type));
}

async function getOrderDetails(request, orders) {
  const adminSession = await loginViaApi(request, 'admin');
  const adminHeaders = authHeaders(adminSession.access_token);
  const details = [];
  for (const order of orders) {
    details.push(await checkedJson(await request.get(`${backendUrl}/api/admin/orders/${order.id}`, {
      headers: adminHeaders,
    })));
  }
  return details;
}

async function loginViaApi(request, role) {
  const endpoint = role === 'admin' ? 'admin/login' : 'partner/login';
  const identifier = role === 'admin' ? ADMIN_EMAIL : PARTNER_PHONE;
  const password = role === 'admin' ? ADMIN_PASSWORD : PARTNER_PASSWORD;
  return checkedJson(await request.post(`${backendUrl}/api/auth/${endpoint}`, {
    data: { identifier, password },
  }));
}

async function checkedJson(response) {
  expect(response.ok(), await response.text()).toBe(true);
  return response.json();
}

function authHeaders(accessToken) {
  return {
    Authorization: `Bearer ${accessToken}`,
  };
}
