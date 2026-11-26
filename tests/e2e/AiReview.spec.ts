import { expect, request as playwrightRequest, test } from '@playwright/test';
import { analyze, login, textFile, watchPage } from './Helpers';

test('两种 AI 审阅保存原文引用和人工决定且不改变预筛结果', async ({ page }) => {
  const verify = watchPage(page);
  await login(page);

  const configured = await page.request.patch(`${process.env.E2E_API_BASE_URL}/api/v1/llm-settings`, {
    data: {
      enabled: true, base_url: process.env.E2E_LLM_BASE_URL, model: 'e2e-review',
      api_key: 'synthetic-test-key', timeout_seconds: 10, max_tokens: 1200, temperature: 0,
    },
  });
  expect(configured.status()).toBe(200);
  expect((await configured.json()).code).toBe(0);

  const sourceText = '质量手册\n文件编号：QM-77\n版本：01\n批准：负责人\n生效日期：2026年11月01日\n'
    + '质量管理体系已经建立、实施并保持。组织职能和适用法规要求已在体系文件中说明。';
  await page.getByTestId('upload-files').setInputFiles(textFile('AI审阅质量手册.txt', sourceText));
  const result = await analyze(page);
  const coverageBefore = await page.getByTestId('prescreen-coverage').innerText();
  const countBefore = await page.getByTestId('active-count').innerText();

  await expect(page.getByTestId('ai-review-panel')).toBeVisible();
  await expect(page.getByTestId('ai-review-list')).toContainText('尚无 AI 审阅记录');
  const reviewUrl = `${process.env.E2E_API_BASE_URL}/api/v1/validations/${result.run_uid}/ai-reviews`;
  const unknownRule = await page.request.post(reviewUrl, {
    data: { mode: 'evidence_search', rule_id: 'R-UNKNOWN', file_uid: result.documents[0].file_uid },
  });
  expect(unknownRule.status()).toBe(400);
  expect((await unknownRule.json()).code).toBe(1001);
  const unrelatedFile = await page.request.post(reviewUrl, {
    data: { mode: 'evidence_search', rule_id: 'R-4.1.1', file_uid: '00000000-0000-4000-8000-000000000000' },
  });
  expect(unrelatedFile.status()).toBe(404);
  expect((await unrelatedFile.json()).code).toBe(1203);
  await page.getByTestId('ai-review-rule').selectOption('R-4.1.1');
  const evidenceResponse = page.waitForResponse(response =>
    response.url().endsWith(`/api/v1/validations/${result.run_uid}/ai-reviews`) && response.request().method() === 'POST');
  await page.getByTestId('ai-review-start').click();
  const evidenceBody = await (await evidenceResponse).json();
  expect(evidenceBody.code).toBe(0);
  expect(evidenceBody.data.mode).toBe('evidence_search');
  const evidenceUid = evidenceBody.data.review_uid as string;
  const evidenceCard = page.getByTestId(`ai-review-card-${evidenceUid}`);
  await expect(evidenceCard).toContainText('质量管理体系');
  await expect(evidenceCard).toContainText('抽取文本第');

  await evidenceCard.locator('[data-review-note]').fill('已与原件逐字核对。');
  await evidenceCard.locator('[data-review-edit-toggle]').click();
  await evidenceCard.locator('[data-review-edited]').fill('人工修订后的候选说明，等待签核。');
  const decisionResponse = page.waitForResponse(response =>
    response.url().endsWith(`/api/v1/ai-reviews/${evidenceUid}/decision`) && response.request().method() === 'PATCH');
  await evidenceCard.locator('[data-review-decision="accepted_edited"]').click();
  expect((await (await decisionResponse).json()).code).toBe(0);
  await expect(evidenceCard.locator('.ai-review-decisions')).toContainText('修改后采纳');

  await page.getByTestId('ai-review-mode-semantic').click();
  const semanticResponse = page.waitForResponse(response =>
    response.url().endsWith(`/api/v1/validations/${result.run_uid}/ai-reviews`) && response.request().method() === 'POST');
  await page.getByTestId('ai-review-start').click();
  const semanticBody = await (await semanticResponse).json();
  expect(semanticBody.code).toBe(0);
  expect(semanticBody.data.mode).toBe('semantic_review');
  expect(semanticBody.data.result.reviews).toHaveLength(5);
  await expect(page.getByTestId('ai-review-list')).toContainText('发现支持线索');

  await expect(page.getByTestId('prescreen-coverage')).toHaveText(coverageBefore);
  await expect(page.getByTestId('active-count')).toHaveText(countBefore);
  const saved = await page.request.get(`${process.env.E2E_API_BASE_URL}/api/v1/validations/${result.run_uid}/ai-reviews`);
  expect(saved.status()).toBe(200);
  const savedRows = (await saved.json()).data;
  expect(savedRows).toHaveLength(2);
  expect(savedRows[0].decisions).toHaveLength(1);
  expect(savedRows[0].decisions[0].edited_result).toContain('人工修订');

  const other = await playwrightRequest.newContext({ baseURL: process.env.E2E_API_BASE_URL });
  try {
    const otherLogin = await other.post('/api/v1/auth/login', {
      data: { email: process.env.E2E_OTHER_EMAIL, password: process.env.E2E_OTHER_PASSWORD },
    });
    expect(otherLogin.status()).toBe(200);
    const denied = await other.post(`/api/v1/validations/${result.run_uid}/ai-reviews`, {
      data: { mode: 'evidence_search', rule_id: 'R-4.1.1', file_uid: result.documents[0].file_uid },
    });
    expect(denied.status()).toBe(403);
    expect((await denied.json()).code).toBe(1104);
  } finally {
    await other.dispose();
  }

  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await verify();
});
