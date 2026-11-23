import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL,
    channel: process.env.E2E_BROWSER_CHANNEL || undefined,
    trace: 'retain-on-failure',
  },
});
