# 整套手册实施计划

目标：将用户确认的导入、生成、整套版本归档及规则网页阅读做成可测试的功能。
设计依据：ManualSuitesDesign.md。沿用当前非主分支，不覆盖工作区既有模型调用改动。

- [x] 先增加纯业务测试：目录生成、编号独立、版本保留、导入归档、重复及容量拒绝、整套检查和 ZIP 内容。
- [x] 实现 Services/ManualSuites/Catalog.py、Content.py、Inspection.py、Archive.py；复用规则引擎与 Word 导出。
- [x] 新增 Models/ManualSuite.py、Schemas/ManualSuite.py、Dao/ManualSuiteDao.py、Api/ManualSuites.py；显式迁移及初始化注册。
- [x] 新增 Types/ManualSuite.ts、Api/ManualSuites.ts、Components/ManualSuites.ts 和辅助视图；接入主导航。
- [x] 在 tests/e2e/ManualSuites.spec.ts 验证真实 MySQL 持久化、生成、导入、查阅、校正、过滤、检查、下载、并发及隔离；测试入口迁移并清理新表。
- [x] 先增加规则手册 E2E；新增鉴权详情接口和独立阅读页，检索实际规则数据。
- [x] 沿用项目虚拟环境运行单元测试、TypeScript 构建、相关 E2E；完成项目结构审查及中文文档。
- [ ] 分功能提交：Git 尚未配置姓名和邮箱，等待用户提供本次提交身份。

接口：GET/POST /manual-suites；GET /manual-suites/{uid}；
POST /manual-suites/{uid}/generations、/imports、/inspections；
PATCH/DELETE /manual-suites/{uid}/items/{id}；GET /manual-suites/{uid}/download。
所有写操作带 revision；返回套册最新详情，陈旧修订返回 HTTP 409。
规则接口 GET /rule-sets/{id} 返回实际加载的完整规则包。

最终验证：107项后端测试、23条完整E2E及TypeScript/Vite构建均通过。结构审查未发现超过300行的代码文件、循环SQL或新增循环依赖。
