import { handbookApi } from '../Api/RuleHandbook';
import type { HandbookRule, RuleHandbook, RuleSetSummary } from '../Types/RuleHandbook';
import { escape } from '../Utils/Html';
import '../Suites.css';
import { factLabels } from '../Types/Prescreen';
import type { User } from '../Api';
import { AccountMenu } from './AccountMenu';

export class RuleHandbookPage {
  private sets: RuleSetSummary[] = [];
  private handbook: RuleHandbook | null = null;
  private query = '';
  private clause = '';
  private type = '';
  private error = '';
  private busy = false;

  constructor(private root: HTMLElement, private back: () => void, private user?: User) {}

  async open(): Promise<void> {
    window.scrollTo(0, 0);
    this.busy = true; this.render();
    try {
      this.sets = await handbookApi.list();
      if (this.sets.length) this.handbook = await handbookApi.get(this.sets[0].rule_set_id);
    } catch (error) { this.error = error instanceof Error ? error.message : '规则手册读取失败'; }
    finally { this.busy = false; this.render(); }
  }

  private render(): void {
    const book = this.handbook;
    const clauses = [...new Set(book?.rules.map(row => row.clause) || [])];
    this.root.innerHTML = `<main class="suite-page" data-testid="rule-handbook"><header class="suite-header"><div><p class="eyebrow">RULE HANDBOOK</p><h1>规则手册</h1><p>${escape(book?.standard || '')} · 规则版本 ${escape(book?.version || '')}</p></div><div class="account-anchor" data-testid="account-anchor"></div><button class="button button-secondary" id="rules-back" data-testid="rules-back">返回文件预筛</button></header>
      <p class="suite-note">这里展示系统实际执行的文本检查规则，包括适用类型、检查条件、依据和建议。${escape(book?.description || '')}</p>
      <p role="status">${this.busy ? '正在读取规则…' : escape(this.error)}</p>
      <section class="suite-card"><label>规则包与版本<select id="rule-set" data-testid="rule-set" ${this.busy ? 'disabled' : ''}>${this.sets.map(row => `<option value="${escape(row.rule_set_id)}" ${row.rule_set_id === book?.rule_set_id ? 'selected' : ''}>${escape(row.title)} · v${escape(row.version)}</option>`).join('')}</select></label>
      <div class="rule-filters suite-form"><label>检索编号、标题或内容<input id="rule-search" data-testid="rule-search" value="${escape(this.query)}" placeholder="例如 DOC-001 或文件控制"></label><label>条款<select id="rule-clause" data-testid="rule-clause"><option value="">全部条款</option>${clauses.map(value => `<option value="${escape(value)}" ${value === this.clause ? 'selected' : ''}>${escape(value)}</option>`).join('')}</select></label><label>适用文件类型<select id="rule-type" data-testid="rule-type"><option value="">全部类型</option>${book?.document_types.map(row => `<option value="${escape(row.type)}" ${row.type === this.type ? 'selected' : ''}>${escape(row.label)}</option>`).join('') || ''}</select></label></div>
      <div id="rule-list" data-testid="rule-list"></div></section></main>`;
    this.root.querySelector('#rules-back')?.addEventListener('click', this.back);
    const anchor = this.root.querySelector<HTMLElement>('[data-testid="account-anchor"]');
    if (anchor && this.user) new AccountMenu(anchor, this.user, () => { location.href = '/admin/'; });
    this.root.querySelector<HTMLInputElement>('#rule-search')?.addEventListener('input', event => { this.query = (event.target as HTMLInputElement).value; this.renderRules(); });
    this.root.querySelector<HTMLSelectElement>('#rule-clause')?.addEventListener('change', event => { this.clause = (event.target as HTMLSelectElement).value; this.renderRules(); });
    this.root.querySelector<HTMLSelectElement>('#rule-type')?.addEventListener('change', event => { this.type = (event.target as HTMLSelectElement).value; this.renderRules(); });
    this.root.querySelector<HTMLSelectElement>('#rule-set')?.addEventListener('change', event => { const value = (event.target as HTMLSelectElement).value; void this.load(value); });
    this.renderRules();
  }

