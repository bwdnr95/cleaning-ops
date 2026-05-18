import { expect, test } from '@playwright/test';

import { adminLogin, createAssignedOrder, openAdminPhotoReview, partnerUploadPhoto } from './helpers';

test('관리자가 사진 링크를 재전송할 수 있다', async ({ browser, page, request }) => {
  const flow = await createAssignedOrder(request);
  await partnerUploadPhoto(browser, { orderId: flow.orderId, photoType: 'after' });
  await adminLogin(page);
  await openAdminPhotoReview(page, flow.orderId);

  const sendButton = page.getByTestId('photo-send-customer-link');
  await expect(sendButton).toContainText('고객 사진 링크 발송');
  await sendButton.click();
  await expect(page.getByTestId('photo-send-notice')).toContainText('고객 링크를 발송');

  await expect(sendButton).toContainText('재전송');
  await sendButton.click();
  await expect(page.getByTestId('photo-send-notice')).toContainText('고객 링크를 발송');
});

test('관리자가 사진을 비공개로 되돌릴 수 있다', async ({ browser, page, request }) => {
  const flow = await createAssignedOrder(request);
  await partnerUploadPhoto(browser, { orderId: flow.orderId, photoType: 'after' });
  await adminLogin(page);
  await openAdminPhotoReview(page, flow.orderId);

  const thumbs = page.locator('[data-testid^="photo-thumb-"]');
  await thumbs.first().click();
  await page.getByTestId('photo-revoke-selected').click();
  await expect(thumbs.first().getByText('비공개')).toBeVisible();
});
