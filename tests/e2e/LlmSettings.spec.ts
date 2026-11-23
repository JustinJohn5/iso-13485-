import { test, expect } from '@playwright/test';
import { spawnSync } from 'node:child_process';
import { login, watchPage } from './Helpers';

test('管理员配置加密保存且不回显，AI 故障保留原草稿', async ({ page, browser }) => {
  await login(page);
  const base = process.env.E2E_API_BASE_URL!;
  // 使用隔离测试后端的不存在路径制造确定的模型服务错误，不发送真实资料或凭据。
  const key = 'synthetic-key-for-e2e-only';
  await page.getByTestId('llm-settings-nav').click();
  await page.getByTestId('llm-enabled').check();
  await page.getByTestId('llm-url').fill(`${base}/intentionally-missing-llm/v1`);
  await page.getByTestId('llm-model').fill('synthetic-test-model');
  await page.getByTestId('llm-key').fill(key);
  await page.getByTestId('llm-tokens').fill('65536');
  await page.getByTestId('llm-timeout').fill('600');
  await expect(page.getByTestId('llm-capacity-note')).toContainText('100万字符');
  const saved = page.waitForResponse((response) => response.url().endsWith('/api/v1/llm-settings') && response.request().method() === 'PATCH');
  await page.getByTestId('save-llm-settings').click();
  const response = await saved;
  expect(response.status()).toBe(200);
  expect(JSON.stringify(await response.json())).not.toContain(key);
  expect((await response.json()).data).toMatchObject({ max_tokens: 65536, timeout_seconds: 600 });
  const persisted = await page.request.get(`${base}/api/v1/llm-settings`);
  expect(persisted.status()).toBe(200);
  expect((await persisted.json()).data).toMatchObject({ max_tokens: 65536, timeout_seconds: 600 });
  await expect(page.getByTestId('llm-notice')).toContainText('配置已保存');
  await expect(page.getByTestId('llm-key')).toHaveValue('');
  await expect(page.getByTestId('llm-key-status')).toHaveText('密钥状态：已配置');
  const check = spawnSync(process.env.E2E_PYTHON!, ['tests/Helpers/E2eDatabase.py', '--llm', key], { encoding: 'utf8', env: process.env });
  expect(check.status, check.stdout + check.stderr).toBe(0);
  const created = await page.request.post(`${base}/api/v1/document-drafts`, { data: { template_id: 'design-plan', parameters: { company: '测试组织', project: 'AI故障测试', product: '测试产品', model: 'MODEL-A', number: 'DP-02', version: '01', requirements: '测试要求内容' } } });
  expect(created.status()).toBe(200);
  const draft = (await created.json()).data;
  const assertClean = watchPage(page, [{ path: `/api/v1/document-drafts/${draft.draft_uid}/ai-draft`, status: 502, code: 1402 }]);
  await page.getByTestId('settings-back').click();
  await page.getByTestId('templates-nav').click();
  await page.getByTestId(`open-draft-${draft.draft_uid}`).click();
  await expect(page.getByTestId('ai-draft')).toBeEnabled();
  const instructions = '请保留详细输入资料。'.repeat(2000) + '长要求末尾';
  await expect(page.getByTestId('ai-instructions')).toHaveAttribute('maxlength', '30000');
  await page.getByTestId('ai-instructions').fill(instructions);
  const failed = page.waitForResponse((response) => response.url().endsWith('/ai-draft'));
  await page.getByTestId('ai-draft').click();
  const failure = await failed;
  expect(failure.request().postDataJSON().instructions).toBe(instructions);
  expect(failure.status()).toBe(502); expect((await failure.json()).code).toBe(1402);
  expect((await failure.json()).data).toEqual({ reason: 'endpoint', provider_status: 404 });
  await expect(page.getByTestId('authoring-notice')).toContainText('原草稿已保留');
  await expect(page.getByTestId('authoring-notice')).toContainText('模型接口不存在');
  await expect(page.getByTestId('draft-revision')).toHaveText('修订 1');
  const current = (await (await page.request.get(`${base}/api/v1/document-drafts/${draft.draft_uid}`)).json()).data;
  expect(current.snapshot).toEqual(draft.snapshot); expect(current.history).toHaveLength(1);
  const context = await browser.newContext();
  try {
    expect((await context.request.post(`${base}/api/v1/auth/login`, { data: { email: process.env.E2E_OTHER_EMAIL, password: process.env.E2E_OTHER_PASSWORD } })).status()).toBe(200);
    const forbidden = await context.request.get(`${base}/api/v1/llm-settings`);
    expect(forbidden.status()).toBe(403); expect((await forbidden.json()).code).toBe(1104);
    const patch = await context.request.patch(`${base}/api/v1/llm-settings`, { data: { enabled: false, base_url: `${base}/v1`, model: 'test', timeout_seconds: 5, max_tokens: 1000, temperature: 0.2 } });
    expect(patch.status()).toBe(403); expect((await patch.json()).code).toBe(1104);
  } finally { await context.close(); }
  await assertClean();
});

test('模型标识错误时显示配置建议且不改动已保存草稿', async ({ page }) => {
  await login(page);
  const base = process.env.E2E_API_BASE_URL!;
  const configured = await page.request.patch(`${base}/api/v1/llm-settings`, { data: {
    enabled: true, base_url: `${base}/intentionally-missing-llm/v1`, model: 'invalid-model-for-test',
    api_key: 'synthetic-key-for-ui-regression', timeout_seconds: 5, max_tokens: 1000, temperature: 0.2,
  } });
  expect(configured.status()).toBe(200);
  const created = await page.request.post(`${base}/api/v1/document-drafts`, { data: {
    template_id: 'market-research', parameters: { company: '测试组织', project: '模型错误提示测试',
      product: '虚构产品', model: 'TEST-A', number: 'MR-ERR-01', version: 'A/0', requirements: '测试资料均为虚构内容' },
  } });
  expect(created.status()).toBe(200);
  const draft = (await created.json()).data;
  const path = `/api/v1/document-drafts/${draft.draft_uid}/ai-draft`;
  const assertClean = watchPage(page, [{ path, status: 502, code: 1402 }]);
  // 后端分类由单元测试及真实404路径覆盖；这里精确注入模型错误响应以验证页面反馈。
  await page.route(`${base}${path}`, (route) => route.fulfill({ status: 502, json: {
    code: 1402, message: '模型标识无效或服务商不支持，请在“模型配置”填写真实 API 模型 ID；原草稿已保留',
    data: { reason: 'invalid_model', provider_status: 400 },
  } }));
  await page.getByTestId('templates-nav').click();
  await page.getByTestId(`open-draft-${draft.draft_uid}`).click();
  await page.getByTestId('ai-instructions').fill('请整理并扩写市场调研章节');
  const failed = page.waitForResponse((response) => response.url().endsWith(path));
  await page.getByTestId('ai-draft').click();
  const failure = await failed;
  expect(failure.status()).toBe(502);
  expect((await failure.json()).data.reason).toBe('invalid_model');
  await expect(page.getByTestId('authoring-notice')).toContainText('模型标识无效');
  await expect(page.getByTestId('authoring-notice')).toContainText('模型配置');
  await expect(page.getByTestId('draft-revision')).toHaveText('修订 1');
  const stored = await page.request.get(`${base}/api/v1/document-drafts/${draft.draft_uid}`);
  expect(stored.status()).toBe(200);
  const current = (await stored.json()).data;
  expect(current.snapshot).toEqual(draft.snapshot);
  expect(current.history).toHaveLength(1);
  await page.screenshot({ path: '.local/LlmFailureDetails.png', fullPage: true });
  await assertClean();
});
