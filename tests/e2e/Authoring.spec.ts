import { test, expect } from '@playwright/test';
import { login, watchPage } from './Helpers';
import { spawnSync } from 'node:child_process';

async function openAuthoring(page: import('@playwright/test').Page) {
  await login(page);
  await page.getByTestId('templates-nav').click();
  await expect(page.getByTestId('template-finished-inspection')).toBeVisible();
}

test('检索、生成、参数联动、修订与历史 Word 下载', async ({ page }) => {
  const assertClean = watchPage(page);
  await openAuthoring(page);
  await page.getByTestId('template-search').fill('无此模板');
  await page.getByTestId('search-templates').click();
  await expect(page.getByTestId('template-empty')).toBeVisible();
  await page.getByTestId('template-search').fill('成品');
  await page.getByTestId('template-category').selectOption('技术文件');
  await page.getByTestId('search-templates').click();
  await page.getByTestId('template-finished-inspection').click();
  const values = { company: '自动化测试组织', project: '自动化测试项目', product: '测试产品', model: 'MODEL-A', number: 'WI-01', version: 'A/0', requirements: '检验依据：经批准的产品技术要求，具体限值待确认。' };
  for (const [key, value] of Object.entries(values)) await page.getByTestId(`parameter-${key}`).fill(value);
  const created = page.waitForResponse((response) => response.url().endsWith('/api/v1/document-drafts') && response.request().method() === 'POST');
  await page.getByTestId('generate-draft').click();
  const response = await created;
  expect(response.status()).toBe(200);
  const draft = (await response.json()).data;
  await expect(page.getByTestId('draft-revision')).toHaveText('修订 1');
  await expect(page.getByTestId('section-s1')).toHaveValue(/MODEL-A/);
  await page.getByTestId('parameter-model').fill('MODEL-B');
  await page.getByTestId('draft-reason').fill('更新型号并重新生成');
  await page.getByTestId('generate-draft').click();
  await expect(page.getByTestId('draft-revision')).toHaveText('修订 2');
  await expect(page.getByTestId('section-s1')).toHaveValue(/MODEL-B/);
  await expect(page.getByTestId('section-s3')).toHaveValue(/MODEL-B/);
  await page.getByTestId('section-s2').fill('已核对技术要求及引用文件清单');
  await page.getByTestId('draft-reason').fill('补充实际确认的检验依据');
  await page.getByTestId('save-draft').click();
  await expect(page.getByTestId('draft-revision')).toHaveText('修订 3');
  await page.getByTestId('reload-draft').click();
  await expect(page.getByTestId('section-s2')).toHaveValue('已核对技术要求及引用文件清单');
  const downloaded = page.waitForEvent('download');
  await page.getByTestId('download-draft').click();
  const file = await downloaded;
  expect(file.suggestedFilename()).toContain('草稿-r3.docx');
  expect(await file.failure()).toBeNull();
  await page.getByTestId('draft-history').locator('summary').click();
  const history = page.waitForEvent('download');
  await page.getByTestId('history-download-1').click();
  expect((await history).suggestedFilename()).toContain('r1.docx');
  const stored = await page.request.get(`${process.env.E2E_API_BASE_URL}/api/v1/document-drafts/${draft.draft_uid}`);
  expect(stored.status()).toBe(200);
  const data = (await stored.json()).data;
  expect(data.history).toHaveLength(3);
  expect(data.snapshot.parameters.model).toBe('MODEL-B');
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: '.local/AuthoringDesktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByTestId('save-draft')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: '.local/AuthoringMobile.png', fullPage: true });
  const check = spawnSync(process.env.E2E_PYTHON!, ['tests/Helpers/E2eDatabase.py', '--draft', draft.draft_uid, '3'], { encoding: 'utf8', env: process.env });
  expect(check.status, check.stdout + check.stderr).toBe(0);
  await assertClean();
});

test('移动端可切换编写、返回预筛、打开配置并退出登录', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const assertClean = watchPage(page);
  await login(page);
  await expect(page.getByTestId('templates-nav')).toBeVisible();
  await page.getByTestId('templates-nav').click();
  await expect(page.getByTestId('template-market-research')).toBeVisible();
  await page.getByTestId('precheck-nav').click();
  await expect(page.getByTestId('upload-dropzone')).toBeVisible();
  await page.getByTestId('llm-settings-nav').click();
  await expect(page.getByTestId('llm-key-status')).toBeVisible();
  await expect(page.getByTestId('settings-back')).toBeVisible();
  await page.getByTestId('settings-back').click();
  await page.getByTestId('logout').click();
  await expect(page.getByTestId('login-form')).toBeVisible();
  await assertClean();
});

