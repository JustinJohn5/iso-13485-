import { authoringApi } from '../Api/Authoring';
import type { Draft, DraftSummary, Template } from '../Types/Authoring';
import { escape } from '../Utils/Html';
import '../authoring.css';
import { llmApi } from '../Api/Llm';
import { LlmSettingsPage } from './LlmSettings';
import { DraftBatchPanel } from './DraftBatch';

export class AuthoringWorkspace {
  private templates: Template[] = [];
  private drafts: DraftSummary[] = [];
  private selected = '';
  private draft: Draft | null = null;
  private parameters: Record<string, string> = {};
  private sections: Record<string, string> = {};
  private query = '';
  private category = '';
  private reason = '';
  private busy = false;
  private message = '';
  private failed = false;
  private aiReady = false;
  private instructions = '';

  constructor(private root: HTMLElement, private back: () => void, private isAdmin = false) {}

  async open(): Promise<void> {
    this.render();
    await this.run(async () => {
      [this.templates, this.drafts] = await Promise.all([authoringApi.templates(), authoringApi.drafts()]);
      this.selected = this.templates[0]?.id || '';
      this.aiReady = (await llmApi.status()).ready;
    });
  }

  private async run(action: () => Promise<void>, success = ''): Promise<void> {
    if (this.busy) return;
    this.busy = true; this.message = ''; this.failed = false; this.render();
    try { await action(); this.message = success; }
    catch (error) { this.failed = true; this.message = error instanceof Error ? error.message : '操作失败，请重试'; }
    finally { this.busy = false; this.render(); }
  }

  private useDraft(draft: Draft): void {
    this.draft = draft; this.selected = draft.snapshot.template_id;
    this.parameters = { ...draft.snapshot.parameters };
    this.sections = Object.fromEntries(draft.snapshot.sections.map((item) => [item.id, item.body]));
    this.reason = '';
  }

