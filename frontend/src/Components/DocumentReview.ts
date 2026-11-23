import type { ControlMetadata, DocumentReview, MetadataChanges, RequirementConflict, VersionGroup } from '../Types/DocumentControl';
import { escape } from '../Utils/Html';

const categories = { policy: 'a) 质量方针和质量目标', manual: 'b) 质量手册', required: 'c) 标准要求的程序和记录', organization: 'd) 组织所需文件和记录', regulatory: 'e) 适用法规要求的其他文件', unclassified: '待确认类别' };
const layers = { document: '受控文件', template: '空白表单模板', record: '已填写记录', unknown: '层级待确认' };
const statuses = { unknown: '批准状态待核实', controlled: '标注为现行/受控', draft: '草稿/待批准', obsolete: '已作废' };

function options(values: Record<string, string>, selected: string): string {
  return Object.entries(values).map(([value, label]) => `<option value="${escape(value)}" ${selected === value ? 'selected' : ''}>${escape(label)}</option>`).join('');
}

export function renderMetadata(metadata: ControlMetadata, index: number, busy: boolean): string {
  const field = (key: keyof MetadataChanges, label: string, type = 'text') => `<label>${label}<input ${busy ? 'disabled' : ''} data-meta-index="${index}" data-meta-field="${key}" data-testid="meta-${index}-${key}" type="${type}" maxlength="${key === 'number' ? 64 : 32}" value="${escape(metadata[key])}"></label>`;
  const select = (key: keyof MetadataChanges, label: string, values: Record<string, string>) => `<label>${label}<select ${busy ? 'disabled' : ''} data-meta-index="${index}" data-meta-field="${key}" data-testid="meta-${index}-${key}">${options(values, metadata[key])}</select></label>`;
  return `<details class="control-metadata" data-testid="metadata-${index}"><summary>文件控制信息：${escape(metadata.number || '编号待确认')} · ${escape(metadata.revision || '版本待确认')}（可校正）</summary>
    <div class="metadata-grid">${field('number', '文件编号')}${field('revision', '版本/修订')}${field('effective_date', '生效日期', 'date')}${select('category', '文件类别（类别不代表优先级）', categories)}${select('layer', '文件层级', layers)}${select('status', '原件标注状态', statuses)}</div>
    ${metadata.warnings.map((warning) => `<p class="control-note">${escape(warning)}</p>`).join('')}
    ${metadata.sources.map((source) => `<small>${escape(source.field)} · ${source.line ? `抽取文本第 ${source.line} 行` : '用户校正'}：${escape(source.quote)}</small>`).join('')}
    <p class="control-note">c/d 类须依据具体要求确认；“批准”字段存在不代表已验证批准。校正信息后需重新检查关联与版本。</p></details>`;
}

function decisionForm(review: DocumentReview, group: VersionGroup | RequirementConflict, kind: 'version' | 'requirement', busy: boolean): string {
  const selected = group.decision?.file_uid || (kind === 'version' ? (group as VersionGroup).suggested_file_uid : '');
  return `<form data-review-decision="${group.id}" data-review-kind="${kind}" class="decision-form">
    <label>${kind === 'version' ? '本次采用的正式版本' : '本次采用的要求依据'}<select required name="file_uid" data-testid="choice-${group.id}" ${busy ? 'disabled' : ''}><option value="">请选择并核对原件</option>${group.file_uids.map((uid) => {
      const document = review.documents.find((item) => item.file_uid === uid)!;
      const blocked = kind === 'version' ? (group as VersionGroup).ineligible[uid] : '';
      return `<option value="${escape(uid)}" ${selected === uid ? 'selected' : ''} ${blocked ? 'disabled' : ''}>${escape(document.name)} · ${escape(document.metadata.revision || '版本未知')}${blocked ? ` · ${escape(blocked)}` : ''}</option>`;
    }).join('')}</select></label>
    <label>确认依据（至少 5 字）<input name="reason" required minlength="5" maxlength="500" data-testid="reason-${group.id}" placeholder="例如：已核对受控清单、批准和生效信息" value="${escape(group.decision?.reason || '')}" ${busy ? 'disabled' : ''}></label>
    <button type="submit" class="button button-secondary" data-testid="confirm-${group.id}" ${busy ? 'disabled' : ''}>${group.decision ? '更新确认依据' : '确认并留痕'}</button>
    ${group.decision ? `<p class="control-confirmed" data-testid="confirmed-${group.id}">已由用户 ${group.decision.user_id} 于 ${escape(group.decision.confirmed_at)} 确认${kind === 'requirement' ? '；源文件仍需修订以消除冲突' : ''}</p>` : ''}</form>`;
}

