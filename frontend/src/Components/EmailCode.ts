import type { CodeDeliveryInfo } from '../Api/Registration';

export interface EmailCodeState { until: number }

export function emailCodeFields(prefix: string): string {
  return '<div class="email-verification">' +
    '<label>邮箱验证码<div class="email-code-row">' +
    '<input data-testid="' + prefix + '-code" name="email_verification_code" autocomplete="one-time-code" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" required placeholder="6位验证码">' +
    '<button data-testid="' + prefix + '-send-code" class="button button-secondary" type="button">发送验证码</button></div></label>' +
    '<p class="auth-help">验证码10分钟内有效，仅用于注册或修改密码。</p>' +
    '<p data-testid="verification-notice" class="auth-help" role="status"></p></div>';
}

export function bindEmailCode(root: HTMLElement, prefix: string, state: EmailCodeState,
  send: () => Promise<CodeDeliveryInfo>, onError: (message: string) => void): void {
  const button = root.querySelector<HTMLButtonElement>('[data-testid="' + prefix + '-send-code"]')!;
  const notice = root.querySelector('[data-testid="verification-notice"]')!;
  let sending = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const update = () => {
    if (timer) clearTimeout(timer);
    if (!button.isConnected) return;
    const remaining = Math.max(0, Math.ceil((state.until - Date.now()) / 1000));
    button.disabled = sending || remaining > 0 || button.closest('form')?.dataset.busy === 'true';
    button.textContent = sending ? '正在发送…' : remaining ? remaining + '秒后重发' : '发送验证码';
    if (remaining > 0) timer = setTimeout(update, 1000);
  };
  button.addEventListener('click', async () => {
    if (sending || state.until > Date.now()) return;
    sending = true; onError(''); notice.textContent = ''; update();
    try {
      const delivery = await send();
      state.until = Date.now() + delivery.resend_after_seconds * 1000;
      notice.textContent = '请求已处理；如邮箱可用于此操作，请检查收件箱和垃圾邮件。';
    } catch (error) {
      if (button.isConnected) onError(error instanceof Error ? error.message : '发送失败，请稍后重试');
    } finally {
      sending = false; update();
    }
  });
  update();
}
