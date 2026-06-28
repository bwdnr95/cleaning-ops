import { expect, test, type Page } from '@playwright/test';

const ADMIN_EMAIL = 'admin@cleanops.kr';
const ADMIN_PASSWORD = 'AdminPass123!';

// 월 합산 청구·정산 탭 진입 스모크.
// (데이터 의존 집계/일괄 액션 단언은 백엔드 서비스 테스트가 담당 — 여기선 탭/뷰 렌더만 확인.)
test('정기청소 > 월 정산 탭에 진입하면 청구 월 피커가 보인다', async ({ page }) => {
  await loginAsAdmin(page);

  // 정기청소 영역 진입
  await page.getByTestId('admin-nav-recurring').click();
  await expect(page.getByTestId('admin-recurring-page')).toBeVisible();

  // 월 정산 탭 전환 → 청구 월 피커 + CSV 내보내기 노출
  await page.getByTestId('recurring-tab-billing').click();
  await expect(page.getByTestId('billing-month')).toBeVisible();
  await expect(page.getByTestId('billing-export')).toBeVisible();

  // 계약 탭으로 되돌아오면 등록 버튼이 다시 보인다(탭 토글 확인).
  await page.getByTestId('recurring-tab-contracts').click();
  await expect(page.getByTestId('recurring-create')).toBeVisible();
});

async function loginAsAdmin(page: Page) {
  await page.goto('/');
  await page.getByTestId('admin-login-identifier').fill(ADMIN_EMAIL);
  await page.getByTestId('admin-login-password').fill(ADMIN_PASSWORD);
  await page.getByTestId('admin-login-submit').click();
  await expect(page.getByTestId('admin-shell')).toBeVisible();
  await expect(page.getByTestId('admin-dashboard-page')).toBeVisible();
}
