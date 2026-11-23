import { test, expect } from '@playwright/test';
import { login, watchPage } from './Helpers';

test('预览并跨文档联动型号，保留独立编号和旧修订，过期批次整体拒绝', async ({ page }) => {
  const assertClean = watchPage(page);
  await login(page);
  const base = process.env.E2E_API_BASE_URL!;
  const drafts = [];
  for (const [index, templateId] of ['design-plan', 'finished-inspection'].entries()) {
    const response = await page.request.post(`${base}/api/v1/document-drafts`, { data: { template_id: templateId, parameters: { company: '测试组织', project: '全局联动测试', product: '测试产品', model: 'MODEL-A', number: `BATCH-${index}`, version: '01', requirements: '经确认的项目输入要求' } } });
    expect(response.status()).toBe(200); drafts.push((await response.json()).data);
  }
  await page.getByTestId('templates-nav').click();
  await page.getByTestId('open-batch').click();
  await page.getByTestId('batch-panel').locator('summary').click();
  for (const draft of drafts) await page.getByTestId(`batch-select-${draft.draft_uid}`).check();
  await page.getByTestId('batch-parameter-model').fill('MODEL-B');
  await page.getByTestId('batch-reason').fill('统一联动项目产品型号');
  const previewed = page.waitForResponse((response) => response.url().endsWith('/document-draft-batches/preview'));
  await page.getByTestId('preview-batch').click();
  const preview = await previewed;
  expect(preview.status()).toBe(200); expect((await preview.json()).data).toHaveLength(2);
  await expect(page.getByTestId('batch-preview')).toContainText('MODEL-A → MODEL-B');
  for (const draft of drafts) {
    const before = (await (await page.request.get(`${base}/api/v1/document-drafts/${draft.draft_uid}`)).json()).data;
    expect(before.revision).toBe(1);
  }
  const applied = page.waitForResponse((response) => response.url().endsWith('/document-draft-batches/apply'));
  await page.getByTestId('apply-batch').click();
  expect((await applied).status()).toBe(200);
  await expect(page.getByTestId('authoring-notice')).toContainText('参数已联动');
  for (const [index, draft] of drafts.entries()) {
    const updated = (await (await page.request.get(`${base}/api/v1/document-drafts/${draft.draft_uid}`)).json()).data;
    expect(updated.revision).toBe(2); expect(updated.history).toHaveLength(2);
    expect(updated.snapshot.parameters.model).toBe('MODEL-B');
    expect(updated.snapshot.parameters.number).toBe(`BATCH-${index}`);
    expect(updated.snapshot.sections.some((section: { body: string }) => section.body.includes('MODEL-A'))).toBe(false);
  }
  // 第一份版本正确、第二份版本过期时，第一份也不能部分写入。
  const stale = await page.request.post(`${base}/api/v1/document-draft-batches/apply`, { data: { drafts: [{ draft_uid: drafts[0].draft_uid, revision: 2 }, { draft_uid: drafts[1].draft_uid, revision: 1 }], parameters: { model: 'MODEL-C' }, reason: '过期批次不应部分应用' } });
  expect(stale.status()).toBe(409); expect((await stale.json()).code).toBe(1703);
  for (const draft of drafts) {
    const unchanged = (await (await page.request.get(`${base}/api/v1/document-drafts/${draft.draft_uid}`)).json()).data;
    expect(unchanged.revision).toBe(2); expect(unchanged.snapshot.parameters.model).toBe('MODEL-B');
  }
  await assertClean();
});
