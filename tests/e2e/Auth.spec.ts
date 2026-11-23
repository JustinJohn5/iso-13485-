import { expect, test } from '@playwright/test';
import { login, watchPage } from './Helpers';

test('专用测试账号可登录并退出', async ({ page }) => {
  const verify = watchPage(page);
  await login(page);
  const logout = page.waitForResponse((response) => response.url().endsWith('/api/v1/auth/logout'));
  await page.getByTestId('logout').click();
  expect((await logout).status()).toBe(200);
  await expect(page.getByTestId('login-form')).toBeVisible();
  await verify();
});
