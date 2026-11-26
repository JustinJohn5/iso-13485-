import './style.css';
import { AuthenticationPage } from './Components/Authentication';
import { AdminWorkspace } from './Components/AdminWorkspace';
import { api, type User } from './Api';
import { startVisitorTracking } from './Utils/VisitorTracking';

const root = document.querySelector<HTMLDivElement>('#app')!;
function showAdmin(user?: User): void {
  const workspace = new AdminWorkspace(root, () => { location.href = '/'; });
  if (user?.role !== 'admin') void workspace.open();
  else void workspace.open();
}
async function boot(): Promise<void> {
  startVisitorTracking(false, '/admin/');
  try { const user = await api.me(); startVisitorTracking(true, '/admin/'); showAdmin(user); }
  catch {
    new AuthenticationPage(root, async (user) => { startVisitorTracking(true, '/admin/'); showAdmin(user); }).showLogin('请登录管理员账号');
  }
}
void boot();
