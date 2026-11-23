import { request } from '../Api';
import type { Draft } from '../Types/Authoring';

export interface LlmConfig {
  enabled: boolean; base_url: string; model: string; api_key_configured: boolean;
  timeout_seconds: number; max_tokens: number; temperature: number;
}

export const llmApi = {
  status: () => request<{ ready: boolean }>('/api/v1/llm-status'),
  config: () => request<LlmConfig>('/api/v1/llm-settings'),
  save: (config: Omit<LlmConfig, 'api_key_configured'> & { api_key?: string }) => request<LlmConfig>('/api/v1/llm-settings', {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(config),
  }),
  draft: (draft: Draft, instructions: string) => request<Draft>(`/api/v1/document-drafts/${encodeURIComponent(draft.draft_uid)}/ai-draft`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ revision: draft.revision, instructions }),
  }),
};
