import { request, type User } from '../Api';

export interface RegistrationInput {
  email: string;
  display_name: string;
  password: string;
  password_confirmation: string;
}

export function register(input: RegistrationInput): Promise<User> {
  return request<User>('/api/v1/auth/register', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input),
  });
}
