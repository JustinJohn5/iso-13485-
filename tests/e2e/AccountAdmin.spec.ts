import { test, expect } from '@playwright/test';
import { login, watchPage } from './Helpers';

test('账户入口、个人文件和分组页面可用且可通过键盘关闭菜单', async ({ page }) => {
  await login(page);
  const verify = watchPage(page);
  await expect(page.getByTestId('account-menu-button')).toBeVisible();
  await page.getByTestId('account-menu-button').click();
  await expect(page.getByTestId('account-menu')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByTestId('account-menu')).toHaveCount(0);
  await page.getByTestId('account-menu-button').click();
  await page.locator('.breadcrumb').click();
  await expect(page.getByTestId('account-menu')).toHaveCount(0);
  await page.setViewportSize({ width: 320, height: 740 });
  await page.getByTestId('account-menu-button').click();
  const menuBounds = await page.getByTestId('account-menu').boundingBox();
  expect(menuBounds).toBeTruthy();
  expect(menuBounds!.x).toBeGreaterThanOrEqual(0);
  expect(menuBounds!.x + menuBounds!.width).toBeLessThanOrEqual(320);
  await page.locator('.breadcrumb').click();
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.getByTestId('account-menu-button').click();
  await page.getByTestId('account-files').click();
  await expect(page.getByTestId('personal-files-page')).toBeVisible();
  await expect(page.getByTestId('file-search')).toBeVisible();
  await page.getByTestId('personal-files-back').click();
  await page.getByTestId('account-menu-button').click();
  await page.getByTestId('account-groups').click();
  await expect(page.getByTestId('file-groups-page')).toBeVisible();
  const groupName = `AccountAdmin-${Date.now()}`;
  await page.getByTestId('group-name').fill(groupName);
  const creating = page.waitForResponse(response => response.url().endsWith('/api/v1/my/file-groups') && response.request().method() === 'POST');
  await page.getByTestId('group-create').click();
  const created = await creating;
  const createdText = await created.text();
  expect(created.status(), `${createdText}; request=${created.request().postData()}`).toBe(200);
  const createdData = JSON.parse(createdText).data;
  await page.request.delete(`${process.env.E2E_API_BASE_URL}/api/v1/my/file-groups/${createdData.group_uid}`);
  await verify();
});

test('后台模型配置保留返回后台导航，管理员后台页面能加载', async ({ page }) => {
  await login(page);
  await expect(page.getByTestId('account-menu-button')).toBeVisible();
  await page.getByTestId('account-menu-button').click();
  await page.getByTestId('account-admin').click();
  await expect(page).toHaveURL(/\/admin\//);
  await expect(page.getByTestId('admin-workspace')).toBeVisible();
  await page.getByTestId('admin-nav-models').click();
  await expect(page.getByTestId('llm-settings-form')).toBeVisible();
  await page.getByTestId('settings-back').click();
  await expect(page.getByTestId('admin-workspace')).toBeVisible();
});

test('后台展示访客最近活跃时间并能读取服务日志和操作记录', async ({ page }) => {
  const verify = watchPage(page);
  await login(page);
  await page.getByTestId('account-menu-button').click();
  await page.getByTestId('account-admin').click();
  await expect(page.getByText('当前在线访客')).toBeVisible();
  await expect(page.getByText('在线用户')).toBeVisible();
  await expect(page.getByText('今日访客')).toBeVisible();
  await expect(page.getByText('今日浏览')).toBeVisible();

  const visitors = page.waitForResponse(response => response.url().includes('/api/v1/admin/visitors'));
  await page.getByTestId('admin-nav-visitors').click();
  expect((await visitors).status()).toBe(200);
  await expect(page.locator('.admin-table')).toContainText('最近活跃时间');
  await expect(page.locator('.admin-table')).toContainText(/登录用户|匿名访客/);

  const logs = page.waitForResponse(response => response.url().includes('/api/v1/admin/logs?'));
  await page.getByTestId('admin-nav-logs').click();
  expect((await logs).status()).toBe(200);
  const filteredLogs = page.waitForResponse(response => response.url().includes('/api/v1/admin/logs?') &&
    new URL(response.url()).searchParams.has('source'));
  await page.getByTestId('admin-log-filters').getByRole('button', { name: '筛选' }).click();
  expect((await filteredLogs).status()).toBe(200);

  const audits = page.waitForResponse(response => response.url().includes('/api/v1/admin/audit-logs'));
  await page.getByTestId('admin-nav-audit').click();
  expect((await audits).status()).toBe(200);
  await expect(page.getByRole('heading', { name: '操作记录' })).toBeVisible();
  await verify();
});
