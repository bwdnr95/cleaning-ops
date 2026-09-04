import { expect, test, type Page } from '@playwright/test';
import { join } from 'node:path';

import { adminLogin, createAssignedOrder } from './helpers';
import { getAppTodayValue } from '../src/domain/time';

const SEED_PARTNER_ID = 'seed-partner-01';
const TEST_BROKER_ID = 'route-state-broker';
const SEARCH_QUERY = 'R6 Photo Review';

test('orders search control uses the expanded desktop and mobile dimensions', async ({ page }) => {
  await adminLogin(page);
  await page.getByTestId('admin-nav-orders').click();

  const searchInput = page.getByRole('textbox', { name: '주문 검색' });
  const searchContainer = searchInput.locator('..');
  await expect(searchInput).toBeVisible();
  await expect(searchContainer).toHaveCSS('height', '40px');
  await expect(searchContainer).toHaveCSS('min-width', '380px');
  await expect(searchInput).toHaveCSS('font-size', '14px');
  await captureEvidence(page, 'orders-search-desktop.png');

  await page.setViewportSize({ width: 375, height: 812 });
  await expect(searchInput).toHaveCSS('font-size', '16px');
  const widths = await searchContainer.evaluate((element) => {
    const toolbar = element.parentElement;
    return {
      search: element.getBoundingClientRect().width,
      toolbar: toolbar?.getBoundingClientRect().width ?? 0,
      toolbarPadding: toolbar
        ? Number.parseFloat(getComputedStyle(toolbar).paddingLeft)
          + Number.parseFloat(getComputedStyle(toolbar).paddingRight)
        : 0,
    };
  });
  expect(widths.search).toBe(widths.toolbar - widths.toolbarPadding);
  await captureEvidence(page, 'orders-search-mobile.png');
});

test('orders restores search filters custom visit range and page two after browser back', async ({ page, request }) => {
  const flow = await createAssignedOrder(request);
  const today = getAppTodayValue();
  let cachedPayload: Record<string, unknown> | null = null;
  let cachedOrder: Record<string, unknown> | null = null;

  await adminLogin(page);
  await page.route('**/api/admin/brokers*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([{
        id: TEST_BROKER_ID,
        name: '뒤로가기 중개사',
        manager_name: null,
        phone: null,
        manager_phone: null,
        memo: null,
        is_active: true,
        order_count: 1,
        unpaid_broker_amount_total: 0,
        unpaid_broker_order_count: 0,
      }]),
    });
  });
  await page.route(/\/api\/admin\/orders\/page\?/, async (route) => {
    const requestUrl = new URL(route.request().url());
    if (cachedPayload && cachedOrder) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ...cachedPayload,
          items: [cachedOrder],
          total: 101,
          page: Number(requestUrl.searchParams.get('page') ?? '1'),
          page_size: Number(requestUrl.searchParams.get('page_size') ?? '50'),
        }),
      });
      return;
    }

    const response = await route.fetch();
    const payload = await response.json();
    const order = payload.items.find((item) => item.id === flow.orderId);
    if (order) {
      cachedPayload = payload;
      cachedOrder = { ...order, broker_id: TEST_BROKER_ID };
    }
    await route.fulfill({ response, json: payload });
  });

  await page.getByTestId('admin-nav-orders').click();
  await expect(page).toHaveURL(/#orders$/);
  await expect(page.getByTestId(`admin-order-row-${flow.orderId}`)).toBeVisible();

  const searchInput = page.getByRole('textbox', { name: '주문 검색' });
  await searchInput.fill(SEARCH_QUERY);
  expect(await hashParam(page, 'q')).toBeNull();
  await expect.poll(() => hashParam(page, 'q')).toBe(SEARCH_QUERY);

  await page.getByTestId('orders-partner-filter').click();
  await page.getByTestId(`orders-partner-option-${SEED_PARTNER_ID}`).click();
  await page.getByTestId('orders-broker-filter').click();
  await page.getByTestId(`orders-broker-option-${TEST_BROKER_ID}`).click();
  await page.getByTestId('orders-received-preset-today').click();
  await page.getByRole('button', { name: '접수 내림차순' }).click();
  await page.getByTestId('orders-pagination-page-size').selectOption('100');

  await page.getByTestId('orders-date-start').click();
  await page.getByTestId(`date-picker-day-${today}`).click();
  await page.getByTestId('orders-date-end').click();
  await page.getByTestId(`date-picker-day-${today}`).click();

  await expect(page.getByTestId('orders-pagination-next')).toBeEnabled();
  await page.getByTestId('orders-pagination-next').click();
  await expect(page.getByTestId('orders-pagination-page')).toHaveText('2 / 2');
  await expect.poll(() => currentOrdersView(page)).toEqual({
    q: SEARCH_QUERY,
    partnerId: SEED_PARTNER_ID,
    brokerId: TEST_BROKER_ID,
    page: '2',
    visitFrom: today,
    visitTo: today,
    received: 'today',
    receivedFrom: today,
    receivedTo: today,
    sort: 'received_desc',
    pageSize: '100',
  });

  await page.getByTestId(`admin-order-row-${flow.orderId}`).click();
  await expect(page.getByTestId('admin-order-detail-page')).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`#orders/${flow.orderId}\\?`));

  const restoredRequest = page.waitForRequest((observed) => {
    const url = new URL(observed.url());
    return url.pathname.endsWith('/api/admin/orders/page')
      && url.searchParams.get('page') === '2'
      && url.searchParams.get('q') === SEARCH_QUERY
      && url.searchParams.get('received_preset') === 'today'
      && url.searchParams.get('sort') === 'received_desc'
      && url.searchParams.get('page_size') === '100';
  });
  await page.goBack();
  await restoredRequest;

  await expect(page.getByTestId('admin-orders-page')).toBeVisible();
  await expect(searchInput).toHaveValue(SEARCH_QUERY);
  await expect(page.getByTestId('orders-partner-filter')).toContainText('클린파트너 강남');
  await expect(page.getByTestId('orders-broker-filter')).toContainText('뒤로가기 중개사');
  await expect(page.getByTestId('orders-date-start')).toContainText(today.replaceAll('-', '.'));
  await expect(page.getByTestId('orders-date-end')).toContainText(today.replaceAll('-', '.'));
  await expect(page.getByTestId('orders-received-preset-today')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByTestId('orders-pagination-page-size')).toHaveValue('100');
  await expect(page.getByTestId('orders-pagination-page')).toHaveText('2 / 2');
  await expect.poll(() => currentOrdersView(page)).toEqual({
    q: SEARCH_QUERY,
    partnerId: SEED_PARTNER_ID,
    brokerId: TEST_BROKER_ID,
    page: '2',
    visitFrom: today,
    visitTo: today,
    received: 'today',
    receivedFrom: today,
    receivedTo: today,
    sort: 'received_desc',
    pageSize: '100',
  });
  await captureEvidence(page, 'orders-route-restored.png');
});

