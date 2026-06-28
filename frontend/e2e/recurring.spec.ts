import { expect, test, type Page } from '@playwright/test';

const ADMIN_EMAIL = 'admin@cleanops.kr';
const ADMIN_PASSWORD = 'AdminPass123!';

// 백엔드는 business_today()(KST, UTC+9)로 도래분을 계산한다. 러너의 로컬 타임존과
// 무관하게 KST 벽시계 날짜를 구해 백엔드 sync 윈도([오늘-30, 오늘+14])와 일치시킨다.
function kstToday(): { iso: string; day: number } {
  const kst = new Date(Date.now() + 9 * 60 * 60 * 1000);
  const year = kst.getUTCFullYear();
  const month = kst.getUTCMonth() + 1;
  const day = kst.getUTCDate();
  const iso = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
  return { iso, day };
}

test('정기계약 생성 → 승인 대기 회차 → 승인하면 정기 주문이 생성된다', async ({ page }) => {
  // 시작일=오늘(KST), 지정일=오늘 일자 → sync 시 정확히 1건(오늘 회차)이 도래한다.
  // (다음 달 같은 날짜는 today+14 호라이즌을 넘어 제외되므로 도래분은 항상 1건.)
  const { iso: startDate, day } = kstToday();
  const stamp = Date.now();
  const label = `E2E 정기계약 ${stamp}`;
  const customerName = `E2E 정기고객 ${stamp}`;
  const serviceName = `E2E 정기청소 ${stamp}`;

  await loginAsAdmin(page);

  // 1) 정기청소 탭 진입
  await page.getByTestId('admin-nav-recurring').click();
  await expect(page.getByTestId('admin-recurring-page')).toBeVisible();

  // 2) 정기계약 등록 폼 작성 (기본 모드 monthly)
  await page.getByTestId('recurring-create').click();
  await page.getByTestId('rc-label').fill(label);
  await page.getByTestId('rc-customer-name').fill(customerName);
  await page.getByTestId('rc-customer-phone').fill('01099998888');
  await page.getByTestId('rc-customer-address').fill('서울 강남구 E2E로 1');
  await page.getByTestId('rc-day-of-month').fill(String(day));
  await page.getByTestId('rc-start-date').fill(startDate);
  await page.getByTestId('rc-service-name').fill(serviceName);
  await page.getByTestId('rc-amount').fill('100000');
  await page.getByTestId('rc-submit').click();

  // 3) 목록 복귀 → 진입 시 sync가 돌아 승인 대기 패널에 도래분 1건이 보인다.
  await expect(page.getByTestId('admin-recurring-page')).toBeVisible();
  await expect(page.getByRole('heading', { name: /승인 대기 회차/ })).toBeVisible();
  const pendingRows = page.locator('[data-testid^="pending-"]');
  await expect(pendingRows).toHaveCount(1);
  await expect(pendingRows).toContainText(customerName);

  // 4) 선택 승인 → 주문 생성. 승인 후 도래분이 비워진다(GENERATED는 list_pending에서 제외).
  await page.getByTestId('recurring-approve').click();
  await expect(page.getByText('도래한 회차가 없습니다.')).toBeVisible();

  // 5) 주문관리에서 생성된 정기 주문을 찾아 '정기' 배지를 확인한다.
  //    (방문일=오늘이라 기본 필터 밖일 수 있어 preset=전체 + 고유 고객명 검색으로 좁힌다.)
  await page.getByTestId('admin-nav-orders').click();
  await expect(page.getByTestId('admin-orders-page')).toBeVisible();
  await page.getByTestId('orders-date-preset-all').click();
  await page.getByLabel('주문 검색').fill(customerName);

  const orderRows = page.locator('[data-testid^="admin-order-row-"]');
  await expect(orderRows).toHaveCount(1);
  // 목록 행에 '정기' 배지가 노출된다.
  await expect(page.getByTestId('order-row-recurring-badge')).toBeVisible();
  await orderRows.click();
  await expect(page.getByTestId('admin-order-detail-page')).toBeVisible();
  await expect(page.getByTestId('order-recurring-badge')).toBeVisible();

  // 6) '정기' 배지를 눌러 계약으로 역링크 → 계약 상세의 회차 원장에서 승인된 회차(생성)를 확인.
  await page.getByTestId('order-recurring-badge').click();
  await expect(page.getByTestId('rc-detail-label')).toHaveText(label);
  const ledger = page.getByTestId('rc-occurrence-ledger');
  await expect(ledger).toBeVisible();
  await expect(ledger.getByText('생성', { exact: true })).toBeVisible();
});

async function loginAsAdmin(page: Page) {
  await page.goto('/');
  await page.getByTestId('admin-login-identifier').fill(ADMIN_EMAIL);
  await page.getByTestId('admin-login-password').fill(ADMIN_PASSWORD);
  await page.getByTestId('admin-login-submit').click();
  await expect(page.getByTestId('admin-shell')).toBeVisible();
  await expect(page.getByTestId('admin-dashboard-page')).toBeVisible();
}
