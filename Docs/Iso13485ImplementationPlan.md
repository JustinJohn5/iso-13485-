# ISO 13485 规则系统实施计划

依据：Iso13485Rules.md、Iso13485GenerationRules.md、Iso13485PrescreenRules.md、Iso13485ClauseMatrix.md。用户已于2026-11-24授权按上述规则修改审核和生成系统。

目标：生成、AI编写、单份审核和整套审核使用同一72项条款目录；保留原件、历史草稿和审核快照。

架构：保留FastAPI、原生TypeScript/Vite、Python3.12.10和MySQL8.4。新增要求目录、审核上下文、证据判断和生成自检模块；在既有JSON快照中保存新增元数据。接口仅增加可选字段和结果字段；兼容旧的pass/fail/skipped字段，新判定采用assessment_status。新运行规则版本为2.0.0。

执行方式：使用subagent-driven-development分工实现要求目录与生成模块，主执行者负责审核和前后端集成，随后独立审查。按test-driven-development先观察核心用例失败，再实现；使用verification-before-completion核对最终结果。工作分支为 `codex/iso13485-rules`，沿用项目虚拟环境。

## 任务1 共用条款目录

文件：新增backend/App/Rules/Requirements/Iso13485.json及backend/App/Services/Rules/RequirementCatalog.py；测试tests/Services/test_RequirementCatalog.py。

输出接口：load_catalog()返回含version、source及requirements的字典；requirements_for_template(template_id)返回独立副本。每项字段为rule_id、clause、title、document_types、templates、topics、conditions、terms、generation、evidence、source、uncertainty。terms为必须概念的同义词组。条件使用design、sterile、implant、installation、servicing、outsourcing、software、cleaning、process_validation、customer_property。覆盖72项末级条款并人工整理概念组，模板映射覆盖现有20项。

- [x] 测试72项唯一条款、模板输入与检索隔离、条件和来源校验；运行并观察尚无目录的失败。
- [x] 建立目录及加载校验，拒绝未知模板、空概念、重复条款和不合法条件。
- [x] 用项目解释器运行test_RequirementCatalog.py，全部通过后提交feat(rules)。

## 任务2 文本生成

文件：新增Authoring/GenerationRules.py；调整TemplateLibrary.py、AiDraft.py、ManualSuites/Catalog.py和Content.py；按需更新编写API、Schema和前端编写页。

接口：enrich_snapshot(snapshot)返回含requirements_basis（版本、条款要求）及generation_review（待补、人工事项）的新快照；requirements_for_template提供共同要求。保持已有四个章节标识和参数合同。模板正文增加与文件用途相符的完整要求和缺口，版本2.0；旧快照仍按其保存内容使用。

```python
snapshot = build_snapshot('design-plan', parameters)
assert snapshot['requirements_basis']['version'] == '2.0.0'
assert any(row['clause'] == '7.3.2' for row in snapshot['requirements_basis']['requirements'])
assert snapshot['generation_review']['pending_count'] > 0
```

- [x] 先新增上述行为、AI传入固定要求、人工修改后重检、整套生成同源要求测试并验证失败。
- [x] 模板与整套生成附要求及自检，AI输入包含固定依据；模型响应失败保留原稿；人工更改与参数联动更新自检。
- [x] 运行生成、批量、Word及AI测试；分别提交feat(authoring)。

## 任务3 审核引擎与上下文

文件：新增Schemas/Prescreen.py、Rules/Applicability.py、Rules/EvidenceChecks.py、Rules/PrescreenReport.py；调整RuleModels.py、RuleSetLoader.py、RuleEngine.py和ScoringService.py。

接口：RuleEngine.evaluate(documents, context=None)保留原调用方式；DocumentInput新增purpose='auto'及template_id=''。PrescreenContext字段：scope（documents/system）、scope_description、as_of_date、facts（上述条件到适用/不适用/未知的映射）、decisions（条款及理由和依据）、purposes（文件UID到用途）。身份和确认时间由后端生成，用户不能指定。RuleEvaluation增加assessment_status、source、basis_kind、matched_terms、missing_terms、locations、manual_review。build_prescreen_report(rules,evaluations,context)返回完整快照字典。

