import { api } from '../Api';
import { suitesApi } from '../Api/ManualSuites';
import type { CatalogEntry, ManualSuite, SuiteItem, SuiteList } from '../Types/ManualSuite';
import { escape } from '../Utils/Html';
import { suiteInspection, suiteMembers, suiteReader } from './SuiteViews';
import '../Suites.css';

export class ManualSuitesPage {
  private catalog: CatalogEntry[] = [];
  private list: SuiteList = { items: [], total: 0, page: 1, page_size: 20 };
  private suite: ManualSuite | null = null;
  private reader: SuiteItem | null = null;
  private selected = new Set<string>();
  private parameters: Record<string, string> = { company: '', project: '', product: '', model: '', requirements: '' };
  private name = '';
  private version = '';
  private query = '';
  private filterVersion = '';
  private date = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  private busy = false;
  private message = '';
  private failed = false;
  private pending: string[] = [];

  constructor(private root: HTMLElement, private back: () => void) {}

  async open(): Promise<void> {
    window.scrollTo(0, 0);
    await this.run(async () => {
      [this.catalog, this.list] = await Promise.all([suitesApi.catalog(), suitesApi.list()]);
      this.selected = new Set(this.catalog.map(row => row.key));
    });
  }

  private async run(action: () => Promise<void>, message = ''): Promise<void> {
    if (this.busy) return;
    this.busy = true; this.failed = false; this.message = ''; this.render();
    try { await action(); this.message = message; }
    catch (error) { this.failed = true; this.message = error instanceof Error ? error.message : '操作失败，请重试'; }
    finally { this.busy = false; this.render(); }
  }

  private use(suite: ManualSuite): void { this.suite = suite; this.reader = null; }

  private render(): void {
    const suite = this.suite;
    const present = new Set(suite?.items.map(item => item.catalog_key));
    this.root.innerHTML = `<main class="suite-page"><header class="suite-header"><div><p class="eyebrow">QUALITY MANUAL LIBRARY</p><h1>整套手册</h1><p>按整套发布版本管理导入原件与生成草稿。</p></div><div class="suite-actions"><button class="button button-secondary" id="suite-back" data-testid="suite-back" ${this.busy ? 'disabled' : ''}>返回文件预筛</button></div></header>
      <p class="suite-note">生成件需要核对适用范围、填写事实并完成组织审批。目录齐全与文本命中不代表已经符合全部标准要求。</p>
      <div class="inline-notice ${this.failed ? 'is-error' : ''}" role="status" data-testid="suite-notice">${this.busy ? '正在处理，请稍候…' : escape(this.message)}</div>
      <fieldset class="suite-fieldset" ${this.busy ? 'disabled' : ''}><div class="suite-layout"><aside>
        <section class="suite-card"><h2>新建发布版本</h2><form id="suite-create-form" class="suite-form"><label>套册名称<input data-testid="suite-name" id="suite-name" value="${escape(this.name)}" maxlength="120" placeholder="组织或项目的体系名称" required></label><label>整套发布版本号<input data-testid="suite-version" id="suite-version" value="${escape(this.version)}" maxlength="32" placeholder="例如 A/0" required></label><button class="button button-primary" data-testid="suite-create">创建版本档案</button></form></section>
        <section class="suite-card"><h2>版本档案</h2><form id="suite-search-form" class="suite-form"><label>套册名称<input data-testid="suite-query" id="suite-query" value="${escape(this.query)}"></label><label>发布版本精确筛选<input data-testid="suite-filter-version" id="suite-filter-version" value="${escape(this.filterVersion)}"></label><button class="button button-secondary" data-testid="suite-search">查询版本</button></form><div data-testid="suite-list">${this.list.items.map(row => `<button class="suite-list-entry ${row.suite_uid === suite?.suite_uid ? 'selected' : ''}" data-open-suite="${row.suite_uid}" data-testid="suite-open-${row.suite_uid}"><b>${escape(row.name)}</b><span>${escape(row.version)} · ${row.item_count} 份文件</span></button>`).join('') || '<p>未找到套册。</p>'}</div><div class="suite-actions"><button id="suite-prev" data-testid="suite-prev" ${this.list.page <= 1 ? 'disabled' : ''}>上一页</button><small>${this.list.page} 页 · 共 ${this.list.total} 套</small><button id="suite-next" data-testid="suite-next" ${this.list.page * this.list.page_size >= this.list.total ? 'disabled' : ''}>下一页</button></div></section>
      </aside><div>${suite ? `<section class="suite-card" data-testid="suite-detail"><div class="suite-actions"><div><h2>${escape(suite.name)}</h2><p>发布版本 ${escape(suite.version)} · 档案修订 ${suite.revision}</p></div><button class="text-button" id="suite-new" data-testid="suite-new">新建其他版本</button><button class="text-button" id="suite-reload" data-testid="suite-reload">重新打开</button></div><div class="suite-actions"><label>审核基准日<input type="date" id="suite-date" data-testid="suite-date" value="${this.date}" required></label><button class="button button-primary" id="suite-inspect" data-testid="suite-inspect" ${!suite.items.length ? 'disabled' : ''}>检查整套</button><button class="button button-secondary" id="suite-download" data-testid="suite-download" ${!suite.items.length ? 'disabled' : ''}>下载整套 ZIP</button></div></section>
        <section class="suite-card"><h2>导入已有文件</h2><p>可分批补充，支持 PDF、DOCX、XLSX、TXT、MD；每套最多100份。正文解析后归档，原件保留。</p><input type="file" multiple accept=".pdf,.docx,.xlsx,.txt,.md" data-testid="suite-upload" id="suite-upload" aria-label="导入整套文件">${this.pending.length ? `<p>有 ${this.pending.length} 份已上传文件等待归档。</p><button id="suite-retry-import" data-testid="suite-retry-import">重试归档</button>` : ''}</section>
        <section class="suite-card"><details ${!suite.items.length ? 'open' : ''}><summary>批量生成目录草稿（${this.catalog.length}项）</summary><form id="suite-generate-form" class="suite-form"><div class="suite-fields">${Object.entries({ company: '组织名称', project: '项目名称', product: '产品名称', model: '产品型号', requirements: '已知输入与编写要求' }).map(([key, label]) => `<label>${label}${key === 'requirements' ? `<textarea data-parameter="${key}" data-testid="suite-parameter-${key}" maxlength="100000" required>${escape(this.parameters[key])}</textarea>` : `<input data-parameter="${key}" data-testid="suite-parameter-${key}" maxlength="120" value="${escape(this.parameters[key])}" required>`}</label>`).join('')}</div><div class="suite-actions"><button type="button" id="suite-select-all" data-testid="suite-select-all">全选可生成项</button><button type="button" id="suite-select-none" data-testid="suite-select-none">清空选择</button></div><div class="suite-directory">${this.catalog.map(row => `<label><input type="checkbox" data-catalog="${row.key}" data-testid="suite-catalog-${row.key}" ${this.selected.has(row.key) ? 'checked' : ''} ${present.has(row.key) ? 'disabled' : ''}><span>${escape(row.title)}<small>${escape(row.number)} · ${present.has(row.key) ? '已提供' : escape(row.category)}</small></span></label>`).join('')}</div><button class="button button-primary" data-testid="suite-generate" ${![...this.selected].some(key => !present.has(key)) ? 'disabled' : ''}>生成所选目录并归档</button></form></details></section>
        ${suiteReader(this.reader)}${suiteMembers(suite, this.catalog)}${suiteInspection(suite)}` : '<section class="suite-card"><h2>建立一套可追溯的手册档案</h2><p>先填写套册名称和发布版本号，再导入已有文件或按目录生成草稿。同名不同版本分别保存，重新进入网页仍可查阅。</p></section>'}</div></div></fieldset></main>`;
    this.bind();
  }

