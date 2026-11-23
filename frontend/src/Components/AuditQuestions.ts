import { download, request, type ValidationResult } from '../Api';
import { escape } from '../Utils/Html';

interface AuditReport {
  run_uid: string; basis: string; disclaimer: string;
  summary: Record<string, number>;
  questions: Array<{ id: string; kind: string; title: string; clause: string; document: string; evidence: string; question: string; action: string }>;
}

const labels: Record<string, string> = { gap: '规则缺项', reference: '引用待核对', conflict: '跨文件冲突', verification: '实施取证' };

export function renderAuditQuestions(): string {
  return `<section class="section-block audit-report" data-testid="audit-panel"><div class="section-title"><div><h2>模拟内审</h2><p>基于本次预筛证据，整理提问、取证和整改方向。</p></div></div>
    <div class="draft-actions"><button class="button button-secondary" data-testid="generate-audit" id="generate-audit">生成内审问题清单</button><button class="button button-secondary" data-testid="download-audit" id="download-audit">下载问题清单 Word</button></div>
    <div id="audit-feedback" role="status"></div><div id="audit-questions" data-testid="audit-questions"></div></section>`;
}

export function bindAuditQuestions(root: HTMLElement, result: ValidationResult): void {
  const generate = root.querySelector<HTMLButtonElement>('#generate-audit');
  const exportButton = root.querySelector<HTMLButtonElement>('#download-audit');
  if (!generate || !exportButton) return;
  const feedback = root.querySelector<HTMLElement>('#audit-feedback')!;
  const panel = root.querySelector<HTMLElement>('#audit-questions')!;
  const url = `/api/v1/validations/${encodeURIComponent(result.run_uid)}/audit-report`;
  async function run(action: () => Promise<void>): Promise<void> {
    generate!.disabled = exportButton!.disabled = true; feedback.textContent = '正在处理…';
    try { await action(); feedback.textContent = ''; }
    catch (error) { feedback.textContent = error instanceof Error ? error.message : '操作失败，请重试'; }
    finally { generate!.disabled = exportButton!.disabled = false; }
  }
  generate.addEventListener('click', () => { void run(async () => {
    const data = await request<AuditReport>(url);
    panel.innerHTML = `<p class="control-note">${escape(data.basis)}</p><div class="audit-summary" data-testid="audit-summary">${Object.entries(data.summary).map(([kind, count]) => `<span>${escape(labels[kind] || kind)} <b>${count}</b></span>`).join('')}</div>
      ${data.questions.map((question, index) => `<article class="audit-question" data-testid="audit-question-${question.kind}"><small>${index + 1} · ${escape(labels[question.kind])}${question.clause ? ` · ${escape(question.clause)}` : ''}</small><h3>${escape(question.title)}</h3>
        ${question.document ? `<p>相关文件范围：${escape(question.document)}</p>` : ''}<blockquote>${escape(question.evidence || '当前可提取文本未检出，请核对原件。')}</blockquote><p><b>审核提问：</b>${escape(question.question)}</p><p><b>建议跟进：</b>${escape(question.action)}</p></article>`).join('')}
      <p class="control-note">${escape(data.disclaimer)}</p>`;
  }); });
  exportButton.addEventListener('click', () => { void run(async () => download(`${url}/download`, '模拟内审问题清单.docx')); });
}
