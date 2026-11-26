import { expect, test, type Page } from '@playwright/test';
import { analyze, login, textFile, watchPage } from './Helpers';

async function configure(page: Page, enabled: boolean): Promise<void> {
  const response = await page.request.patch(`${process.env.E2E_API_BASE_URL}/api/v1/llm-settings`, {
    data: { enabled, base_url: process.env.E2E_LLM_BASE_URL, model: 'e2e-review',
      api_key: 'synthetic-test-key', timeout_seconds: 10, max_tokens: 1200, temperature: 0 },
  });
  expect(response.status()).toBe(200);
}

async function prepare(page: Page, enabled: boolean) {
  await login(page);
  await configure(page, enabled);
  await page.getByTestId('upload-files').setInputFiles(textFile('恢复测试质量手册.txt',
    '质量手册\n文件编号：QM-78\n版本：01\n批准：负责人\n生效日期：2026年11月01日\n'
    + '质量管理体系已经建立、实施并保持。组织职能和适用法规要求已在体系文件中说明。'));
  return analyze(page);
}

test('模型未启用时阻止审阅，管理员配置后可重试并生成结果', async ({ page }) => {
  const verify = watchPage(page);
  const result = await prepare(page, false);
  await expect(page.getByTestId('ai-review-status')).toContainText('联系管理员');
  await expect(page.getByTestId('ai-review-start')).toBeDisabled();
  await expect(page.getByTestId('ai-review-list')).toContainText('尚无 AI 审阅记录');
  const refused = await page.request.post(`${process.env.E2E_API_BASE_URL}/api/v1/validations/${result.run_uid}/ai-reviews`, {
    data: { mode: 'evidence_search', rule_id: 'R-4.1.1', file_uid: result.documents[0].file_uid },
  });
  expect(refused.status()).toBe(409);
  expect((await refused.json()).code).toBe(1401);
  await configure(page, true);
  await page.getByTestId('ai-review-retry').click();
  await expect(page.getByTestId('ai-review-start')).toBeEnabled();
  await page.getByTestId('ai-review-rule').selectOption('R-4.1.1');
  const completed = page.waitForResponse(r => r.url().endsWith('/ai-reviews') && r.request().method() === 'POST');
  await page.getByTestId('ai-review-start').click();
  expect((await completed).status()).toBe(200);
  await expect(page.getByTestId('ai-review-list')).toContainText('质量管理体系');
  await verify();
});

test('模型调用失败时显示审阅错误并保留已有记录和预筛结果', async ({ page }) => {
  const expected = [{ path: '', status: 502, code: 1402 }];
  const verify = watchPage(page, expected);
  const result = await prepare(page, true);
  const url = `${process.env.E2E_API_BASE_URL}/api/v1/validations/${result.run_uid}/ai-reviews`;
  expected[0].path = new URL(url).pathname;
  await expect(page.getByTestId('ai-review-start')).toBeEnabled();
  await page.getByTestId('ai-review-rule').selectOption('R-4.1.1');
  const created = page.waitForResponse(r => r.url() === url && r.request().method() === 'POST');
  await page.getByTestId('ai-review-start').click();
  expect((await created).status()).toBe(200);
  const coverage = await page.getByTestId('prescreen-coverage').innerText();
  const count = await page.getByTestId('active-count').innerText();
  const saved = await page.request.patch(`${process.env.E2E_API_BASE_URL}/api/v1/llm-settings`, {
    data: { enabled: true, base_url: `${process.env.E2E_API_BASE_URL}/intentionally-missing-llm/v1`,
      model: 'e2e-failure', api_key: 'synthetic-test-key', timeout_seconds: 5, max_tokens: 1200, temperature: 0 },
  });
  expect(saved.status()).toBe(200);
  const failed = page.waitForResponse(r => r.url() === url && r.request().method() === 'POST');
  await page.getByTestId('ai-review-start').click();
  const response = await failed;
  expect(response.status()).toBe(502);
  expect((await response.json()).code).toBe(1402);
  await expect(page.getByTestId('ai-review-status')).toContainText('AI 文件审阅失败');
  await expect(page.getByTestId('ai-review-start')).toBeEnabled();
  await expect(page.getByTestId('ai-review-list').locator('[data-review-card]')).toHaveCount(1);
  expect((await (await page.request.get(url)).json()).data).toHaveLength(1);
  await expect(page.getByTestId('prescreen-coverage')).toHaveText(coverage);
  await expect(page.getByTestId('active-count')).toHaveText(count);
  await verify();
});

test('审阅记录读取失败时显示迁移提示，重试恢复且不重新运行预筛', async ({ page }) => {
  const path = /\/api\/v1\/validations\/[^/]+\/ai-reviews$/;
  const expected = [{ path: '', status: 503, code: 1502 }];
  // 仅模拟缺迁移的 HTTP 边界，不删除或重命名测试库表。
  await page.route(path, async route => {
    if (route.request().method() !== 'GET') return route.continue();
    expected[0].path = new URL(route.request().url()).pathname;
    await route.fulfill({ status: 503, contentType: 'application/json',
      headers: { 'Access-Control-Allow-Origin': new URL(process.env.E2E_BASE_URL!).origin, 'Access-Control-Allow-Credentials': 'true' },
      body: JSON.stringify({ code: 1502, message: '数据库结构尚未升级，请联系管理员执行迁移。', data: null }) });
  });
  const verify = watchPage(page, expected);
  const result = await prepare(page, true);
  await expect(page.getByTestId('ai-review-status')).toContainText('迁移');
  await expect(page.getByTestId('ai-review-start')).toBeDisabled();
  const count = await page.getByTestId('active-count').innerText();
  const coverage = await page.getByTestId('prescreen-coverage').innerText();
  await page.unroute(path);
  const loaded = page.waitForResponse(r => r.url().endsWith(`/validations/${result.run_uid}/ai-reviews`));
  await page.getByTestId('ai-review-retry').click();
  expect((await loaded).status()).toBe(200);
  await expect(page.getByTestId('ai-review-start')).toBeEnabled();
  await expect(page.getByTestId('ai-review-list')).toContainText('尚无 AI 审阅记录');
  await expect(page.getByTestId('active-count')).toHaveText(count);
  await expect(page.getByTestId('prescreen-coverage')).toHaveText(coverage);
  await verify();
});
