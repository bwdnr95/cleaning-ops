import { expect, test } from '@playwright/test';
import { adminLogin, partnerLogin } from './helpers';

test('관리자는 사이드바에서 텍스트 로그아웃 버튼을 눌러 로그인 화면으로 돌아간다', async ({ browser }) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  try {
    await adminLogin(page);

    const logoutButton = page.getByTestId('admin-logout');
    await expect(logoutButton).toBeVisible();
    await expect(logoutButton).toContainText('로그아웃');

    await logoutButton.click();
    await expect(page.getByTestId('admin-login-submit')).toBeVisible();
  } finally {
    await context.close();
  }
});

test('협력사는 상단바 로그아웃 버튼을 눌러 협력사 로그인 화면으로 돌아간다', async ({ browser }) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  try {
    await partnerLogin(page);

    const logoutButton = page.getByTestId('partner-topbar-logout');
    await expect(logoutButton).toBeVisible();
    await expect(logoutButton).toContainText('로그아웃');

    await logoutButton.click();
    await expect(page.getByTestId('partner-login-submit')).toBeVisible();
  } finally {
    await context.close();
  }
});
