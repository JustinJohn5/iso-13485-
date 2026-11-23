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
  disclaimer: string;
}

const apiBase = import.meta.env.VITE_API_BASE_URL;

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
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
  validate: (uids: string[]) => {
    const body = new FormData();
    uids.forEach((uid) => body.append('file_uids', uid));
    return request<ValidationResult>('/api/v1/validations', { method: 'POST', body });
  },
};
