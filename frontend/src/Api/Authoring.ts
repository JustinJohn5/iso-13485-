import { download, request } from '../Api';
import type { Draft, DraftSummary, Template } from '../Types/Authoring';

const json = (method: string, body: unknown) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
export const authoringApi = {
  templates: (q = '', category = '') => request<Template[]>(`/api/v1/templates?${new URLSearchParams({ q, category })}`),
  drafts: () => request<DraftSummary[]>('/api/v1/document-drafts'),
  draft: (uid: string) => request<Draft>(`/api/v1/document-drafts/${encodeURIComponent(uid)}`),
  create: (templateId: string, parameters: Record<string, string>) => request<Draft>('/api/v1/document-drafts', json('POST', { template_id: templateId, parameters })),
  update: (draft: Draft, reason: string, changes: { parameters?: Record<string, string>; sections?: Record<string, string> }) =>
    request<Draft>(`/api/v1/document-drafts/${encodeURIComponent(draft.draft_uid)}`, json('PATCH', { revision: draft.revision, reason, ...changes })),
  download: (draft: Draft, revision = draft.revision) => download(`/api/v1/document-drafts/${encodeURIComponent(draft.draft_uid)}/download?revision=${revision}`, `${draft.snapshot.title}-草稿-r${revision}.docx`),
};