  private bind(): void {
    this.root.querySelector('#suite-back')?.addEventListener('click', this.back);
    for (const [id, set] of Object.entries({ 'suite-name': (v: string) => { this.name = v; }, 'suite-version': (v: string) => { this.version = v; }, 'suite-query': (v: string) => { this.query = v; }, 'suite-filter-version': (v: string) => { this.filterVersion = v; }, 'suite-date': (v: string) => { this.date = v; } })) {
      this.root.querySelector<HTMLInputElement>(`#${id}`)?.addEventListener('input', event => set((event.target as HTMLInputElement).value));
    }
    this.root.querySelector('#suite-create-form')?.addEventListener('submit', event => { event.preventDefault(); void this.run(async () => {
      this.use(await suitesApi.create(this.name, this.version)); this.pending = [];
      this.query = ''; this.filterVersion = ''; this.list = await suitesApi.list();
    }, '版本档案已创建，请导入文件或生成目录草稿。'); });
    this.root.querySelector('#suite-search-form')?.addEventListener('submit', event => { event.preventDefault(); void this.loadList(1); });
    this.root.querySelector('#suite-prev')?.addEventListener('click', () => { void this.loadList(this.list.page - 1); });
    this.root.querySelector('#suite-next')?.addEventListener('click', () => { void this.loadList(this.list.page + 1); });
    this.root.querySelectorAll<HTMLButtonElement>('[data-open-suite]').forEach(button => button.addEventListener('click', () => { void this.run(async () => { this.use(await suitesApi.detail(button.dataset.openSuite!)); this.pending = []; }); }));
    this.root.querySelector('#suite-new')?.addEventListener('click', () => { this.suite = null; this.version = ''; this.pending = []; this.render(); });
    this.root.querySelector('#suite-reload')?.addEventListener('click', () => { void this.run(async () => { this.use(await suitesApi.detail(this.suite!.suite_uid)); }); });
    this.root.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>('[data-parameter]').forEach(input => input.addEventListener('input', () => { this.parameters[input.dataset.parameter!] = input.value; }));
    this.root.querySelectorAll<HTMLInputElement>('[data-catalog]').forEach(input => input.addEventListener('change', () => {
      if (input.checked) this.selected.add(input.dataset.catalog!); else this.selected.delete(input.dataset.catalog!);
      const present = new Set(this.suite!.items.map(row => row.catalog_key));
      const button = this.root.querySelector<HTMLButtonElement>('[data-testid="suite-generate"]');
      if (button) button.disabled = ![...this.selected].some(key => !present.has(key));
    }));
    this.root.querySelector('#suite-select-all')?.addEventListener('click', () => { this.selected = new Set(this.catalog.map(row => row.key)); this.render(); });
    this.root.querySelector('#suite-select-none')?.addEventListener('click', () => { this.selected.clear(); this.render(); });
    this.root.querySelector('#suite-generate-form')?.addEventListener('submit', event => { event.preventDefault(); void this.run(async () => {
      const existing = new Set(this.suite!.items.map(row => row.catalog_key));
      this.use(await suitesApi.generate(this.suite!, [...this.selected].filter(key => !existing.has(key)), this.parameters)); await this.refreshList();
    }, '所选目录草稿已生成并归档，请逐项复核。'); });
    this.root.querySelector<HTMLInputElement>('#suite-upload')?.addEventListener('change', event => { const files = [...(event.target as HTMLInputElement).files || []]; void this.upload(files); });
    this.root.querySelector('#suite-retry-import')?.addEventListener('click', () => { void this.run(async () => { await this.importPending(); }, '文件已归档。'); });
    this.root.querySelectorAll<HTMLButtonElement>('[data-read]').forEach(button => button.addEventListener('click', () => { void this.run(async () => { this.reader = await suitesApi.item(this.suite!, button.dataset.read!); }); }));
    this.root.querySelector('#suite-close-reader')?.addEventListener('click', () => { this.reader = null; this.render(); });
    this.root.querySelector('#suite-edit-form')?.addEventListener('submit', event => {
      event.preventDefault();
      const item = this.reader!;
      const sections = Object.fromEntries([...this.root.querySelectorAll<HTMLTextAreaElement>('[data-suite-section]')].map(input => [input.dataset.suiteSection!, input.value]));
      const reason = this.root.querySelector<HTMLInputElement>('#suite-edit-reason')!.value;
      void this.run(async () => {
        this.use(await suitesApi.revise(this.suite!, item.id, item.catalog_key, item.file_version, sections, reason));
        this.reader = await suitesApi.item(this.suite!, item.id);
      }, '本套正文已保存，请重新检查后导出。');
    });
    this.root.querySelectorAll<HTMLButtonElement>('[data-save-item]').forEach(button => button.addEventListener('click', () => {
      const id = button.dataset.saveItem!;
      const key = this.root.querySelector<HTMLSelectElement>(`[data-item-key="${id}"]`)!.value;
      const version = this.root.querySelector<HTMLInputElement>(`[data-item-version="${id}"]`)!.value;
      void this.run(async () => { this.use(await suitesApi.revise(this.suite!, id, key, version)); }, '成员信息已保存，请重新检查整套。');
    }));
    this.root.querySelectorAll<HTMLButtonElement>('[data-remove-item]').forEach(button => button.addEventListener('click', () => { void this.run(async () => { this.use(await suitesApi.remove(this.suite!, button.dataset.removeItem!)); await this.refreshList(); }, '已移出本套，上传原件保留；请重新检查。'); }));
    this.root.querySelector('#suite-inspect')?.addEventListener('click', () => { void this.run(async () => { if (!this.date) throw new Error('请选择审核基准日'); this.use(await suitesApi.inspect(this.suite!, this.date)); }, '整套检查已保存。'); });
    this.root.querySelector('#suite-download')?.addEventListener('click', () => { void this.run(async () => { await suitesApi.download(this.suite!); }, '整套归档已下载。'); });
  }

  private async refreshList(): Promise<void> { this.list = await suitesApi.list(this.query, this.filterVersion, this.list.page); }
  private async loadList(page: number): Promise<void> { await this.run(async () => { this.list = await suitesApi.list(this.query, this.filterVersion, page); }); }
  private async importPending(): Promise<void> {
    if (!this.pending.length) return;
    this.use(await suitesApi.import(this.suite!, this.pending)); this.pending = []; await this.refreshList();
  }

  private async upload(files: File[]): Promise<void> {
    if (!files.length) return;
    await this.run(async () => {
      if (this.suite!.items.length + files.length + this.pending.length > 100) throw new Error('本套最多100份文件，请减少本批文件数量');
      const failures: string[] = [];
      for (const file of files) {
        try { this.pending.push((await api.upload(file, 'auto')).file_uid); }
        catch (error) { failures.push(`${file.name}：${error instanceof Error ? error.message : '上传失败'}`); }
      }
      await this.importPending();
      if (failures.length) throw new Error(`已归档成功解析的文件；以下文件未归档：${failures.join('；')}`);
    }, '本批文件已解析归档，请核对目录归属和文件版本。');
  }
}
