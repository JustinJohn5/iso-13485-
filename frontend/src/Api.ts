import type { ControlMetadata, DocumentReview, MetadataChanges } from './Types/DocumentControl';
import type { AssessmentStatus, DocumentPurpose, PrescreenContext, PrescreenReport } from './Types/Prescreen';

export interface ApiEnvelope<T> {
  code: number;
  message: string;
  data: T;
}

export interface User {
  id: number;
  email: string;
  display_name: string;
  role: string;
}

export interface DocumentType {
  type: string;
  label: string;
  description: string;
}

export interface UploadedDocument {
  file_uid: string;
  name: string;
  document_type: string;
  size_bytes: number;
  char_count: number;
  page_count: number;
  warnings: string[];
  type_detection: TypeDetection;
  control_metadata: ControlMetadata;
}

export interface TypeDetection {
  type: string;
  label: string;
  source: 'filename' | 'content' | 'unrecognized' | 'ambiguous';
  confidence: 'high' | 'medium' | 'low';
  reason: string;
}

export interface Finding {
  rule_id: string;
  title: string;
  clause: string;
  clause_title: string;
  severity: string;
  status: 'pass' | 'fail' | 'skipped';
  document_name: string;
  evidence: string;
  detail: string;
  suggestion: string;
  assessment_status?: AssessmentStatus;
  document_uid?: string;
  purpose?: DocumentPurpose;
  matched_terms?: string[];
  missing_terms?: string[];
  locations?: Array<{ document_uid?: string; file_uid?: string; line: number; quote: string; kind?: string; excerpted?: boolean }>;
  basis_kind?: 'standard' | 'project';
  source?: string;
  manual_review?: string[];
  checks?: Array<{ id: string; element: string; assessment_status: AssessmentStatus; matched_term: string; locations?: Finding['locations']; location_count?: number; detail: string }>;
}

export interface ValidationResult {
  run_uid: string;
  rule_set: { title: string; standard: string; version: string };
  score: {
    score: number;
    verdict: string;
    passed_count: number;
    failed_count: number;
    skipped_count: number;
    total_count: number;
    clause_matrix: Array<{ clause: string; clause_title: string; rate: number }>;
  };
  findings: Finding[];
  documents: Array<{ name: string; document_type: string; type_label: string }>;
  duplicate_files: Array<{ name: string; kept_name: string }>;
  excluded_versions: string[];
  document_review: DocumentReview | null;
  disclaimer: string;
  prescreen?: PrescreenReport;
}

const apiBase = import.meta.env.VITE_API_BASE_URL;

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!apiBase) throw new Error('缺少前端配置 VITE_API_BASE_URL');
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    credentials: 'include',
    headers: { ...init.headers },
  });
  const envelope = (await response.json()) as ApiEnvelope<T>;
  if (!response.ok || envelope.code !== 0) throw new Error(envelope.message || '请求失败');
  return envelope.data;
}

export async function download(path: string, filename: string): Promise<void> {
  if (!apiBase) throw new Error('缺少前端配置 VITE_API_BASE_URL');
  const response = await fetch(`${apiBase}${path}`, { credentials: 'include' });
  if (!response.ok) {
    const body = await response.json();
    throw new Error(body.message || '下载失败');
  }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a');
  link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const api = {
  me: () => request<User>('/api/v1/auth/me'),
  login: (email: string, password: string) => request<User>('/api/v1/auth/login', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  }),
  logout: () => request<null>('/api/v1/auth/logout', { method: 'POST' }),
  documentTypes: () => request<DocumentType[]>('/api/v1/document-types'),
  upload: (file: File, documentType: string) => {
    const body = new FormData();
    body.append('file', file);
    body.append('document_type', documentType);
    return request<UploadedDocument>('/api/v1/documents', { method: 'POST', body });
  },
  updateType: (uid: string, documentType: string) => request<Pick<UploadedDocument, 'file_uid' | 'document_type' | 'type_detection' | 'control_metadata'>>(`/api/v1/documents/${encodeURIComponent(uid)}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document_type: documentType }),
  }),
  createReview: (uids: string[], asOf: string, overrides: Record<string, MetadataChanges>) => request<DocumentReview>('/api/v1/document-reviews', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ file_uids: uids, as_of_date: asOf, overrides }),
  }),
  confirmReview: (review: DocumentReview, kind: 'version' | 'requirement', issue: string, uid: string, reason: string) => request<DocumentReview>(`/api/v1/document-reviews/${encodeURIComponent(review.review_uid)}/decisions`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ revision: review.revision, kind, issue_id: issue, file_uid: uid, reason }),
  }),
  validate: (uids: string[], reviewUid = '', reviewRevision?: number, context?: PrescreenContext) => {
    const body = new FormData();
    uids.forEach((uid) => body.append('file_uids', uid));
    if (reviewUid) body.append('review_uid', reviewUid);
    if (reviewRevision !== undefined) body.append('review_revision', String(reviewRevision));
    if (context) body.append('context', JSON.stringify(context));
    return request<ValidationResult>('/api/v1/validations', { method: 'POST', body });
  },
};
