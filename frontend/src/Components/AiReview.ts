import { aiReviewApi } from '../Api/AiReview';
import { llmApi } from '../Api/Llm';
import { ApiRequestError } from '../Api';
import type { AiReviewDecisionKind, AiReviewRecord } from '../Types/AiReview';
import type { ValidationResult } from '../Api';
import { escape } from '../Utils/Html';
import '../ai-review.css';

const modeLabels = { evidence_search: '查找依据', semantic_review: '逐项审阅' } as const;
const signalLabels: Record<string, string> = { support: '支持线索', contrary: '反向线索', uncertain: '待核实' };
const statusLabels: Record<string, string> = {
  supporting_signal: '发现支持线索', contrary_signal: '发现反向线索',
  not_found_in_candidates: '候选片段中未找到', needs_more_information: '需要补充信息',
  human_verification: '需要人工核实',
};
const decisionLabels: Record<AiReviewDecisionKind, string> = {
  accepted: '采纳', accepted_edited: '修改后采纳', rejected: '驳回',
};

function citationView(citation: { quote: string; reason: string; start_line: number; end_line: number }, fileName: string): string {
  const line = citation.start_line === citation.end_line
    ? `抽取文本第 ${citation.start_line} 行`
    : `抽取文本第 ${citation.start_line}-${citation.end_line} 行`;
  return `<blockquote>${escape(citation.quote)}</blockquote><p>${escape(citation.reason)}</p><small>${escape(fileName)} · ${line}</small>`;
}

function resultView(review: AiReviewRecord): string {
  const result = review.result;
  const partial = review.text_status === 'partial'
    ? '<p class="ai-review-warning">部分内容无法抽取；扫描页、图片及截断区域未参与审阅。</p>' : '';
  const body = review.mode === 'evidence_search'
    ? `${(result.claims || []).map(claim => `<div class="ai-review-citation"><b>${escape(signalLabels[claim.signal] || claim.signal)}</b>${citationView(claim, review.file_name)}</div>`).join('') || '<p>候选片段中没有可引用的线索。</p>'}${(result.questions || []).map(question => `<p class="ai-review-question">待人工核对：${escape(question)}</p>`).join('')}`
    : (result.reviews || []).map(item => `<article class="ai-review-element" data-testid="ai-review-element-${escape(item.element_id)}"><h4>${escape(item.element_id)} · ${escape(item.element)}</h4><span class="ai-review-status">${escape(statusLabels[item.status] || item.status)}</span><p>${escape(item.rationale)}</p>${item.support.map(citation => `<div class="ai-review-citation"><b>支持线索</b>${citationView(citation, review.file_name)}</div>`).join('')}${item.contrary.map(citation => `<div class="ai-review-citation is-contrary"><b>反向线索</b>${citationView(citation, review.file_name)}</div>`).join('')}${item.questions.map(question => `<p class="ai-review-question">待人工核对：${escape(question)}</p>`).join('')}</article>`).join('');
  return `<p class="ai-review-summary">${escape(result.summary)}</p>${partial}<div class="ai-review-result">${body}</div><small class="ai-review-meta">模型 ${escape(review.model)} · ${review.latency_ms} ms · 规则 v${escape(review.rule_set_version)}</small>`;
}

