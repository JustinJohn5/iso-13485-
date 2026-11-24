import { expect } from '@playwright/test';
import { createHash, randomUUID } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';

export function testEmail(): string {
  if (!process.env.E2E_REGISTRATION_PREFIX) throw new Error('请通过隔离测试入口运行注册测试');
  return process.env.E2E_REGISTRATION_PREFIX + '-' + randomUUID() + '@example.com';
}

export function inboxCode(email: string): string {
  const name = createHash('sha256').update(email.toLowerCase()).digest('hex') + '.json';
  const inbox = JSON.parse(readFileSync(join(process.env.E2E_MAIL_DIR!, name), 'utf-8'));
  expect(inbox.email).toBe(email.toLowerCase());
  expect(inbox.code).toMatch(/^[0-9]{6}$/);
  return inbox.code;
}

export function verificationDatabase(email: string, action: string, purpose = 'registration', value = ''): any {
  const result = spawnSync(process.env.E2E_PYTHON!, [resolve('tests/Helpers/VerificationDatabase.py'), email, action, purpose, value], {
    encoding: 'utf-8', env: process.env,
  });
  expect(result.status, result.stdout + result.stderr).toBe(0);
  return result.stdout.trim() ? JSON.parse(result.stdout.trim()) : undefined;
}
