import { request, type User } from '../Api';

export interface RegistrationInput {
  email: string;
  display_name: string;
  password: string;
  password_confirmation: string;
  email_verification_code: string;
}

export interface CodeDeliveryInfo {
  expires_in_seconds: number;
  resend_after_seconds: number;
}

export function sendRegistrationCode(email: string): Promise<CodeDeliveryInfo> {
  return request<CodeDeliveryInfo>('/api/v1/auth/registration-codes', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email }),
  });
}

export function sendPasswordChangeCode(): Promise<CodeDeliveryInfo> {
  return request<CodeDeliveryInfo>('/api/v1/auth/password-change-codes', { method: 'POST' });
}

export function changePassword(input: Omit<RegistrationInput, 'email' | 'display_name'> & { current_password: string }): Promise<null> {
  return request<null>('/api/v1/auth/password', {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input),
  });
}

export function register(input: RegistrationInput): Promise<User> {
  return request<User>('/api/v1/auth/register', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input),
  });
}
