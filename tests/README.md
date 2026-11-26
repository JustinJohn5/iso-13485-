# 测试说明

## 环境准备

- 沿用 Python 3.12.10 和项目虚拟环境。在 `backend` 目录执行 `python -m pip install -r requirements.lock`，需要时安装 `pytest`。单元测试不连接数据库。
- 前端与根目录分别执行 `npm ci`，沿用 Node.js 26.13.1。根目录执行 `npx playwright install chromium`；已安装 Edge 时也可配置 `E2E_BROWSER_CHANNEL=msedge`。
- E2E 使用 MySQL 8.4 的独立库（如 `iso13485_codextest`），先用当前发布版本初始化表。严禁使用开发或正式业务库。无需每次重建测试库。
- `.env.test` 须配置 `E2E_SMTP_PORT=5425`（选择空闲端口）。测试入口临时启动仅监听本机的 STARTTLS SMTP 收件箱，动态生成授权值与证书，用真实发信模块收件；不会向真实邮箱投递。`tests/Helpers/MailSink.py` 依赖既有 `cryptography`，无需新增依赖。端口与开发、正式服务错开。
- AI 审阅 E2E 由 `tests/Helpers/MockLlmServer.py` 临时启动仅绑定 `127.0.0.1` 的 OpenAI 兼容模拟服务，使用随机空闲端口，不访问外部模型服务；测试通过管理员 API 临时配置，结束时恢复测试库原配置。
- 复制根目录 `.env.test.example` 为 `.env.test`，填写测试连接串、随机密钥、前后端地址及端口。上传目录须在项目 `.local` 内；相对路径按后端目录解析。真实 `.env.test` 被 Git 忽略。

## 单元测试和构建

在已激活虚拟环境的 `backend` 目录执行：

