import { expect, test, type Page } from '@playwright/test';
import { watchPage } from './Helpers';
import { inboxCode, testEmail, verificationDatabase } from './EmailHelpers';
import { rateLimitDatabase } from './RateLimitHelpers';

const registerPath = '/api/v1/auth/register';
const sendPath = '/api/v1/auth/registration-codes';
const password = 'RegisterPass2026';
const newPassword = 'ChangedPass2026';

async function registration(page: Page, email: string): Promise<void> {
  await page.goto(process.env.E2E_BASE_URL!);
  await page.getByTestId('show-register').click();
  await page.getByTestId('register-name').fill('注册测试用户');
  await page.getByTestId('register-email').fill(email);
  await page.getByTestId('register-password').fill(password);
  await page.getByTestId('register-confirm').fill(password);
}

test('验证码只出现在注册和改密，真实 SMTP 测试收件箱完成注册和改密后旧会话失效', async ({ page, browser }) => {
  const verify = watchPage(page, [{ path: '/api/v1/auth/password', status: 400, code: 1112 }]);
  const email = testEmail();
  const base = process.env.E2E_API_BASE_URL!;
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(process.env.E2E_BASE_URL!);
  await expect(page.getByTestId('register-code')).toHaveCount(0);
  await expect(page.getByTestId('login-form')).toBeVisible();
  await registration(page, email);
  const sent = page.waitForResponse(r => r.url().endsWith(sendPath));
  await page.getByTestId('register-send-code').click();
  expect((await sent).status()).toBe(200);
  await expect(page.getByTestId('verification-notice')).toContainText('如邮箱可用于此操作');
  await expect(page.getByTestId('register-send-code')).toBeDisabled();
  await expect(page.getByTestId('register-password')).toHaveValue(password);
  await page.getByTestId('register-code').fill(inboxCode(email));
  await page.getByTestId('register-submit').click();
  await expect(page.getByTestId('login-success')).toContainText('注册成功');
  await expect(page.getByTestId('register-code')).toHaveCount(0);
  await page.getByTestId('login-password').fill(password);
  await page.getByTestId('login-submit').click();
  await expect(page.getByTestId('upload-dropzone')).toBeVisible();
  expect(verificationDatabase(email, 'state')).toMatchObject({ used: true });

  const otherContext = await browser.newContext();
  try {
    const login = await otherContext.request.post(base + '/api/v1/auth/login', { data: { email, password } });
    expect(login.status()).toBe(200);
    await page.getByTestId('change-password-nav').click();
    await expect(page.getByTestId('password-email')).toHaveText(email);
    const passwordCodeResponse = page.waitForResponse(r => r.url().endsWith('/api/v1/auth/password-change-codes'));
    await page.getByTestId('password-send-code').click();
    expect((await passwordCodeResponse).status()).toBe(200);
    await page.getByTestId('password-code').fill(inboxCode(email));
    await page.getByTestId('password-current').fill('IncorrectPass2026');
    await page.getByTestId('password-new').fill(newPassword);
    await page.getByTestId('password-confirm').fill(newPassword);
    const rejected = page.waitForResponse(r => r.url().endsWith('/api/v1/auth/password'));
    await page.getByTestId('password-submit').click();
    expect((await rejected).status()).toBe(400);
    await expect(page.getByTestId('password-error')).toContainText('当前密码');
    await page.getByTestId('password-current').fill(password);
    await page.getByTestId('password-new').fill(newPassword);
    await page.getByTestId('password-confirm').fill(newPassword);
    await expect(page.getByTestId('password-code')).toHaveValue(inboxCode(email));
    await page.getByTestId('password-submit').click();
    await expect(page.getByTestId('login-success')).toContainText('密码已修改');
    verificationDatabase(email, 'password', 'password_change', newPassword);
    expect(verificationDatabase(email, 'state', 'password_change')).toMatchObject({ used: true });
    expect((await otherContext.request.get(base + '/api/v1/auth/me')).status()).toBe(401);
    expect((await page.request.post(base + '/api/v1/auth/login', { data: { email, password } })).status()).toBe(401);
    await page.getByTestId('login-email').fill(email);
    await page.getByTestId('login-password').fill(newPassword);
    await page.getByTestId('login-submit').click();
    await expect(page.getByTestId('upload-dropzone')).toBeVisible();
    const replay = await page.request.patch(base + '/api/v1/auth/password', { data: {
      current_password: newPassword, password: 'ThirdPass2026', password_confirmation: 'ThirdPass2026',
      email_verification_code: inboxCode(email),
    } });
    expect(replay.status()).toBe(400);
    expect((await replay.json()).code).toBe(1108);
  } finally {
    await otherContext.close();
  }
  await verify();
});