test('active orders navigation resets the mounted list to the default view', async ({ page }) => {
  await adminLogin(page);
  await page.getByTestId('admin-nav-orders').click();
  const searchInput = page.getByRole('textbox', { name: '주문 검색' });
  await searchInput.fill(SEARCH_QUERY);
  await expect.poll(() => hashParam(page, 'q')).toBe(SEARCH_QUERY);
  await page.getByTestId('orders-received-preset-today').click();
  await page.getByRole('button', { name: '접수 내림차순' }).click();
  await page.getByTestId('orders-pagination-page-size').selectOption('100');

  await page.getByTestId('admin-nav-orders').click();

  await expect(page).toHaveURL(/#orders$/);
  await expect(searchInput).toHaveValue('');
  await expect(page.getByTestId('orders-received-preset-all')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByTestId('orders-pagination-page-size')).toHaveValue('50');
  await expect.poll(() => currentOrdersView(page)).toEqual({
    q: null,
    partnerId: null,
    brokerId: null,
    page: null,
    visitFrom: null,
    visitTo: null,
    received: null,
    receivedFrom: null,
    receivedTo: null,
    sort: null,
    pageSize: null,
  });
});

test('shell create order returns to the current filtered orders view on cancel', async ({ page }) => {
  await adminLogin(page);
  await page.getByTestId('admin-nav-orders').click();
  const searchInput = page.getByRole('textbox', { name: '주문 검색' });
  await searchInput.fill(SEARCH_QUERY);
  await expect.poll(() => hashParam(page, 'q')).toBe(SEARCH_QUERY);
  await page.getByTestId('orders-received-preset-today').click();
  await expect.poll(() => hashParam(page, 'received')).toBe('today');

  await page.getByTestId('admin-nav-create-order').click();

  await expect(page).toHaveURL(/#orders\/new\?/);
  await expect.poll(() => currentOrdersView(page)).toMatchObject({
    q: SEARCH_QUERY,
    received: 'today',
  });

  await page.getByRole('button', { name: '취소', exact: true }).click();

  await expect(page).toHaveURL(/#orders\?/);
  await expect(searchInput).toHaveValue(SEARCH_QUERY);
  await expect(page.getByTestId('orders-received-preset-today')).toHaveAttribute('aria-pressed', 'true');
  await expect.poll(() => currentOrdersView(page)).toMatchObject({
    q: SEARCH_QUERY,
    received: 'today',
  });
});

async function captureEvidence(page: Page, filename: string): Promise<void> {
  const evidenceDir = process.env.CUSTOMER_FIX_EVIDENCE_DIR;
  if (!evidenceDir) {
    return;
  }
  await page.screenshot({ path: join(evidenceDir, filename), fullPage: true });
}

async function hashParam(page: Page, key: string): Promise<string | null> {
  return page.evaluate((paramKey) => {
    const queryString = window.location.hash.split('?')[1] ?? '';
    return new URLSearchParams(queryString).get(paramKey);
  }, key);
}

async function currentOrdersView(page: Page): Promise<{
  readonly q: string | null;
  readonly partnerId: string | null;
  readonly brokerId: string | null;
  readonly page: string | null;
  readonly visitFrom: string | null;
  readonly visitTo: string | null;
  readonly received: string | null;
  readonly receivedFrom: string | null;
  readonly receivedTo: string | null;
  readonly sort: string | null;
  readonly pageSize: string | null;
}> {
  return {
    q: await hashParam(page, 'q'),
    partnerId: await hashParam(page, 'partner_id'),
    brokerId: await hashParam(page, 'broker_id'),
    page: await hashParam(page, 'page'),
    visitFrom: await hashParam(page, 'visit_from'),
    visitTo: await hashParam(page, 'visit_to'),
    received: await hashParam(page, 'received'),
    receivedFrom: await hashParam(page, 'received_from'),
    receivedTo: await hashParam(page, 'received_to'),
    sort: await hashParam(page, 'sort'),
    pageSize: await hashParam(page, 'page_size'),
  };
}
