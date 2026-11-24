import type { DocumentReview } from './DocumentControl';

export interface CatalogEntry { key: string; title: string; number: string; document_type: string; category: string }
export interface SuiteItem {
  id: string; title: string; number: string; file_version: string; catalog_key: string;
  document_type: string; origin: 'generated' | 'imported'; text?: string;
  sections?: Array<{ id: string; title: string; body: string }>;
}
export interface SuiteSummary {
  suite_uid: string; name: string; version: string; revision: number; item_count: number; updated_at: string;
}
export interface SuiteInspection {
  summary: string; checked_at: string; rule_set: { title: string; standard: string; version: string };
  score: { score: number }; missing_catalog: CatalogEntry[]; review: DocumentReview;
  findings: Array<{ rule_id: string; title: string; clause: string; status: string; document_name: string; evidence: string; detail: string; suggestion: string }>;
}
export interface ManualSuite extends SuiteSummary { items: SuiteItem[]; inspection: SuiteInspection | null }
export interface SuiteList { items: SuiteSummary[]; total: number; page: number; page_size: number }
