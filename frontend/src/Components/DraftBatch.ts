import { request } from '../Api';
import { authoringApi } from '../Api/Authoring';
import type { DraftSummary } from '../Types/Authoring';
import { escape } from '../Utils/Html';

interface BatchRequest {
  drafts: Array<{ draft_uid: string; revision: number }>;
  parameters: Record<string, string>; reason: string;
}
interface BatchPreview {
  draft_uid: string; title: string; revision: number; next_revision: number;
  changes: Record<string, { before: string; after: string }>;
}
const labels: Record<string, string> = { company: '组织名称', project: '项目名称', product: '产品名称', model: '产品型号' };

export class DraftBatchPanel {
  private drafts: DraftSummary[] = [];
  private pending: BatchRequest | null = null;
  private busy = false;

  constructor(private root: HTMLElement, private applied: () => Promise<void>) {}

  async open(): Promise<void> {
    this.root.innerHTML = '<p role="status">正在读取可联动草稿…</p>';
    try { this.drafts = await authoringApi.drafts(); this.render(); }
    catch (error) { this.root.textContent = error instanceof Error ? error.message : '读取草稿失败'; }
  }

  private render(): void {
    this.root.innerHTML = `<details class="batch-panel" data-testid="batch-panel"><summary>跨文档参数联动</summary>
      <p class="control-note">选择1～20份草稿，只填写需要统一的参数。预览后提交会按各自模板重新生成全文，覆盖人工和 AI 正文；原修订保留。只影响所选草稿，不修改已上传原件或受控文件。</p>
      <form id="batch-form"><fieldset class="authoring-fieldset" id="batch-fields"><div class="batch-drafts">${this.drafts.map((draft) => `<label><input type="checkbox" data-batch-uid="${draft.draft_uid}" data-testid="batch-select-${draft.draft_uid}"><span>${escape(draft.title)} · ${escape(draft.project)}（修订 ${draft.revision}）</span></label>`).join('') || '<p>暂无已保存草稿。</p>'}</div>
        <div class="authoring-fields">${Object.entries(labels).map(([key, label]) => `<label>${label}<input data-batch-parameter="${key}" data-testid="batch-parameter-${key}" maxlength="120" placeholder="留空表示不修改"></label>`).join('')}</div>
        <label class="section-editor">变更原因<input required minlength="5" maxlength="500" id="batch-reason" data-testid="batch-reason"></label>
        <button type="submit" class="button button-secondary" data-testid="preview-batch">预览联动影响</button></fieldset></form>
      <p id="batch-notice" data-testid="batch-notice" role="status"></p><div id="batch-preview" data-testid="batch-preview"></div></details>`;
    this.root.querySelector('#batch-form')!.addEventListener('submit', (event) => {
      event.preventDefault(); void this.preview();
    });
    this.root.querySelector('#batch-form')!.addEventListener('input', () => {
      this.pending = null; this.root.querySelector('#batch-preview')!.innerHTML = '';
    });
  }

  private async run(action: () => Promise<void>): Promise<void> {
    if (this.busy) return;
    this.busy = true;
    const fieldset = this.root.querySelector<HTMLFieldSetElement>('#batch-fields')!;
    fieldset.disabled = true;
    const feedback = this.root.querySelector<HTMLElement>('#batch-notice')!;
    feedback.textContent = '正在处理…';
    try { await action(); feedback.textContent = ''; }
    catch (error) { feedback.textContent = error instanceof Error ? error.message : '参数联动失败'; }
    finally { this.busy = false; fieldset.disabled = false; }
  }

  private async preview(): Promise<void> {
    await this.run(async () => {
      const selected = Array.from(this.root.querySelectorAll<HTMLInputElement>('[data-batch-uid]:checked')).map((input) => input.dataset.batchUid!);
      const parameters = Object.fromEntries(Array.from(this.root.querySelectorAll<HTMLInputElement>('[data-batch-parameter]')).filter((input) => input.value.trim()).map((input) => [input.dataset.batchParameter!, input.value.trim()]));
      if (!selected.length || selected.length > 20) throw new Error('请选择1～20份草稿');
      if (!Object.keys(parameters).length) throw new Error('请至少填写一个需要统一的参数');
      const reason = this.root.querySelector<HTMLInputElement>('#batch-reason')!.value;
      const payload = { drafts: this.drafts.filter((draft) => selected.includes(draft.draft_uid)).map((draft) => ({ draft_uid: draft.draft_uid, revision: draft.revision })), parameters, reason };
      const preview = await request<BatchPreview[]>('/api/v1/document-draft-batches/preview', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      this.pending = payload;
      this.root.querySelector('#batch-preview')!.innerHTML = `<p>将重新生成 ${preview.length} 份草稿，其余参数及各文件编号保持原值。原修订可从历史下载。</p>${preview.map((item) => `<article class="batch-change"><b>${escape(item.title)} · 修订 ${item.revision} → ${item.next_revision}</b>${Object.entries(item.changes).map(([key, change]) => `<p>${escape(labels[key])}：${escape(change.before)} → ${escape(change.after)}</p>`).join('')}</article>`).join('')}<button class="button button-primary" type="button" id="apply-batch" data-testid="apply-batch">按预览应用并保存新修订</button>`;
      this.root.querySelector('#apply-batch')!.addEventListener('click', () => { void this.apply(); });
    });
  }

  private async apply(): Promise<void> {
    if (!this.pending) return;
    const button = this.root.querySelector<HTMLButtonElement>('#apply-batch')!;
    button.disabled = true;
    await this.run(async () => {
      await request('/api/v1/document-draft-batches/apply', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this.pending) });
      this.pending = null;
      await this.applied();
    });
    button.disabled = false;
  }
}
