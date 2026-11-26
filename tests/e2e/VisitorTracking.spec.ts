import { expect, test } from '@playwright/test';

test('匿名首次打开登录页只记录一次正确的页面浏览', async ({ page }) => {
  const events: Array<{ page: string; event: string }> = [];
  page.on('request', request => {
    if (request.url().endsWith('/api/v1/visits') && request.method() === 'POST') {
      events.push(request.postDataJSON() as { page: string; event: string });
    }
  });

  const authResponse = page.waitForResponse(response => response.url().endsWith('/api/v1/auth/me'));
  const loginVisitResponse = page.waitForResponse(response => response.url().endsWith('/api/v1/visits') &&
    response.request().postDataJSON().page === '/login');
  await page.goto(process.env.E2E_BASE_URL!);
  await expect(page.getByTestId('login-email')).toBeVisible();
  await authResponse;
  await loginVisitResponse;

  expect(events).toEqual([{ page: '/login', event: 'pageview' }]);
});
