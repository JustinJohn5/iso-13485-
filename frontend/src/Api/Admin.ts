import { request } from '../Api';
import type { PageResult } from '../Types/PersonalFiles';

export interface AdminOverview { online_visitors: number; online_users: number; today_visitors: number; today_views: number; timezone: string; services: { api: string; database: string }; }
export interface AdminVisitor { visitor_uid: string; identity: string; user_id: number | null; page: string; first_seen: string; last_seen: string; online: boolean; }
export interface AuditEntry { id: number; actor: string; action: string; target_type: string; target_id: string; detail: string; created_at: string; }
export const adminApi = {
  overview: () => request<AdminOverview>('/api/v1/admin/overview'),
  visitors: (page = 1) => request<PageResult<AdminVisitor>>(`/api/v1/admin/visitors?page=${page}&page_size=20`),
  logs: (filters: { source: string; level?: string; keyword?: string; request_id?: string; date?: string }) => {
    const params = new URLSearchParams(); Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v); });
    return request<{ lines: string[]; truncated: boolean; source: string }>(`/api/v1/admin/logs?${params}`);
  },
  audits: (page = 1) => request<PageResult<AuditEntry>>(`/api/v1/admin/audit-logs?page=${page}&page_size=20`),
};