test('无验证码和错误验证码不能创建账号，重发限流与五次失败失效由后端执行', async ({ page }) => {
  const verify = watchPage(page);
  const email = testEmail();
  const base = process.env.E2E_API_BASE_URL!;
  const data = { email, display_name: '注册测试用户', password, password_confirmation: password };
  expect((await page.request.post(base + registerPath, { data })).status()).toBe(400);
  const sent = await page.request.post(base + sendPath, { data: { email } });
  expect(sent.status()).toBe(200);
  const code = inboxCode(email);
  const retry = await page.request.post(base + sendPath, { data: { email } });
  expect(retry.status()).toBe(429);
  expect((await retry.json()).code).toBe(1109);
  const wrongCode = code === '000000' ? '111111' : '000000';
  for (let attempt = 0; attempt < 5; attempt++) {
    const wrong = await page.request.post(base + registerPath, { data: { ...data, email_verification_code: wrongCode } });
    expect(wrong.status()).toBe(400);
    expect((await wrong.json()).code).toBe(1108);
  }
  const expired = await page.request.post(base + registerPath, { data: { ...data, email_verification_code: code } });
  expect(expired.status()).toBe(400);
  expect((await expired.json()).code).toBe(1108);
  expect(verificationDatabase(email, 'state')).toMatchObject({ attempts: 5, expired: true, used: false });
  verificationDatabase(email, 'no-user');
  await verify();
});

test('过期与重发旧码不能注册，其他邮箱与注册用途的验证码不能改密', async ({ page }) => {
  const verify = watchPage(page);
  const base = process.env.E2E_API_BASE_URL!;
  const email = testEmail();
  const other = testEmail();
  const data = { email, display_name: '注册测试用户', password, password_confirmation: password };
  expect((await page.request.post(base + sendPath, { data: { email } })).status()).toBe(200);
  const originalCode = inboxCode(email);
  verificationDatabase(email, 'expire');
  expect((await page.request.post(base + registerPath, { data: { ...data, email_verification_code: originalCode } })).status()).toBe(400);
  verificationDatabase(email, 'no-user');
  verificationDatabase(email, 'age');
  expect((await page.request.post(base + sendPath, { data: { email } })).status()).toBe(200);
  const code = inboxCode(email);
  expect(code).not.toBe(originalCode);
  expect((await page.request.post(base + registerPath, { data: { ...data, email_verification_code: originalCode } })).status()).toBe(400);
  expect((await page.request.post(base + sendPath, { data: { email: other } })).status()).toBe(200);
  expect((await page.request.post(base + registerPath, { data: { ...data, email: other, email_verification_code: code } })).status()).toBe(400);
  verificationDatabase(other, 'no-user');
  expect((await page.request.post(base + registerPath, { data: { ...data, email_verification_code: code } })).status()).toBe(201);
  expect((await page.request.post(base + '/api/v1/auth/login', { data: { email, password } })).status()).toBe(200);
  const denied = await page.request.patch(base + '/api/v1/auth/password', { data: {
    current_password: password, password: newPassword, password_confirmation: newPassword, email_verification_code: code,
  } });
  expect(denied.status()).toBe(400);
  expect((await denied.json()).code).toBe(1108);
  expect((await page.request.post(base + '/api/v1/auth/login', { data: { email, password } })).status()).toBe(200);
  await verify();
});

test('公开注册验证码接口不暴露邮箱是否已注册', async ({ page }) => {
  const base = process.env.E2E_API_BASE_URL!;
  const existingEmail = process.env.E2E_EMAIL!;
  const newEmail = testEmail();
  const existing = await page.request.post(base + sendPath, { data: { email: existingEmail } });
  const fresh = await page.request.post(base + sendPath, { data: { email: newEmail } });

  expect(existing.status()).toBe(fresh.status());
  expect(await existing.json()).toEqual(await fresh.json());
  expect(existing.status()).toBe(200);

  const duplicate = await page.request.post(base + registerPath, { data: {
    email: existingEmail,
    display_name: '重复注册探测',
    password,
    password_confirmation: password,
    email_verification_code: '000000',
  } });
  expect(duplicate.status()).toBe(400);
  expect((await duplicate.json()).code).toBe(1108);
});

test('来源 IP 达到发送上限后拒绝新验证码请求', async ({ page }) => {
  const base = process.env.E2E_API_BASE_URL!;
  const address = testEmail();
  const prefix = process.env.E2E_REGISTRATION_PREFIX!.replace('reg-', '');
  const ipAddress = `198.18.${Number.parseInt(prefix.slice(0, 2), 16)}.${Math.max(1, Number.parseInt(prefix.slice(2, 4), 16) % 254)}`;
  rateLimitDatabase(ipAddress, 'exhaust');
  try {
    const limited = await page.request.post(base + sendPath, {
      data: { email: address },
      headers: { 'X-Forwarded-For': ipAddress },
    });
    expect(limited.status()).toBe(429);
    expect((await limited.json()).code).toBe(1109);
    verificationDatabase(address, 'no-user');
    verificationDatabase(address, 'no-challenge');
  } finally {
    rateLimitDatabase(ipAddress, 'clear');
  }
});
