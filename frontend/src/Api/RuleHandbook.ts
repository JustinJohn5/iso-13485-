import { request } from '../Api';
import type { RuleHandbook, RuleSetSummary } from '../Types/RuleHandbook';

export const handbookApi = {
  list: () => request<RuleSetSummary[]>('/api/v1/rule-sets'),
  get: (id: string) => request<RuleHandbook>(`/api/v1/rule-sets/${encodeURIComponent(id)}`),
};