function reviewCard(review: AiReviewRecord): string {
  const decisions = review.decisions.map(item => `<li><b>${escape(decisionLabels[item.decision])}</b><span>${escape(item.note)}</span><time>${escape(item.created_at)}</time>${item.edited_result ? `<p>${escape(item.edited_result)}</p>` : ''}</li>`).join('');
  return `<article class="ai-review-card" data-review-card="${escape(review.review_uid)}" data-testid="ai-review-card-${escape(review.review_uid)}">
    <div class="ai-review-card-heading"><div><h3>${escape(review.clause)} · ${escape(review.rule_title)}</h3><p>${escape(review.file_name)} · ${escape(modeLabels[review.mode])}</p></div><span>${escape(review.model)}</span></div>
    ${resultView(review)}
    <details class="ai-review-decisions"><summary>人工决定（${review.decisions.length}）</summary><ul>${decisions || '<li>尚无人工决定</li>'}</ul></details>
    <div class="ai-review-decision-form"><label>人工说明<textarea data-review-note maxlength="1000" placeholder="填写采纳或驳回理由"></textarea></label>
      <div class="ai-review-actions"><button type="button" class="button button-secondary" data-review-decision="accepted">采纳</button><button type="button" class="button button-secondary" data-review-edit-toggle>修改后采纳</button><button type="button" class="button button-secondary" data-review-decision="rejected">驳回</button></div>
      <div class="ai-review-edit" hidden><label>修改后的审阅内容<textarea data-review-edited maxlength="12000">${escape(review.result.summary)}</textarea></label><button type="button" class="button button-primary" data-review-decision="accepted_edited">保存修改并采纳</button></div>
      <p class="ai-review-form-status" role="status" data-review-status></p>
    </div>
  </article>`;
}

export function renderAiReviewPanel(data: ValidationResult): string {
  if (!data.prescreen || !data.documents.length || !data.findings.length) return '';
  const rules = [...new Map(data.findings.map(item => [item.rule_id, item])).values()];
  return `<section class="ai-review-panel" data-testid="ai-review-panel">
    <div class="ai-review-heading"><div><p class="eyebrow">AI ASSISTED READING</p><h2>AI 文件阅读审核</h2></div></div>
    <p class="ai-review-boundary">AI 只整理候选原文线索，不作符合性结论，也不会改变本次预筛状态、覆盖率或分数。请逐条对照原文件复核。</p>
    <div class="ai-review-controls">
      <fieldset class="ai-review-modes"><legend>审阅方式</legend><label data-testid="ai-review-mode-evidence"><input type="radio" name="ai-review-mode" value="evidence_search" checked><span>查找依据</span></label><label data-testid="ai-review-mode-semantic"><input type="radio" name="ai-review-mode" value="semantic_review"><span>逐项审阅</span></label></fieldset>
      <label>检查项<select data-testid="ai-review-rule">${rules.map(item => `<option value="${escape(item.rule_id)}">${escape(item.clause)} · ${escape(item.title)}</option>`).join('')}</select></label>
      <label>本次预筛文件<select data-testid="ai-review-file">${data.documents.map(item => `<option value="${escape(item.file_uid)}">${escape(item.name)}</option>`).join('')}</select></label>
      <button type="button" class="button button-primary" data-testid="ai-review-start">开始 AI 审阅</button>
    </div>
    <p class="ai-review-panel-status" role="status" data-testid="ai-review-status"></p>
    <button type="button" class="button button-secondary" data-testid="ai-review-retry">重新检查并加载记录</button>
    <div class="ai-review-list" data-testid="ai-review-list"><p>正在读取本次任务的 AI 审阅记录…</p></div>
  </section>`;
}

