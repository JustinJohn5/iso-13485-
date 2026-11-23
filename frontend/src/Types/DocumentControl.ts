export interface ControlMetadata {
  number: string; revision: string; effective_date: string; status: string; category: string; layer: string;
  sources: Array<{ field: string; quote: string; line: number }>;
  warnings: string[];
}
export type MetadataChanges = Partial<Pick<ControlMetadata, 'number' | 'revision' | 'effective_date' | 'status' | 'category' | 'layer'>>;
export interface ReviewDecision {
  file_uid: string; reason: string; user_id: number; confirmed_at: string; kind: 'version' | 'requirement'; issue_id: string;
}
export interface ReviewDocument { file_uid: string; name: string; document_type: string; metadata: ControlMetadata }
export interface VersionGroup {
  id: string; number: string; file_uids: string[]; ineligible: Record<string, string>;
  suggested_file_uid: string; explanation: string; decision: ReviewDecision | null;
}
export interface RequirementConflict {
  id: string; number: string; field: string; file_uids: string[]; explanation: string; decision: ReviewDecision | null;
  facts: Array<{ file_uid: string; quote: string; line: number; value: string }>;
}
export interface DocumentReview {
  review_uid: string; revision: number; ready: boolean; as_of_date: string;
  documents: ReviewDocument[]; version_groups: VersionGroup[]; requirement_conflicts: RequirementConflict[];
  references: Array<{ source_file_uid: string; number: string; quote: string; line: number; target_file_uids: string[]; status: string }>;
  decision_history: ReviewDecision[];
}
