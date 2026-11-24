import { api, type User } from '../Api';
import { register } from '../Api/Registration';
import { escape } from '../Utils/Html';
import '../Authentication.css';

export class AuthenticationPage {
  private mode: 'login' | 'register' = 'login';
  private email = '';
  private name = '';
  private busy = false;

  constructor(private root: HTMLElement, private authenticated: (user: User) => Promise<void>) {}

  showLogin(message = ''): void { this.render(message); }

  private render(error = '', success = ''): void {
    const signingUp = this.mode === 'register';
    const prefix = signingUp ? 'register' : 'login';
    this.root.innerHTML = `<main class="login-page"><section class="login-panel">
      <div class="brand-mark">Q</div><p class="eyebrow">QUALITY SYSTEM REVIEW</p>
      <h1>${signingUp ? '创建账号' : 'ISO 13485<br>文件预筛平台'}</h1>
      <p class="login-copy">${signingUp ? '注册后可管理自己的文件和整套手册。' : '上传质量体系文件，查看文本规则预筛结果与待核实事项。'}</p>
      ${success ? `<p class="inline-notice auth-success" data-testid="login-success" role="status">${escape(success)}</p>` : ''}
      <form class="login-form" data-testid="${prefix}-form">
        ${signingUp ? `<label>显示名称<input data-testid="register-name" name="display_name" autocomplete="name" required maxlength="64" value="${escape(this.name)}"></label>` : ''}
        <label>邮箱<input data-testid="${prefix}-email" name="email" type="email" autocomplete="username" required maxlength="190" autocapitalize="none" spellcheck="false" placeholder="name@company.com" value="${escape(this.email)}"></label>
        <label>密码<input data-testid="${prefix}-password" name="password" type="password" autocomplete="${signingUp ? 'new-password' : 'current-password'}" required ${signingUp ? 'aria-describedby="password-help" maxlength="72"' : ''}></label>
        ${signingUp ? '<p class="auth-help" id="password-help">8～72位，须包含字母和数字；中文等多字节字符总计不超过72字节。</p><label>确认密码<input data-testid="register-confirm" name="password_confirmation" type="password" autocomplete="new-password" required maxlength="72"></label>' : ''}
        <p class="form-error" data-testid="auth-error" role="alert">${escape(error)}</p>
        <button data-testid="${prefix}-submit" class="button button-primary" type="submit">${signingUp ? '注册账号' : '登录工作区'} <span aria-hidden="true">→</span></button>
      </form>
      <p class="auth-switch">${signingUp ? '已有账号？' : '还没有账号？'}<button data-testid="${signingUp ? 'show-login' : 'show-register'}" class="text-button" type="button">${signingUp ? '返回登录' : '注册账号'}</button></p>
      <p class="login-foot">${signingUp ? '注册完成后请使用邮箱和密码登录' : '仅登录账号可访问文件与校验记录'}</p>
      </section><aside class="login-aside"><div class="aside-rule"></div><p>DOCUMENT<br>CONTROL</p><span>受控文件的<br>结构化预筛</span><small>RULESET · 1.0</small></aside></main>`;
    this.root.querySelector('[data-testid="show-register"], [data-testid="show-login"]')?.addEventListener('click', () => {
      this.email = this.root.querySelector<HTMLInputElement>('[name="email"]')!.value.trim();
      this.mode = signingUp ? 'login' : 'register';
      this.name = ''; this.render();
    });
    this.root.querySelector('form')!.addEventListener('submit', event => { event.preventDefault(); void this.submit(); });
  }

  private async submit(): Promise<void> {
    if (this.busy) return;
    const form = this.root.querySelector('form')!;
    const data = new FormData(form);
    this.email = String(data.get('email')).trim().toLowerCase();
    this.name = String(data.get('display_name') || '').trim();
    const password = String(data.get('password'));
    const confirmation = String(data.get('password_confirmation') || '');
    if (this.mode === 'register') {
      let message = '';
      if (!this.name) message = '请输入显示名称';
      else if (password !== confirmation) message = '两次密码不一致';
      else if (password.length < 8 || password.length > 72 || !/[A-Za-z]/.test(password) || !/\d/.test(password)) message = '密码需为8～72位，且同时包含字母和数字';
      else if (new TextEncoder().encode(password).length > 72) message = '密码编码后超过72字节，请缩短密码';
      if (message) { this.root.querySelector('[data-testid="auth-error"]')!.textContent = message; return; }
    }
    this.busy = true;
    const controls = this.root.querySelectorAll<HTMLInputElement | HTMLButtonElement>('input, button');
    controls.forEach(control => { control.disabled = true; });
    this.root.querySelector('[data-testid="auth-error"]')!.textContent = '';
    try {
      if (this.mode === 'register') {
        const user = await register({ email: this.email, display_name: this.name, password, password_confirmation: confirmation });
        this.email = user.email; this.name = ''; this.mode = 'login';
        this.render('', '注册成功，请登录');
      } else await this.authenticated(await api.login(this.email, password));
    } catch (error) {
      this.render(error instanceof Error ? error.message : '请求失败，请重试');
    } finally {
      this.busy = false;
      controls.forEach(control => { control.disabled = false; });
    }
  }
}