test('十万字符资料和十二万字符章节可完整保存及重新加载', async ({ page }) => {
  const assertClean = watchPage(page);
  await openAuthoring(page);
  await page.getByTestId('template-market-research').click();
  const requirements = '资'.repeat(99996) + '资料末尾';
  const values = { company: '容量测试组织', project: '长文本容量测试', product: '测试产品', model: 'LONG-A', number: 'MR-LONG', version: 'A/0', requirements };
  await expect(page.getByTestId('parameter-requirements')).toHaveAttribute('maxlength', '100000');
  for (const [key, value] of Object.entries(values)) await page.getByTestId(`parameter-${key}`).fill(value);
  const created = page.waitForResponse((response) => response.url().endsWith('/api/v1/document-drafts') && response.request().method() === 'POST');
  await page.getByTestId('generate-draft').click();
  const response = await created;
  expect(response.status()).toBe(200);
  const draft = (await response.json()).data;
  expect(draft.snapshot.parameters.requirements).toBe(requirements);
  await expect(page.getByTestId('section-s2')).toHaveValue(draft.snapshot.sections[1].body);
  const body = '文'.repeat(119996) + '章节末尾';
  await expect(page.getByTestId('section-s2')).toHaveAttribute('maxlength', '120000');
  await page.getByTestId('section-s2').fill(body);
  await page.getByTestId('draft-reason').fill('验证长章节完整保存');
  const saving = page.waitForResponse((response) => response.url().endsWith(`/document-drafts/${draft.draft_uid}`) && response.request().method() === 'PATCH');
  await page.getByTestId('save-draft').click();
  expect((await saving).status()).toBe(200);
  await expect(page.getByTestId('draft-revision')).toHaveText('修订 2');
  await page.getByTestId('reload-draft').click();
  await expect(page.getByTestId('authoring-notice')).toHaveText('已加载最新保存版本');
  await expect(page.getByTestId('section-s2')).toHaveValue(body);
  const stored = await page.request.get(`${process.env.E2E_API_BASE_URL}/api/v1/document-drafts/${draft.draft_uid}`);
  expect(stored.status()).toBe(200);
  const data = (await stored.json()).data;
  expect(data.snapshot.parameters.requirements).toBe(requirements);
  expect(data.snapshot.sections[1].body).toBe(body);
  expect(data.history).toHaveLength(2);
  await assertClean();
});

test('草稿并发与跨用户权限拒绝且不改动原记录', async ({ page, browser }) => {
  const assertClean = watchPage(page);
  await openAuthoring(page);
  const base = process.env.E2E_API_BASE_URL!;
  const response = await page.request.post(`${base}/api/v1/document-drafts`, { data: { template_id: 'design-plan', parameters: { company: '测试组织', project: '并发测试', product: '测试产品', model: 'A', number: 'DP-01', version: '01', requirements: '测试项目的设计输入要求' } } });
  expect(response.status()).toBe(200);
  const draft = (await response.json()).data;
  const url = `${base}/api/v1/document-drafts/${draft.draft_uid}`;
  const saved = await page.request.patch(url, { data: { revision: 1, sections: { s1: '实际保存的正文内容' }, reason: '保存有效正文修订' } });
  expect(saved.status()).toBe(200);
  const stale = await page.request.patch(url, { data: { revision: 1, sections: { s1: '不应覆盖的过期正文' }, reason: '使用过期版本提交' } });
  expect(stale.status()).toBe(409); expect((await stale.json()).code).toBe(1703);
  const context = await browser.newContext();
  try {
    const logged = await context.request.post(`${base}/api/v1/auth/login`, { data: { email: process.env.E2E_OTHER_EMAIL, password: process.env.E2E_OTHER_PASSWORD } });
    expect(logged.status()).toBe(200);
    for (const path of [url, `${url}/download`]) {
      const denied = await context.request.get(path);
      expect(denied.status()).toBe(403); expect((await denied.json()).code).toBe(1104);
    }
  } finally { await context.close(); }
  const current = (await (await page.request.get(url)).json()).data;
  expect(current.revision).toBe(2); expect(current.history).toHaveLength(2);
  expect(current.snapshot.sections[0].body).toBe('实际保存的正文内容');
  await assertClean();
});
