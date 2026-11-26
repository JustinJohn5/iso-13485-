import { request } from '../Api';

const allowed = new Set(['/', '/login', '/register', '/password', '/prescreen', '/history', '/manuals', '/authoring', '/my/files', '/my/file-groups', '/admin/', '/admin/overview', '/admin/visitors', '/admin/models', '/admin/logs', '/admin/audit-logs']);
let interval: number | undefined;
let visibility: (() => void) | undefined;
let currentPage = '';
let loggedIn = false;
function pagePath(path: string): string {
  if (allowed.has(path) && path.startsWith('/admin/')) return path;
  if (path.startsWith('/admin/')) return '/admin/';
  return allowed.has(path) ? path : '/prescreen';
}
function send(event: 'pageview' | 'heartbeat' | 'logout'): void {
  const page = currentPage || pagePath(location.pathname);
  void request('/api/v1/visits', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ page, event }) }).catch(() => undefined);
}
export function startVisitorTracking(isLoggedIn: boolean, path = location.pathname): void {
  const next = pagePath(path), changed = currentPage !== next;
  currentPage = next; loggedIn = isLoggedIn;
  if (changed) send('pageview');
  if (interval === undefined) {
    interval = window.setInterval(() => { if (document.visibilityState === 'visible') send('heartbeat'); }, 60_000);
    visibility = () => { if (document.visibilityState === 'visible') send('heartbeat'); };
    document.addEventListener('visibilitychange', visibility);
  }
}
export function stopVisitorTracking(): void {
  if (loggedIn) send('logout');
  if (interval !== undefined) window.clearInterval(interval);
  if (visibility) document.removeEventListener('visibilitychange', visibility);
  interval = undefined; visibility = undefined; currentPage = ''; loggedIn = false;
}
