import type { DocumentReview } from './DocumentControl';
import type { DraftSnapshot, GenerationMetadata } from './Authoring';
import type { Finding } from '../Api';
import type { PrescreenReport } from './Prescreen';

export interface CatalogEntry { key: string; title: string; number: string; document_type: string; category: string }
export interface SuiteItem extends GenerationMetadata {
  id: string; title: string; number: string; file_version: string; catalog_key: string;
  document_type: string; origin: 'generated' | 'imported'; text?: string;
  sections?: Array<{ id: string; title: string; body: string }>;
  snapshot?: DraftSnapshot;
}
export interface SuiteSummary {
  suite_uid: string; name: string; version: string; revision: number; item_count: number; updated_at: string;
}
export interface SuiteInspection {
  checked_revision?: number;
  summary: string; checked_at: string; rule_set: { title: string; standard: string; version: string };
  score: { score: number; verdict?: string }; missing_catalog: CatalogEntry[]; review: DocumentReview;
  findings: Finding[];
  prescreen?: PrescreenReport;
}
export interface ManualSuite extends SuiteSummary {
  items: SuiteItem[]; inspection: SuiteInspection | null;
  inspection_history?: Array<{ checked_revision: number; checked_at: string; version: string }>;
}
export interface SuiteList { items: SuiteSummary[]; total: number; page: number; page_size: number }
