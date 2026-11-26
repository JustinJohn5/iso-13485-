# ISO 13485 AI 文件审阅实施计划

> 代码执行者按任务完成测试、审查和提交；每个功能有独立提交。

**目标：** 在预筛结果页加入 AI 查找依据和 AI 逐项审阅，并支持人工决定留痕。

**架构：** 后端复用现有 OpenAI 兼容客户端，按单条规则和单份预筛文件检索候选文本；对模型 JSON 和原文引用严格校验。MySQL 保存独立 AI 审阅记录与决定历史，前端将其作为预筛结果的独立建议展示，不改写规则状态或分数。

**技术栈：** Python 3.12.10、FastAPI、SQLAlchemy 2.x、MySQL 8.4、原生 TypeScript、Vite、Playwright。

**设计说明：** `docs/superpowers/specs/2026-11-26-ai-document-review-design.md`

## 全局约束

- 默认规则包仅处理 `iso13485-core` 2.0.0 的文本预筛数据。
- 大模型配置唯一来源是后端 MySQL 管理配置，调用复用 `complete_json`；不得新增模型环境变量或供应商 SDK。
- SQL 使用 SQLAlchemy 参数化查询；批量加载本次任务文件，不在循环内逐条访问数据库。
- 人工决定和 AI 结果不得覆盖原预筛快照、Finding、覆盖率或分数。
- 每个证据都要精确匹配源文本片段；位置标为抽取行号，不伪装成原件页或单元格坐标。
- 测试沿用 Python 3.12.10、Node 26.13.1 和隔离 MySQL 8.4 `_codextest`。
- 代码、命令、界面说明和文档均使用中文；新增测试放在根目录 `tests/`。

---

### 任务 1：AI 审阅后端基础与证据查找

**文件：**
- 新增：`backend/App/Models/AiReview.py`
- 新增：`backend/App/Dao/AiReviewDao.py`
- 新增：`backend/App/Schemas/AiReview.py`
- 新增：`backend/App/Services/AiReview/Common.py`
- 新增：`backend/App/Services/AiReview/EvidenceSearch.py`
- 新增：`backend/App/Api/AiReviews.py`
- 新增：`backend/MigrateAiReviews.py`
- 修改：`backend/App/Models/__init__.py`
- 修改：`backend/Main.py`
- 测试：`tests/Services/test_AiReview.py`
- 测试：`tests/Helpers/MockLlmServer.py`
- 修改：`tests/RunE2e.py`
- 修改：`tests/.env.test.example`（若仓库实际模板位于根目录，则按实际路径处理）

**接口：**
- `POST /api/v1/validations/{run_uid}/ai-reviews`，JSON 输入 `{mode: "evidence_search", rule_id, file_uid}`。
- 返回审阅标识、模式、规则、文件、模型、耗时、已校验证据建议和决定历史。
- `GET /api/v1/validations/{run_uid}/ai-reviews` 读取本任务审阅结果。
- `PATCH /api/v1/ai-reviews/{review_uid}/decision` 输入 `{decision, note, edited_result?}`。
- 文件只能来自该已完成预筛任务；普通审核员只能访问自己任务，管理员可访问全部。

- [ ] **步骤 1：先写证据查找失败测试**
  - 覆盖检索候选保留源行、精确摘录被接受、伪造摘录被拒绝、未知规则与文件被拒绝、模型 JSON 字段非法、未配置模型错误。
- [ ] **步骤 2：运行测试确认按预期失败**
  - 在 `backend` 目录用项目虚拟环境运行：`..\\.venv\\Scripts\\python.exe -m pytest ..\\tests\\Services\\test_AiReview.py -q`。
- [ ] **步骤 3：实现模型、DAO、请求校验及证据候选检索**
  - 检索基于规则同义词、条款标题、文本窗口和邻近行；每次只读预筛中的一份文件。
  - 候选结果携带文件标识、抽取文本起止行、原文片段标识。
