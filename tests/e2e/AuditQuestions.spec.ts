import { test, expect } from '@playwright/test';
import { analyze, login, textFile, watchPage } from './Helpers';

test('预筛缺项及缺失引用生成内审清单并下载，其他用户不可读取', async ({ page, browser }) => {
  const assertClean = watchPage(page);
  await login(page);
  await page.getByTestId('upload-files').setInputFiles(textFile('采购控制程序.txt', '采购控制程序\n文件编号：QP-51\n适用范围：测试产品采购活动，引用 QR-99 表单。\n职责：由采购部门管理供应商，具体评价记录待补充。'));
  const result = await analyze(page);
  const requested = page.waitForResponse((response) => response.url().endsWith('/audit-report'));
  await page.getByTestId('generate-audit').click();
  const response = await requested;
  expect(response.status()).toBe(200);
  const report = (await response.json()).data;
  expect(report.summary.gap).toBeGreaterThan(0);
  expect(report.summary.reference).toBe(1);
  await expect(page.getByTestId('audit-summary')).toContainText('规则缺项');
  await expect(page.getByTestId('audit-question-reference')).toContainText('QR-99');
  await expect(page.getByTestId('audit-question-gap').first()).toContainText('审核提问');
  const downloaded = page.waitForEvent('download');
  await page.getByTestId('download-audit').click();
  const file = await downloaded;
  expect(file.suggestedFilename()).toBe('模拟内审问题清单.docx');
  expect(await file.failure()).toBeNull();
  const context = await browser.newContext();
  try {
    const base = process.env.E2E_API_BASE_URL!;
    expect((await context.request.post(`${base}/api/v1/auth/login`, { data: { email: process.env.E2E_OTHER_EMAIL, password: process.env.E2E_OTHER_PASSWORD } })).status()).toBe(200);
    const forbidden = await context.request.get(`${base}/api/v1/validations/${result.run_uid}/audit-report`);
    expect(forbidden.status()).toBe(403); expect((await forbidden.json()).code).toBe(1104);
  } finally { await context.close(); }
  await assertClean();
});
