# 文件分组快捷操作实施计划

> 执行方式：本会话按任务执行，使用测试驱动与完成前验证；遵循 AGENTS.md 在当前非主分支继续。

**目标：** 按用户已确认的流程提供上传到本组、整组预筛和打包下载。

**架构：** 复用上传接口并增加可选 group_uid，文件与成员在同一事务保存。分组选择和 ZIP 下载只读取本人文件；前端载入预筛队列，保留范围与已有用途，由用户点击执行。

**技术栈：** 既有 TypeScript/Vite、Python 3.12、MySQL 8.4、Playwright，无新增依赖和数据库迁移。

## 约束与接口

- 上传：POST /api/v1/documents，multipart 可选 group_uid；保留现有响应。
- 整组选择：GET /api/v1/my/file-groups/{uid}/selection，返回 PersonalFile[]；空组和超过20份明确拒绝。
- 下载：GET /api/v1/my/file-groups/{uid}/download，ZIP；最多100份、原件合计200MB，检查真实体积和受控路径，失败不返回残缺包。
- SQL：上传增加一次组所有权锁定；选择最多三次查询；下载两次批量读取，无循环 SQL。
- 预筛：先校验去重后总数，超过20份时队列保持不变，不静默截断、不自动执行。
- 后台进入分组后，可通过 URL 中的组标识转到预筛页，不在浏览器存放文件内容或凭据。
- 测试仅使用 .env.test 的 MySQL 8.4 测试副本与5400/8400端口。

## 任务一：分组服务与上传事务

文件：backend/App/Services/PersonalFiles.py、FileGroupOperations.py；backend/App/Utils/StoredFiles.py；backend/App/Api/PersonalFiles.py、Documents.py；tests/Services/test_FileGroupOperations.py。

- [ ] 新增服务测试：组选择顺序与所有权，空组、21份拒绝；ZIP原件内容、重名、越权、缺失及限额；有界SQL。
- [ ] 运行并确认新接口尚不存在导致失败。
- [ ] 提供 owned_group、group_files、group_selection；封装受控原件路径供单文件和ZIP共用。
- [ ] 上传在写盘前锁定本人分组，文件行和成员同事务，异常回滚并清理原件。
- [ ] ZIP使用可自动清理的临时文件，完整生成后响应，下载结束关闭句柄。
- [ ] 运行服务测试并检查正常及拒绝路径。

## 任务二：界面与完整交互

文件：frontend/src/Components/FileGroups.ts、frontend/src/Api/PersonalFiles.ts、frontend/src/Api.ts、frontend/src/Main.ts、frontend/src/Account.css；tests/e2e/FileGroupOperations.spec.ts；tests/Helpers/GroupArchive.py。

- [ ] 新增E2E并确认按钮缺失导致失败：上传入组、ZIP内容、整组载入、范围用途保留、不自动执行、容量拒绝、后台跳转与越权。
- [ ] 卡片新增三项操作、隐藏上传控件、操作进度与错误反馈；成员选择限定当前卡片。
- [ ] 预筛队列先计算去重后的总容量，完整加入或完整拒绝；清除过期预筛结果。
- [ ] 相关E2E和前端双入口构建通过后同步用户指南、测试说明及CHANGELOG，选择性暂存本轮文件并提交，保留既有AI审阅改动。

## 任务三：配置与诊断说明

文件：Docs/Email163Setup.md、Docs/AiReviewTroubleshooting.md、backend/.env.example、deploy.md。

- [ ] 记录网易官方开通SMTP及授权码步骤，提供465/SSL完整配置；不将部分SMTP值写入实际.env。
- [ ] AI诊断记录开发库缺少ai_reviews及ai_review_decisions，密钥解密成功但外部调用尚未验证。
- [ ] 给出项目虚拟环境下迁移与逐层验证步骤；本轮不迁移开发库、不发送真实文件到外部模型。
- [ ] 完成结构审查、相关回归，文档单独提交；报告仍需用户填写的邮箱配置。
