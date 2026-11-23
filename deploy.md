# 部署说明

前端、后端和 MySQL 分别部署、独立扩容。前端仅访问后端 HTTP API；数据库只开放给后端网络，不向前端或公网开放。部署使用 Ubuntu，开发环境 macOS；Windows 可使用对应 PowerShell 命令，但生产进程与目录权限按 Ubuntu 配置。

## 端口规划

| 环境 | 前端 | 后端 | MySQL 示例端口 |
|---|---:|---:|---:|
| 本地开发 | 5300 | 8300 | 3406 |
| 测试/E2E | 5400 | 8400 | 3407 |
| 正式环境 | 5500 | 8500 | 3306（私网） |

更换端口只调整对应环境变量与代理配置。正式环境建议由 HTTPS 反向代理对外提供前端和 API。

## 数据库

1. 部署 MySQL 8.4，创建应用专用数据库与最小权限账号。
2. 仅允许后端服务器访问 MySQL 端口，配置备份、恢复和监控策略。
3. 首次空库可在后端目录按已审核版本执行 `python InitDb.py`；命令仅创建缺失表，不会修改既有表。
4. 已部署数据库的结构升级必须使用经测试副本验证的迁移脚本。当前模型新增 `uploaded_files.document_type`，旧库迁移 SQL：

```sql
ALTER TABLE uploaded_files
  ADD COLUMN document_type VARCHAR(48) NOT NULL DEFAULT 'other' COMMENT '质量体系文档类型';
```

在 `_codextest` 测试库验证后再纳入正式发布流程。正式库只在获准发布时迁移。

## 后端

1. 使用 `.python-version` 指定的 Python 3.12.10，单独部署后端代码并在 `backend` 目录执行 `pip install -r requirements.lock`。
2. 将 `backend/.env.example` 安全复制为服务器 `backend/.env`，填写环境、端口、CORS 来源、MySQL URL、上传/日志目录及随机 `CONFIG_ENCRYPTION_KEY`、`JWT_SECRET`。不得把真实密钥写入镜像、代码或日志。
3. 生产环境设置 `APP_ENV=prod`、`BACKEND_HOST=0.0.0.0`，通过防火墙仅允许反向代理访问后端端口；CORS 只允许正式前端域名。
4. 首次创建管理员可在后端目录交互执行 `python CreateAdmin.py`。生产运行使用进程管理器启动：

```bash
   python Run.py
```

5. 上传目录不可置于 Web 静态目录；限制磁盘权限，纳入备份与保留周期管理。

## 前端

1. 使用 `.nvmrc` 指定的 Node.js 26.13.1，在独立构建环境进入 `frontend`，复制环境示例为相应 `.env.production` 并设置 `VITE_API_BASE_URL` 和 `FRONTEND_PORT`。
2. 执行 `npm ci`、`npm run build`，把 `dist/` 发布到静态 Web 服务或 CDN。
3. 配置 HTTPS 与 SPA 路由回退；浏览器到后端 API 使用 HTTPS。前端构建变量会进入公开产物，只允许非敏感配置。

## 环境变量清单

- 后端：`APP_ENV`、`LOG_LEVEL`、`LOG_DIR`、`BACKEND_HOST`、`BACKEND_PORT`、`FRONTEND_PORT`、`CORS_ORIGINS`、`DATABASE_URL`、`DATABASE_POOL_SIZE`、`DATABASE_MAX_OVERFLOW`、`CONFIG_ENCRYPTION_KEY`、`JWT_SECRET`、`JWT_EXPIRE_MINUTES`、`UPLOAD_DIR`、`MAX_UPLOAD_SIZE_MB`、`RULE_SET_DIR`、`ACCESS_TOKEN_COOKIE_NAME`。
- 前端：`VITE_APP_TITLE`、`VITE_API_BASE_URL`、`FRONTEND_PORT`。这些值会暴露给浏览器，不得存放秘密。
- 测试/E2E：使用独立 `APP_ENV=test`、测试 MySQL 和不与开发/正式环境冲突的端口。E2E 账号通过 `E2E_EMAIL`、`E2E_PASSWORD` 临时注入，不写入仓库。

配置字段和端口示例见 `backend/.env.example` 与 `frontend/.env.example`。修改端口、加密密钥或跨域来源时需同步维护这两个示例文件。