- [ ] **步骤 4：实现 AI 查找依据 API 和人工决定追加记录**
  - 复用 `complete_json`；核对 run 权限、规则版本、rule_id、file_uid 归属；分析与决定持久化至独立 MySQL 表。
  - 每次决定附加操作者、时间、决定类型和理由；审计日志只记录操作类型，不记录正文或敏感内容。
- [ ] **步骤 5：运行服务测试并验证迁移脚本只针对 MySQL 8.4 与 `_codextest`**
- [ ] **步骤 6：提交证据查找后端功能，提交信息使用中文且含必填正文**

### 任务 2：证据查找前端和浏览器回归

**文件：**
- 新增：`frontend/src/Types/AiReview.ts`
- 新增：`frontend/src/Api/AiReview.ts`
- 新增：`frontend/src/Components/AiReview.ts`
- 修改：`frontend/src/Api.ts`
- 修改：`frontend/src/Components/Results.ts`
- 修改：`frontend/src/Main.ts`
- 修改：`frontend/src/prescreen.css`
- 测试：`tests/e2e/AiReview.spec.ts`
- 修改：`tests/e2e/Helpers.ts`
- 修改：`tests/RunE2e.py`

**界面：** 预筛结果中显示独立 AI 审阅区域，用户选择一条规则和本次任务的一份文件，点击“查找依据”；结果按支持、反向线索和待核实内容展示摘录、文件及抽取行号，提供采纳、修改后采纳和驳回操作。

- [ ] **步骤 1：先写 Playwright 流程**
  - 使用合成文件和测试用 OpenAI 兼容服务；断言请求、响应、原文摘录、决定状态、服务端保存结果和权限隔离。
- [ ] **步骤 2：运行 E2E 确认新交互失败**
- [ ] **步骤 3：实现类型、请求封装、结果组件和事件绑定**
  - 所有 AI 文本使用转义；等待状态、失败反馈、重复点击保护、未配置模型提示均需覆盖。
- [ ] **步骤 4：运行 TypeScript/Vite 构建和单项 E2E**
- [ ] **步骤 5：更新使用手册、E2E 说明、端口清单和 CHANGELOG 后提交**

### 任务 3：逐检查项语义审阅

**文件：**
- 新增：`backend/App/Services/AiReview/RequirementReview.py`
- 修改：`backend/App/Schemas/AiReview.py`
- 修改：`backend/App/Api/AiReviews.py`
- 修改：`tests/Services/test_AiReview.py`
- 修改：`tests/e2e/AiReview.spec.ts`
- 修改：`frontend/src/Components/AiReview.ts`
- 修改：`frontend/src/Types/AiReview.ts`

**接口：** 使用同一 POST 路由，输入模式切换为 `semantic_review`，并沿用 `rule_id` 和 `file_uid`。

- [ ] **步骤 1：先写逐项审阅合同测试**
  - 必需元素必须一一对应规则组；支持摘录和反向摘录都必须通过源文本校验；仅在检索片段中未找到时返回限定范围的候选状态；不得将其标为正式缺陷。
- [ ] **步骤 2：运行定向测试确认按预期失败**
- [ ] **步骤 3：实现逐项提示、输出结构校验和前端模式选择**
  - 输出包含每个元素的候选状态、支持与反向原文、理由、人工问题；拒绝缺少元素或伪造引用的响应。
- [ ] **步骤 4：运行后端服务测试、TypeScript 构建和 AI 审阅 E2E**
- [ ] **步骤 5：更新使用与部署说明、CHANGELOG 后提交语义审阅功能**

### 任务 4：完整回归和项目结构审查

- [ ] 运行 AI 审阅相关后端测试、规则预筛回归、完整前端构建和对应 E2E。
- [ ] 检查 MySQL 测试库迁移、权限、审计记录、配置缺失降级、跨用户拒绝和分数不变。
- [ ] 对项目相关模块做结构审查；发现需大规模拆分时先报告清单，不擅自重构。
- [ ] 检查最终 Git diff，只暂存本次功能文件，保留现有未跟踪 `RunWeb.bat`。
