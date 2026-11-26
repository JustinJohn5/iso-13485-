import { escape } from '../Utils/Html';
import { personalFilesApi } from '../Api/PersonalFiles';
import type { FileGroup, PersonalFile } from '../Types/PersonalFiles';
import { PersonalFilesPage } from './PersonalFiles';
import type { User } from '../Api';
import { AccountMenu } from './AccountMenu';
import { startVisitorTracking } from '../Utils/VisitorTracking';

export class FileGroupsPage {
  private groups: FileGroup[] = []; private files: PersonalFile[] = []; private busy = false; private error = '';
  private expandedGroups = new Set<string>();
  constructor(private root: HTMLElement, private back: () => void, private user?: User,
    private onLogout?: () => void | Promise<void>) {}
  async open(): Promise<void> { await this.load(); }
  private async load(): Promise<void> { this.busy = true; this.render(); try { const [g, f] = await Promise.all([personalFilesApi.groups(), personalFilesApi.files({ page: 1, page_size: 100 })]); this.groups = g.items; this.files = f.items; this.error = ''; } catch (e) { this.error = e instanceof Error ? e.message : '分组加载失败'; } finally { this.busy = false; this.render(); } }
  private render(): void {
    this.root.innerHTML = `<section data-testid="file-groups-page"><header class="account-page-heading"><div><p class="eyebrow">MY FILE GROUPS</p><h1>文件分组</h1></div><div class="account-anchor" data-testid="account-anchor"></div><button class="button button-secondary" data-testid="file-groups-back">返回工作区</button></header><p class="account-error" role="alert">${escape(this.error)}</p>
      <form class="account-create-group"><label>新分组名称<input data-testid="group-name" ${this.busy ? 'disabled' : ''} required maxlength="80" placeholder="例如：2026年度体系文件"></label><button class="button button-primary" data-testid="group-create" ${this.busy ? 'disabled' : ''}>创建分组</button></form>
      <section class="group-list">${this.groups.map(g => `<article class="group-card" data-testid="group-row-${escape(g.group_uid)}"><div><strong>${escape(g.name)}</strong><small>${g.file_count} 份文件</small></div><button data-rename="${escape(g.group_uid)}">重命名</button><button data-delete="${escape(g.group_uid)}">删除分组</button><details data-group="${escape(g.group_uid)}" ${this.expandedGroups.has(g.group_uid) ? 'open' : ''}><summary data-testid="group-members-toggle">批量管理成员</summary><div class="group-members">${this.files.map(f => `<label><input type="checkbox" data-testid="group-file-${escape(f.file_uid)}" data-file="${escape(f.file_uid)}" ${f.groups.some(x => x.group_uid === g.group_uid) ? 'checked' : ''}>${escape(f.name)}</label>`).join('') || '<p>暂无文件</p>'}</div><button data-testid="group-add-members" data-group="${escape(g.group_uid)}">批量加入所选</button><button data-testid="group-remove-members" data-group="${escape(g.group_uid)}">批量移出所选</button></details></article>`).join('') || '<p>尚未创建分组</p>'}</section></section>`;
    this.root.querySelector('[data-testid="file-groups-back"]')?.addEventListener('click', this.back);
    this.root.querySelectorAll<HTMLDetailsElement>('details[data-group]').forEach(details => details.addEventListener('toggle', () => {
      if (details.open) this.expandedGroups.add(details.dataset.group!); else this.expandedGroups.delete(details.dataset.group!);
    }));
    const anchor = this.root.querySelector<HTMLElement>('[data-testid="account-anchor"]');
    if (anchor && this.user) new AccountMenu(anchor, this.user, () => { location.href = '/admin/'; }, this.onLogout, {
      files: () => { startVisitorTracking(true, '/my/files'); void new PersonalFilesPage(this.root, this.back, this.user, this.onLogout).open(); },
      groups: () => { startVisitorTracking(true, '/my/file-groups'); void this.load(); },
    });
    const create = (event: Event) => {
      event.preventDefault(); if (this.busy) return;
      const name = this.root.querySelector<HTMLInputElement>('[data-testid="group-name"]')!.value.trim();
      this.busy = true;
      void personalFilesApi.createGroup(name).then(() => this.load()).catch(err => { this.error = err.message; this.busy = false; this.render(); });
    };
    this.root.querySelector('form')?.addEventListener('submit', create);
    this.root.querySelector('[data-testid="group-create"]')?.addEventListener('click', create);
    this.root.querySelectorAll<HTMLButtonElement>('[data-rename]').forEach(b => b.addEventListener('click', () => { const g = this.groups.find(x => x.group_uid === b.dataset.rename); const name = prompt('请输入新的分组名称', g?.name || ''); if (name?.trim()) void personalFilesApi.renameGroup(g!.group_uid, name.trim()).then(() => this.load()).catch(err => { this.error = err.message; this.render(); }); }));
    this.root.querySelectorAll<HTMLButtonElement>('[data-delete]').forEach(b => b.addEventListener('click', () => { if (confirm('删除分组不会删除文件，是否继续？')) void personalFilesApi.deleteGroup(b.dataset.delete!).then(() => this.load()).catch(err => { this.error = err.message; this.render(); }); }));
    this.root.querySelectorAll<HTMLButtonElement>('[data-testid="group-add-members"],[data-testid="group-remove-members"]').forEach(b => b.addEventListener('click', () => { const ids = [...this.root.querySelectorAll<HTMLInputElement>(`[data-testid^="group-file-"]:checked`)].map(x => x.dataset.file!); if (!ids.length) { this.error = '请先选择文件'; this.render(); return; } const groupUid = b.dataset.group!; const action = b.dataset.testid === 'group-add-members' ? personalFilesApi.addMembers(groupUid, ids) : personalFilesApi.removeMembers(groupUid, ids); void action.then(() => { this.expandedGroups.delete(groupUid); return this.load(); }).catch(err => { this.error = err.message; this.render(); }); }));
  }
}
