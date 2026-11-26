import { escape } from '../Utils/Html';
import { personalFilesApi } from '../Api/PersonalFiles';
import type { FileGroup, PersonalFile } from '../Types/PersonalFiles';
import { FileGroupsPage } from './FileGroups';
import type { User } from '../Api';
import { AccountMenu } from './AccountMenu';
import { startVisitorTracking } from '../Utils/VisitorTracking';

export class PersonalFilesPage {
  private rows: PersonalFile[] = []; private groups: FileGroup[] = []; private selected = new Set<string>();
  private page = 1; private total = 0; private busy = false; private error = ''; private keyword = ''; private type = ''; private group = '';
  constructor(private root: HTMLElement, private back: () => void, private user?: User,
    private onLogout?: () => void | Promise<void>) {}
  async open(): Promise<void> { await this.load(); }
  private async load(): Promise<void> {
    this.busy = true; this.render();
    try {
      const [files, groups] = await Promise.all([personalFilesApi.files({ page: this.page, page_size: 20, keyword: this.keyword, document_type: this.type, group_uid: this.group }), personalFilesApi.groups()]);
      this.rows = files.items; this.total = files.total; this.groups = groups.items; this.error = '';
    } catch (e) { this.error = e instanceof Error ? e.message : '文件读取失败'; }
    finally { this.busy = false; this.render(); }
  }
  private render(): void {
    this.root.innerHTML = `<section data-testid="personal-files-page"><header class="account-page-heading"><div><p class="eyebrow">MY DOCUMENTS</p><h1>已上传文件</h1></div><div class="account-anchor" data-testid="account-anchor"></div><button class="button button-secondary" data-testid="personal-files-back">返回工作区</button></header>
      <p class="account-error" role="alert" data-testid="personal-files-error">${escape(this.error)}</p><div class="account-filters"><label>搜索文件<input data-testid="file-search" value="${escape(this.keyword)}" placeholder="输入文件名"></label><label>文件类型<select data-testid="file-type-filter"><option value="">全部类型</option>${[...new Set(this.rows.map(x => x.document_type))].map(x => `<option value="${escape(x)}" ${x === this.type ? 'selected' : ''}>${escape(x)}</option>`).join('')}</select></label><label>分组<select data-testid="file-group-filter"><option value="">全部分组</option>${this.groups.map(x => `<option value="${escape(x.group_uid)}" ${x.group_uid === this.group ? 'selected' : ''}>${escape(x.name)}</option>`).join('')}</select></label><button data-testid="file-search-submit">搜索</button></div>
      <p>共 ${this.total} 份文件，可选择最多20份加入当前预筛。</p><div class="account-table">${this.rows.map(file => `<div class="account-file-row" data-testid="file-row-${escape(file.file_uid)}"><input type="checkbox" data-testid="file-select-${escape(file.file_uid)}" ${this.selected.has(file.file_uid) ? 'checked' : ''} aria-label="选择 ${escape(file.name)}"><strong>${escape(file.name)}</strong><span>${escape(file.document_type)}</span><span>${escape(file.text_status || '')}</span><button data-download="${escape(file.file_uid)}" data-testid="file-download-${escape(file.file_uid)}">下载原件</button></div>`).join('') || '<p>暂无匹配文件</p>'}</div>
      <footer><button data-testid="files-previous" ${this.page <= 1 ? 'disabled' : ''}>上一页</button><span>第 ${this.page} 页</span><button data-testid="files-next" ${this.page * 20 >= this.total ? 'disabled' : ''}>下一页</button><button class="button button-primary" data-testid="selected-files-load" ${!this.selected.size || this.busy ? 'disabled' : ''}>加入当前预筛（${this.selected.size}/20）</button></footer></section>`;
    this.root.querySelector('[data-testid="personal-files-back"]')?.addEventListener('click', this.back);
    const anchor = this.root.querySelector<HTMLElement>('[data-testid="account-anchor"]');
    if (anchor && this.user) new AccountMenu(anchor, this.user, () => { location.href = '/admin/'; }, this.onLogout, {
      files: () => { startVisitorTracking(true, '/my/files'); void this.load(); },
      groups: () => { startVisitorTracking(true, '/my/file-groups'); void new FileGroupsPage(this.root, this.back, this.user, this.onLogout).open(); },
    });
    let searchTimer = 0;
    this.root.querySelector('[data-testid="file-search"]')?.addEventListener('input', e => { window.clearTimeout(searchTimer); this.keyword = (e.target as HTMLInputElement).value.trim(); this.page = 1; searchTimer = window.setTimeout(() => { void this.load(); }, 250); });
    this.root.querySelector('[data-testid="file-search-submit"]')?.addEventListener('click', () => { this.keyword = this.root.querySelector<HTMLInputElement>('[data-testid="file-search"]')!.value.trim(); this.page = 1; void this.load(); });
    this.root.querySelector('[data-testid="file-type-filter"]')?.addEventListener('change', e => { this.type = (e.target as HTMLSelectElement).value; this.page = 1; void this.load(); });
    this.root.querySelector('[data-testid="file-group-filter"]')?.addEventListener('change', e => { this.group = (e.target as HTMLSelectElement).value; this.page = 1; void this.load(); });
    this.root.querySelectorAll<HTMLInputElement>('[data-testid^="file-select-"]').forEach(box => box.addEventListener('change', () => { const uid = box.closest<HTMLElement>('[data-testid^="file-row-"]')!.dataset.testid!.slice(9); if (box.checked && this.selected.size < 20) this.selected.add(uid); else this.selected.delete(uid); this.render(); }));
    this.root.querySelectorAll<HTMLButtonElement>('[data-download]').forEach(button => button.addEventListener('click', () => { const file = this.rows.find(x => x.file_uid === button.dataset.download); if (file) void personalFilesApi.download(file).catch(e => { this.error = e.message; this.render(); }); }));
    this.root.querySelector('[data-testid="files-previous"]')?.addEventListener('click', () => { this.page--; void this.load(); });
    this.root.querySelector('[data-testid="files-next"]')?.addEventListener('click', () => { this.page++; void this.load(); });
    this.root.querySelector('[data-testid="selected-files-load"]')?.addEventListener('click', () => { document.dispatchEvent(new CustomEvent('personal-files-selected', { detail: [...this.selected].slice(0, 20) })); this.back(); });
  }
}
