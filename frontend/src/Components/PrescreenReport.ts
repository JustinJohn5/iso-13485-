import type { Finding } from '../Api';
import { assessmentLabels, factLabels, purposeLabels, type PrescreenReport } from '../Types/Prescreen';
import { escape } from '../Utils/Html';
import '../prescreen.css';

export function renderPrescreenSummary(report: PrescreenReport, verdict = ''): string {
  const coverage = report.coverage;
  const scope = report.context?.scope === 'system' ? '组织体系级' : '单份或选定文件';
  return `<div class="prescreen-report" data-testid="prescreen-summary"><div class="prescreen-coverage"><span>基础文本线索覆盖率</span><strong data-testid="prescreen-coverage">${coverage.computable && coverage.value !== null ? `${escape(coverage.value)}%` : '—'}</strong><span data-testid="active-count">${coverage.denominator}</span><small>适用文本检查单元 · 已检出 ${coverage.numerator} 项</small></div>
    <p>${scope} · 规则 ${escape(report.version)} · 基准日 ${escape(report.context?.as_of_date || '未指定')}<br>${escape(report.context?.scope_description || '仅对所选文件承载的要求进行预筛。')}</p>
    ${!coverage.computable ? '<p>当前范围或适用性信息不足，暂不计算覆盖率。</p>' : ''}
    <div class="prescreen-states">${Object.entries(assessmentLabels).map(([key, label]) => `<div data-testid="prescreen-count-${key}"><b>${report.counts[key as keyof typeof assessmentLabels] || 0}</b><span>${label}</span></div>`).join('')}</div><p>适用性待确认：${report.applicability_pending || 0} 项。${escape(report.calculation || '覆盖率按子检查和对象不加权；未知适用性与仅人工事项单列。')}</p>
    <details><summary data-testid="prescreen-frozen-context">本次范围与条件快照</summary><p>${Object.entries(report.context?.facts || {}).map(([key, value]) => `${escape(factLabels[key] || key)}：${value === 'yes' ? '适用' : value === 'no' ? '事实不适用（仍须条款确认）' : '未知'}`).join('；')}</p>${(report.context?.decisions || []).map(row => `<p data-testid="prescreen-frozen-decision-${escape(row.clause)}">条款 ${escape(row.clause)}<br>理由：${escape(row.reason)}<br>依据：${escape(row.basis)}${row.confirmed_by !== undefined && row.confirmed_at ? `<br>确认用户 ${escape(row.confirmed_by)} · ${escape(row.confirmed_at)}` : ''}</p>`).join('')}</details>
    ${verdict ? `<p data-testid="result-verdict"><strong>${escape(verdict)}</strong></p>` : ''}<p>${escape(report.boundary || '预筛仅提供文本线索；实施与符合性需人工审核。')}</p></div>`;
}

export function findingLabel(finding: Pick<Finding, 'status' | 'assessment_status'>): string {
  return finding.assessment_status ? assessmentLabels[finding.assessment_status] || finding.assessment_status : finding.status === 'pass' ? '通过' : finding.status === 'fail' ? '待核实' : '未适用';
}

function locations(rows: Finding['locations']): string {
  return (rows || []).map(row => `<small>证据位置：${escape(row.file_uid || row.document_uid)} · 抽取文本第 ${escape(row.line)} 行（非原件页坐标）${row.excerpted ? ' · 证据节选' : ''}<br>${escape(row.quote)}</small>`).join('');
}

export function findingDetails(finding: Finding): string {
  return `<div class="finding-extra">${finding.purpose && purposeLabels[finding.purpose] ? `<small>本项文件用途：${escape(purposeLabels[finding.purpose])}</small>` : ''}${finding.basis_kind ? `<small>依据类别：${finding.basis_kind === 'standard' ? '标准要求' : '项目约定'}</small>` : ''}${finding.source ? `<small>来源：${escape(typeof finding.source === 'object' ? JSON.stringify(finding.source) : finding.source)}</small>` : ''}${finding.matched_terms?.length ? `<small>命中要素：${finding.matched_terms.map(escape).join('；')}</small>` : ''}${finding.missing_terms?.length ? `<small>缺失要素：${finding.missing_terms.map(escape).join('；')}</small>` : ''}${locations(finding.locations)}${finding.checks?.length ? `<details><summary>逐项要素（${finding.checks.length}）</summary>${finding.checks.map(row => `<p><b>${escape(row.element)}</b> · ${escape(assessmentLabels[row.assessment_status] || row.assessment_status)}<br>${escape(row.detail)}${row.matched_term ? `<br>命中词：${escape(row.matched_term)}` : ''}${locations(row.locations)}${(row.location_count || 0) > (row.locations?.length || 0) ? '<small>仅展示代表证据。请查阅原件核对其余线索。</small>' : ''}</p>`).join('')}</details>` : ''}${finding.manual_review?.length ? `<small>人工核实：${finding.manual_review.map(escape).join('；')}</small>` : ''}</div>`;
}
