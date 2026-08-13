import { expect, test } from '@playwright/test';
import { createAssignedOrder, partnerLogin } from './helpers';

// 협력사 페이지 신규 기능 검증: 작업 메모, 운영팀 안내 패널, 정기 배지, 하단 네비/내 정보(로그아웃).
// 핵심 작업 플로우(시작→사진→완료)는 partner-customer-e2e.spec.ts가 이미 덮는다.

test('협력사가 작업 메모를 남기면 목록에 보이고 운영팀 안내 패널이 뜬다', async ({ browser, request }) => {
  const flow = await createAssignedOrder(request);

  const context = await browser.newContext();
  const page = await context.newPage();
  try {
    await partnerLogin(page);
    await page.getByTestId(`partner-job-row-${flow.orderId}`).click();
    await expect(page.getByTestId('partner-job-detail-page')).toBeVisible();

    const backButton = page.getByRole('button', { name: '작업 목록으로 돌아가기' });
    await expect(backButton).toBeVisible();
    const backButtonBox = await backButton.boundingBox();
    expect(backButtonBox?.width ?? 0).toBeGreaterThanOrEqual(44);
    expect(backButtonBox?.height ?? 0).toBeGreaterThanOrEqual(44);

    // 단발 주문이므로 정기 배지는 없어야 한다(정기 노출은 boolean is_recurring로만 제어).
    await expect(page.getByTestId('partner-recurring-badge')).toHaveCount(0);

    // 작업 메모 저장 → 메모 아이템으로 다시 노출(새로고침 후에도 유지되는 타임라인 기반).
    const memoText = `현장 메모 ${Date.now()}: 공동현관 비번 1234#`;
    await page.getByTestId('partner-memo-input').fill(memoText);
    await page.getByTestId('partner-memo-save').click();
    await expect(page.getByTestId('partner-memo-item').filter({ hasText: memoText })).toBeVisible();

    // 새로고침 후에도 메모가 유지되는지(저장이 서버에 반영됐는지) 확인.
    await page.reload();
    await page.getByTestId(`partner-job-row-${flow.orderId}`).click();
    await expect(page.getByTestId('partner-memo-item').filter({ hasText: memoText })).toBeVisible();

    // 운영팀 안내 패널이 정상 로드(에러 아님). 안내 발송 전이라 빈 상태 문구를 노출한다.
    const messagesPanel = page.getByTestId('partner-messages-panel');
    await expect(messagesPanel).toBeVisible();
    await expect(messagesPanel).toContainText('작업 배정 안내');
  } finally {
    await context.close();
  }
});

test('협력사 하단 네비로 내 정보 탭과 로그아웃에 접근할 수 있다', async ({ browser }) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  try {
    await partnerLogin(page);

    // 목록 화면에서는 하단 네비가 보인다.
    await expect(page.getByTestId('partner-nav-jobs')).toBeVisible();
    await page.getByTestId('partner-nav-account').click();

    await expect(page.getByTestId('partner-account-page')).toBeVisible();
    await expect(page.getByTestId('partner-current-password')).toBeVisible();
    await expect(page.getByTestId('partner-new-password')).toBeVisible();
    await expect(page.getByTestId('partner-logout')).toBeVisible();

    // 로그아웃하면 협력사 로그인 화면으로 돌아간다.
    await page.getByTestId('partner-logout').click();
    await expect(page.getByTestId('partner-login-submit')).toBeVisible();
  } finally {
    await context.close();
  }
});
