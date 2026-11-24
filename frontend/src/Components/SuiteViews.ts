import { escape } from '../Utils/Html';
import type { CatalogEntry, ManualSuite, SuiteInspection, SuiteItem } from '../Types/ManualSuite';
import { renderGenerationReview } from './GenerationReview';
import { findingDetails, findingLabel, renderPrescreenSummary } from './PrescreenReport';
import { purposeSelect } from './PrescreenContext';
import type { PrescreenContext } from '../Types/Prescreen';
import { renderRequirementManual } from './DocumentReview';

export function suiteMembers(suite: ManualSuite, directory: CatalogEntry[], context: PrescreenContext): string {
  return `<section class="suite-card" data-testid="suite-items"><h2>文件清单 · ${suite.items.length} / 100</h2>
    <p>整套发布版本：${escape(suite.version)}。文件自身版本独立保留；调整归属不会修改原件正文。</p>
    ${suite.items.length ? suite.items.map(item => `<article class="suite-member">
      <div><strong>${escape(item.title)}</strong><small>${escape(item.number || '编号待确认')} · ${item.origin === 'generated' ? '生成草稿' : '导入原件'}</small></div>
      <label>目录归属<select data-item-key="${item.id}" data-testid="suite-item-key-${item.id}"><option value="">待归类</option>${directory.map(row => `<option value="${row.key}" ${item.catalog_key === row.key ? 'selected' : ''}>${escape(row.title)}</option>`).join('')}</select></label>
      <label>文件版本<input data-item-version="${item.id}" data-testid="suite-item-version-${item.id}" maxlength="32" value="${escape(item.file_version)}"></label>
      <label>文件用途${purposeSelect(context.purposes[item.id] || 'auto', `suite-item-purpose-${item.id}`, `data-suite-purpose="${item.id}"`)}</label>
      <div class="suite-actions"><button class="text-button" data-read="${item.id}" data-testid="suite-read-${item.id}">查阅正文</button><button class="text-button" data-save-item="${item.id}" data-testid="suite-save-${item.id}">保存归类</button><button class="text-button" data-remove-item="${item.id}" data-testid="suite-remove-${item.id}">移出本套</button></div>
    </article>`).join('') : '<p>本版本尚未添加文件。请选择目录生成草稿，或上传已有文件。</p>'}</section>`;
}

export function suiteReader(item: SuiteItem | null): string {
  return item ? `<section class="suite-card" data-testid="suite-reader"><div class="suite-actions"><h2>${escape(item.title)}</h2><button class="text-button" id="suite-close-reader" data-testid="suite-close-reader">收起正文</button></div><p>文件版本：${escape(item.file_version || '待确认')} · ${item.origin === 'generated' ? '待复核草稿' : '抽取文本，版式请以原件为准'}</p>${renderGenerationReview(item.snapshot || item)}<pre class="suite-text">${escape(item.text || '')}</pre>
    ${item.sections ? `<details><summary data-testid="suite-edit-body">编辑本套生成件正文</summary><form id="suite-edit-form" class="suite-form">${item.sections.map(row => `<label>${escape(row.title)}<textarea data-suite-section="${row.id}" data-testid="suite-section-${row.id}" maxlength="120000" required>${escape(row.body)}</textarea></label>`).join('')}<label>变更原因<input data-testid="suite-edit-reason" id="suite-edit-reason" minlength="5" maxlength="500" required></label><button class="button button-primary" data-testid="suite-save-body">保存本套正文</button></form></details>` : ''}</section>` : '';
}

export function suiteInspectionHistory(suite: ManualSuite, previous?: SuiteInspection): string {
  const history = suite.inspection_history || [];
  if (!history.length) return '';
  return `<section class="suite-card" data-testid="suite-inspection-history"><h2>历史检查</h2>
    <div class="suite-actions">${history.map(row => `<button class="text-button" data-checked-revision="${row.checked_revision}" data-testid="suite-inspection-${row.checked_revision}">修订 ${row.checked_revision} · 规则 ${escape(row.version)} · ${escape(row.checked_at)}</button>`).join('')}
    ${previous ? '<button class="text-button" id="suite-close-historical" data-testid="suite-close-historical">返回当前检查</button>' : ''}</div></section>`;
}

export function suiteInspection(suite: ManualSuite, previous?: SuiteInspection): string {
  const report = previous ?? suite.inspection;
  if (!report) return '<section class="suite-card"><h2>整套检查</h2><p>当前文件尚未检查或文件已变更，请点击“检查整套”。</p></section>';
  const names = new Map(report.review.documents.map(item => [item.file_uid, item.name]));
  const refs = report.review.references;
  const conflicts = [...report.review.version_groups, ...report.review.requirement_conflicts];
  return `<section class="suite-card" data-testid="suite-inspection">${previous ? `<p data-testid="suite-historical-report">历史检查 · 档案修订 ${escape(previous.checked_revision)}</p>` : ''}<h2>${escape(report.summary)}</h2>
    ${report.prescreen ? renderPrescreenSummary(report.prescreen, report.score.verdict) : `<p>文本线索分数：${report.score.score} · ${escape(report.rule_set.standard)} · 规则 v${escape(report.rule_set.version)} · 基准日 ${escape(report.review.as_of_date)}</p>`}
    <p>未提供目录 ${report.missing_catalog.length} 项。请按组织实际情况核对适用范围。</p>
    ${report.missing_catalog.length ? `<details><summary>未提供目录（${report.missing_catalog.length}）</summary><ul>${report.missing_catalog.map(row => `<li>${escape(row.title)} · ${escape(row.number)}</li>`).join('')}</ul></details>` : '<p>已提供本目录全部项目；仍须人工确认内容、批准和实施证据。</p>'}
    <details ${conflicts.length ? 'open' : ''}><summary>版本及内容冲突（${conflicts.length}）</summary>${conflicts.map(row => `<p><b>${escape(row.number)}</b>：${escape(row.explanation)}<br>${row.file_uids.map(id => escape(names.get(id) || id)).join('、')}</p>`).join('') || '<p>未检测到当前规则支持的冲突。</p>'}<p>冲突原件均保留；请核对后移出不适用文件，或修订原件并重新导入。</p></details>
    ${renderRequirementManual(report.review)}
    <details><summary>编号引用（${refs.length}）</summary>${refs.map(row => `<p>${escape(names.get(row.source_file_uid) || '')} → ${escape(row.number)}：${row.status === 'linked' ? '编号候选已找到' : row.status === 'missing' ? '本套未提供' : '版本待确认'}<br><small>${escape(row.quote)}</small></p>`).join('') || '<p>未抽取到明确编号引用。</p>'}</details>
    <details open><summary data-testid="suite-inspection-findings">检查项目（${report.findings.length}）</summary>${report.findings.map(row => `<article class="suite-finding" data-testid="suite-finding-${escape(row.rule_id)}"><b>${escape(row.rule_id)} · ${escape(row.title)}</b><span>${escape(findingLabel(row))} · ${escape(row.clause)} · ${escape(row.document_name)}</span><p>${escape(row.evidence || row.detail)}</p>${findingDetails(row)}<small>${escape(row.suggestion)}</small></article>`).join('')}</details></section>`;
}
