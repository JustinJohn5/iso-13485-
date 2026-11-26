export type AiReviewMode = 'evidence_search' | 'semantic_review';
export type AiReviewDecisionKind = 'accepted' | 'accepted_edited' | 'rejected';

export interface AiCitation {
  snippet_id: string;
  quote: string;
  reason: string;
  file_uid: string;
  start_line: number;
  end_line: number;
}

export interface AiReviewRecord {
  review_uid: string;
  mode: AiReviewMode;
  rule_id: string;
  rule_title: string;
  clause: string;
  rule_set_version: string;
  file_uid: string;
  file_name: string;
  text_status: string;
  model: string;
  latency_ms: number;
  created_at: string;
  result: {
    summary: string;
    claims?: Array<AiCitation & { signal: 'support' | 'contrary' | 'uncertain'; reason: string }>;
    questions?: string[];
    reviews?: Array<{
      element_id: string;
      element: string;
      terms: string[];
      status: 'supporting_signal' | 'contrary_signal' | 'not_found_in_candidates' | 'needs_more_information' | 'human_verification';
      support: AiCitation[];
      contrary: AiCitation[];
      rationale: string;
      questions: string[];
    }>;
  };
  decisions: Array<{
    decision: AiReviewDecisionKind;
    note: string;
    edited_result: string;
    decided_by: number;
    created_at: string;
  }>;
}
