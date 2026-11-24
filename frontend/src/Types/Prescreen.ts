export type FactStatus = 'yes' | 'unknown' | 'no';
export type DocumentPurpose = 'auto' | 'procedure' | 'plan' | 'instruction' | 'report' | 'form' | 'record';
export type AssessmentStatus = 'evidence_found' | 'gap' | 'pending_input' | 'conflict' | 'unreadable' | 'manual_review' | 'not_applicable' | 'out_of_scope';
export interface PrescreenContext {
  scope: 'documents' | 'system'; scope_description: string; as_of_date: string | null;
  facts: Record<string, FactStatus>;
  decisions: Array<{ clause: string; reason: string; basis: string }>;
  purposes: Record<string, DocumentPurpose>;
}
export interface PrescreenReport {
  version: string; context: Omit<PrescreenContext, 'decisions'> & { decisions: Array<PrescreenContext['decisions'][number] & { confirmed_by?: number; confirmed_at?: string }> };
  counts: Record<AssessmentStatus, number>;
  coverage: { value: number | null; denominator: number; numerator: number; computable: boolean };
  items: unknown[];
  applicability_pending?: number;
  calculation?: string;
  boundary?: string;
  manual_questions?: Array<{ rule_id: string; clause: string; document_uid: string; question: string }>;
}
export const assessmentLabels: Record<AssessmentStatus, string> = {
  evidence_found: '已检出要求线索', gap: '文本缺口', pending_input: '信息待补', conflict: '内容冲突',
  unreadable: '无法判定', manual_review: '人工核实', not_applicable: '不适用且已确认', out_of_scope: '本文件不承载',
};
export const factLabels: Record<string, string> = {
  design: '设计开发', sterile: '无菌产品', implant: '植入产品', installation: '安装', servicing: '服务',
  outsourcing: '外包', software: '软件', cleaning: '清洁', process_validation: '过程确认', customer_property: '顾客财产',
};
export const purposeLabels: Record<DocumentPurpose, string> = {
  auto: '自动判断用途', procedure: '程序', plan: '计划', instruction: '作业规程', report: '报告', form: '空白表单', record: '实际记录',
};
export function createPrescreenContext(date: string): PrescreenContext {
  return { scope: 'documents', scope_description: '', as_of_date: date, facts: Object.fromEntries(Object.keys(factLabels).map(key => [key, 'unknown'])), decisions: [], purposes: {} };
}

/** 只恢复客户端可提交字段，不回传服务端确认身份和确认时间。 */
export function editableContext(saved: PrescreenContext): PrescreenContext {
  return { scope: saved.scope, scope_description: saved.scope_description, as_of_date: saved.as_of_date,
    facts: { ...saved.facts }, purposes: { ...saved.purposes },
    decisions: saved.decisions.map(row => ({ clause: row.clause, reason: row.reason, basis: row.basis })) };
}
