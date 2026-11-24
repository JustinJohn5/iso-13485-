import { test, expect } from '@playwright/test';
import { login, textFile, watchPage } from './Helpers';
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';

test('按发布版本生成、导入、阅读、检查和下载，历史版本保持独立', async ({ page }, testInfo) => {
  const clean = watchPage(page);
  await login(page);
  await page.getByTestId('suites-nav').click();
  await page.getByTestId('suite-name').fill('测试整套体系');
  await page.getByTestId('suite-version').fill('A/0');
  await page.getByTestId('suite-create').click();
  await expect(page.getByTestId('suite-detail')).toContainText('A/0');
  for (const [key, value] of Object.entries({ company: '测试组织', project: '套册测试', product: '测试产品', model: 'MODEL-A', requirements: '依据实际产品资料填写，不编造记录' })) {
    await page.getByTestId(`suite-parameter-${key}`).fill(value);
  }
  const generation = page.waitForResponse(r => r.url().endsWith('/generations'));
  await page.getByTestId('suite-generate').click();
  const generated = await generation;
  expect(generated.status()).toBe(200);
  const first = (await generated.json()).data;
  expect(first.items.length).toBe(20);
  await expect(page.getByTestId('suite-items')).toContainText('质量手册');
  await page.getByTestId(`suite-read-${first.items[0].id}`).click();
  await expect(page.getByTestId('suite-reader')).toContainText('MODEL-A');
  await page.getByTestId('suite-edit-body').click();
  await page.getByTestId('suite-section-s1').fill('已核实范围：测试组织 MODEL-A 医疗器械的生产与服务。');
  await page.getByTestId('suite-edit-reason').fill('按本次审核范围修订正文');
  await page.getByTestId('suite-save-body').click();
  await expect(page.getByTestId('suite-reader')).toContainText('已核实范围');
  await page.getByTestId(`suite-item-version-${first.items[0].id}`).fill('B/1');
  await page.getByTestId(`suite-save-${first.items[0].id}`).click();
  await expect(page.getByTestId('suite-notice')).toContainText('成员信息已保存');
  await page.getByTestId('suite-upload').setInputFiles(textFile('补充要求.txt', '文件编号：EX-01\n版本：B/2\n补充要求\n适用范围：测试产品的补充控制要求。核对相关记录与实际实施证据，保留原始受控依据。'));
  await expect(page.getByTestId('suite-items')).toContainText('补充要求.txt');
  const inspection = page.waitForResponse(r => r.url().endsWith('/inspections'));
  await page.getByTestId('suite-inspect').click();
  expect((await inspection).status()).toBe(200);
  await expect(page.getByTestId('suite-inspection')).toContainText('文本检查完成');
  const download = page.waitForEvent('download');
  await page.getByTestId('suite-download').click();
  const archive = await download;
  expect(archive.suggestedFilename()).toContain('.zip');
  const output = testInfo.outputPath('ManualSuite.zip');
  await archive.saveAs(output);
  const verified = spawnSync(process.env.E2E_PYTHON!, [resolve('tests/Helpers/SuiteArchive.py'), first.suite_uid, output], { encoding: 'utf-8', env: process.env });
  expect(verified.status, verified.stdout + verified.stderr).toBe(0);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByTestId('suite-download')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('ManualSuiteMobile.png') });
  // 页面重新打开后从数据库恢复已保存的21份文件。
  await page.getByTestId('suite-back').click();
  await page.getByTestId('suites-nav').click();
  await page.getByTestId(`suite-open-${first.suite_uid}`).click();
  await expect(page.getByTestId('suite-items')).toContainText('补充要求.txt');
  await page.getByTestId('suite-new').click();
  await page.getByTestId('suite-name').fill('测试整套体系');
  await page.getByTestId('suite-version').fill('A/1');
  await page.getByTestId('suite-create').click();
  await expect(page.getByTestId('suite-items')).not.toContainText('补充要求.txt');
  const base = process.env.E2E_API_BASE_URL!;
  const old = (await (await page.request.get(`${base}/api/v1/manual-suites/${first.suite_uid}`)).json()).data;
  expect(old.items.length).toBe(21); expect(old.version).toBe('A/0');
  await page.getByTestId('suite-filter-version').fill('A/0');
  await page.getByTestId('suite-search').click();
  await expect(page.getByTestId('suite-list')).toContainText('A/0');
  await expect(page.getByTestId('suite-list')).not.toContainText('A/1');
  await clean();
});

