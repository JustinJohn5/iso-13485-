import { expect, test, type Page } from '@playwright/test';
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';
import { currentRunCount, login, textFile, watchPage } from './Helpers';

async function createGroup(page: Page, files: string[] = []): Promise<string> {
  const api = process.env.E2E_API_BASE_URL!;
  const created = await page.request.post(`${api}/api/v1/my/file-groups`, { data: { name: `快捷分组-${crypto.randomUUID()}` } });
  expect(created.status()).toBe(200);
  const uid = (await created.json()).data.group_uid as string;
  if (files.length) {
    const members = await page.request.post(`${api}/api/v1/my/file-groups/${uid}/members`, { data: { file_uids: files } });
    expect(members.status()).toBe(200);
  }
  return uid;
}

async function openGroups(page: Page, uid: string) {
  await page.getByTestId('account-menu-button').click();
  await page.getByTestId('account-groups').click();
  const card = page.getByTestId(`group-row-${uid}`);
  await expect(card).toBeVisible();
  return card;
}

test('分组上传自动入组且下载完整原件，整组载入保留范围与已有用途且不自动预筛', async ({ page }, info) => {
  const verify = watchPage(page);
  await login(page);
  await page.getByTestId('upload-files').setInputFiles(textFile('已有记录.txt', '文件编号：REC-OLD\n原有记录'));
  await expect(page.getByTestId('document-purpose-0')).toBeEnabled();
  await page.getByTestId('document-purpose-0').selectOption('record');
  await page.getByTestId('prescreen-scope').selectOption('system');
  await page.getByTestId('prescreen-scope-description').fill('采购与生产过程质量管理体系');
  const before = currentRunCount();
  const uid = await createGroup(page);
  const card = await openGroups(page, uid);
  const contents = ['文件编号：QP-A\n原件甲', '文件编号：QP-B\n原件乙'];
  await expect(card.getByTestId('group-upload')).toBeEnabled();
  await card.getByTestId('group-upload-input').setInputFiles(contents.map(text => textFile('同名程序.txt', text)));
  await expect(card).toContainText('2 份文件');
  await expect(page.getByTestId('group-notice')).toContainText('已上传 2 份文件');
  const members = await page.request.get(`${process.env.E2E_API_BASE_URL}/api/v1/my/files?group_uid=${uid}&page=1&page_size=100`);
  expect(members.status()).toBe(200);
  const grouped = (await members.json()).data;
  expect(grouped.total).toBe(2);
  expect(grouped.items.every((file: { groups: Array<{ group_uid: string }> }) => file.groups.some(group => group.group_uid === uid))).toBe(true);
  const downloading = page.waitForEvent('download');
  await card.getByTestId('group-download').click();
  const download = await downloading;
  expect(download.suggestedFilename()).toMatch(/\.zip$/);
  const archive = info.outputPath('分组原件.zip');
  await download.saveAs(archive);
  const checked = spawnSync(process.env.E2E_PYTHON!, [resolve('tests/Helpers/GroupArchive.py'), archive, JSON.stringify(contents)], { encoding: 'utf-8' });
  expect(checked.status, checked.stdout + checked.stderr).toBe(0);
  await card.getByTestId('group-prescreen').click();
  await expect(page.getByTestId('upload-dropzone')).toBeVisible();
  await expect(page.getByTestId('document-purpose-2')).toBeVisible();
  await expect(page.getByTestId('document-purpose-3')).toHaveCount(0);
  await expect(page.getByTestId('document-purpose-0')).toHaveValue('record');
  await expect(page.getByTestId('prescreen-scope')).toHaveValue('system');
  await expect(page.getByTestId('prescreen-scope-description')).toHaveValue('采购与生产过程质量管理体系');
  await expect(page.getByTestId('results-title')).toHaveCount(0);
  expect(currentRunCount()).toBe(before);
  await expect(page.getByTestId('analyze-button')).toBeEnabled();
  await verify();
});

test('队列容量不足时整组不载入，原队列保留且不会静默截断', async ({ page }) => {
  const verify = watchPage(page);
  await login(page);
  await page.getByTestId('upload-files').setInputFiles(Array.from({ length: 19 }, (_, i) => textFile(`既有-${i}.txt`, `文件编号：OLD-${i}\n独立记录${i}`)));
  await expect(page.getByTestId('analyze-button')).toBeEnabled();
  const ids: string[] = [];
  for (let i = 0; i < 2; i++) {
    const response = await page.request.post(`${process.env.E2E_API_BASE_URL}/api/v1/documents`, { multipart: { file: textFile(`待加入-${i}.txt`) } });
    expect(response.status()).toBe(200);
    ids.push((await response.json()).data.file_uid);
  }
  const uid = await createGroup(page, ids);
  const card = await openGroups(page, uid);
  await card.getByTestId('group-prescreen').click();
  await expect(page.getByTestId('workspace-notice')).toContainText('超过 20 份');
  await expect(page.getByTestId('document-purpose-18')).toBeVisible();
  await expect(page.getByTestId('document-purpose-19')).toHaveCount(0);
  await verify();
});

test('空组和21份组明确拒绝整组预筛，空组拒绝打包下载', async ({ page }) => {
  await login(page);
  const uid = await createGroup(page);
  const base = `/api/v1/my/file-groups/${uid}`;
  const verify = watchPage(page, [
    { path: `${base}/selection`, status: 400, code: 1001 },
    { path: `${base}/download`, status: 400, code: 1001 },
  ]);
  const card = await openGroups(page, uid);
  await card.getByTestId('group-prescreen').click();
  await expect(page.getByTestId('group-error')).toContainText('分组为空');
  await card.getByTestId('group-download').click();
  await expect(page.getByTestId('group-error')).toContainText('分组为空');
  const ids: string[] = [];
  for (let i = 0; i < 21; i++) {
    const response = await page.request.post(`${process.env.E2E_API_BASE_URL}/api/v1/documents`, { multipart: { file: textFile(`容量-${i}.txt`) } });
    expect(response.status()).toBe(200);
    ids.push((await response.json()).data.file_uid);
  }
  const joined = await page.request.post(`${process.env.E2E_API_BASE_URL}${base}/members`, { data: { file_uids: ids } });
  expect(joined.status()).toBe(200);
  await card.getByTestId('group-prescreen').click();
  await expect(page.getByTestId('group-error')).toContainText('20');
  await expect(page.getByTestId('file-groups-page')).toBeVisible();
  await verify();
});

test('后台账户中的分组可跳转到预筛页载入整组', async ({ page }) => {
  const verify = watchPage(page);
  await login(page);
  const response = await page.request.post(`${process.env.E2E_API_BASE_URL}/api/v1/documents`, { multipart: { file: textFile('后台组程序.txt') } });
  expect(response.status()).toBe(200);
  const uid = await createGroup(page, [(await response.json()).data.file_uid]);
  await page.getByTestId('account-menu-button').click();
  await page.getByTestId('account-admin').click();
  await expect(page.getByTestId('admin-workspace')).toBeVisible();
  const card = await openGroups(page, uid);
  await card.getByTestId('group-prescreen').click();
  await expect(page.getByTestId('document-purpose-0')).toBeVisible();
  await expect(page).toHaveURL(process.env.E2E_BASE_URL! + '/');
  await expect(page.getByTestId('analyze-button')).toBeEnabled();
  await expect(page.getByTestId('results-title')).toHaveCount(0);
  await verify();
});