export function bindAiReviewEvents(root: HTMLElement, data: ValidationResult): void {
  const panel = root.querySelector<HTMLElement>('[data-testid="ai-review-panel"]');
  if (!panel) return;
  const list = panel.querySelector<HTMLElement>('[data-testid="ai-review-list"]')!;
  const status = panel.querySelector<HTMLElement>('[data-testid="ai-review-status"]')!;
  const records: AiReviewRecord[] = [];
  const startButton = panel.querySelector<HTMLButtonElement>('[data-testid="ai-review-start"]')!;
  const retryButton = panel.querySelector<HTMLButtonElement>('[data-testid="ai-review-retry"]')!;
  let pending = false;
  let ready = false;
  let loaded = false;
  startButton.disabled = true;

  const updateControls = () => {
    panel.querySelectorAll<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement | HTMLButtonElement>('input, select, textarea, button')
      .forEach(control => { control.disabled = pending; });
    startButton.disabled = pending || !ready || !loaded;
  };

  const paint = () => {
    list.innerHTML = records.length ? records.slice().reverse().map(reviewCard).join('') : '<p>本次预筛尚无 AI 审阅记录。</p>';
    list.querySelectorAll<HTMLButtonElement>('[data-review-edit-toggle]').forEach(button => button.addEventListener('click', () => {
      const form = button.closest<HTMLElement>('.ai-review-decision-form');
      const editor = form?.querySelector<HTMLElement>('.ai-review-edit');
      if (editor) editor.hidden = !editor.hidden;
    }));
    list.querySelectorAll<HTMLButtonElement>('[data-review-decision]').forEach(button => button.addEventListener('click', async () => {
      if (pending) return;
      const card = button.closest<HTMLElement>('[data-review-card]')!;
      const note = card.querySelector<HTMLTextAreaElement>('[data-review-note]')!.value.trim();
      const decision = button.dataset.reviewDecision as AiReviewDecisionKind;
      const edited = card.querySelector<HTMLTextAreaElement>('[data-review-edited]')?.value.trim() || '';
      const formStatus = card.querySelector<HTMLElement>('[data-review-status]')!;
      if (!note) { formStatus.textContent = '请先填写人工说明。'; return; }
      if (decision === 'accepted_edited' && !edited) { formStatus.textContent = '请填写修改后的审阅内容。'; return; }
      pending = true;
      updateControls();
      try {
        const saved = await aiReviewApi.decide(card.dataset.reviewCard!, decision, note, decision === 'accepted_edited' ? edited : '');
        const record = records.find(item => item.review_uid === card.dataset.reviewCard);
        record?.decisions.push(saved);
        formStatus.textContent = '人工决定已保存。';
        paint();
      } catch (error) {
        formStatus.textContent = error instanceof Error ? error.message : '人工决定保存失败';
      } finally {
        pending = false;
        updateControls();
      }
    }));
  };

  startButton.addEventListener('click', async () => {
    if (pending || !ready || !loaded) return;
    const mode = panel.querySelector<HTMLInputElement>('input[name="ai-review-mode"]:checked')?.value as 'evidence_search' | 'semantic_review';
    const ruleId = panel.querySelector<HTMLSelectElement>('[data-testid="ai-review-rule"]')!.value;
    const fileUid = panel.querySelector<HTMLSelectElement>('[data-testid="ai-review-file"]')!.value;
    pending = true; updateControls(); status.textContent = '正在生成 AI 候选意见…';
    try {
      const created = await aiReviewApi.create(data.run_uid, mode, ruleId, fileUid);
      records.push(created); status.textContent = '候选意见已保存，请核对原文。'; paint();
    } catch (error) {
      if (error instanceof ApiRequestError && error.code === 1401) ready = false;
      if (error instanceof ApiRequestError && error.code === 1502) loaded = false;
      status.textContent = error instanceof ApiRequestError && error.code === 1401
        ? '模型尚未启用或配置不完整，请联系管理员完成模型配置，再重新检查。'
        : error instanceof Error ? error.message : 'AI 审阅失败';
    } finally {
      pending = false; updateControls();
    }
  });

  const reload = async () => {
    if (pending) return;
    pending = true; updateControls(); status.textContent = '正在检查模型状态并读取审阅记录…';
    try {
      const [history, model] = await Promise.allSettled([aiReviewApi.list(data.run_uid), llmApi.status()]);
      if (!panel.isConnected) return;
      loaded = history.status === 'fulfilled';
      ready = model.status === 'fulfilled' && model.value.ready;
      if (history.status === 'fulfilled') {
        records.splice(0, records.length, ...history.value); paint();
      } else list.innerHTML = '<p>暂时无法读取 AI 审阅记录，请重新加载。</p>';
      const failure = history.status === 'rejected' ? history.reason : model.status === 'rejected' ? model.reason : null;
      status.textContent = failure ? (failure instanceof Error ? failure.message : '读取审阅信息失败，请重试。')
        : ready ? '' : '模型尚未启用或配置不完整，请联系管理员完成模型配置，再重新检查。';
    } finally {
      pending = false; updateControls();
    }
  };
  retryButton.addEventListener('click', () => { void reload(); });
  void reload();
}
