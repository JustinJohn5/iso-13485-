# 个人中心与后台实施计划

> 执行使用 subagent-driven-development 的测试与审查流程；已按 dispatching-parallel-agents 划分无重叠文件的任务。主代理统一集成和提交。

**目标：** 交付个人文件库、分组、账户菜单及可用管理后台。
**架构：** 同一 Vite 工程增加 admin/index.html，多入口构建。后端新增独立路由、服务、模型及迁移，既有接口兼容。
**技术栈：** 现有 TypeScript、Python3.12.10、MySQL8.4。
**设计：** ../specs/2026-11-26-account-admin-design.md

## 全局约束

中文文档和错误；不新增数据库或依赖；新文件 PascalCase。当前 codex/iso13485-rules 非主分支按 AGENTS.md 12.2 原地继续，保留已有未提交改动。任务1、2不编辑 Main.py/Models/__init__.py，主代理统一注册与清理。任务3独占前端文件。先新增测试，确认缺失功能失败，再实现。禁止子代理继续派生代理。各任务不提交，由主代理按功能选择文件及文档增量提交。

## 任务1：个人文件服务

- [ ] 创建 tests/e2e/PersonalFiles.spec.ts，先断言账户入口及文件搜索、分组持久化；运行观察缺失功能失败。
- [ ] 创建 backend/App/Models/FileGroup.py、Schemas/PersonalFiles.py、Services/PersonalFiles.py、Api/PersonalFiles.py、MigratePersonalFiles.py；批量成员操作、所有权校验、原件下载。
- [ ] 接口 GET /api/v1/my/files 参数 page/page_size/keyword/document_type/group_uid；返回 items/total/page/page_size，items 字段 file_uid/name/document_type/size_bytes/text_status/created_at/groups/control_metadata/type_detection。
- [ ] GET /api/v1/my/files/{uid}/download 返回 FileResponse。GET /api/v1/my/files/selection?file_uids=重复参数 返回不超过20份相同摘要结构，用于加载预筛队列。
- [ ] GET/POST /api/v1/my/file-groups；PATCH/DELETE /api/v1/my/file-groups/{uid}；POST/DELETE /api/v1/my/file-groups/{uid}/members JSON {file_uids:string[]}。组字段 group_uid/name/file_count/created_at，列表 items/total/page/page_size。
- [ ] 单元测试输入校验，数据库/E2E验证所有权、重复名、移除组保留文件、原件下载。

```ts
expect((await page.request.get(`${api}/api/v1/my/files?page_size=1`)).status()).toBe(200);
expect((await page.request.get(`${api}/api/v1/my/files/${otherUid}/download`)).status()).toBe(404);
```

## 任务2：访客与后台服务

- [ ] 测试日志越界、脱敏、无权限接口、访客计数，然后实现。
- [ ] 创建 Models/Visitor.py、Services/VisitorTracking.py、Services/AdminLogs.py、Api/Visits.py、Api/Admin.py、MigrateAdmin.py。
- [ ] POST /api/v1/visits JSON {page:string,event:'pageview'|'heartbeat'|'logout'}，page 仅预定义功能路径。访客 Cookie 服务端签发，数据库只存摘要；有效用户身份查库，过期身份清除。pageview增加今日浏览数，heartbeat只更新时间。匿名与登录关联同一访客。
- [ ] GET /api/v1/admin/overview 返回 online_visitors/online_users/today_visitors/today_views/timezone/services:{api,database}。
- [ ] GET /api/v1/admin/visitors 返回 items/total/page/page_size；字段 visitor_uid/identity/user_id/page/first_seen/last_seen/online；不暴露原始Cookie/IP。
- [ ] GET /api/v1/admin/logs 参数 source=app|error,level,keyword,request_id,date；返回 {lines:string[],truncated:boolean,source:string}；限制读取文件及字节，目录穿越和符号链接拒绝。
- [ ] GET /api/v1/admin/audit-logs 返回 items/total/page/page_size，字段 id/actor/action/target_type/target_id/detail/created_at。不得携带密钥。
- [ ] 仅admin；所有功能有失败中文提示；迁移包含全部新表。用SQL聚合统计，列表最多固定几次查询，禁止N+1。

```python
assert redact('Authorization: Bearer abc.def.ghi') == 'Authorization: [已脱敏]'
assert result['today_views'] == 2  # 同访客两次pageview和一次heartbeat
```

## 任务3：前端账户和后台

- [ ] 新增 tests/e2e/AccountAdmin.spec.ts，先跑缺失入口失败。
- [ ] Components/AccountMenu.ts、PersonalFiles.ts、FileGroups.ts、AdminWorkspace.ts、Api/PersonalFiles.ts、Api/Admin.ts、Utils/VisitorTracking.ts、Account.css、Admin.css；按上述接口合同实现。
- [ ] Main.ts 使用账户菜单，保留现有 queue；selection转为File元信息及已有uid，不读取/上传原件，维持20份上限及已选去重。
- [ ] 移除Main和Authoring的模型管理入口，账户菜单admin链接 /admin/。Authoring等登录页面有统一账户入口；改密返回此前页面。
- [ ] admin/index.html、src/Admin.ts 作为后台启动入口，vite.config.ts增加双入口构建。后台模型页复用LlmSettingsPage并能返回后台。
- [ ] 前台及后台挂载访客追踪，首次及功能导航pageview、可见时60秒heartbeat，失败不影响业务；卸载/登出清理登录关联。
- [ ] 运行构建及相关E2E，覆盖菜单外点/键盘/320px、普通账号无后台权限、日志筛选、模型配置保存。

## 任务4：集成验收

- [ ] 注册模型/路由，RunE2e.py迁移与仅本轮数据清理；修订旧E2E导航选择器。
- [ ] pytest服务测试、TS/Vite构建、相关Playwright核心及异常路径、真实MySQL数据断言。
- [ ] 独立审查权限、日志脱敏和统计正确性，处理发现。
- [ ] 测试迁移后开发库迁移；确认进程归属再重启后端。浏览器验收前台菜单和/admin/，保留展示页。
- [ ] 更新文档、结构审查清单、按功能中文Conventional Commits正文提交，保留基线未提交改动。
