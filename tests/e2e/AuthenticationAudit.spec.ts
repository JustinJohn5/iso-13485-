import { expect, test } from '@playwright/test';
import { login, watchPage } from './Helpers';

test('成功登录与登出会记录操作者及操作', async ({ page }) => {
  const assertNoErrors = watchPage(page);
  await login(page);
  const base = process.env.E2E_API_BASE_URL!;
  const identity = (await (await page.request.get(`${base}/api/v1/auth/me`)).json()).data;
  const loginHistory = await page.request.get(`${base}/api/v1/admin/audit-logs?page_size=100`);
  expect(loginHistory.status()).toBe(200);
  const loginEntries = (await loginHistory.json()).data.items;
  expect(loginEntries).toContainEqual(expect.objectContaining({
    actor: '自动化测试账号', action: 'user_login', target_id: String(identity.id), detail: '账号登录成功',
  }));

  await page.getByTestId('logout').click();
  await expect(page.getByTestId('login-form')).toBeVisible();
  await login(page);
  const logoutHistory = await page.request.get(`${base}/api/v1/admin/audit-logs?page_size=100`);
  expect(logoutHistory.status()).toBe(200);
  const logoutEntries = (await logoutHistory.json()).data.items;
  expect(logoutEntries).toContainEqual(expect.objectContaining({
    actor: '自动化测试账号', action: 'user_logout', target_id: String(identity.id), detail: '账号退出登录成功',
  }));
  await assertNoErrors();
});
