import type { User } from '../Api';
import { escape } from '../Utils/Html';
import { PersonalFilesPage } from './PersonalFiles';
import { FileGroupsPage } from './FileGroups';
import '../Account.css';
import { startVisitorTracking, stopVisitorTracking } from '../Utils/VisitorTracking';
import { PasswordChangePage } from './PasswordChange';
import { api } from '../Api';

export class AccountMenu {
  private panel?: HTMLElement;
  constructor(private anchor: HTMLElement, private user: User, private onAdmin?: () => void, private onLogout?: () => void,
    private actions: { files?: () => void; groups?: () => void; password?: () => void } = {}) {
    this.render();
  }
  private render(): void {
    this.anchor.innerHTML = `<button type="button" class="account-menu-trigger" data-testid="account-menu-button" aria-haspopup="menu" aria-expanded="false" aria-label="打开账户菜单">${escape(this.user.display_name || this.user.email)} ▾</button>`;
    const trigger = this.anchor.querySelector<HTMLButtonElement>('[data-testid="account-menu-button"]')!;
    trigger.addEventListener('click', () => this.panel ? this.close() : this.open());
  }
  private open(): void {
    this.panel?.remove();
    this.panel = document.createElement('div'); this.panel.className = 'account-popover'; this.panel.dataset.testid = 'account-menu';
    this.panel.setAttribute('role', 'menu');
    this.panel.innerHTML = `<button role="menuitem" data-testid="account-files">已上传文件</button><button role="menuitem" data-testid="account-groups">文件分组</button><button role="menuitem" data-testid="account-password">修改密码</button>${this.user.role === 'admin' ? '<a role="menuitem" data-testid="account-admin" href="/admin/">后台管理</a>' : ''}<button role="menuitem" data-testid="account-logout">退出登录</button>`;
    this.anchor.append(this.panel);
    this.anchor.querySelector('[data-testid="account-menu-button"]')?.setAttribute('aria-expanded', 'true');
    this.panel.querySelector('[data-testid="account-files"]')?.addEventListener('click', () => this.actions.files ? (this.close(), this.actions.files()) : this.showFiles());
    this.panel.querySelector('[data-testid="account-groups"]')?.addEventListener('click', () => this.actions.groups ? (this.close(), this.actions.groups()) : this.showGroups());
    this.panel.querySelector('[data-testid="account-password"]')?.addEventListener('click', () => {
      this.close();
      if (this.actions.password) { this.actions.password(); return; }
      startVisitorTracking(true, '/password');
      new PasswordChangePage(this.openOverlay(), this.user, () => { this.closeOverlay(); }, () => {
        stopVisitorTracking();
        location.assign('/?password_changed=1');
      }).open();
    });
    this.panel.querySelector('[data-testid="account-logout"]')?.addEventListener('click', () => { void this.logout(); });
    this.panel.querySelector('[data-testid="account-admin"]')?.addEventListener('click', event => { if (this.onAdmin) { event.preventDefault(); this.onAdmin(); } });
    document.addEventListener('pointerdown', this.outside, true); document.addEventListener('keydown', this.keydown);
  }
  private readonly outside = (event: PointerEvent) => { if (!this.anchor.contains(event.target as Node)) this.close(); };
  private readonly keydown = (event: KeyboardEvent) => { if (event.key === 'Escape') { this.close(); this.anchor.querySelector<HTMLButtonElement>('[data-testid="account-menu-button"]')?.focus(); } };
  private close(): void {
    this.panel?.remove(); this.panel = undefined;
    this.anchor.querySelector('[data-testid="account-menu-button"]')?.setAttribute('aria-expanded', 'false');
    document.removeEventListener('pointerdown', this.outside, true); document.removeEventListener('keydown', this.keydown);
  }
  private showFiles(): void { this.close(); startVisitorTracking(true, '/my/files'); new PersonalFilesPage(this.openOverlay(), () => this.closeOverlay(), this.user, () => this.logoutFromOverlay()).open(); }
  private showGroups(): void { this.close(); startVisitorTracking(true, '/my/file-groups'); new FileGroupsPage(this.openOverlay(), () => this.closeOverlay(), this.user, () => this.logoutFromOverlay()).open(); }
  private async logoutFromOverlay(): Promise<void> { this.closeOverlay(false); await this.logout(); }
  private async logout(): Promise<void> {
    this.close();
    if (this.onLogout) { await this.onLogout(); return; }
    await api.logout().catch(() => undefined);
    stopVisitorTracking();
    location.assign('/');
  }
  private overlay?: HTMLElement;
  private hiddenRoot?: HTMLElement;
  private rootParent?: HTMLElement;
  private rootNextSibling?: ChildNode | null;
  private openOverlay(): HTMLElement {
    this.hiddenRoot = this.anchor.closest<HTMLElement>('#app') || undefined;
    if (this.hiddenRoot?.parentElement) { this.rootParent = this.hiddenRoot.parentElement; this.rootNextSibling = this.hiddenRoot.nextSibling; this.hiddenRoot.remove(); }
    this.overlay = document.createElement('div'); this.overlay.className = 'account-overlay'; this.overlay.innerHTML = '<div class="account-view" data-testid="account-view"></div>'; document.body.append(this.overlay); return this.overlay.querySelector<HTMLElement>('.account-view')!;
  }
  private closeOverlay(trackResume = true): void { this.overlay?.remove(); this.overlay = undefined; if (this.hiddenRoot && this.rootParent) this.rootParent.insertBefore(this.hiddenRoot, this.rootNextSibling || null); this.hiddenRoot = undefined; this.rootParent = undefined; this.rootNextSibling = undefined; if (trackResume) startVisitorTracking(true, location.pathname === '/admin/' ? '/admin/' : '/prescreen'); }
}
