import { test, expect } from '@playwright/test';
import { login, watchPage } from './Helpers';

test('规则手册可独立阅读并按条款和关键词检索实际规则', async ({ page }) => {
  const clean = watchPage(page);
  await login(page);
  await page.getByTestId('rules-nav').click();
  await expect(page.getByTestId('rule-handbook')).toContainText('ISO 13485:2016');
  await expect(page.getByTestId('rule-handbook')).toContainText('1.0.1');
  await page.getByTestId('rule-clause').selectOption('4.2.4');
  await page.getByTestId('rule-type').selectOption('quality_manual');
  await page.getByTestId('rule-search').fill('DOC-001');
  await expect(page.getByTestId('rule-list')).toContainText('文件应有可识别的编号');
  await expect(page.getByTestId('rule-list')).not.toContainText('DOC-002');
  await page.getByTestId('rule-search').fill('找不到的检查项');
  await expect(page.getByTestId('rule-list')).toContainText('未找到');
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByTestId('rules-back').click();
  await expect(page.getByTestId('upload-dropzone')).toBeVisible();
  await clean();
});
