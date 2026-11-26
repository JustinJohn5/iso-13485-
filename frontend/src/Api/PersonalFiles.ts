import { download, request } from '../Api';
import type { FileGroup, PageResult, PersonalFile } from '../Types/PersonalFiles';

export const personalFilesApi = {
  files: (query: { page: number; page_size: number; keyword?: string; document_type?: string; group_uid?: string }) => {
    const params = new URLSearchParams({ page: String(query.page), page_size: String(query.page_size) });
    if (query.keyword) params.set('keyword', query.keyword);
    if (query.document_type) params.set('document_type', query.document_type);
    if (query.group_uid) params.set('group_uid', query.group_uid);
    return request<PageResult<PersonalFile>>(`/api/v1/my/files?${params}`);
  },
  groups: (page = 1, page_size = 100) => request<PageResult<FileGroup>>(`/api/v1/my/file-groups?page=${page}&page_size=${page_size}`),
  createGroup: (name: string) => request<FileGroup>('/api/v1/my/file-groups', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) }),
  renameGroup: (uid: string, name: string) => request<FileGroup>(`/api/v1/my/file-groups/${encodeURIComponent(uid)}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) }),
  deleteGroup: (uid: string) => request<null>(`/api/v1/my/file-groups/${encodeURIComponent(uid)}`, { method: 'DELETE' }),
  addMembers: (uid: string, file_uids: string[]) => request<unknown>(`/api/v1/my/file-groups/${encodeURIComponent(uid)}/members`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ file_uids }) }),
  removeMembers: (uid: string, file_uids: string[]) => request<unknown>(`/api/v1/my/file-groups/${encodeURIComponent(uid)}/members`, { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ file_uids }) }),
  selection: (uids: string[]) => { const params = new URLSearchParams(); uids.slice(0, 20).forEach(uid => params.append('file_uids', uid)); return request<PersonalFile[]>(`/api/v1/my/files/selection?${params}`); },
  download: (file: PersonalFile) => download(`/api/v1/my/files/${encodeURIComponent(file.file_uid)}/download`, file.name),
};
