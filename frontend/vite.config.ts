import { defineConfig, loadEnv } from 'vite';
import { resolve } from 'node:path';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  if (!env.FRONTEND_PORT) throw new Error('缺少环境变量 FRONTEND_PORT，请检查前端 .env 文件');
  const port = Number(env.FRONTEND_PORT);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error('环境变量 FRONTEND_PORT 必须是 1~65535 之间的整数');
  }
  if (!env.VITE_API_BASE_URL) throw new Error('缺少环境变量 VITE_API_BASE_URL，请检查前端 .env 文件');
  return {
    server: { port, strictPort: true },
    preview: { port, strictPort: true },
    build: { rollupOptions: { input: { main: resolve(__dirname, 'index.html'), admin: resolve(__dirname, 'admin/index.html') } } },
  };
});
