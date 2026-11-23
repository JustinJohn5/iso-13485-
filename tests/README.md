# 测试说明

## 环境准备

- 后端：Python `3.12.10`，在 `backend` 目录创建虚拟环境并执行 `pip install -r requirements.lock`。
- 单元测试：安装 `pytest`（`pip install pytest`）。测试不连接数据库，不需要真实业务数据。
- 前端：在 `frontend` 目录执行 `npm install`。
- 浏览器 E2E：在项目根目录执行 `npm install`，再执行 `npx playwright install chromium`。

## 运行方式

- 后端全部单元测试：在 `backend` 目录执行 `python -m pytest ../tests/Services -q`。
- 单个测试文件：`python -m pytest ../tests/Services/test_RuleEngine.py -q`。
- 前端构建与 TypeScript 检查：在 `frontend` 目录执行 `npm run build`。
- E2E 无头运行：配置 `E2E_BASE_URL`、`E2E_EMAIL`、`E2E_PASSWORD` 后，在项目根目录执行 `npm run test:e2e`。
- E2E 有头调试：在项目根目录执行 `npx playwright test --headed`。

## 目录结构

- `tests/Services/`：文本规则引擎与文件安全校验。
- `tests/e2e/`：浏览器登录、上传及预筛交互。

## 注意事项

- 单元测试使用内存中的规则模型和临时文件，不访问 MySQL。
- 手工运行后端接口需要使用独立 MySQL 8.4 开发/测试数据库；测试环境须配置 `APP_ENV=test` 和独立的 `DATABASE_URL`，不得复用正式数据库。
- E2E 必须连接测试数据库（建议库名后缀 `_codextest`），并预先创建专用测试账号。测试账号通过环境变量提供，不写入用例。
- E2E 服务需分别启动：后端使用测试环境配置，前端设置 `VITE_API_BASE_URL` 和 `FRONTEND_PORT`。后端/前端测试端口应与本地开发和正式端口分开。
- E2E 上传写入测试数据库和测试上传目录；运行后清理测试库中的测试数据与上传文件。
- 当前规则集只做文本线索预筛，不构成 ISO 13485 认证、审核或法规符合性结论。
