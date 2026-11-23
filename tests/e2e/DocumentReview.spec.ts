import { expect, test, type Page } from '@playwright/test';
import { analyze, currentRunCount, login, textFile, verifyReviewSnapshot, watchPage } from './Helpers';

function document(name: string, number: string, revision: string, effective: string, extra = '', status = '现行有效') {
  return textFile(name, `文件编号：${number}\n版本：${revision}\n生效日期：${effective}\n文件状态：${status}\n批准：负责人\n适用范围：医疗器械产品质量体系\n${extra}`);
}

async function check(page: Page) {
  await expect(page.getByTestId('check-relations')).toBeEnabled();
  const response = page.waitForResponse((item) => item.url().endsWith('/api/v1/document-reviews') && item.request().method() === 'POST');
  await page.getByTestId('check-relations').click();
  const received = await response;
  expect(received.status()).toBe(200);
  const body = await received.json();
  expect(body.code).toBe(0);
  await expect(page.getByTestId('check-relations')).toBeEnabled();
  return body.data;
}

async function confirm(page: Page, id: string, uid: string) {
  await page.getByTestId(`choice-${id}`).selectOption(uid);
  await page.getByTestId(`reason-${id}`).fill('已核对受控清单、批准及审核日期适用性');
  const response = page.waitForResponse((item) => item.url().endsWith('/decisions') && item.request().method() === 'PATCH');
  await page.getByTestId(`confirm-${id}`).click();
  const received = await response;
  expect(received.status()).toBe(200);
  await expect(page.getByTestId(`confirmed-${id}`)).toBeVisible();
  return (await received.json()).data;
}

test('确认正式版后只计分所选版本且冻结依据保留原件', async ({ page }) => {
  const verify = watchPage(page);
  await login(page);
  await page.getByTestId('upload-files').setInputFiles([
    document('采购程序旧版.txt', 'QP-07', '01', '2025年01月01日'),
    document('采购程序新版.txt', 'QP-07', '02', '2026年01月01日'),
  ]);
  await expect(page.getByTestId('file-detection-1')).toBeVisible();
  await page.getByTestId('review-date').fill('2026-11-23');
  const review = await check(page);
  const group = review.version_groups[0];
  const selected = review.documents[1].file_uid;
  expect(group.suggested_file_uid).toBe(selected);
  expect(review.ready).toBe(false);
  await page.getByTestId('analyze-button').click();
  await expect(page.getByRole('status')).toContainText('已发现文件冲突');
  await expect(page.getByTestId('results')).toHaveCount(0);
  await confirm(page, group.id, selected);
  const result = await analyze(page);
  expect(result.documents).toHaveLength(1);
  await expect(page.getByTestId('excluded-versions')).toContainText('采购程序旧版.txt');
  await expect(page.getByTestId('review-snapshot')).toBeVisible();
  await confirm(page, group.id, review.documents[0].file_uid);
  verifyReviewSnapshot(result.run_uid, selected, review.documents[0].file_uid);
  await verify();
});