```python
results = RuleEngine(rules).evaluate([blank_form])
assert next(row for row in results if row.rule.rule_id == 'DOC-003').assessment_status == 'pending_input'
```

- [x] 先测试空审批、仅标题、否定、占位、条件未知/不适用/外包、单份和体系缺件、非法日期、零分母、同义词与证据位置，观察失败。
- [x] 加载72项要求及项目约定；按用途、章节及明确主题路由。不能自动理解的语义、复杂表格与来源疑点进入人工核实；不得宣称完成全部语义审核。
- [x] 覆盖率不加权；未知适用性和人工项单列；新结论使用文本缺口等措辞，保留旧规则的历史解释能力。
- [x] 运行规则、分类和审核相关测试，提交feat(prescreen)。

## 任务4 API与网页联动

文件：Documents.py、ManualSuites/Inspection.py、Schemas/ManualSuite.py、AuditReports.py、QuestionBuilder.py；frontend/src/Main.ts、Api.ts、Components/Results.ts、RuleHandbook.ts、SuiteViews.ts及新增审核上下文组件与类型。

审核POST可选新增context的JSON表单；套册检查新增可选context。持久化完整prescreen快照至既有review_snapshot JSON和套册 inspection JSON；套册保留当前结果和最近三次归档快照。生成快照沿用既有 JSON。所有权限、版本锁和原件保留不变。前端增加审核范围、条件、理由和文件用途，展示八种详细状态、来源、待补要素和人工问题。规则手册显示来源类别及条件；生成页显示依据和自检。

- [x] 新增Playwright场景先验证新控件/结果缺失。
- [x] 接口严格校验context大小、条件、条款及文件UID；确认人使用当前用户、时间使用服务端；禁止未知字段与伪造确认。
- [x] 新结果与旧状态兼容显示；模拟内审从冻结的新状态构造问题，不将待补误判为实施证据。
- [x] 在MySQL8.4测试副本运行新交互及既有核心路径；提交feat(ui,prescreen)。

## 任务5 验证与交付

- [x] 更新四份规则文档的实施状态和能力边界、README、tests/README.md、deploy.md及CHANGELOG.md。
- [x] 运行backend工作目录的`.venv/Scripts/python.exe -m pytest ../tests/Services -q`；macOS/Ubuntu使用`.venv/bin/python`。
- [x] 运行frontend的`npm run build -- --mode development`。
- [x] 项目根目录运行`backend/.venv/Scripts/python.exe tests/RunE2e.py`；入口严格校验APP_ENV=test及_codextest库并清理账号、进程和本次数据。
- [x] 审查结构规模、重复和耦合，独立代码审查，修复真实问题；不进行未确认的大规模结构拆分。
- [x] 检查仅本次改动提交，原始DOCX/PDF不变；最终报告验证证据和人工审核边界。


## 交付复核

- 现有普通模板与整套目录共用条款目录，生成快照固定规则版本。AI 成功、失败路径由模拟客户端和隔离浏览器场景验证。
- 核对了普通预筛、套册复查和模拟内审。208 项后端用例、32 条浏览器用例以及 TypeScript 和 Vite 构建通过。浏览器回归使用 MySQL 8.4 测试副本。
- `Rules/RuleEngine.py` 当前 269 行，其中包含旧版兼容和新版调度。后续若继续扩展，可按这两项职责拆分，使旧版结果和当前判定各自有清晰入口。`frontend/src/Main.ts` 当前 265 行，同时处理主界面与审核表单。后续可移出审核状态和交互处理，缩小页面入口的修改范围。
- 本次已抽取共用规则目录、证据、适用性、受控引用、报告和套册历史模块。核对相关导入与数据库写入路径，新增检查在内存计算。套册检查和历史保存共用现有按修订条件更新流程。
- 原始 DOCX 与 PDF 的 SHA256 和条款目录记录一致。代码与文档在开发分支交付。
