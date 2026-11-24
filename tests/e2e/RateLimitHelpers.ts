import { expect } from '@playwright/test';
import { resolve } from 'node:path';
import { spawnSync } from 'node:child_process';

export function rateLimitDatabase(ipAddress: string, action: 'exhaust' | 'clear'): void {
  const result = spawnSync(process.env.E2E_PYTHON!, [resolve('tests/Helpers/RateLimitDatabase.py'), ipAddress, action], {
    encoding: 'utf-8', env: process.env,
  });
  expect(result.status, result.stdout + result.stderr).toBe(0);
}
