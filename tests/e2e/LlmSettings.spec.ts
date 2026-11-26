import { test, expect } from '@playwright/test';
import { spawnSync } from 'node:child_process';
import { login, watchPage } from './Helpers';

test('普通账号绕过导航打开模型配置时仍无编辑表单且接口拒绝修改', async ({ page, browser }) => {
  await login(page);
  const base = process.env.E2E_API_BASE_URL!;
  const before = (await (await page.request.get(`${base}/api/v1/llm-settings`)).json()).data;
  const context = await browser.newContext();
  try {
    const loggedIn = await context.request.post(`${base}/api/v1/auth/login`, {
      data: { email: process.env.E2E_OTHER_EMAIL, password: process.env.E2E_OTHER_PASSWORD },
    });
    expect(loggedIn.status()).toBe(200);
    const reviewer = await context.newPage();
    const verify = watchPage(reviewer);
    await reviewer.goto(process.env.E2E_BASE_URL!);
    await expect(reviewer.getByTestId('upload-dropzone')).toBeVisible();
    await expect(reviewer.getByTestId('llm-settings-nav')).toHaveCount(0);
    // 模拟绕过导航直接进入页面，仍须通过服务端当前账号复核。
    let configurationRequests = 0;
    reviewer.on('request', request => { if (request.url().endsWith('/api/v1/llm-settings')) configurationRequests += 1; });
    await reviewer.evaluate(async () => {
      const path = '/src/Components/LlmSettings.ts';
      const { LlmSettingsPage } = await import(path);
      await new LlmSettingsPage(document.querySelector('#app'), () => {}).open();
    });
    expect(configurationRequests).toBe(0);
    await expect(reviewer.getByTestId('llm-notice')).toContainText('仅管理员');
    await expect(reviewer.getByTestId('save-llm-settings')).toHaveCount(0);
    await expect(reviewer.getByTestId('llm-key')).toHaveCount(0);
    for (const response of [
      await context.request.get(`${base}/api/v1/llm-settings`),
      await context.request.patch(`${base}/api/v1/llm-settings`, {
        data: { enabled: false, base_url: `${base}/v1`, model: 'unauthorized', timeout_seconds: 5, max_tokens: 1000, temperature: 0 },
      }),
      await context.request.patch(`${base}/api/v1/llm-settings`, { data: {} }),
    ]) {
      expect(response.status()).toBe(403);
      expect((await response.json()).code).toBe(1104);
    }
    expect((await (await page.request.get(`${base}/api/v1/llm-settings`)).json()).data).toEqual(before);
    await verify();
  } finally { await context.close(); }
});

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
  await expect(page.getByTestId('authoring-notice')).toContainText('原草稿已保留');
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
