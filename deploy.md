# 部署说明

前端、后端和 MySQL 分别部署、独立扩容。前端仅访问后端 HTTP API；数据库只开放给后端网络，不向前端或公网开放。部署使用 Ubuntu，开发环境 macOS；Windows 可使用对应 PowerShell 命令，但生产进程与目录权限按 Ubuntu 配置。

## 端口规划

| 环境 | 前端 | 后端 | MySQL 示例端口 |
|---|---:|---:|---:|
| 本地开发 | 5300 | 8320 | 3406 |
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
- 测试/E2E：复制根目录 `.env.test.example` 为 `.env.test`，配置独立 `APP_ENV=test`、MySQL 8.4 的 `_codextest` 库、测试密钥及上传目录。测试前后端使用 5400/8400，开发与正式服务使用其他端口。同一 MySQL 实例可提供独立测试库；单独部署测试实例时设置其实际端口。
- 测试入口地址：`E2E_BASE_URL` 为测试前端，`E2E_API_BASE_URL` 和 `VITE_API_BASE_URL` 为测试后端，必须对应测试服务的地址和端口；`E2E_BROWSER_CHANNEL` 留空使用 Playwright Chromium，可填 `msedge` 使用本机 Edge。
- `tests/RunE2e.py` 在子进程环境中临时注入随机 `E2E_EMAIL`、`E2E_PASSWORD` 和当前解释器路径 `E2E_PYTHON`；这些不是部署凭证，不写入仓库。准备、运行与清理方式见 `tests/README.md`。

配置字段和端口示例见 `backend/.env.example` 与 `frontend/.env.example`。修改端口、加密密钥或跨域来源时需同步维护这两个示例文件。

## 1.0.1 更新部署

本次无数据库结构变更，既有数据库无需迁移。部署后重启后端并重新构建前端，规则包版本为 1.0.1。

- `POST /api/v1/documents` 省略 `document_type` 时默认为 `auto`；手动类型继续兼容。响应新增 `type_detection`（类型、标签、线索来源、置信度和说明）。
- 新增 `PATCH /api/v1/documents/{file_uid}`，JSON 为 `{"document_type":"auto"}` 或已有类型；仅允许上传者或管理员且具备写权限时修改。响应返回实际类型和识别信息。反向代理如限制方法，需允许 PATCH；后端已同步允许该跨域方法。
- `POST /api/v1/validations` 保留原有响应，新增 `documents`、`duplicate_files`；相同内容相同类型只判定一次，相同内容不同类型返回 HTTP 400 / code 1001，不创建预筛记录。
- 自动分类只决定当前专用规则的适用范围，不区分完整的文件层级，不提供跨文件关联结论；后续建设方案见 `Docs/DocumentSetDesign.md`。

## 1.1.0 文件集审查更新

本次新增 `document_reviews` 表（审查标识、创建者索引、修订号、JSON 快照、创建时间），以及 `validation_runs.review_snapshot` 可空 JSON 列。初始空库通过既有 `InitDb.py` 建表；已有库使用版本化入口 `MigrateDocumentReviews.py`，不删表重建，不改写已有预筛结果。

先备份数据库，在 MySQL 8.4 的 `_codextest` 副本应用并运行回归。激活项目虚拟环境后，在 `backend` 目录执行：

```bash
python MigrateDocumentReviews.py --env-file ../.env.test
```

测试通过后，本地开发环境执行 `python MigrateDocumentReviews.py`，从后端 `.env` 读取开发连接。入口可重复执行；MySQL DDL 不保证事务回滚，部分失败时保留备份、确认表/列状态后重试。正式环境只有获得发布授权后才可使用同一入口 `python MigrateDocumentReviews.py --allow-production`，不使用开发/测试连接串替代正式配置。随后部署前后端并重启服务。

新增 API：

- `POST /api/v1/document-reviews`：JSON `file_uids`、`as_of_date` 和可选 `overrides`（文件标识 → 校正字段）。一次批量读取文件；校正支持编号、修订、生效日、类别、层级、状态，保存于审查快照，不改原件。
- `GET /api/v1/document-reviews/{review_uid}`：读取本人或管理员可访问的快照。
- `PATCH /api/v1/document-reviews/{review_uid}/decisions`：JSON `revision`、`kind`（version/requirement）、`issue_id`、`file_uid`、`reason`。通过权限、候选、日期状态及乐观锁校验后更新，追加历史与审计日志。
- `POST /api/v1/validations` 增加 Form 字段 `review_uid` / `review_revision`。提交审查时两者须对应最新修订，按确认范围预筛并保存冻结快照。旧调用未提交审查时仍可处理无检测冲突文件；检测到版本或明确期限冲突会返回 409，不能绕过确认。
- 上传和类型修改响应新增 `control_metadata`；预筛新增 `excluded_versions`、`document_review`。原有字段保留，前后端须一同发布。

错误码：1601 审查不存在（404）、1602 审查已更新（409）、1603 文件集/类型已变化（409）、1604 冲突未确认（409）；非法元数据或不允许的候选使用 1001（400），越权使用 1104（403）。本次无需新增环境变量或大模型配置。

界面中的正式版是本次预筛采用依据，不能替代组织受控批准发布。内容比较只覆盖明确同编号的数字保存期限；完整语义冲突与法规适用性仍需人工复核。详见 `Docs/DocumentControl.md`。
