import { expect, test, type Page } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';
import { watchPage } from './Helpers';
import { inboxCode } from './EmailHelpers';

const password = 'RegisterPass2026';
const endpoint = '/api/v1/auth/register';

function email(): string {
  if (!process.env.E2E_REGISTRATION_PREFIX) throw new Error('请通过隔离测试入口运行注册测试');
  return `${process.env.E2E_REGISTRATION_PREFIX}-${randomUUID()}@example.com`;
}

function database(address: string, count = 1): void {
  const result = spawnSync(process.env.E2E_PYTHON!, [resolve('tests/Helpers/RegistrationDatabase.py'), address, String(count)], {
    encoding: 'utf-8', env: process.env,
  });
  expect(result.status, result.stdout + result.stderr).toBe(0);
}

async function form(page: Page, address: string): Promise<void> {
  await page.goto(process.env.E2E_BASE_URL!);
  await page.getByTestId('show-register').click();
  await page.getByTestId('register-name').fill('注册测试用户');
  await page.getByTestId('register-email').fill(address);
  await page.getByTestId('register-password').fill(password);
  await page.getByTestId('register-confirm').fill(password);
  const sent = page.waitForResponse(r => r.url().endsWith('/api/v1/auth/registration-codes'));
  await page.getByTestId('register-send-code').click();
  expect((await sent).status()).toBe(200);
  await page.getByTestId('register-code').fill(inboxCode(address));
}

test('可在手机注册普通账号并登录，Cookie保持登录且无管理员权限', async ({ page }) => {
  const verify = watchPage(page, [{ path: '/api/v1/llm-settings', status: 403, code: 1104 }]);
  const address = email();
  await page.setViewportSize({ width: 390, height: 844 });
  await form(page, address.toUpperCase());
  const registered = page.waitForResponse(r => r.url().endsWith(endpoint));
  await page.getByTestId('register-submit').click();
  const response = await registered;
  expect(response.status()).toBe(201);
  const body = await response.json();
  expect(body.data).toMatchObject({ email: address, display_name: '注册测试用户', role: 'auditor' });
  expect(Object.keys(body.data).sort()).toEqual(['display_name', 'email', 'id', 'role']);
  expect(response.headers()['set-cookie']).toBeUndefined();
  await expect(page.getByTestId('login-success')).toContainText('注册成功');
  await expect(page.getByTestId('login-email')).toHaveValue(address);
  await expect(page.getByTestId('login-password')).toHaveValue('');
  database(address);
  await page.getByTestId('login-password').fill(password);
  const loggedIn = page.waitForResponse(r => r.url().endsWith('/api/v1/auth/login'));
  await page.getByTestId('login-submit').click();
  expect((await loggedIn).status()).toBe(200);
  await expect(page.getByTestId('upload-dropzone')).toBeVisible();
  await expect(page.getByTestId('llm-settings-nav')).toHaveCount(0);
  const cookies = await page.context().cookies(process.env.E2E_API_BASE_URL!);
  expect(cookies.find(c => c.name === (process.env.ACCESS_TOKEN_COOKIE_NAME || 'iso_access_token'))).toMatchObject({ httpOnly: true, sameSite: 'Lax' });
  await page.reload();
  await expect(page.getByTestId('upload-dropzone')).toBeVisible();
  await page.getByTestId('suites-nav').click();
  await expect(page.getByTestId('suite-create')).toBeVisible();
  const denied = await page.request.get(`${process.env.E2E_API_BASE_URL}/api/v1/llm-settings`);
  expect(denied.status()).toBe(403);
  expect((await denied.json()).code).toBe(1104);
  await page.getByTestId('suite-back').click();
  await page.getByTestId('logout').click();
  await expect(page.getByTestId('login-form')).toBeVisible();
  await verify();
});

test('两次密码不一致或强度不足时保留表单，重复邮箱不创建重复账号', async ({ page }) => {
  const verify = watchPage(page, [{ path: endpoint, status: 400, code: 1108 }]);
  const address = email();
  let requests = 0;
  page.on('request', r => { if (r.url().endsWith(endpoint)) requests += 1; });
  await form(page, address);
  await page.getByTestId('register-confirm').fill('OtherPass2026');
  await page.getByTestId('register-submit').click();
  await expect(page.getByTestId('auth-error')).toContainText('两次密码不一致');
  await page.getByTestId('register-password').fill('12345678');
  await page.getByTestId('register-confirm').fill('12345678');
  await page.getByTestId('register-submit').click();
  await expect(page.getByTestId('auth-error')).toContainText('字母和数字');
  expect(requests).toBe(0);
  database(address, 0);
  await page.getByTestId('register-password').fill(password);
  await page.getByTestId('register-confirm').fill(password);
  await page.getByTestId('register-submit').click();
  await expect(page.getByTestId('login-success')).toBeVisible();
  await page.getByTestId('show-register').click();
  await page.getByTestId('register-name').fill('重复注册');
  await page.getByTestId('register-email').fill(address.toUpperCase());
  await page.getByTestId('register-password').fill(password);
  await page.getByTestId('register-confirm').fill(password);
  await page.getByTestId('register-code').fill('000000');
  const duplicate = page.waitForResponse(r => r.url().endsWith(endpoint));
  await page.getByTestId('register-submit').click();
  expect((await duplicate).status()).toBe(400);
  await expect(page.getByTestId('auth-error')).toContainText('验证码');
  await expect(page.getByTestId('register-name')).toHaveValue('重复注册');
  await expect(page.getByTestId('register-password')).toHaveValue('');
  await expect(page.getByTestId('register-submit')).toBeEnabled();
  database(address);
  await page.getByTestId('show-login').click();
  await expect(page.getByTestId('login-form')).toBeVisible();
  await verify();
});

test('服务端拒绝弱密码、错误确认和权限字段，并发同邮箱只有一次成功', async ({ page }) => {
  const verify = watchPage(page);
  const address = email();
  const sent = await page.request.post(process.env.E2E_API_BASE_URL + '/api/v1/auth/registration-codes', { data: { email: address } });
  expect(sent.status()).toBe(200);
  const data = { email: address, display_name: '注册测试用户', password, password_confirmation: password, email_verification_code: inboxCode(address) };
  for (const changes of [{ password: '12345678', password_confirmation: '12345678' },
    { password_confirmation: 'OtherPass2026' }, { role: 'admin' }, { email: 'invalid' }, { display_name: '   ' }]) {
    const rejected = await page.request.post(`${process.env.E2E_API_BASE_URL}${endpoint}`, { data: { ...data, ...changes } });
    expect(rejected.status()).toBe(400);
    expect((await rejected.json()).code).toBe(1001);
  }
  database(address, 0);
  const responses = await Promise.all([1, 2].map(() => page.request.post(`${process.env.E2E_API_BASE_URL}${endpoint}`, { data })));
  expect(responses.filter(r => r.status() === 201)).toHaveLength(1);
  for (const response of responses) {
    if (response.status() === 201) expect((await response.json()).code).toBe(0);
    else {
      expect(response.status()).toBe(400);
      expect((await response.json()).code).toBe(1108);
    }
  }
  database(address);
  await verify();
});
