import { expect, type Download, type Page } from '@playwright/test';
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';

export const manualText = '某公司 质量手册\n文件编号：QM-01\n版本：01\n编制：质量部门 审核：质量经理 批准：负责人\n2020年02月01日发布\n适用范围：本质量管理体系适用于医疗器械产品的设计与生产。';

export function watchPage(page: Page, expected: Array<{ path: string; status: number; code: number }> = []) {
  const errors: string[] = [];
  const initialAuth: Promise<void>[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => {
    if (message.type() !== 'error') return;
    const allowed = [{ path: '/api/v1/auth/me', status: 401, code: 1103 }, ...expected];
    const expectedError = allowed.some((item) => message.location().url.endsWith(item.path) && message.text().includes(String(item.status)));
    if (!expectedError) errors.push(`${message.location().url}: ${message.text()}`);
  });
  page.on('response', (response) => {
    if (response.status() < 400) return;
    const allowed = [{ path: '/api/v1/auth/me', status: 401, code: 1103 }, ...expected];
    const match = allowed.find((item) => response.url().endsWith(item.path) && response.status() === item.status);
    if (match) {
      initialAuth.push(response.json().then((body) => { expect(body.code).toBe(match.code); }));
    } else errors.push(`${response.status()} ${response.url()}`);
  });
  return async () => { await Promise.all(initialAuth); expect(errors).toEqual([]); };
}

export async function login(page: Page) {
  const email = process.env.E2E_EMAIL;
  const password = process.env.E2E_PASSWORD;
  if (!email || !password || !process.env.E2E_BASE_URL) throw new Error('请使用独立测试环境运行 E2E');
  await page.goto(process.env.E2E_BASE_URL);
  await page.getByTestId('login-email').fill(email);
  await page.getByTestId('login-password').fill(password);
  await page.getByTestId('login-submit').click();
  await expect(page.getByTestId('upload-dropzone')).toBeVisible();
}

export async function verifyWordDownload(download: Download, path: string, model: string, revision: number) {
  await download.saveAs(path);
  const result = spawnSync(process.env.E2E_PYTHON!, [resolve('tests/Helpers/WordDownload.py'), path, model, String(revision)], {
    encoding: 'utf-8', env: process.env,
  });
  expect(result.status, result.stdout + result.stderr).toBe(0);
}

export function textFile(name: string, text = manualText) {
  return { name, mimeType: 'text/plain', buffer: Buffer.from(text) };
}

export function docxFile() {
  const result = spawnSync(process.env.E2E_PYTHON!, [resolve('tests/Helpers/DocumentFixture.py')]);
  expect(result.status, result.stderr.toString()).toBe(0);
  return { name: '质量管理体系手册.docx', mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', buffer: result.stdout };
}

export function currentRunCount(): number {
  const result = spawnSync(process.env.E2E_PYTHON!, [resolve('tests/Helpers/E2eDatabase.py'), '--count'], { encoding: 'utf-8', env: process.env });
  expect(result.status, result.stdout + result.stderr).toBe(0);
  return Number(result.stdout.trim());
}

export function verifyReviewSnapshot(runUid: string, selectedUid: string, excludedUid: string) {
  const result = spawnSync(process.env.E2E_PYTHON!, [resolve('tests/Helpers/E2eDatabase.py'), '--review', runUid, selectedUid, excludedUid], { encoding: 'utf-8', env: process.env });
  expect(result.status, result.stdout + result.stderr).toBe(0);
}

export async function analyze(page: Page) {
  await expect(page.getByTestId('analyze-button')).toBeEnabled();
  const response = page.waitForResponse((item) => item.url().endsWith('/api/v1/validations') && item.request().method() === 'POST');
  await page.getByTestId('analyze-button').click();
  const received = await response;
  expect(received.status()).toBe(200);
  const body = await received.json();
  expect(body.code).toBe(0);
  await expect(page.getByTestId('results-title')).toBeVisible();
  return body.data;
}

export function verifyDatabase(runUid: string, documentCount: number, expectedType: string) {
  const python = process.env.E2E_PYTHON;
  if (!python) throw new Error('缺少测试数据库验证解释器配置');
  const result = spawnSync(python, [resolve('tests/Helpers/E2eDatabase.py'), runUid, String(documentCount), expectedType], {
    encoding: 'utf-8', env: process.env,
  });
  expect(result.status, result.stdout + result.stderr).toBe(0);
}