test('重复版本、过期操作及跨用户访问被拒绝且不改写内容', async ({ page, browser }) => {
  const clean = watchPage(page);
  await login(page);
  const base = process.env.E2E_API_BASE_URL!;
  const data = { name: '版本边界测试', version: '01' };
  const created = await page.request.post(`${base}/api/v1/manual-suites`, { data });
  expect(created.status()).toBe(200);
  const suite = (await created.json()).data;
  const duplicate = await page.request.post(`${base}/api/v1/manual-suites`, { data });
  expect(duplicate.status()).toBe(409); expect((await duplicate.json()).code).toBe(1803);
  const stale = await page.request.post(`${base}/api/v1/manual-suites/${suite.suite_uid}/generations`, { data: {
    revision: 2, catalog_keys: ['quality-manual'], parameters: { company: '测试', project: '测试', product: '测试', model: '测试', requirements: '已知输入' },
  } });
  expect(stale.status()).toBe(409); expect((await stale.json()).code).toBe(1802);
  const context = await browser.newContext();
  const auth = await context.request.post(`${base}/api/v1/auth/login`, { data: { email: process.env.E2E_OTHER_EMAIL, password: process.env.E2E_OTHER_PASSWORD } });
  expect(auth.status()).toBe(200);
  const denied = await context.request.get(`${base}/api/v1/manual-suites/${suite.suite_uid}`);
  expect(denied.status()).toBe(403); expect((await denied.json()).code).toBe(1104);
  await context.close();
  const unchanged = (await (await page.request.get(`${base}/api/v1/manual-suites/${suite.suite_uid}`)).json()).data;
  expect(unchanged.items).toEqual([]); expect(unchanged.revision).toBe(1);
  await clean();
});

test('目录校正和移出使旧检查失效，并发变更只允许一个成功', async ({ page }) => {
  const clean = watchPage(page);
  await login(page);
  await page.getByTestId('suites-nav').click();
  await page.getByTestId('suite-name').fill('校正与并发测试');
  await page.getByTestId('suite-version').fill('B/0');
  await page.getByTestId('suite-create').click();
  const imported = page.waitForResponse(r => r.url().endsWith('/imports'));
  await page.getByTestId('suite-upload').setInputFiles(textFile('待归类.txt'));
  const suite = (await (await imported).json()).data;
  const id = suite.items[0].id;
  await expect(page.getByTestId('suite-items')).toContainText('待归类.txt');
  await page.getByTestId('suite-inspect').click();
  await expect(page.getByTestId('suite-inspection')).toBeVisible();
  await page.getByTestId(`suite-item-key-${id}`).selectOption('document-control');
  await page.getByTestId(`suite-item-version-${id}`).fill('B/2');
  await page.getByTestId(`suite-save-${id}`).click();
  await expect(page.getByTestId('suite-notice')).toContainText('成员信息已保存');
  await expect(page.getByTestId('suite-inspection')).toHaveCount(0);
  const base = `${process.env.E2E_API_BASE_URL!}/api/v1/manual-suites/${suite.suite_uid}`;
  const current = (await (await page.request.get(base)).json()).data;
  expect(current.items[0].file_version).toBe('B/2'); expect(current.items[0].document_type).toBe('procedure');
  const mutations = await Promise.all(['B/3', 'B/4'].map(file_version => page.request.patch(`${base}/items/${id}`, { data: {
    revision: current.revision, catalog_key: 'document-control', file_version,
  } })));
  expect(mutations.map(response => response.status()).sort()).toEqual([200, 409]);
  const rejected = mutations.find(response => response.status() === 409)!;
  expect((await rejected.json()).code).toBe(1802);
  await page.getByTestId('suite-reload').click();
  await expect(page.getByTestId('suite-notice')).toBeEmpty();
  await page.getByTestId(`suite-remove-${id}`).click();
  await expect(page.getByTestId('suite-items')).not.toContainText('待归类.txt');
  const final = (await (await page.request.get(base)).json()).data;
  expect(final.items).toEqual([]); expect(final.inspection).toBeNull();
  await clean();
});

test('清空目录后可手动勾选单份生成，失败输入不创建成员', async ({ page }) => {
  const clean = watchPage(page);
  await login(page);
  await page.getByTestId('suites-nav').click();
  await page.getByTestId('suite-name').fill('自选目录测试');
  await page.getByTestId('suite-version').fill('01');
  await page.getByTestId('suite-create').click();
  await page.getByTestId('suite-select-none').click();
  await expect(page.getByTestId('suite-generate')).toBeDisabled();
  await page.getByTestId('suite-catalog-quality-manual').check();
  await expect(page.getByTestId('suite-generate')).toBeEnabled();
  for (const [key, value] of Object.entries({ company: '测试组织', project: '自选目录', product: '测试产品', model: 'MODEL-A', requirements: '经确认的产品资料与体系输入' })) {
    await page.getByTestId(`suite-parameter-${key}`).fill(value);
  }
  const generated = page.waitForResponse(r => r.url().endsWith('/generations'));
  await page.getByTestId('suite-generate').click();
  const result = (await (await generated).json()).data;
  expect(result.items).toHaveLength(1);
  expect(result.items[0].catalog_key).toBe('quality-manual');
  const base = `${process.env.E2E_API_BASE_URL!}/api/v1/manual-suites/${result.suite_uid}`;
  const invalid = await page.request.post(`${base}/generations`, { data: { revision: result.revision, catalog_keys: ['does-not-exist'], parameters: {} } });
  expect(invalid.status()).toBe(400); expect((await invalid.json()).code).toBe(1001);
  const unchanged = (await (await page.request.get(base)).json()).data;
  expect(unchanged.items).toHaveLength(1); expect(unchanged.revision).toBe(result.revision);
  await clean();
});
