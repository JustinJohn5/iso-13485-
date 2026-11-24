import { download, request } from '../Api';
import type { CatalogEntry, ManualSuite, SuiteItem, SuiteList } from '../Types/ManualSuite';

const json = (method: string, body: unknown) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
const path = (uid: string) => `/api/v1/manual-suites/${encodeURIComponent(uid)}`;
export const suitesApi = {
  catalog: () => request<CatalogEntry[]>('/api/v1/manual-suite-catalog'),
  list: (q = '', version = '', page = 1) => request<SuiteList>(`/api/v1/manual-suites?${new URLSearchParams({ q, version, page: String(page) })}`),
  create: (name: string, version: string) => request<ManualSuite>('/api/v1/manual-suites', json('POST', { name, version })),
  detail: (uid: string) => request<ManualSuite>(path(uid)),
  generate: (suite: ManualSuite, keys: string[], parameters: Record<string, string>) => request<ManualSuite>(`${path(suite.suite_uid)}/generations`, json('POST', { revision: suite.revision, catalog_keys: keys, parameters })),
  import: (suite: ManualSuite, uids: string[]) => request<ManualSuite>(`${path(suite.suite_uid)}/imports`, json('POST', { revision: suite.revision, file_uids: uids })),
  item: (suite: ManualSuite, id: string) => request<SuiteItem>(`${path(suite.suite_uid)}/items/${encodeURIComponent(id)}`),
  revise: (suite: ManualSuite, id: string, key: string, version: string, sections?: Record<string, string>, reason?: string) => request<ManualSuite>(`${path(suite.suite_uid)}/items/${encodeURIComponent(id)}`, json('PATCH', { revision: suite.revision, catalog_key: key, file_version: version, sections, reason })),
  remove: (suite: ManualSuite, id: string) => request<ManualSuite>(`${path(suite.suite_uid)}/items/${encodeURIComponent(id)}`, json('DELETE', { revision: suite.revision })),
  inspect: (suite: ManualSuite, asOf: string) => request<ManualSuite>(`${path(suite.suite_uid)}/inspections`, json('POST', { revision: suite.revision, as_of_date: asOf })),
  download: (suite: ManualSuite) => download(`${path(suite.suite_uid)}/download`, `${suite.name}-${suite.version.replace(/[<>:"/\\|?*]/g, '-')}.zip`),
};
