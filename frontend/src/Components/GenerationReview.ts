import type { GenerationMetadata } from '../Types/Authoring';
import { factLabels } from '../Types/Prescreen';
import { escape } from '../Utils/Html';
import '../prescreen.css';

function describe(value: unknown): string {
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  if (Array.isArray(value)) return value.map(describe).filter(Boolean).join('；');
  if (value && typeof value === 'object') return Object.entries(value).filter(([, item]) => item !== null && item !== '').map(([key, item]) => `${({ section_id: '章节', message: '说明', detail: '详情', clause: '条款', title: '标题', item: '事项', reason: '原因', missing: '缺失', missing_terms: '缺失要素', placeholder: '待确认', source: '来源' } as Record<string, string>)[key] || key}：${describe(item)}`).join('；');
  return '';
}

export function renderGenerationReview(metadata: GenerationMetadata): string {
  const basis = metadata.requirements_basis;
  const review = metadata.generation_review;
  if (!basis && !review) return '';
  return `<section class="generation-review"><h3>生成依据与待补事项</h3><p>依据和自检随当前已保存版本保留；文本生成不能代替真实活动、审批或实施证据。</p>
    ${review ? `<div data-testid="generation-review"><p>待补 ${escape(review.pending_count ?? review.pending?.length ?? 0)} 项</p>${review.pending?.length ? `<ul>${review.pending.map(row => `<li>${escape(describe(row))}</li>`).join('')}</ul>` : '<p>未检出当前自检定义支持的待补项，仍须人工复核。</p>'}${review.reference_gaps?.length ? `<p>引用待核对：</p><ul>${review.reference_gaps.map(row => `<li>${escape(describe(row))}</li>`).join('')}</ul>` : ''}${review.missing_requirements?.length ? `<p>要求安排待补：</p><ul>${review.missing_requirements.map(row => `<li>${escape(describe(row))}</li>`).join('')}</ul>` : ''}${review.manual_review?.length ? `<p>人工核实：</p><ul>${review.manual_review.map(row => `<li>${escape(describe(row))}</li>`).join('')}</ul>` : ''}${review.boundary ? `<p>${escape(review.boundary)}</p>` : ''}</div>` : ''}
    ${basis ? `<details data-testid="generation-basis"><summary data-testid="generation-basis-toggle">${basis.legacy ? '历史依据待核对' : '固定条款依据'} · v${escape(basis.version)} · ${basis.requirements?.length || 0} 项</summary>${basis.source ? `<p>目录来源：${escape(describe(basis.source))}</p>` : ''}${(basis.requirements || []).map(row => `<article><b>${escape(row.clause)} ${escape(row.title)}</b><p>编写要求：${escape(describe(row.generation))}</p><p>来源：${escape(describe(row.source))}</p>${row.conditions?.length ? `<p>适用条件：${row.conditions.map(value => escape(factLabels[value] || value)).join('、')}</p>` : ''}${row.uncertainty ? `<p>不确定事项：${escape(describe(row.uncertainty))}</p>` : ''}</article>`).join('')}</details>` : ''}</section>`;
}
