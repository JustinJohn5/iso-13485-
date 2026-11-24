export interface RuleSetSummary {
  rule_set_id: string; title: string; version: string; standard: string; description: string;
}
export interface HandbookRule {
  rule_id: string; title: string; clause: string; clause_title: string; severity: string;
  document_types: string[]; rationale: string; suggestion: string; per_document: boolean;
  basis_kind?: 'standard' | 'project'; source?: string; conditions?: string[];
  uncertainty?: string; templates?: string[]; topics?: string[];
  check: { type: string; patterns: string[]; headings: string[]; terms: string[][];
    min_matches: number; min_groups: number | null; min_chars: number; max_age_days: number | null;
    not_future: boolean; documents: string[] };
}
export interface RuleHandbook extends RuleSetSummary {
  rules: HandbookRule[]; document_types: Array<{ type: string; label: string }>;
  severities: Record<string, { label: string; weight: number; score_cap: number | null }>;
}
