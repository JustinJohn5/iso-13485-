import type { User } from '../Api';
import { adminApi, type AdminOverview } from '../Api/Admin';
import { api } from '../Api';
import { escape } from '../Utils/Html';
import { LlmSettingsPage } from './LlmSettings';
import '../Admin.css';
import { startVisitorTracking } from '../Utils/VisitorTracking';

export class AdminWorkspace {
  private section = 'overview'; private overview?: AdminOverview; private content: unknown;
  private error = ''; private busy = false; private user?: User;
  constructor(private root: HTMLElement, private navigateFront: () => void) {}
  async open(): Promise<void> {
    this.busy = true; this.render();
    try { this.user = await api.me(); if (this.user.role !== 'admin') { this.section = 'forbidden'; this.error = '当前账号没有后台管理权限。'; } else await this.load(); }
    catch (e) { this.error = e instanceof Error ? e.message : '后台身份验证失败'; this.section = 'login'; }
    finally { this.busy = false; this.render(); }
  }
  private async load(): Promise<void> {
    this.error = '';
    try {
      if (this.section === 'overview') this.overview = await adminApi.overview();
      else if (this.section === 'visitors') this.content = await adminApi.visitors();
      else if (this.section === 'logs') this.content = await adminApi.logs({ source: 'app' });
      else if (this.section === 'audit') this.content = await adminApi.audits();
    } catch (e) { this.error = e instanceof Error ? e.message : '后台数据加载失败'; }
  }
  private render(): void {
    if (this.section === 'models' && this.user?.role === 'admin') { void new LlmSettingsPage(this.root, () => { this.section = 'overview'; void this.openSection('overview'); }).open(); return; }
    const sections = [['overview','概览','admin-nav-overview'],['visitors','访客状态','admin-nav-visitors'],['models','模型配置','admin-nav-models'],['logs','服务器日志','admin-nav-logs'],['audit','操作记录','admin-nav-audit']] as const;
    let main = '';
    if (this.section === 'login') main = `<section><h1>后台登录</h1><p>${escape(this.error)}</p><a class="button button-secondary" href="/">返回工作区</a></section>`;
    else if (this.section === 'forbidden') main = `<section data-testid="admin-forbidden"><h1>无权访问</h1><p role="alert">${escape(this.error)}</p><a class="button button-secondary" href="/">返回工作区</a></section>`;
    else if (this.section === 'overview') main = `<section><h1>后台概览</h1>${this.busy ? '<p role="status">正在加载…</p>' : ''}${this.overview ? `<div class="admin-stats">${[['当前在线访客',this.overview.online_visitors],['在线用户',this.overview.online_users],['今日访客',this.overview.today_visitors],['今日浏览',this.overview.today_views]].map(([label,value]) => `<article><span>${label}</span><strong>${value}</strong></article>`).join('')}</div><p>API：${escape(this.overview.services.api)} · 数据库：${escape(this.overview.services.database)}</p>` : ''}</section>`;
    else if (this.section === 'visitors') { const d = this.content as any; main = `<section><h1>访客状态</h1><div class="admin-table" data-testid="admin-visitors-table">${(d?.items || []).map((v:any) => `<article><strong>${v.identity === 'user' ? '登录用户' : '匿名访客'}</strong> · ${escape(v.page)} · ${v.online ? '在线' : '离线'}<small>最近活跃时间：${escape(v.last_seen)}</small></article>`).join('')}</div></section>`; }
    else if (this.section === 'logs') { const d = this.content as any; main = `<section><h1>服务器日志</h1><form data-testid="admin-log-filters"><select name="source"><option value="app">应用日志</option><option value="error">错误日志</option></select><input name="level" placeholder="级别"><input name="date" type="date"><input name="request_id" placeholder="请求编号"><input name="keyword" placeholder="关键词"><button>筛选</button></form><pre>${escape((d?.lines || []).join('\n'))}</pre>${d?.truncated ? '<p>结果已截断</p>' : ''}</section>`; }
    else if (this.section === 'audit') { const d = this.content as any; main = `<section><h1>操作记录</h1><div class="admin-table">${(d?.items || []).map((x:any) => `<article>${escape(x.created_at)} · ${escape(x.actor)} · ${escape(x.action)} · ${escape(x.target_type)}</article>`).join('')}</div></section>`; }
    this.root.innerHTML = `<div class="admin-shell" data-testid="admin-workspace"><aside><a href="/admin/" class="admin-brand">QMS · 管理后台</a>${sections.map(([id,label,testid]) => `<button data-section="${id}" data-testid="${testid}" class="${id === this.section ? 'active' : ''}">${label}</button>`).join('')}<a href="/">返回工作区</a></aside><main><header><span>${escape(this.user?.display_name || '管理员')}</span></header>${this.error ? `<p class="admin-error" role="alert">${escape(this.error)}</p><button data-testid="admin-retry">重新加载</button>` : ''}${main}</main></div>`;
    this.root.querySelectorAll<HTMLButtonElement>('[data-section]').forEach(b => b.addEventListener('click', () => void this.openSection(b.dataset.section!)));
    this.root.querySelector('a[href="/"]')?.addEventListener('click', event => { event.preventDefault(); this.navigateFront(); });
    this.root.querySelector('[data-testid="admin-retry"]')?.addEventListener('click', () => void this.openSection(this.section));
    this.root.querySelector('form[data-testid="admin-log-filters"]')?.addEventListener('submit', e => { e.preventDefault(); const data = new FormData(e.currentTarget as HTMLFormElement); void this.openSection('logs', Object.fromEntries(data.entries()) as any); });
  }
  private async openSection(section: string, filters?: { source:string; level?:string; keyword?:string; request_id?:string; date?:string }): Promise<void> {
    this.section = section; this.busy = true; this.render();
    startVisitorTracking(true, `/admin/${section === 'audit' ? 'audit-logs' : section}`);
    if (section === 'models') { this.busy = false; this.render(); return; }
    try { if (section === 'logs' && filters) this.content = await adminApi.logs(filters); else await this.load(); }
    catch (e) { this.error = e instanceof Error ? e.message : '后台数据加载失败'; }
    finally { this.busy = false; this.render(); }
  }
}
