import { expect, test } from '@playwright/test';
import { analyze, currentRunCount, docxFile, login, textFile, verifyDatabase, watchPage } from './Helpers';

test('自动识别质量手册并展示不同证据及合并条款', async ({ page }) => {
  const verify = watchPage(page);
  await login(page);
  await page.getByTestId('upload-files').setInputFiles(textFile('QM-01 质量手册.txt'));
  await expect(page.getByTestId('file-detection-0')).toContainText('自动识别：质量手册');
  const result = await analyze(page);
  expect(result.documents[0].document_type).toBe('quality_manual');
  await expect(page.getByTestId('result-documents')).toContainText('质量手册');
  await expect(page.getByTestId('evidence-DOC-001')).toContainText('文件编号：QM-01');
  await expect(page.getByTestId('evidence-DOC-002')).toContainText('版本：01');
  await expect(page.getByTestId('evidence-DOC-003')).toContainText('批准：负责人');
  await expect(page.getByTestId('evidence-DOC-004')).toContainText('2020年02月01日发布');
  await expect(page.getByTestId('finding-DOC-001').locator('td[rowspan="4"]')).toHaveCount(1);
  await expect(page.getByTestId('finding-R-4.2.2')).toBeVisible();
  await expect(page.getByTestId('finding-R-5.6.2')).not.toBeVisible();
  await page.getByTestId('toggle-skipped').click();
  await expect(page.getByTestId('finding-R-5.6.2')).toBeVisible();
  verifyDatabase(result.run_uid, 1, 'quality_manual');
  await page.getByTestId('reset-result').click();
  await expect(page.getByTestId('results')).toHaveCount(0);
  await expect(page.getByTestId('analyze-button')).toBeDisabled();
  await verify();
});

test('正文识别和手动修正后重新判定使用最新类型', async ({ page }) => {
  const verify = watchPage(page);
  await login(page);
  await page.getByTestId('upload-files').setInputFiles(textFile('未命名.txt'));
  await expect(page.getByTestId('file-detection-0')).toContainText('根据正文');
  await page.getByTestId('document-type-0').selectOption('procedure');
  await expect(page.getByTestId('file-detection-0')).toContainText('手动选择：程序文件');
  const manual = await analyze(page);
  expect(manual.documents[0].document_type).toBe('procedure');
  verifyDatabase(manual.run_uid, 1, 'procedure');
  await page.getByTestId('document-type-0').selectOption('auto');
  await expect(page.getByTestId('file-detection-0')).toContainText('自动识别：质量手册');
  const automatic = await analyze(page);
  verifyDatabase(automatic.run_uid, 1, 'quality_manual');
  await verify();
});

test('同内容不同文件名只计分一次', async ({ page }) => {
  const verify = watchPage(page);
  await login(page);
  await page.getByTestId('upload-files').setInputFiles(textFile('质量手册基线.txt'));
  await expect(page.getByTestId('file-detection-0')).toContainText('质量手册');
  const baseline = await analyze(page);
  await page.getByTestId('reset-result').click();
  await page.getByTestId('upload-files').setInputFiles([textFile('质量手册原件.txt'), textFile('质量手册副本.txt')]);
  await expect(page.getByTestId('file-detection-1')).toContainText('质量手册');
  const result = await analyze(page);
  expect(result.duplicate_files).toHaveLength(1);
  expect(result.documents).toHaveLength(1);
  await expect(page.getByTestId('duplicate-note')).toContainText('已合并 1 份');
  await expect(page.getByTestId('finding-DOC-001')).toHaveCount(1);
  await expect(page.getByTestId('active-count')).toHaveText(String(baseline.prescreen.coverage.denominator));
  expect(result.prescreen.coverage).toEqual(baseline.prescreen.coverage);
  verifyDatabase(result.run_uid, 1, 'quality_manual');
  await verify();
});

test('未知内容提示人工确认且移除不产生预筛结果', async ({ page }) => {
  const verify = watchPage(page);
  await login(page);
  const text = '这是一份普通说明。内容描述工作时间与日常安排，没有明确的文件类别和标题。'.repeat(4);
  await page.getByTestId('upload-files').setInputFiles(textFile('附件.txt', text));
  await expect(page.getByTestId('file-detection-0')).toContainText('请手动确认');
  await expect(page.getByTestId('remove-file-0')).toBeEnabled();
  await page.getByTestId('remove-file-0').click();
  await expect(page.getByTestId('document-type-0')).toHaveCount(0);
  await expect(page.getByTestId('analyze-button')).toBeDisabled();
  await verify();
});

test('真实DOCX抽取后自动识别且非法类型修改被拒绝', async ({ page }) => {
  const verify = watchPage(page);
  await login(page);
  const upload = page.waitForResponse((item) => item.url().endsWith('/api/v1/documents') && item.request().method() === 'POST');
  await page.getByTestId('upload-files').setInputFiles(docxFile());
  const received = await upload;
  expect(received.status()).toBe(200);
  const file = (await received.json()).data;
  await expect(page.getByTestId('file-detection-0')).toContainText('质量手册');
  const rejected = await page.request.patch(`${process.env.E2E_API_BASE_URL}/api/v1/documents/${file.file_uid}`, { data: { document_type: 'invalid' } });
  expect(rejected.status()).toBe(400);
  expect((await rejected.json()).code).toBe(1001);
  const result = await analyze(page);
  verifyDatabase(result.run_uid, 1, 'quality_manual');
  await expect(page.getByTestId('evidence-DOC-001')).toContainText('文件编号：QM-01');
  await verify();
});

test('相同内容不同类型明确提示且不生成审核记录', async ({ page }) => {
  const verify = watchPage(page, [{ path: '/api/v1/validations', status: 400, code: 1001 }]);
  await login(page);
  await page.getByTestId('upload-files').setInputFiles([textFile('质量手册A.txt'), textFile('质量手册B.txt')]);
  await expect(page.getByTestId('file-detection-1')).toContainText('质量手册');
  await page.getByTestId('document-type-1').selectOption('procedure');
  await expect(page.getByTestId('file-detection-1')).toContainText('手动选择：程序文件');
  const before = currentRunCount();
  const response = page.waitForResponse((item) => item.url().endsWith('/api/v1/validations'));
  await page.getByTestId('analyze-button').click();
  expect((await response).status()).toBe(400);
  await expect(page.getByRole('status')).toContainText('相同内容的文件选择了不同类型');
  await expect(page.getByTestId('results')).toHaveCount(0);
  expect(currentRunCount()).toBe(before);
  await page.getByTestId('document-type-1').selectOption('auto');
  const result = await analyze(page);
  verifyDatabase(result.run_uid, 1, 'quality_manual');
  await verify();
});
