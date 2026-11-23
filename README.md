# ISO 13485 文件预筛平台

本项目提供一个基于浏览器的质量体系文件文本预筛工具。用户登录后可上传 PDF、DOCX、XLSX、TXT、MD 文件，自动识别或手动修正文件类型，并查看规则命中、可检索证据和建议。

预筛仅识别当前规则包中的文本线索，不代表文件内容真实、过程有效、体系符合标准，也不构成认证、审核结论或法规符合性声明。扫描件和图片型 PDF 暂不做 OCR。

## 已完成的基础

- 后端：Python 3.12.10、FastAPI、SQLAlchemy 2.x、MySQL 8.4。
- 前端：原生 TypeScript + Vite，前后端独立构建，只通过 HTTP API 通信。
- 后端已有模块：安全配置、日志、密码/JWT、文件防护、PDF/DOCX/XLSX/TXT 抽取、规则判定和评分模型。
- 本次补齐：可运行 API、登录、文件上传与预筛流程、ISO 13485 基础规则包、网页工作区、单元测试、E2E 用例及部署说明。
- 识别改进：添加文件后自动解析，按文件名、正文标题及关键词识别类型；线索不足或歧义时提示人工确认，已上传类型可直接修改。
- 结果改进：各检查项展示具体命中文字，相邻同文件同条款合并展示，未适用项折叠；相同内容同类型只计分一次，不同类型提示冲突。

现已支持当前批次的编号引用、同编号版本冲突、人工正式版确认及明确保存期限对照，操作见 [关联文件与正式版本](Docs/DocumentControl.md)。预筛保存采用依据快照，候选原件保留；完整语义一致性、长期审核项目和跨批次补件仍按 [文件集关联设计](Docs/DocumentSetDesign.md) 后续建设。

## 本地运行

中文操作手册见 [Markdown 版](Docs/UserGuide.md) 或 [可阅读和打印的网页手册](Docs/UserGuide.html)，包含本机实际端口、登录、上传预筛、规则说明和常见问题。

1. 安装 MySQL 8.4，并创建仅供开发使用的数据库和账号。数据库端口不要暴露给公网。
2. 将 `backend/.env.example` 复制为 `backend/.env`，生成并填写真实的 `CONFIG_ENCRYPTION_KEY`、`JWT_SECRET` 和本机 MySQL 连接串。真实 `.env` 不提交 Git。
3. 使用 `.python-version` 指定的 Python 3.12.10，在 `backend` 目录创建虚拟环境，并安装锁定文件 `requirements.lock`。
4. 先在独立 MySQL 8.4 测试库（建议名称 `iso13485_codextest`）验证初始化脚本；确认无误后，仅对空的开发数据库运行 `python InitDb.py`，再运行 `python CreateAdmin.py` 交互式创建管理员。切勿将正式库用作验证目标。
5. 在 `backend` 目录运行 `python Run.py`；监听地址与端口从 `backend/.env` 读取。
6. 使用 `.nvmrc` 指定的 Node.js 26.13.1，将 `frontend/.env.example` 复制为 `frontend/.env.development`，确认 API 地址，然后在 `frontend` 目录执行 `npm ci` 和 `npm run dev`。
7. 打开 `http://127.0.0.1:5300` 登录。端口以各环境 `.env` 中的设置为准。

初始化表命令只会为不存在的表创建结构，不会升级既有表。后续数据库结构变更须编写并审核迁移后应用；本次新增的 `uploaded_files.document_type` 在旧数据库上需要先按迁移说明添加字段。

## 端口清单

| 环境 | 前端 | 后端 | MySQL 示例端口 |
|---|---:|---:|---:|
| 本地开发 | 5300 | 8320 | 3406 |
| 测试/E2E | 5400 | 8400 | 3407 |
| 正式环境 | 5500 | 8500 | 仅内网访问，按部署配置 |

所有端口通过环境变量配置。前端变量只包含浏览器可见的 API 地址与页面配置；密钥和数据库凭证仅存后端环境文件。

本机当前新版后端使用 8320，网页仍为 5300，MySQL 实际为 3306；表中列出环境示例的规划值。原后端 8300/8310 进程暂保留，新网页已通过前端环境配置连接 8320。实际配置和操作见使用手册。

## 项目结构

```text
backend/App/Api/          FastAPI 路由
backend/App/Services/     文档抽取、规则引擎与评分
backend/App/Models/       SQLAlchemy 数据模型
backend/App/Rules/        JSON 规则包
frontend/src/             TypeScript 页面、API 与样式
tests/                    后端单元测试与 Playwright E2E
```

## 验证

测试准备和命令见 [tests/README.md](tests/README.md)。后端开发数据库初始化与分层部署见 [deploy.md](deploy.md)。
