import type { Finding, ValidationResult } from '../Api';
import { escape } from '../Utils/Html';

function findingRows(items: Finding[]): string {
  return items.map((item, index) => {
    const previous = items[index - 1];
    const startsGroup = !previous || previous.clause !== item.clause || previous.document_name !== item.document_name;
    let span = 1;
    while (index + span < items.length && items[index + span].clause === item.clause && items[index + span].document_name === item.document_name) span++;
    const clause = startsGroup ? `<td rowspan="${span}" class="clause-cell"><span class="clause-id">${escape(item.clause)}</span><small>${escape(item.clause_title)}</small>${item.document_name ? `<small>${escape(item.document_name)}</small>` : ''}</td>` : '';
    const state = item.status === 'pass' ? '通过' : item.status === 'fail' ? '待核实' : '未适用';
    const severity = ({ critical: '严重', major: '主要', minor: '一般', observation: '观察' } as Record<string, string>)[item.severity] || item.severity;
    return `<tr data-testid="finding-${escape(item.rule_id)}">${clause}<td><strong>${escape(item.title)}</strong><small>${escape(item.rule_id)}</small></td><td><span class="severity severity-${escape(item.severity)}">${escape(severity)}</span></td><td><span class="finding-status status-${escape(item.status)}"><i></i>${state}</span></td><td data-testid="evidence-${escape(item.rule_id)}">${escape(item.evidence || item.detail || '—')}</td><td>${escape(item.suggestion || '—')}</td></tr>`;
  }).join('');
}

function findingTable(items: Finding[]): string {
  return `<div class="table-scroll"><table><thead><tr><th>文件与条款</th><th>检查项</th><th>级别</th><th>状态</th><th>命中证据</th><th>建议</th></tr></thead><tbody>${findingRows(items)}</tbody></table></div>`;
}

export function renderResult(data: ValidationResult): string {
  const active = data.findings.filter((item) => item.status !== 'skipped');
  const skipped = data.findings.filter((item) => item.status === 'skipped');
  const documents = data.documents.map((item) => `<span>${escape(item.name)} · ${escape(item.type_label)}</span>`).join('');
  return `<section class="result-section" id="result" data-testid="results">
    <div class="result-heading"><div><p class="eyebrow">SCREENING RESULT · ${escape(data.run_uid.slice(0, 8))}</p><h2 data-testid="results-title">预筛结果</h2></div><button id="reset-result" data-testid="reset-result" class="button button-secondary">新建预筛</button></div>
    <div class="result-documents" data-testid="result-documents">${documents}</div>
    ${data.duplicate_files.length ? `<p class="duplicate-note" data-testid="duplicate-note">已合并 ${data.duplicate_files.length} 份内容相同的文件，每份内容只参与一次计分。</p>` : ''}
    <div class="result-overview"><div class="score-block"><span>规则线索得分</span><strong>${data.score.score}<small>/100</small></strong><em>${escape(data.score.verdict)}</em></div><div class="result-stat"><strong data-testid="active-count">${data.score.total_count}</strong><span>参与检查项</span></div><div class="result-stat success-stat"><strong>${data.score.passed_count}</strong><span>通过</span></div><div class="result-stat warning-stat"><strong>${data.score.failed_count}</strong><span>待核实</span></div><div class="result-stat muted-stat"><strong>${data.score.skipped_count}</strong><span>未适用</span></div></div>
    ${findingTable(active)}
    ${skipped.length ? `<details class="skipped-findings" data-testid="skipped-findings"><summary data-testid="toggle-skipped">未参与判定的规则（${skipped.length} 项）</summary>${findingTable(skipped)}</details>` : ''}
    <div class="result-disclaimer">${escape(data.disclaimer)}</div></section>`;
}
