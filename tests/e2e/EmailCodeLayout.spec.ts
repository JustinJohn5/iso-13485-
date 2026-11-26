import { expect, test, type Page } from '@playwright/test';
import { login, watchPage } from './Helpers';

async function checkCodeLayout(page: Page, prefix: string): Promise<void> {
  for (const width of [1898, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    const input = page.getByTestId(`${prefix}-code`);
    const button = page.getByTestId(`${prefix}-send-code`);
    await expect(input).toBeVisible();
    await expect(button).toBeVisible();
    const field = (await input.boundingBox())!;
    const action = (await button.boundingBox())!;
    expect(field.width).toBeGreaterThanOrEqual(120);
    expect(action.width).toBeLessThanOrEqual(160);
    expect(field.x + field.width).toBeLessThanOrEqual(action.x - 7);
    expect(action.x + action.width).toBeLessThanOrEqual(width);
    await input.fill('012345');
    await expect(input).toHaveValue('012345');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
}

test('注册验证码输入框与发送按钮在桌面和窄屏均完整可用', async ({ page }) => {
  const verify = watchPage(page);
  await page.goto(process.env.E2E_BASE_URL!);
  await page.getByTestId('show-register').click();
  await checkCodeLayout(page, 'register');
  await verify();
});

test('修改密码验证码输入框与发送按钮在桌面和窄屏均完整可用', async ({ page }) => {
  const verify = watchPage(page);
  await login(page);
  await page.getByTestId('change-password-nav').click();
  await checkCodeLayout(page, 'password');
  await verify();
});