  private render(): void {
    const template = this.templates.find((item) => item.id === this.selected);
    const visible = this.templates.filter((item) => (!this.category || item.category === this.category) &&
      this.query.toLocaleLowerCase().split(/\s+/).every((word) => `${item.title}${item.category}${item.description}`.toLocaleLowerCase().includes(word)));
    const fields = template?.fields.map((field) => `<label>${escape(field.label)}${field.multiline ?
      `<textarea required rows="4" maxlength="8000" data-parameter="${field.key}" data-testid="parameter-${field.key}">${escape(this.parameters[field.key] || '')}</textarea>` :
      `<input required maxlength="120" data-parameter="${field.key}" data-testid="parameter-${field.key}" value="${escape(this.parameters[field.key] || '')}">`}</label>`).join('') || '';
    this.root.innerHTML = `<div class="app-shell">
      <aside class="sidebar"><a class="brand" href="#"><span class="brand-mark">Q</span><span><b>QMS</b><small>DOCUMENT AUTHORING</small></span></a>
        <div class="side-label">工作区</div><button class="nav-item" data-testid="precheck-nav" id="back-precheck" ${this.busy ? 'disabled' : ''}>▦ 文件预筛</button>
        <button class="nav-item active" data-testid="templates-nav">▤ 模板与编写</button><div class="sidebar-bottom"><p class="control-note">示例模板库 v1.0<br>生成、复核、修订、导出</p></div></aside>
      <main class="main-content"><header class="topbar"><div class="breadcrumb">工作区 <span>/</span><b>模板与编写</b></div><span>草稿工作区</span></header>
        <div class="content-wrap authoring-wrap"><section class="page-heading"><div><p class="eyebrow">DOCUMENT AUTHORING</p><h1>模板与编写</h1><p>查找模板，填写项目参数，生成并修订技术文件。</p></div></section>
          <div class="notice-bar"><span class="notice-icon">i</span><p>模板为项目自有示例；生成文件保留草稿状态，批准、生效、检验限值及事实数据须人工核实。</p></div>
          ${this.message ? `<p data-testid="authoring-notice" class="inline-notice ${this.failed ? 'is-error' : ''}" role="status">${escape(this.message)}</p>` : ''}
          <section class="section-block batch-section"><button class="button button-secondary" type="button" id="open-batch" data-testid="open-batch" ${this.busy ? 'disabled' : ''}>跨文档参数联动</button><div id="batch-container"></div></section>
          <fieldset class="authoring-fieldset" ${this.busy ? 'disabled' : ''}>
            <div class="authoring-grid"><section class="section-block template-panel"><h2>模板检索</h2>
              <form id="template-search-form" class="template-search"><input aria-label="搜索模板" data-testid="template-search" id="template-query" placeholder="搜索名称、用途或关键词" value="${escape(this.query)}">
                <select aria-label="模板分类" data-testid="template-category" id="template-category"><option value="">全部分类</option>${['体系文件', '技术文件', '设计开发'].map((category) => `<option ${this.category === category ? 'selected' : ''}>${category}</option>`).join('')}</select>
                <button class="button button-secondary" type="submit" data-testid="search-templates">搜索</button></form>
              <div class="template-cards" data-testid="template-list">${visible.map((item) => `<button type="button" class="template-card ${this.selected === item.id ? 'selected' : ''}" data-template="${item.id}" data-testid="template-${item.id}"><span>${escape(item.category)} · v${escape(item.version)}</span><strong>${escape(item.title)}</strong><p>${escape(item.description)}</p></button>`).join('') || '<p data-testid="template-empty">未找到匹配模板，请更换关键词。</p>'}</div>
              <h3>我的近期草稿</h3><div class="draft-list">${this.drafts.map((item) => `<button type="button" data-open-draft="${item.draft_uid}" data-testid="open-draft-${item.draft_uid}">${escape(item.title)} · ${escape(item.project)} <small>修订 ${item.revision}</small></button>`).join('') || '<p class="control-note">生成后的草稿会保存到这里，最多显示最近50份。</p>'}</div>
            </section><section class="section-block authoring-editor"><h2>${escape(template?.title || '选择模板')}</h2>
              <form id="parameters-form"><div class="authoring-fields">${fields}</div>
                ${this.draft ? '<p class="control-note">更新参数会按模板重新生成全部章节，覆盖当前人工及 AI 正文；旧修订保留，可从历史下载。此处只联动本草稿。</p>' : ''}
                <button class="button button-primary" type="submit" data-testid="generate-draft" ${!template ? 'disabled' : ''}>${this.draft ? '更新参数并重新生成' : '生成文档草稿'}</button></form>
              ${this.draft ? `<div class="draft-preview" data-testid="draft-preview"><div class="section-title"><h2>正文预览与修改</h2><span data-testid="draft-revision">修订 ${this.draft.revision}</span></div>
                <p class="control-note" data-testid="draft-origin">来源：${this.draft.snapshot.origin === 'ai' ? 'AI 辅助编写' : this.draft.snapshot.origin === 'manual' ? '人工修订' : '参数化模板'} · 待人工复核</p>
                <div class="ai-draft-panel"><h3>AI 辅助编写</h3><p class="control-note" data-testid="ai-status">${this.aiReady ? '模型已启用；将向配置的服务发送已保存草稿和编写要求，请确认资料允许发送。AI 会覆盖当前章节并保存为新修订。' : '模型尚未启用，可先使用模板和人工编辑。'}所有生成内容均需人工复核。</p>
                  ${this.isAdmin ? '<button type="button" class="text-button" id="open-llm-settings" data-testid="open-llm-settings">管理模型配置</button>' : ''}
                  <label class="section-editor">编写要求<textarea rows="3" maxlength="4000" data-testid="ai-instructions" id="ai-instructions" placeholder="例如：细化检验步骤，缺失限值标记待确认">${escape(this.instructions)}</textarea></label>
                  <button type="button" class="button button-secondary" id="ai-draft" data-testid="ai-draft" ${!this.aiReady ? 'disabled' : ''}>按已保存草稿进行 AI 编写</button></div>
                <form id="sections-form">${this.draft.snapshot.sections.map((section) => `<label class="section-editor">${escape(section.title)}<textarea required rows="5" maxlength="12000" data-section="${section.id}" data-testid="section-${section.id}">${escape(this.sections[section.id] || '')}</textarea></label>`).join('')}
                  <button type="submit" class="button button-secondary" data-testid="save-draft">保存正文修订</button></form>
                <label class="section-editor">变更原因（更新参数或保存正文时必填，至少5字）<input data-testid="draft-reason" id="draft-reason" minlength="5" maxlength="500" value="${escape(this.reason)}"></label>
                <div class="draft-actions"><button type="button" class="button button-primary" id="download-draft" data-testid="download-draft">下载 Word 草稿</button><button type="button" class="button button-secondary" id="reload-draft" data-testid="reload-draft">重新加载已保存版本</button></div>
                <p class="control-note">下载以已保存版本为准。重新加载会丢弃未保存编辑。</p>
                <details class="draft-history" data-testid="draft-history"><summary>版本与变更记录（${this.draft.history.length}）</summary>${[...this.draft.history].reverse().map((entry) => `<div><b>修订 ${entry.revision}</b> · ${escape(entry.created_at)} · 用户 ${entry.user_id}<p>${escape(entry.reason)}</p><button type="button" class="text-button" data-history-download="${entry.revision}" data-testid="history-download-${entry.revision}">下载此修订</button></div>`).join('')}</details>
              </div>` : ''}
            </section></div>
          </fieldset>${this.busy ? '<p role="status">正在处理，请稍候…</p>' : ''}
        </div></main></div>`;
    this.bind();
  }

