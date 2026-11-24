import { createPrescreenContext, factLabels, purposeLabels, type DocumentPurpose, type FactStatus, type PrescreenContext } from '../Types/Prescreen';
import { escape } from '../Utils/Html';
import '../prescreen.css';

export { createPrescreenContext };
export function purposeSelect(value: DocumentPurpose, testId: string, attributes = ''): string {
  return `<select data-testid="${escape(testId)}" ${attributes}>${Object.entries(purposeLabels).map(([key, label]) => `<option value="${key}" ${key === value ? 'selected' : ''}>${label}</option>`).join('')}</select>`;
}

export function renderPrescreenContext(context: PrescreenContext, busy = false): string {
  return `<section class="section-block prescreen-context" data-testid="prescreen-context"><h2>审核范围与适用条件</h2>
    <p>条件未知会进入待确认；选择条件不适用不会自动排除条款。外包仍需控制，实施与有效性须人工审核。</p>
    <fieldset ${busy ? 'disabled' : ''}><div class="prescreen-fields"><label>本次审核范围<select data-testid="prescreen-scope" data-prescreen-scope><option value="documents" ${context.scope === 'documents' ? 'selected' : ''}>单份或选定文件</option><option value="system" ${context.scope === 'system' ? 'selected' : ''}>组织体系级</option></select></label>
    <label class="prescreen-wide">组织范围说明${context.scope === 'system' ? '（体系级必填）' : '（选填）'}<textarea data-testid="prescreen-scope-description" data-prescreen-description maxlength="2000" ${context.scope === 'system' ? 'required' : ''}>${escape(context.scope_description)}</textarea></label>
    ${Object.entries(factLabels).map(([key, label]) => `<label>${label}<select data-testid="prescreen-fact-${key}" data-prescreen-fact="${key}">${Object.entries({ unknown: '未知，待确认', yes: '适用', no: '事实不适用，仍需条款确认' }).map(([value, name]) => `<option value="${value}" ${context.facts[key] === value ? 'selected' : ''}>${name}</option>`).join('')}</select></label>`).join('')}</div>
    <details class="prescreen-decisions"><summary data-testid="prescreen-decisions-toggle">条款不适用说明（${Object.keys(context.decisions).length}）</summary><p>仅限第6、7、8章；须逐条提供理由和证据。设计开发删减须填写适用法规依据。确认人及确认时间由服务端记录。</p>
      <div data-testid="prescreen-decisions">${context.decisions.map(row => `<article><b>${escape(row.clause)}</b><p>理由：${escape(row.reason)}<br>依据：${escape(row.basis)}</p><button type="button" class="text-button" data-prescreen-remove="${escape(row.clause)}" data-testid="prescreen-remove-decision-${escape(row.clause)}">移除此说明</button></article>`).join('')}</div>
      <div class="prescreen-fields"><label>条款号<input data-testid="prescreen-decision-clause" data-prescreen-clause placeholder="例如 7.5.5" maxlength="16"></label><label>不适用理由（至少5字）<textarea data-testid="prescreen-decision-reason" data-prescreen-reason maxlength="1000"></textarea></label><label>依据或法规依据（至少5字）<textarea data-testid="prescreen-decision-evidence" data-prescreen-evidence maxlength="1000"></textarea></label></div>
      <p class="form-error" data-testid="prescreen-decision-error" data-prescreen-error role="status"></p><button type="button" class="button button-secondary" data-testid="prescreen-add-decision" data-prescreen-add>添加条款说明</button>
    </details></fieldset></section>`;
}

export function bindPrescreenContext(root: HTMLElement, context: PrescreenContext, changed: (context: PrescreenContext, redraw: boolean) => void): void {
  const update = (redraw = true) => changed(context, redraw);
  root.querySelector<HTMLSelectElement>('[data-prescreen-scope]')?.addEventListener('change', event => { context.scope = (event.target as HTMLSelectElement).value as PrescreenContext['scope']; update(); });
  root.querySelector<HTMLTextAreaElement>('[data-prescreen-description]')?.addEventListener('input', event => { context.scope_description = (event.target as HTMLTextAreaElement).value; update(false); });
  root.querySelectorAll<HTMLSelectElement>('[data-prescreen-fact]').forEach(select => select.addEventListener('change', () => { context.facts[select.dataset.prescreenFact!] = select.value as FactStatus; update(); }));
  root.querySelectorAll<HTMLButtonElement>('[data-prescreen-remove]').forEach(button => button.addEventListener('click', () => { context.decisions = context.decisions.filter(row => row.clause !== button.dataset.prescreenRemove); update(); }));
  root.querySelector('[data-prescreen-add]')?.addEventListener('click', () => {
    const clause = root.querySelector<HTMLInputElement>('[data-prescreen-clause]')!.value.trim();
    const reason = root.querySelector<HTMLTextAreaElement>('[data-prescreen-reason]')!.value.trim();
    const evidence = root.querySelector<HTMLTextAreaElement>('[data-prescreen-evidence]')!.value.trim();
    const error = !/^[678](?:\.\d{1,2}){1,3}$/.test(clause) ? '请输入第6、7、8章的有效条款号，具体条款由后端校验' : reason.length < 5 || evidence.length < 5 ? '理由和依据均须至少5字；设计开发须有适用法规依据' : '';
    root.querySelector('[data-prescreen-error]')!.textContent = error;
    if (error) return;
    context.decisions = [...context.decisions.filter(row => row.clause !== clause), { clause, reason, basis: evidence }]; update();
  });
}
