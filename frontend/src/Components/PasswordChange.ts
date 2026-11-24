import type { User } from '../Api';
import { changePassword, sendPasswordChangeCode } from '../Api/Registration';
import { escape } from '../Utils/Html';
import { bindEmailCode, emailCodeFields, type EmailCodeState } from './EmailCode';
import '../Authentication.css';

export class PasswordChangePage {
  private busy = false;
  private codeState: EmailCodeState = { until: 0 };

  constructor(private root: HTMLElement, private user: User, private back: () => void,
    private changed: () => void) {}

  open(): void {
    this.root.innerHTML = '<main class="login-page"><section class="login-panel">' +
      '<div class="brand-mark">Q</div><p class="eyebrow">账号安全</p><h1>修改密码</h1>' +
      '<p class="login-copy">验证码将发送到当前账号的邮箱。修改成功后请重新登录。</p>' +
      '<form class="login-form" data-testid="password-form">' +
      '<label>账号邮箱<span class="password-email" data-testid="password-email">' + escape(this.user.email) + '</span></label>' +
      '<label>当前密码<input data-testid="password-current" name="current_password" type="password" autocomplete="current-password" required maxlength="72"></label>' +
      '<label>新密码<input data-testid="password-new" name="password" type="password" autocomplete="new-password" required maxlength="72"></label>' +
      '<p class="auth-help">8～72位，须包含字母和数字；编码后不超过72字节。</p>' +
      '<label>确认新密码<input data-testid="password-confirm" name="password_confirmation" type="password" autocomplete="new-password" required maxlength="72"></label>' +
      emailCodeFields('password') +
      '<p class="form-error" data-testid="password-error" role="alert"></p>' +
      '<button class="button button-primary" data-testid="password-submit" type="submit">确认修改密码</button></form>' +
      '<p class="auth-switch"><button data-testid="password-back" class="text-button" type="button">返回工作区</button></p>' +
      '</section><aside class="login-aside"><div class="aside-rule"></div><span>账号安全</span></aside></main>';
    bindEmailCode(this.root, 'password', this.codeState, sendPasswordChangeCode,
      message => { this.root.querySelector('[data-testid="password-error"]')!.textContent = message; });
    this.root.querySelector('[data-testid="password-back"]')!.addEventListener('click', this.back);
    this.root.querySelector('form')!.addEventListener('submit', event => { event.preventDefault(); void this.submit(); });
  }

  private async submit(): Promise<void> {
    if (this.busy) return;
    const form = this.root.querySelector<HTMLFormElement>('form')!;
    const data = new FormData(form);
    const password = String(data.get('password'));
    const confirmation = String(data.get('password_confirmation'));
    const error = this.root.querySelector('[data-testid="password-error"]')!;
    if (password !== confirmation) { error.textContent = '两次密码不一致'; return; }
    if (password.length < 8 || password.length > 72 || !/[A-Za-z]/.test(password) || !/\d/.test(password)) {
      error.textContent = '密码需为8～72位，且同时包含字母和数字'; return;
    }
    if (new TextEncoder().encode(password).length > 72) {
      error.textContent = '密码编码后超过72字节，请缩短密码'; return;
    }
    this.busy = true; error.textContent = '';
    form.dataset.busy = 'true';
    const controls = this.root.querySelectorAll<HTMLInputElement | HTMLButtonElement>('input, button');
    controls.forEach(control => { control.disabled = true; });
    try {
      await changePassword({ current_password: String(data.get('current_password')), password,
        password_confirmation: confirmation, email_verification_code: String(data.get('email_verification_code')) });
      this.changed();
    } catch (failure) {
      error.textContent = failure instanceof Error ? failure.message : '修改失败，请稍后重试';
      form.querySelectorAll<HTMLInputElement>('input[type="password"]').forEach(input => { input.value = ''; });
    } finally {
      this.busy = false;
      delete form.dataset.busy;
      controls.forEach(control => {
        control.disabled = control.dataset.testid === 'password-send-code' && this.codeState.until > Date.now();
      });
    }
  }
}