export function renderDocumentReview(review: DocumentReview | null, asOf: string, busy: boolean, hasFiles: boolean): string {
  const name = (uid: string) => escape(review?.documents.find((row) => row.file_uid === uid)?.name || uid);
  return `<section class="section-block document-review" data-testid="document-review-panel"><div class="section-title"><div><h2>关联文件与正式版本</h2></div></div>
    <p class="control-note">按 4.2.1 的 a～e 类组织文件，不将列举顺序视为效力排序。先核对编号、层级、状态和生效信息；建议版本需人工确认，原件始终保留。</p>
    <div class="review-actions"><label>审核基准日<input type="date" data-testid="review-date" id="review-date" value="${escape(asOf)}" ${busy ? 'disabled' : ''}></label><button class="button button-secondary" id="check-relations" data-testid="check-relations" ${busy || !hasFiles ? 'disabled' : ''}>检查关联与版本</button></div>
    ${review ? `<p class="control-note" data-testid="review-status">${review.ready ? '冲突依据已确认，可继续预筛' : '存在未确认冲突，请选择依据并确认'} · 审查 ${escape(review.review_uid)} / 修订 ${review.revision}</p>
      ${review.version_groups.map((group) => `<article class="control-conflict" data-testid="version-${group.number}"><h3>同编号版本冲突 · ${escape(group.number)}</h3><p>${escape(group.explanation)}</p><ul>${group.file_uids.map((uid) => { const doc = review.documents.find((item) => item.file_uid === uid)!; return `<li>${name(uid)} · 版本 ${escape(doc.metadata.revision || '未知')} · 生效 ${escape(doc.metadata.effective_date || '未知')} · ${escape(statuses[doc.metadata.status as keyof typeof statuses] || doc.metadata.status)}${group.ineligible[uid] ? ` · ${escape(group.ineligible[uid])}` : ''}</li>`; }).join('')}</ul>${decisionForm(review, group, 'version', busy)}</article>`).join('')}
      ${review.requirement_conflicts.map((group) => `<article class="control-conflict" data-testid="requirement-${group.number}"><h3>跨文件要求冲突 · ${escape(group.number)} / ${escape(group.field)}</h3><p>${escape(group.explanation)}</p>${group.facts.map((fact) => `<blockquote>${name(fact.file_uid)} · 抽取文本第 ${fact.line} 行<br>${escape(fact.quote)}</blockquote>`).join('')}${decisionForm(review, group, 'requirement', busy)}</article>`).join('')}
      <details class="reference-list" ${review.references.length ? 'open' : ''}><summary>编号引用对照（${review.references.length} 项）</summary>${review.references.map((ref) => `<p data-testid="reference-${escape(ref.number)}"><b>${name(ref.source_file_uid)} → ${escape(ref.number)}</b> · ${ref.status === 'missing' ? '本次未提供、待补充' : ref.status === 'pending' ? '候选或版本待确认' : '已找到编号候选，内容及指定版本仍需核对'}<small>抽取文本第 ${ref.line} 行：${escape(ref.quote)}</small></p>`).join('')}</details>
      <p class="control-note">当前跨文件内容检查仅覆盖明确指向同一编号的数字保存期限，尚未覆盖全部职责、频次和语义冲突。确认记录用于本次预筛，不代替组织的受控批准与发布。</p>` : ''}</section>`;
}

export function bindReviewEvents(root: HTMLElement, onMetadata: (index: number, field: keyof MetadataChanges, value: string) => void,
  onDate: (value: string) => void, onCheck: () => void, onDecision: (kind: 'version' | 'requirement', id: string, uid: string, reason: string) => void): void {
  root.querySelectorAll<HTMLInputElement | HTMLSelectElement>('[data-meta-field]').forEach((input) => input.addEventListener('change', () => onMetadata(Number(input.dataset.metaIndex), input.dataset.metaField as keyof MetadataChanges, input.value)));
  root.querySelector<HTMLInputElement>('#review-date')?.addEventListener('change', (event) => onDate((event.target as HTMLInputElement).value));
  root.querySelector('#check-relations')?.addEventListener('click', onCheck);
  root.querySelectorAll<HTMLFormElement>('[data-review-decision]').forEach((form) => form.addEventListener('submit', (event) => {
    event.preventDefault(); const data = new FormData(form);
    onDecision(form.dataset.reviewKind as 'version' | 'requirement', form.dataset.reviewDecision!, String(data.get('file_uid')), String(data.get('reason')));
  }));
}
