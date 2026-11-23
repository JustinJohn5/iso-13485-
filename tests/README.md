# 测试说明

## 环境准备

- 沿用 Python 3.12.10 和项目虚拟环境。在 `backend` 目录执行 `python -m pip install -r requirements.lock`，需要时安装 `pytest`。单元测试不连接数据库。
- 前端与根目录分别执行 `npm ci`，沿用 Node.js 26.13.1。根目录执行 `npx playwright install chromium`；已安装 Edge 时也可配置 `E2E_BROWSER_CHANNEL=msedge`。
- E2E 使用 MySQL 8.4 的独立库（如 `iso13485_codextest`），先用当前发布版本初始化表。严禁使用开发或正式业务库。无需每次重建测试库。
- 复制根目录 `.env.test.example` 为 `.env.test`，填写测试连接串、随机密钥、前后端地址及端口。上传目录须在项目 `.local` 内；相对路径按后端目录解析。真实 `.env.test` 被 Git 忽略。

## 单元测试和构建

在已激活虚拟环境的 `backend` 目录执行：

```bash
python -m pytest ../tests/Services -q
python -m pytest ../tests/Services/test_DocumentClassifier.py -q
python -m pytest ../tests/Services/test_RuleEngine.py -q
```

在 `frontend` 目录执行 `npm run build -- --mode development`，读取既有 `.env.development` 并完成 TypeScript 检查和构建。正式构建使用 `npm run build`，需先准备 `.env.production`。不能因缺少构建环境配置而添加业务代码默认值。

## E2E 运行方式

在项目根目录运行。Windows PowerShell：

```powershell
./backend/.venv/Scripts/python.exe tests/RunE2e.py
./backend/.venv/Scripts/python.exe tests/RunE2e.py tests/e2e/Recognition.spec.ts
./backend/.venv/Scripts/python.exe tests/RunE2e.py --headed
```

macOS / Ubuntu：

```bash
./backend/.venv/bin/python tests/RunE2e.py
./backend/.venv/bin/python tests/RunE2e.py tests/e2e/Recognition.spec.ts
./backend/.venv/bin/python tests/RunE2e.py --headed
```

默认无头运行。入口读取 `.env.test`，校验环境、库名、MySQL 版本、上传目录和端口，应用本次文件集审查迁移，创建随机专用管理员和隔离审核员，独立启动测试前后端，等待就绪后运行 Playwright。不需要人工启动测试服务，也不使用现有管理员密码。用例在一个 worker 中顺序执行，避免共享本次临时账号的计数断言互相干扰，单个用例可独立运行。

测试端口默认前端 5400、后端 8400，与本地 5300/8320、正式 5500/8500 分离；数据库按连接串实际端口访问独立测试库。测试结束（包括用例失败）会停止本次启动的服务，并批量清理本次账号、上传原件与预筛记录。强制杀死测试入口可能跳过清理，需检查 `.local/E2eLogs` 和测试进程归属再处理，不得盲目结束端口进程或清空测试库。

## 目录及覆盖范围

- `tests/Services/`：文件安全校验、自动类型识别、手动覆盖、歧义与未知类型、规则证据及日期文本。
- `tests/Services/test_DocumentReview.py`：版本建议与人工选择、状态日期限制、记录实例、编号引用、保存期限及快照变化。
- `tests/e2e/Helpers.ts`：登录、上传样本、网络与浏览器错误监测、数据库断言。
- `tests/e2e/Auth.spec.ts`：专用账号登录和退出。
- `tests/e2e/Recognition.spec.ts`：自动识别、真实 DOCX 抽取、证据差异、条款合并、折叠、手动类型更新、重复计分、冲突拒绝、非法类型与移除。
- `tests/e2e/DocumentReview.spec.ts`：正式版确认、候选排除、保留原件、跨文件期限、元数据校正、记录层级、并发过期和其他用户越权。通过 MySQL 读取验证已生成快照不会被后续确认覆盖，并有审计留痕。
- `tests/Helpers/`：DOCX 样本生成和测试库只读验证；`tests/RunE2e.py`：环境与数据生命周期管理。

浏览器用例检查 pageerror、console error、非预期 HTTP 错误及页面反馈，写入场景同时查询测试库验证类型、去重数量及拒绝后无新增记录。只允许按具体路径、状态码和业务码标明的预期失败，不整体忽略浏览器错误。

`E2E_OTHER_EMAIL` / `E2E_OTHER_PASSWORD` 与既有 E2E 动态凭据一样，仅由入口临时注入，用于验证其他审核员不能读取或确认他人的审查。清理同时覆盖两名随机用户、审查、审计、预筛及上传原件；不删除其他测试数据。

本工具当前只做文本线索预筛。测试通过不表示规则覆盖 ISO 13485 全部要求，也不验证企业实际执行情况。