```bash
python -m pytest ../tests/Services -q
python -m pytest ../tests/Services/test_DocumentClassifier.py -q
python -m pytest ../tests/Services/test_RuleEngine.py -q
python -m pytest ../tests/Services/test_RequirementCatalog.py ../tests/Services/test_GenerationRules.py ../tests/Services/test_Prescreen.py -q
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

默认无头运行。入口读取 `.env.test`，校验环境、库名、MySQL 版本、上传目录和端口，应用所需迁移（含 AI 审阅表），创建随机专用管理员和隔离审核员，独立启动测试前后端及回环模拟服务，等待就绪后运行 Playwright。不需要人工启动测试服务，也不使用现有管理员密码。用例在一个 worker 中顺序执行，避免共享本次临时账号的计数断言互相干扰，单个用例可独立运行。

测试端口默认前端 5400、后端 8400，与本地 5300/8320、正式 5500/8500 分离；数据库按连接串实际端口访问独立测试库。测试结束（包括用例失败）会停止本次启动的服务，并批量清理本次账号、上传原件与预筛记录。强制杀死测试入口可能跳过清理，需检查 `.local/E2eLogs` 和测试进程归属再处理，不得盲目结束端口进程或清空测试库。

Windows 若出现 Playwright 转换缓存的 `EPERM`，可在专用测试终端把 `TMP` 和 `TEMP` 指向项目 `.local` 内一个独立的可写子目录，再运行测试入口。

## 目录及覆盖范围

- `test_RequirementCatalog.py` 核对 72 项条款和 20 项生成映射。`test_GenerationRules.py` 核对条款依据、自检和修订。`test_Prescreen.py` 覆盖条件、受控引用、否定表述、部分抽取、证据保留和覆盖率。
- `tests/e2e/IsoRules.spec.ts` 验证待补证据、体系范围、不适用说明、生成自检以及套册上下文持久化。单独运行时将该路径传给 `tests/RunE2e.py`。

- `tests/Services/test_Registration.py`：邮箱及姓名规范化、密码强度与确认、UTF-8 72字节边界和权限字段拒绝；后端目录执行 `python -m pytest ../tests/Services/test_Registration.py -q`。
- `tests/Services/test_EmailSender.py` 和 `test_ClientAddress.py`：SMTP TLS、失败脱敏、HMAC 摘要及可信代理地址解析；`tests/e2e/EmailVerification.spec.ts` 通过真实 STARTTLS SMTP 和 MySQL 验证注册、改密、普通登录无验证码、验证码过期/错误/旧码/邮箱与用途隔离、来源 IP 限流、公开邮箱隐私、单次使用及旧会话撤销。根目录运行 `python tests/RunE2e.py tests/e2e/EmailVerification.spec.ts tests/e2e/Registration.spec.ts tests/e2e/Auth.spec.ts`；加 `--headed` 可观察。`VerificationDatabase.py` 仅对本次随机邮箱前缀做状态核对和时间调整，`RateLimitDatabase.py` 仅预置或清除本轮生成的测试来源 IP 配额。
- `tests/e2e/Registration.spec.ts`：390px注册、注册后登录及Cookie刷新保持、重复邮箱、表单错误、服务端权限与无效输入拒绝、并发去重；根目录执行 `python tests/RunE2e.py tests/e2e/Registration.spec.ts`。`tests/Helpers/RegistrationDatabase.py`核对真实MySQL密码哈希及审计。入口以随机前缀标识并清理本次注册账号及数据，禁止连接正式库。

- `tests/e2e/RuleHandbook.spec.ts`：登录后阅读真实规则、按条款及关键词筛选、检查条件和建议；单项运行 `python tests/RunE2e.py tests/e2e/RuleHandbook.spec.ts`。最终全量验证：107项后端测试、23条E2E、TypeScript及Vite构建通过。

- `tests/Services/test_ManualSuites.py`：20项目录生成、独立编号与版本、快照隔离、重复与容量拒绝、正文修订、实际规则检查及真实 Word/ZIP 内容。
- `tests/e2e/ManualSuites.spec.ts`：整套创建、生成、编辑、导入、检查、下载内容、版本筛选、MySQL 持久化和审计、跨用户隔离、过期与真正并发拒绝、成员校正/移出及390px窄屏。`tests/Helpers/SuiteArchive.py` 核对下载包与数据库，入口自动迁移并清理本次套册数据。
- 单项运行：根目录 `python tests/RunE2e.py tests/e2e/ManualSuites.spec.ts`；单元测试在后端目录运行 `python -m pytest ../tests/Services/test_ManualSuites.py -q`，均使用既有项目虚拟环境。

- 长文本回归：`test_TemplateLibrary.py` 覆盖10万字符资料、12万字符章节及 Word 完整导出；`test_AiDraft.py` 覆盖长模型输入输出、系统提示计入100万字符总限制、响应边界及超限不截断。模型成功响应仍使用模拟客户端，不代表真实服务已经连通。
- `tests/e2e/Authoring.spec.ts` 验证长资料与章节在浏览器、API、MySQL 保存及重载后完整一致；`LlmSettings.spec.ts` 验证65,536 token及600秒配置持久化，以及长要求发起失败调用后原草稿保留。所有写入均在测试副本并随测试清理。

- `tests/Services/test_DraftBatch.py` 与 `tests/e2e/DraftBatch.spec.ts`：批量计划、共享字段边界、预览不写入、跨文件参数更新、各编号保留、旧版保留与任一过期时整体拒绝。

- `tests/Services/test_AuditQuestions.py`：问题分类、去重、原文证据、旧版排除、已确认冲突仍提示、实际 Word 记录字段。
- `tests/e2e/AuditQuestions.spec.ts`：预筛至内审问题清单的完整交互、引用缺项、下载及其他用户权限。

- `tests/Services/test_AiDraft.py`：SDK 超时/重试配置、脱敏日志、未配置拒绝、异常 JSON 和章节合同；使用合成数据与模拟客户端，不调用真实模型。
- `tests/Services/test_AiReview.py`：候选片段行号、原文引用精确匹配、逐项完整覆盖和未检出范围约束。`tests/e2e/AiReview.spec.ts` 验证两种模式、人工修改采纳历史、其他用户越权拒绝及预筛分数不变；只调用本地合成 OpenAI 兼容服务。
- `tests/e2e/LlmSettings.spec.ts`：管理员配置、API Key 密文入库且不回显、审核员越权拒绝、实际模型调用失败后保留草稿。测试结束仅在配置仍由本次账号修改时恢复原测试库配置，不触碰开发/正式配置。
- 模型配置权限回归还覆盖普通账号直接打开配置页面、服务端拒绝无权限的合法及非法参数请求，并比较拒绝前后的测试库配置一致。单项执行 `python tests/RunE2e.py tests/e2e/LlmSettings.spec.ts`。

- `tests/Services/test_TemplateLibrary.py`：模板检索、输入边界、参数联动、历史隔离及真实 Word 内容。
- `tests/Services/test_WordExport.py`：参考手册页面尺寸、封面和页眉、宋体行距、更改历史、动态目录与页码、长标识和原手册内容隔离；无数据库依赖。可在后端虚拟环境执行 `python -m pytest ../tests/Services/test_WordExport.py -q`。
- Word 下载 E2E 使用 `tests/Helpers/WordDownload.py` 读取实际下载件，校验新版格式以及当前／历史修订的型号与正文，不只检查文件名。运行方式仍为根目录 `python tests/RunE2e.py tests/e2e/Authoring.spec.ts`，依赖既有 `.env.test` 和 MySQL 8.4 `_codextest` 副本。
- `tests/e2e/Authoring.spec.ts`：检索、生成、编辑、参数更新、历史下载、乐观锁和跨用户访问；另以390px窄屏验证模板、配置、返回、退出导航。草稿数据保存在独立 MySQL 测试库，结束后随本次测试用户清理。

- `tests/Services/`：文件安全校验、自动类型识别、手动覆盖、歧义与未知类型、规则证据及日期文本。
- `tests/Services/test_DocumentReview.py`：版本建议与人工选择、状态日期限制、记录实例、编号引用、保存期限及快照变化。
- `tests/e2e/Helpers.ts`：登录、上传样本、网络与浏览器错误监测、数据库断言。
- `tests/e2e/Auth.spec.ts`：专用账号登录和退出。
- `tests/e2e/EmailCodeLayout.spec.ts`：注册和改密的验证码输入、发送按钮在1898px、390px和320px下完整可用；运行 `python tests/RunE2e.py tests/e2e/EmailCodeLayout.spec.ts`，沿用上述隔离服务与测试库配置。
- `tests/e2e/Recognition.spec.ts`：自动识别、真实 DOCX 抽取、证据差异、条款合并、折叠、手动类型更新、重复计分、冲突拒绝、非法类型与移除。
- `tests/e2e/DocumentReview.spec.ts`：正式版确认、候选排除、保留原件、跨文件期限、元数据校正、记录层级、并发过期和其他用户越权。通过 MySQL 读取验证已生成快照不会被后续确认覆盖，并有审计留痕。
- `tests/Helpers/`：DOCX 样本生成和测试库只读验证；`tests/RunE2e.py`：环境与数据生命周期管理。

浏览器用例检查 pageerror、console error、非预期 HTTP 错误及页面反馈，写入场景同时查询测试库验证类型、去重数量及拒绝后无新增记录。只允许按具体路径、状态码和业务码标明的预期失败，不整体忽略浏览器错误。

`E2E_OTHER_EMAIL` / `E2E_OTHER_PASSWORD` 与既有 E2E 动态凭据一样，仅由入口临时注入，用于验证其他审核员不能读取或确认他人的审查。清理同时覆盖两名随机用户、审查、审计、预筛及上传原件；不删除其他测试数据。

本工具当前只做文本线索预筛。测试通过不表示规则覆盖 ISO 13485 全部要求，也不验证企业实际执行情况。
