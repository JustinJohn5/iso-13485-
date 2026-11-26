import { request } from '../Api';
import type { AiReviewDecisionKind, AiReviewMode, AiReviewRecord } from '../Types/AiReview';

export const aiReviewApi = {
  list: (runUid: string) => request<AiReviewRecord[]>(`/api/v1/validations/${encodeURIComponent(runUid)}/ai-reviews`),
  create: (runUid: string, mode: AiReviewMode, ruleId: string, fileUid: string) => request<AiReviewRecord>(
    `/api/v1/validations/${encodeURIComponent(runUid)}/ai-reviews`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode, rule_id: ruleId, file_uid: fileUid }),
    },
  ),
  decide: (reviewUid: string, decision: AiReviewDecisionKind, note: string, editedResult = '') => request<AiReviewRecord['decisions'][number]>(
    `/api/v1/ai-reviews/${encodeURIComponent(reviewUid)}/decision`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision, note, edited_result: editedResult }),
    },
  ),
};