test('跨文件期限冲突保留双方并展示待补充引用', async ({ page }) => {
  const verify = watchPage(page);
  await login(page);
  await page.getByTestId('upload-files').setInputFiles([
    document('质量手册.txt', 'QM-02', '01', '2025年01月01日', 'QR-07 记录保存期限为3年，按 QP-07 执行'),
    document('采购程序.txt', 'QP-07', '01', '2025年01月01日', 'QR-07 记录保存期限为5年'),
  ]);
  await expect(page.getByTestId('file-detection-1')).toBeVisible();
  const review = await check(page);
  expect(review.version_groups).toHaveLength(0);
  const group = review.requirement_conflicts[0];
  await expect(page.getByTestId('requirement-QR-07')).toContainText('3年');
  await expect(page.getByTestId('requirement-QR-07')).toContainText('5年');
  await expect(page.getByTestId('reference-QR-07').first()).toContainText('本次未提供');
  await confirm(page, group.id, review.documents[1].file_uid);
  const result = await analyze(page);
  expect(result.documents).toHaveLength(2);
  expect(result.document_review.requirement_conflicts[0].decision.file_uid).toBe(review.documents[1].file_uid);
  expect(result.score.verdict).toBe('存在冲突，待修订');
  await expect(page.getByTestId('result-verdict')).toHaveText('存在冲突，待修订');
  await expect(page.getByTestId('review-snapshot')).toContainText('仍需');
  await page.screenshot({ path: '.local/ReviewDesktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: '.local/ReviewMobile.png', fullPage: true });
  await verify();
});

test('填写记录确认层级后不会互相替换并支持校正编号类别', async ({ page }) => {
  const verify = watchPage(page);
  await login(page);
  await page.getByTestId('upload-files').setInputFiles([
    document('供应商评价记录甲.txt', 'QR-01', '01', '2025年01月01日', '供应商甲评价结果合格'),
    document('供应商评价记录乙.txt', 'QR-01', '01', '2025年01月01日', '供应商乙评价结果合格'),
  ]);
  await expect(page.getByTestId('file-detection-1')).toBeVisible();
  for (const index of [0, 1]) {
    await page.getByTestId(`metadata-${index}`).locator('summary').click();
    await page.getByTestId(`meta-${index}-layer`).selectOption('record');
  }
  await page.getByTestId('metadata-0').locator('summary').click();
  await page.getByTestId('meta-0-category').selectOption('required');
  await page.getByTestId('metadata-0').locator('summary').click();
  await page.getByTestId('meta-0-number').fill('QR-001');
  await page.getByTestId('meta-0-number').press('Tab');
  const review = await check(page);
  expect(review.version_groups).toHaveLength(0);
  expect(review.documents[0].metadata.category).toBe('required');
  expect(review.documents[0].metadata.number).toBe('QR-001');
  const result = await analyze(page);
  expect(result.documents).toHaveLength(2);
  await verify();
});

test('拒绝绕过确认、过期决策和其他用户越权且不产生预筛写入', async ({ page, playwright }) => {
  const verify = watchPage(page);
  await login(page);
  await page.getByTestId('upload-files').setInputFiles([
    document('风险管理程序甲.txt', 'QP-09', '01', '2025年01月01日', '风险控制由质量部负责'),
    document('风险管理程序乙.txt', 'QP-09', '01', '2025年01月01日', '风险控制由技术部负责'),
  ]);
  await expect(page.getByTestId('file-detection-1')).toBeVisible();
  const review = await check(page);
  const base = process.env.E2E_API_BASE_URL;
  const before = currentRunCount();
  const form = new URLSearchParams();
  review.documents.forEach((item: { file_uid: string }) => form.append('file_uids', item.file_uid));
  const rejected = await page.request.post(`${base}/api/v1/validations`, { data: form.toString(), headers: { 'Content-Type': 'application/x-www-form-urlencoded' } });
  expect(rejected.status()).toBe(409);
  expect((await rejected.json()).code).toBe(1604);
  expect(currentRunCount()).toBe(before);
  const group = review.version_groups[0];
  const confirmed = await confirm(page, group.id, review.documents[0].file_uid);
  const data = { revision: 1, kind: 'version', issue_id: group.id, file_uid: review.documents[0].file_uid, reason: '已经验证的确认依据' };
  const stale = await page.request.patch(`${base}/api/v1/document-reviews/${review.review_uid}/decisions`, { data });
  expect(stale.status()).toBe(409);
  expect((await stale.json()).code).toBe(1602);
  form.append('review_uid', review.review_uid);
  form.append('review_revision', '1');
  const staleRun = await page.request.post(`${base}/api/v1/validations`, { data: form.toString(), headers: { 'Content-Type': 'application/x-www-form-urlencoded' } });
  expect(staleRun.status()).toBe(409);
  expect((await staleRun.json()).code).toBe(1602);
  expect(currentRunCount()).toBe(before);
  const other = await playwright.request.newContext();
  try {
    const logged = await other.post(`${base}/api/v1/auth/login`, { data: { email: process.env.E2E_OTHER_EMAIL, password: process.env.E2E_OTHER_PASSWORD } });
    expect(logged.status()).toBe(200);
    const denied = await other.patch(`${base}/api/v1/document-reviews/${review.review_uid}/decisions`, { data: { ...data, revision: confirmed.revision } });
    expect(denied.status()).toBe(403);
    expect((await denied.json()).code).toBe(1104);
    expect((await other.get(`${base}/api/v1/document-reviews/${review.review_uid}`)).status()).toBe(403);
  } finally { await other.dispose(); }
  const restored = await page.request.get(`${base}/api/v1/document-reviews/${review.review_uid}`);
  expect((await restored.json()).data.revision).toBe(confirmed.revision);
  await verify();
});
