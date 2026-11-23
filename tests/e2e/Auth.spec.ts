import { expect, test } from '@playwright/test';

test('登录后可添加文件并查看规则预筛结果', async ({ page }) => {
  const baseUrl = process.env.E2E_BASE_URL;
  const email = process.env.E2E_EMAIL;
  const password = process.env.E2E_PASSWORD;
  test.skip(!baseUrl || !email || !password, '需要配置隔离的 E2E 服务与专用测试账号');

  const pageErrors: string[] = [];
  const consoleErrors: string[] = [];
  const unexpectedResponses: string[] = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  page.on('response', (response) => {
    const isExpectedLoggedOutCheck = response.url().endsWith('/api/v1/auth/me') && response.status() === 401;
    if (response.url().includes('/api/v1/') && response.status() >= 400 && !isExpectedLoggedOutCheck) {
      unexpectedResponses.push(`${response.status()} ${response.url()}`);
    }
  });
  await page.goto(baseUrl!);
  await page.getByTestId('login-email').fill(email!);
  await page.getByTestId('login-password').fill(password!);
  await page.getByTestId('login-submit').click();
  await expect(page.getByRole('heading', { name: '文件预筛' })).toBeVisible();

  await page.getByTestId('upload-files').setInputFiles({
    name: '质量手册.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('文件编号：QMS-001\n版本号：A\n批准：质量负责人\n生效日期：2026-11-01\n质量管理体系范围包括医疗器械产品的设计与生产。'.repeat(3)),
  });
  await page.getByTestId('analyze-button').click();
  await expect(page.getByTestId('results-title')).toBeVisible();
  await expect(page.getByText('DOC-001')).toBeVisible();
  await expect(page.getByText('QMS-001')).toBeVisible();
  await expect(page.getByText('预筛结果仅用于内部文件检查', { exact: false })).toBeVisible();
  expect(pageErrors).toEqual([]);
  expect(consoleErrors).toEqual([]);
  expect(unexpectedResponses).toEqual([]);
});