  private async load(id: string): Promise<void> {
    this.busy = true; this.error = ''; this.render();
    try { this.handbook = await handbookApi.get(id); this.clause = ''; this.type = ''; }
    catch (error) { this.error = error instanceof Error ? error.message : '规则手册读取失败'; }
    finally { this.busy = false; this.render(); }
  }

  private condition(rule: HandbookRule): string {
    const check = rule.check;
    switch (check.type) {
      case 'present': return `正文匹配以下表达式，至少命中 ${check.min_matches} 次：\n${check.patterns.join('\n')}`;
      case 'absent': return `正文不得匹配以下表达式：\n${check.patterns.join('\n')}`;
      case 'all_terms': return `至少覆盖 ${check.min_groups ?? check.terms.length} 组词；同组任一词可命中：\n${check.terms.map(row => row.join(' / ')).join('\n')}`;
      case 'requirements': return `按文件用途与章节核对要求要素；同组词提供同义线索：\n${(check.terms || []).map(row => row.join(' / ')).join('\n')}\n占位、否定及适用性未知须继续核实。`;
      case 'section': return `查找章节标题：${check.headings.join(' / ')}`;
      case 'length': return `抽取正文至少 ${check.min_chars} 个字符`;
      case 'date': return `查找日期：${check.patterns.join(' / ')}\n${check.not_future ? '不能晚于运行当天。' : ''}${check.max_age_days !== null ? `距运行当天不超过 ${check.max_age_days} 天。` : ''}`;
      case 'required_documents': return `核对已提供的文件类型：${check.documents.map(value => this.label(value)).join('、')}`;
      default: return '请参照规则包定义核对';
    }
  }

  private label(type: string): string { return this.handbook?.document_types.find(row => row.type === type)?.label || type; }

  private renderRules(): void {
    const list = this.root.querySelector('#rule-list');
    if (!list || !this.handbook) return;
    const words = this.query.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
    const rules = this.handbook.rules.filter(rule => (!this.clause || rule.clause === this.clause) &&
      (!this.type || rule.document_types.includes('*') || rule.document_types.includes(this.type)) &&
      words.every(word => `${rule.rule_id} ${rule.title} ${rule.clause} ${rule.clause_title} ${rule.rationale} ${rule.suggestion} ${rule.source || ''} ${(rule.topics || []).join(' ')} ${this.condition(rule)}`.toLocaleLowerCase().includes(word)));
    list.innerHTML = `<p>显示 ${rules.length} / ${this.handbook.rules.length} 条规则</p>` + (rules.map(rule => {
      const severity = this.handbook!.severities[rule.severity];
      return `<article class="suite-finding" data-testid="handbook-rule-${escape(rule.rule_id)}"><h2>${escape(rule.rule_id)} · ${escape(rule.title)}</h2><p>条款 ${escape(rule.clause)} ${escape(rule.clause_title)} · ${escape(severity?.label || rule.severity)} · ${rule.per_document ? '逐份检查' : '同类合并检查'}</p><p>适用：${rule.document_types.includes('*') ? '所有文件' : rule.document_types.map(type => escape(this.label(type))).join('、')}</p>${rule.basis_kind ? `<p>依据类别：${rule.basis_kind === 'standard' ? '标准要求' : '项目约定'}</p>` : ''}${rule.source ? `<p>来源：${escape(typeof rule.source === 'object' ? JSON.stringify(rule.source) : rule.source)}</p>` : ''}<p>条件：${rule.conditions?.length ? rule.conditions.map(value => escape(factLabels[value] || value)).join('、') : '按文件范围与用途判断'}</p>${rule.uncertainty ? `<p>不确定事项：${escape(rule.uncertainty)}</p>` : ''}${rule.templates?.length ? `<p>关联模板：${rule.templates.map(escape).join('、')}</p>` : ''}<pre class="rule-check">${escape(this.condition(rule))}</pre><p><b>依据：</b>${escape(rule.rationale)}</p><p><b>建议：</b>${escape(rule.suggestion)}</p>${severity && !rule.basis_kind ? `<small>历史权重 ${severity.weight}${severity.score_cap !== null ? ` · 得分上限 ${severity.score_cap}` : ''}</small>` : ''}</article>`;
    }).join('') || '<p>未找到匹配规则，请调整检索条件。</p>');
  }
}