  private bind(): void {
    this.root.querySelector('#open-batch')?.addEventListener('click', () => {
      void new DraftBatchPanel(this.root.querySelector<HTMLElement>('#batch-container')!, async () => {
        this.drafts = await authoringApi.drafts();
        if (this.draft) this.useDraft(await authoringApi.draft(this.draft.draft_uid));
        this.message = '所选草稿参数已联动，旧修订保留。'; this.render();
      }).open();
    });
    this.root.querySelector('#open-llm-settings')?.addEventListener('click', () => {
      void new LlmSettingsPage(this.root, () => { void this.run(async () => { this.aiReady = (await llmApi.status()).ready; }); }).open();
    });
    this.root.querySelector<HTMLTextAreaElement>('#ai-instructions')?.addEventListener('input', (event) => { this.instructions = (event.target as HTMLTextAreaElement).value; });
    this.root.querySelector('#ai-draft')?.addEventListener('click', () => { void this.run(async () => {
      if (this.instructions.trim().length < 5) throw new Error('请填写至少5字的编写要求');
      this.useDraft(await llmApi.draft(this.draft!, this.instructions));
      this.drafts = await authoringApi.drafts();
    }, 'AI 已生成新修订，请逐项核对事实、参数和待确认事项。'); });
    this.root.querySelector('#back-precheck')?.addEventListener('click', this.back);
    this.root.querySelector<HTMLFormElement>('#template-search-form')?.addEventListener('submit', (event) => {
      event.preventDefault(); this.query = this.root.querySelector<HTMLInputElement>('#template-query')!.value;
      this.category = this.root.querySelector<HTMLSelectElement>('#template-category')!.value; this.render();
    });
    this.root.querySelectorAll<HTMLButtonElement>('[data-template]').forEach((button) => button.addEventListener('click', () => {
      this.selected = button.dataset.template!; this.draft = null; this.sections = {}; this.reason = ''; this.render();
    }));
    this.root.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>('[data-parameter]').forEach((input) => input.addEventListener('input', () => { this.parameters[input.dataset.parameter!] = input.value; }));
    this.root.querySelectorAll<HTMLTextAreaElement>('[data-section]').forEach((input) => input.addEventListener('input', () => { this.sections[input.dataset.section!] = input.value; }));
    this.root.querySelector<HTMLInputElement>('#draft-reason')?.addEventListener('input', (event) => { this.reason = (event.target as HTMLInputElement).value; });
    this.root.querySelector('#parameters-form')?.addEventListener('submit', (event) => {
      event.preventDefault(); void this.run(async () => {
        if (this.draft && this.reason.trim().length < 5) throw new Error('请填写至少5字的变更原因');
        this.useDraft(this.draft ? await authoringApi.update(this.draft, this.reason, { parameters: this.parameters }) : await authoringApi.create(this.selected, this.parameters));
        this.drafts = await authoringApi.drafts();
      }, '草稿已生成并保存，请复核正文后下载。');
    });
    this.root.querySelector('#sections-form')?.addEventListener('submit', (event) => {
      event.preventDefault(); void this.run(async () => {
        if (this.reason.trim().length < 5) throw new Error('请填写至少5字的变更原因');
        this.useDraft(await authoringApi.update(this.draft!, this.reason, { sections: this.sections }));
        this.drafts = await authoringApi.drafts();
      }, '正文修订已保存，历史版本保留。');
    });
    this.root.querySelectorAll<HTMLButtonElement>('[data-open-draft]').forEach((button) => button.addEventListener('click', () => {
      void this.run(async () => this.useDraft(await authoringApi.draft(button.dataset.openDraft!)));
    }));
    this.root.querySelector('#reload-draft')?.addEventListener('click', () => { void this.run(async () => this.useDraft(await authoringApi.draft(this.draft!.draft_uid)), '已加载最新保存版本'); });
    this.root.querySelector('#download-draft')?.addEventListener('click', () => { void this.run(async () => authoringApi.download(this.draft!), '已下载保存版本的 Word 草稿'); });
    this.root.querySelectorAll<HTMLButtonElement>('[data-history-download]').forEach((button) => button.addEventListener('click', () => { void this.run(async () => authoringApi.download(this.draft!, Number(button.dataset.historyDownload))); }));
  }
}
