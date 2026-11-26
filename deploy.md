# 部署说明

## 更新记录

- 2026-11-26：订正迁移与编号：`三、数据库迁移`补入 `MigrateAiReviews.py`、`ai_reviews`/`ai_review_decisions` 说明及缺表时的 503/1502 表现；原与 AI 章节重号的「5.9 注册与修改密码邮箱验证码」调整为 4.2，环境变量章节的指引同步改指 4.1、4.2；MySQL 端口示例按实际实例改为 3306（README、`backend/.env.example`、用户手册同步）。无代码、依赖、端口或环境变量变更。
- 2026-11-26：新增账户菜单、个人文件与分组，以及 `/admin/` 管理后台；新增 `file_groups`、`file_group_members`、`visitors`、`visitor_daily` 表。先在 MySQL 8.4 `_codextest` 验证两项迁移与 E2E，再迁移开发库；正式库须取得发布授权。无新增环境变量、端口或依赖。
- 2026-11-26：修复验证码输入布局并强化模型配置管理员复核；AI 审阅新增模型就绪检查与手动重试。后端缺表时返回503/1502及迁移提示，所有异常响应遵守既有 CORS 允许列表。按当时的邮箱验证码迁移说明（现 4.2 节）补齐既有迁移后重启后端、重新构建前端，无新增环境变量。
- 2026-11-26：新增预筛结果中的 AI 查找依据、逐项审阅及人工决定追加留痕；API Key 沿用网页加密配置。新增 `ai_reviews` 与 `ai_review_decisions` 表，先在 `_codextest` 验证 `MigrateAiReviews.py`，再按授权流程迁移目标数据库；无新增环境变量、端口或依赖。
- 2026-11-24：验证码仅用于注册和修改密码，登录不变。新增 SMTP 配置、来源 IP 小时限流及可信代理设置，公开注册响应不暴露邮箱是否已注册。
- 2026-11-24：注册验证码请求增加 MySQL 来源 IP 小时限流；统一邮箱是否已注册时的公开响应，并新增可信代理配置。迁移同时创建 `email_verification_ip_limits` 表。

- 2026-11-24：登录页新增公开注册及 `POST /api/v1/auth/register`，默认普通使用账号（`auditor`），不开放管理员自注册。沿用用户表、密码哈希和登录 Cookie；发布时重启后端并重新构建前端，无新增依赖、环境变量或迁移。

- 2026-11-24：新增登录可访问的规则手册页面和 `GET /api/v1/rule-sets/{id}` 规则详情接口；随前后端发布，沿用既有鉴权，无数据库迁移、依赖或环境变量变更。

- 2026-11-24：补全可直接照做的完整部署步骤（服务器准备 → MySQL 8.4 → 后端 systemd → 前端构建 → Nginx 反向代理与 HTTPS → 部署校验 → 日志、备份、升级回滚），新增域名与 Cookie 的同站约束、多进程启动选项；无代码、依赖、端口或环境变量变更。

- 2026-11-24：新增按整套发布版本管理的导入、20项目录批量生成、正文编辑、预筛与 ZIP 下载；新增 `manual_suites` 表，先在 MySQL 8.4 测试副本验证 `MigrateManualSuites.py`，再迁移开发或经授权的正式库。无新增依赖、端口或环境变量。

- 2026-11-23：Word 草稿导出采用参考质量手册版式；将 `backend/App/Assets/Documents/ManualLayout.docx` 随后端发布并重启后端，无数据库迁移、新依赖或新增环境变量，详见 `Docs/WordLayout.md`。

- 2026-11-23：扩大长文本输入、章节及模型输出限制；无数据库迁移或新增环境变量，更新后重启后端并重新构建前端。

- 2026-11-23：修正 `backend/.python-version` 为已使用的 Python 3.12.10，与虚拟环境、依赖解析版本及部署文档一致；不升级运行时。

- 2026-11-23：新增明确选择草稿、预览差异和事务化提交的跨文档参数联动，无额外迁移或环境配置。

## 一、部署前须知

### 1.1 三部分独立部署

前端、后端、MySQL 分别部署、可独立扩容：

- 前端：静态文件，任意静态 Web 服务或 CDN 托管；
- 后端：Python 3.12.10 + uvicorn 常驻进程，只提供 HTTP API；
- 数据库：MySQL 8.4，只允许后端服务器访问，不对前端或公网开放。

三者之间只通过环境变量描述的地址通信。更换主机、端口或域名时只改 `.env` 与反向代理配置，不改代码。

### 1.2 版本与端口

| 项目 | 版本/取值 | 依据 |
|---|---|---|
| 后端运行时 | Python 3.12.10 | `backend/.python-version` |
| 前端运行时 | Node.js 26.13.1 | `.nvmrc`、`frontend/package.json` 的 `engines` |
| 数据库 | MySQL 8.4（迁移脚本强制校验 8.4） | `Migrate*.py` |
| 依赖锁定 | `backend/requirements.lock`、`frontend/package-lock.json` | 安装只可用锁定文件 |

| 环境 | 前端 | 后端 | MySQL 端口 |
|---|---:|---:|---:|
| 本地开发 | 5300 | 8320 | 3306 |
| 测试/E2E | 5400 | 8400 | 3306（同一实例的 `_codextest` 库） |
| 正式环境 | 5500（或 443 反代） | 8500 | 3306（仅私网） |

MySQL 端口按实际实例填写：本机 `backend/.env` 与 `.env.test` 均为 3306，开发库 `iso13485` 与测试库 `iso13485_codextest` 是同一实例上的两个库，靠库名隔离；另建独立测试实例时才改为此实例端口。更换端口只调整对应环境变量与代理配置，不改业务代码。

### 1.3 域名与 Cookie 的同站约束（部署前必须确认）

登录令牌写在 HttpOnly Cookie 中，`SameSite=Lax`，`APP_ENV=prod` 时带 `Secure` 标记（见 `backend/App/Api/Auth.py`）。因此正式环境必须满足以下之一：

- **推荐：同域反向代理**。前端与 `/api/` 由同一个域名（如 `https://iso.example.com`）提供，浏览器同源，无跨域、无 Cookie 丢失；
- 前端与 API 使用同一主域下的不同子域（如 `app.example.com` 与 `api.example.com`），仍属同站，需在 `CORS_ORIGINS` 精确填写前端来源；
- 前端与 API 分属完全不同的注册域时，`SameSite=Lax` 会导致登录态不随请求发送。这种拓扑需要改动 Cookie 策略（`SameSite=None` + 强制 HTTPS），属于代码变更，必须先与维护方确认，不要在部署阶段临时改动。

### 1.4 必须随版本一起发布的非代码文件

- `backend/App/Rules/core.json`：规则包，缺失时后端启动即报「规则包目录不存在」；
- `backend/App/Assets/Documents/ManualLayout.docx`：Word 统一版式资产，缺失时草稿与套册导出失败。

`InitDb.py` 只创建缺失的表，不会修改既有表结构；结构升级必须走 `Migrate*.py`。

## 二、完整部署步骤（Ubuntu 22.04 / 24.04）

以下命令以正式环境为例：后端目录 `/srv/iso/backend`、前端目录 `/srv/iso/frontend`、运行用户 `isoapp`、域名 `iso.example.com`、后端端口 8500。macOS 也可按同一顺序操作，仅包管理与进程管理命令不同（macOS 没有 systemd，用前台进程或 launchd）。

### 2.1 服务器准备

```bash
sudo apt update
sudo apt install -y build-essential curl git nginx ufw rsync unzip \
  libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev \
  libffi-dev liblzma-dev libncursesw5-dev

# 后端运行时：Python 3.12.10，装在 /opt 供运行账号可读
sudo env PYENV_ROOT=/opt/pyenv git clone --depth 1 https://github.com/pyenv/pyenv.git /opt/pyenv
sudo env PYENV_ROOT=/opt/pyenv /opt/pyenv/bin/pyenv install 3.12.10
/opt/pyenv/versions/3.12.10/bin/python -V   # 应为 3.12.10

# 前端构建运行时：Node.js 26.13.1（nvm 方式，仅构建阶段需要）
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
# 重新登录后
nvm install 26.13.1
nvm use 26.13.1
node -v   # 应为 v26.13.1
```

说明：

- 不要把 Python 装在 root 家目录（`pyenv install` 默认位置），否则运行账号 `isoapp` 无权读取解释器；装在 `/opt/pyenv` 可避免该问题；
- 系统自带的 `python3.12` 版本号未必是 3.12.10，与 `.python-version` 不一致时按上面的方式补装，不要用更高版本解释器跑本项目；
- 如服务器已有 `uv`，可用 `UV_PYTHON_INSTALL_DIR=/opt/python uv python install 3.12.10` 替代，效果相同。

创建运行用户与目录：

```bash
sudo mkdir -p /srv/iso /var/www/iso-frontend
sudo chown -R isoapp:isoapp /srv/iso
```

取代码（Git 或打包上传均可），前后端可分别放到各自服务器：

```bash
sudo -u isoapp git clone <仓库地址> /srv/iso
# 或本地打包上传后：sudo rsync -av --exclude node_modules --exclude .venv ./ isoapp@服务器:/srv/iso/
```

不要把本机的 `backend/.env`、`.venv`、`node_modules`、`Storage/`、`Logs/`、`dist/` 复制到服务器，这些都在目标机生成。

### 2.2 数据库（MySQL 8.4）

安装 8.4（Ubuntu 官方源通常为 8.0，需用 MySQL 官方 APT 仓库选择 `mysql-8.4-lts`）：

```bash
wget https://dev.mysql.com/get/mysql-apt-config_0.8.33-1_all.deb
sudo dpkg -i mysql-apt-config_0.8.33-1_all.deb   # 选择 MySQL 8.4 LTS
sudo apt update
sudo apt install -y mysql-server
mysql -V   # 确认 8.4.x
```

创建数据库与最小权限账号（登录数据库主机执行 `mysql -h <数据库主机> -u root -p`，或在前端/后端机用 `mysql -h 10.0.0.12 -u root -p`）：

```sql
CREATE DATABASE IF NOT EXISTS iso13485
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER 'iso_app'@'10.0.%' IDENTIFIED BY '替换为强密码';
GRANT CREATE, ALTER, INDEX, REFERENCES, SELECT, INSERT, UPDATE, DELETE
  ON iso13485.* TO 'iso_app'@'10.0.%';
FLUSH PRIVILEGES;
```

约束与建议：

1. `bind-address` 与防火墙只放行后端服务器所在网段，禁止对公网开放 3306；
2. 密码中的特殊字符在 `DATABASE_URL` 中必须 URL 编码（`#` 写作 `%23`、`@` 写作 `%40`）；
3. 配置定时备份与监控；
4. 建议同时建一个测试库 `iso13485_codextest`，任何迁移先在它上面跑通。

### 2.3 后端部署

安装依赖（只用锁定文件，不要用 `requirements.txt` 自由解版本）：

```bash
sudo -u isoapp -H bash -lc '
  cd /srv/iso/backend
  /opt/pyenv/versions/3.12.10/bin/python -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.lock
'
sudo -u isoapp -H /srv/iso/backend/.venv/bin/python -V   # 应为 3.12.10
```

生成配置与密钥：

```bash
sudo -u isoapp cp /srv/iso/backend/.env.example /srv/iso/backend/.env
sudo -u isoapp -H /srv/iso/backend/.venv/bin/python -c \
  "import os,base64;print('CONFIG_ENCRYPTION_KEY='+base64.urlsafe_b64encode(os.urandom(32)).decode())"
sudo -u isoapp -H /srv/iso/backend/.venv/bin/python -c \
  "import os;print('JWT_SECRET='+os.urandom(48).hex())"
sudo chmod 600 /srv/iso/backend/.env
sudo chown isoapp:isoapp /srv/iso/backend/.env
```

`backend/.env` 正式环境取值要点（字段含义见「环境变量清单」）：

```ini
# 运行环境：dev / test / prod
APP_ENV=prod
LOG_LEVEL=INFO
LOG_DIR=/srv/iso/backend/Logs
# Nginx 与后端同机时用 127.0.0.1；反向代理在另一台时改 0.0.0.0 并用防火墙限定来源
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8500
FRONTEND_PORT=5500
CORS_ORIGINS=https://iso.example.com
DATABASE_URL=mysql+pymysql://iso_app:密码@10.0.0.12:3306/iso13485?charset=utf8mb4
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
CONFIG_ENCRYPTION_KEY=上一步生成的值
JWT_SECRET=上一步生成的值
JWT_EXPIRE_MINUTES=480
UPLOAD_DIR=/srv/iso/backend/Storage
MAX_UPLOAD_SIZE_MB=40
RULE_SET_DIR=./App/Rules
ACCESS_TOKEN_COOKIE_NAME=iso_access_token
```

`.env` 每行只写一个 `键=值`，注释单独占一行；行内注释会被当作值的一部分读入（如 `BACKEND_HOST=127.0.0.1  # 注释` 会导致监听地址非法）。

注意：

- 密钥缺失、仍是示例占位值、长度或格式不符时，后端启动直接报中文错误并退出，不会带病运行；
- `CONFIG_ENCRYPTION_KEY` 只加密网页中配置的大模型 API Key，与数据库分开备份；更换后已存密钥无法解密，需在网页重新填写；
- `UPLOAD_DIR` 严禁放在 Web 静态目录（如 `/var/www`）下。

初始化数据库：

```bash
# 空库首次部署：InitDb.py 会依据当前模型创建全部业务表
sudo -u isoapp -H /srv/iso/backend/.venv/bin/python /srv/iso/backend/InitDb.py

# 创建首个管理员（交互输入邮箱、显示名、密码）
sudo -u isoapp -H bash -lc 'cd /srv/iso/backend && .venv/bin/python CreateAdmin.py'
```

已有数据库升级时不要运行 `InitDb.py`，按「三、数据库迁移」执行对应 `Migrate*.py`。

注册 systemd 服务 `/etc/systemd/system/iso-backend.service`：

```ini
[Unit]
Description=ISO 13485 文件预筛平台后端
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=isoapp
Group=isoapp
WorkingDirectory=/srv/iso/backend
Environment=PYTHONUNBUFFERED=1
ExecStart=/srv/iso/backend/.venv/bin/python Run.py
Restart=always
RestartSec=5
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ReadWritePaths=/srv/iso/backend/Storage /srv/iso/backend/Logs
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
```

启动与自检：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now iso-backend
sudo systemctl status iso-backend --no-pager
curl -s http://127.0.0.1:8500/          # 返回 {"code":0,...}
journalctl -u iso-backend -n 50 --no-pager
```

`Run.py` 以单进程 uvicorn 启动，监听地址与端口取自 `backend/.env`。需要多进程时改用（此时不再使用 `Run.py`，端口须与 `.env` 保持一致）：

```bash
cd /srv/iso/backend
/srv/iso/backend/.venv/bin/python -m uvicorn Main:app \
  --host 127.0.0.1 --port 8500 --workers 4
```

长文 AI 生成是耗时请求，多进程能避免单个长任务占满工作线程；进程数按 CPU 与内存评估，不要超过数据库连接池总量（`DATABASE_POOL_SIZE + DATABASE_MAX_OVERFLOW` 为每进程上限）。

### 2.4 前端部署

前端只在构建阶段需要 Node.js，产物是纯静态文件，运行时不依赖 Node.js，也不连接数据库。

```bash
cd /srv/iso/frontend
nvm use 26.13.1
npm ci
cp .env.example .env.production
```

`.env.production` 中至少确认：

```ini
VITE_APP_TITLE=ISO 13485 文件预筛平台
# 同域反代时填平台域名：前端会请求 {该值}/api/v1/...
VITE_API_BASE_URL=https://iso.example.com
# 仅影响本地 dev/preview，不进入构建产物
FRONTEND_PORT=5500
```

同样不要写行内注释，`VITE_API_BASE_URL` 带多余字符会导致请求地址拼接错误。

构建并发布静态文件：

```bash
npm run build
sudo rsync -a --delete dist/ /var/www/iso-frontend/
sudo chown -R www-data:www-data /var/www/iso-frontend
```

注意：`VITE_*` 变量会被编译进浏览器可见的产物，只能放非敏感配置；改动 `VITE_API_BASE_URL` 必须重新构建，不能靠改服务器文件生效。`dist/` 已被 `.gitignore` 忽略，仓库或上传包里残留的旧产物不可直接发布（引用哈希可能与实际文件不对应），一律在目标机执行 `npm run build` 生成。

### 2.5 Nginx 反向代理与 HTTPS

同域反代方案：`/` 提供前端静态文件，`/api/` 转发到后端 8500。

```bash
sudo tee /etc/nginx/sites-available/iso-platform > /dev/null <<'CONF'
server {
    listen 80;
    server_name iso.example.com;

    root /var/www/iso-frontend;
    index index.html;

    # 单文件上传上限 40MB；套册批量与长文请求留出余量
    client_max_body_size 128m;
    client_body_timeout 120s;

    # 前端静态资源
    location /assets/ {
        expires 30d;
        add_header Cache-Control "public, immutable";
        try_files $uri =404;
    }

    location / {
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache";
    }

    # 后端 API
    location /api/ {
        proxy_pass http://127.0.0.1:8500;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Cookie $http_cookie;

        # AI 长文生成：单次超时上限 600 秒，留出重试与网络余量
        proxy_connect_timeout 10s;
        proxy_send_timeout 700s;
        proxy_read_timeout 700s;

        # 套册 ZIP 下载可达数百 MB，允许较大的临时缓冲文件
        proxy_max_temp_file_size 2048m;
        proxy_request_buffering off;
    }
}
CONF
sudo ln -sf /etc/nginx/sites-available/iso-platform /etc/nginx/sites-enabled/iso-platform
sudo nginx -t && sudo systemctl reload nginx
```

要点：

- `proxy_pass http://127.0.0.1:8500;` 结尾不带 `/`，保留 `/api/v1/...` 完整路径；
- 后端已允许 `PATCH`、`DELETE`（类型修正、审查决策、移出套册成员），反向代理若自行限制方法必须放行；
- 反向代理改端口、加 HTTPS 或换域名时同步更新本文件与 `.env` 的 `CORS_ORIGINS`。

启用 HTTPS：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d iso.example.com
sudo systemctl status certbot.timer --no-pager   # 确认自动续期
```

证书生效后，浏览器到前端与 API 均为 HTTPS；`APP_ENV=prod` 下登录 Cookie 带 `Secure`，纯 HTTP 访问会导致登录态无法保存。

### 2.6 部署校验清单

```bash
# 后端进程与端口
sudo systemctl is-active iso-backend
sudo ss -ltnp | grep 8500

# 后端直连
curl -s http://127.0.0.1:8500/ | head -c 200

# 经反向代理（同域）
curl -sI https://iso.example.com/ | head -n 3
curl -s https://iso.example.com/api/v1/auth/me   # 未登录应返回 401 业务错误，不应是 502/504

# 数据库
mysql -h 10.0.0.12 -u iso_app -p -e "use iso13485; show tables;"
```

浏览器侧确认：登录成功、刷新后仍保持登录、上传一个 PDF/DOCX 能出预筛结果、套册 ZIP 可下载、Word 导出可打开、管理员「模型配置」可保存。

### 2.7 日志查看

| 来源 | 路径 / 命令 |
|---|---|
| 后端应用日志 | `/srv/iso/backend/Logs/`（按日期轮转，`LOG_DIR` 可改） |
| 后端实时输出 | `journalctl -u iso-backend -f` |
| 后端最近错误 | `journalctl -u iso-backend -p err -n 100 --no-pager` |
| Nginx 访问/错误 | `/var/log/nginx/access.log`、`/var/log/nginx/error.log` |
| 系统与内核 | `journalctl -xe` |

日志已做敏感信息过滤，不会输出密码、完整令牌、加密主密钥或大模型 API Key；排查时不要把 `.env` 内容贴进工单或聊天。

### 2.8 备份

需要一起备份的三类数据缺一不可，且分开保管：

```bash
# 1) 数据库（草稿、审阅快照、套册正文、大模型配置密文）
mysqldump -h 10.0.0.12 -u iso_app -p \
  --single-transaction --routines --triggers iso13485 \
  | gzip > /var/backups/iso13485-$(date +%F).sql.gz

# 2) 上传原件与导出依赖
sudo tar czf /var/backups/iso-storage-$(date +%F).tar.gz -C /srv/iso/backend Storage

# 3) 配置文件与密钥（单独加密保管，不与数据库备份同处）
sudo tar czf /root/iso-env-$(date +%F).tar.gz -C /srv/iso/backend .env
```

恢复顺序：先还原数据库，再还原 `Storage/` 与 `.env`，最后启动后端。`CONFIG_ENCRYPTION_KEY` 与数据库密文必须配套，任一丢失都需在网页重新填写大模型 API Key。

备份账号权限：应用账号默认只有业务表的读写与建表权限，`mysqldump` 还需要 `SHOW VIEW`、`TRIGGER`、`EVENT`、`PROCESS`（使用 `--single-transaction` 时不锁表）。用独立备份账号执行 `mysqldump`，或为备份用途单独授权，不要为此把应用账号提升为管理员。

### 2.9 升级与回滚

```bash
# 升级
sudo -u isoapp -H bash -lc 'cd /srv/iso/backend && git fetch --all && git checkout <发布标签>'
sudo -u isoapp -H /srv/iso/backend/.venv/bin/python -m pip install -r /srv/iso/backend/requirements.lock
# 有结构变更时先迁移（见第三节），再重启
sudo systemctl restart iso-backend

cd /srv/iso/frontend && git fetch --all && git checkout <发布标签> && nvm use 26.13.1
npm ci && npm run build
sudo rsync -a --delete dist/ /var/www/iso-frontend/
sudo systemctl reload nginx
```

回滚：

1. 代码回退到上一个发布标签，重新安装锁定依赖并重启后端；
2. 前端用上一版产物重新 `rsync`；
3. 数据库**不要**为回滚删表：新增表与新增列保留，旧代码不受影响；
4. 结构变更造成数据异常时，从迁移前备份恢复，并在恢复后重新核对上传原件与套册成员。

### 2.10 其他平台说明

- macOS 开发机：命令基本一致，把 `systemctl` 换成前台运行或 launchd，`www-data` 换成 `_www`；
- Windows：使用 `.venv/Scripts/python.exe` 代替 `.venv/bin/python`，进程守护用服务管理器或任务计划；生产环境仍按 Ubuntu 配置目录权限与进程账号；
- 所有平台都用项目虚拟环境中的解释器执行 Python 命令，不要用系统默认解释器。

## 三、数据库迁移

迁移脚本均要求 MySQL 8.4，`APP_ENV=prod` 时必须显式传 `--allow-production`，`APP_ENV=test` 时库名必须以 `_codextest` 结尾。

| 脚本 | 作用 | 幂等 |
|---|---|---|
| `InitDb.py` | 创建全部缺失表（仅空库首次部署） | 是（只建缺失表） |
| `MigrateDocumentDrafts.py` | 新增 `document_drafts` 表 | 是 |
| `MigrateDocumentReviews.py` | 新增 `document_reviews` 表与 `validation_runs.review_snapshot` | 是（不删表重建） |
| `MigrateManualSuites.py` | 新增 `manual_suites` 表 | 是 |
| `MigrateEmailVerification.py` | 新增验证码与来源限流状态表 | 是 |
| `MigratePersonalFiles.py` | 新增个人文件分组及成员引用表 | 是 |
| `MigrateAdmin.py` | 新增访客状态与每日访问聚合表 | 是 |
| `MigrateAiReviews.py` | 新增 `ai_reviews` 与 `ai_review_decisions` 表 | 是（只建缺失表） |

漏跑任一脚本的表现是接口返回 503 与业务码 `1502`（缺表 1146），AI 审阅面板会提示“数据库结构尚未升级”；按本节表格逐项核对已执行脚本，不要只看 `InitDb.py`。

标准流程（默认读 `backend/.env`；`--env-file` 可指定其他配置文件；以下脚本名按本次要应用的迁移替换）：

```bash
cd /srv/iso/backend

# 1) 测试库验证（数据库名须以 _codextest 结尾）
.venv/bin/python MigrateManualSuites.py --env-file ../.env.test

# 2) 开发库
.venv/bin/python MigrateManualSuites.py

# 3) 正式库（取得发布授权后）
.venv/bin/python MigrateManualSuites.py --allow-production
```

历史迁移说明：

- `uploaded_files.document_type`：旧库需执行
  `ALTER TABLE uploaded_files ADD COLUMN document_type VARCHAR(48) NOT NULL DEFAULT 'other' COMMENT '质量体系文档类型';`
  先在 `_codextest` 验证再纳入发布流程。
- `document_drafts`（1.2.0）：`MigrateDocumentDrafts.py`，仅建表，不改既有文件与预筛记录；回滚代码时保留新增表，避免丢失草稿。
- `document_reviews`（1.1.0）：`MigrateDocumentReviews.py`；MySQL DDL 不保证事务回滚，部分失败时保留备份、确认表/列状态后重试。
- `manual_suites`（1.3.0）：`MigrateManualSuites.py`，只建表，不改既有业务表；回退应用时保留新表与上传原件。
- `email_verification_codes`、`email_verification_ip_limits`（本次）：`MigrateEmailVerification.py`，只建验证码与限流状态表；回退应用时保留表和审计，不删除用户数据。
- `file_groups`、`file_group_members`：`MigratePersonalFiles.py`，只建个人分组及文件引用表，不迁移或删除原件。
- `visitors`、`visitor_daily`：`MigrateAdmin.py`，只建访客状态和每日访问聚合表；启用前没有历史访问统计数据。
- `ai_reviews`、`ai_review_decisions`（AI 文件阅读审核）：`MigrateAiReviews.py`，只建候选审阅与人工决定追加表，不改预筛记录、规则包或评分；AI 记录与规则评分相互独立，回退应用时保留新表与已有审阅留痕。
- 跨域配置允许 `DELETE`，用于移出套册或文件分组成员；反向代理需放行。

## 四、环境变量清单

- 后端：`APP_ENV`、`LOG_LEVEL`、`LOG_DIR`、`BACKEND_HOST`、`BACKEND_PORT`、`FRONTEND_PORT`、`CORS_ORIGINS`、`DATABASE_URL`、`DATABASE_POOL_SIZE`、`DATABASE_MAX_OVERFLOW`、`CONFIG_ENCRYPTION_KEY`、`JWT_SECRET`、`JWT_EXPIRE_MINUTES`、`UPLOAD_DIR`、`MAX_UPLOAD_SIZE_MB`、`RULE_SET_DIR`、`ACCESS_TOKEN_COOKIE_NAME`；SMTP 与可选 `TRUSTED_PROXY_CIDRS` 字段见 4.1、4.2。
- 前端：`VITE_APP_TITLE`、`VITE_API_BASE_URL`、`FRONTEND_PORT`。这些值会暴露给浏览器，不得存放秘密。
- 测试/E2E：复制根目录 `.env.test.example` 为 `.env.test`，配置独立 `APP_ENV=test`、MySQL 8.4 的 `_codextest` 库、测试密钥及上传目录。测试前后端使用 5400/8400，开发与正式服务使用其他端口。同一 MySQL 实例可提供独立测试库；单独部署测试实例时设置其实际端口。
- 测试入口地址：`E2E_BASE_URL` 为测试前端，`E2E_API_BASE_URL` 和 `VITE_API_BASE_URL` 为测试后端，必须对应测试服务的地址和端口；`E2E_BROWSER_CHANNEL` 留空使用 Playwright Chromium，可填 `msedge` 使用本机 Edge。
- `E2E_SMTP_PORT` 为本机隔离 STARTTLS 收件箱端口（示例 5425），不得与其他服务冲突。测试入口临时生成邮件账号、授权值、可信证书及收件目录，仅用于本次测试，不修改运行环境 SMTP，也不向外网转发。
- `tests/RunE2e.py` 在子进程环境中临时注入随机 `E2E_EMAIL`、`E2E_PASSWORD` 和当前解释器路径 `E2E_PYTHON`；这些不是部署凭证，不写入仓库。准备、运行与清理方式见 `tests/README.md`。

配置字段和端口示例见 `backend/.env.example` 与 `frontend/.env.example`。修改端口、加密密钥或跨域来源时需同步维护这两个示例文件。

大模型的服务地址、模型、API Key、超时、最大输出 token 与温度**不是**环境变量，统一在网页「模型配置」中维护，仅存于 MySQL 并以 `CONFIG_ENCRYPTION_KEY` 加密；`.env` 不设同名配置或回退值。

### 4.1 邮箱验证码环境变量

验证码只用于注册和登录后的修改密码，登录本身不需要验证码。真实部署在后端 `.env` 配置 SMTP；以下字段不能放入前端环境变量：

```ini
EMAIL_SMTP_HOST=smtp.example.com
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USERNAME=mailer@example.com
EMAIL_SMTP_PASSWORD=请在服务器本地填写SMTP授权码
EMAIL_FROM_ADDRESS=mailer@example.com
EMAIL_SMTP_STARTTLS=true
EMAIL_SMTP_SSL=false
EMAIL_SMTP_TIMEOUT_SECONDS=10
TRUSTED_PROXY_CIDRS=10.0.0.0/24,2001:db8::/48
```

`EMAIL_SMTP_STARTTLS` 与 `EMAIL_SMTP_SSL` 必须二选一，且服务端始终校验证书；端口常见组合是 STARTTLS/587 或 SSL/465，按邮件服务商要求填写。五个连接和身份字段全部留空时，后端仍可启动和登录，但发送验证码会返回“邮箱服务尚未配置”；只填写部分字段或使用非法端口会阻止启动并给出中文错误。SMTP 授权码不能使用 MySQL 密码替代。

发布顺序：先在 `_codextest` 测试库执行 `MigrateEmailVerification.py` 并运行验证码 E2E，再迁移开发库；正式库须先获发布授权并添加 `--allow-production`。迁移后重启后端、重新构建前端。测试入口的 `E2E_SMTP_PORT` 只启动本机隔离收件箱，不配置到正式 `.env`，也不向外部邮箱转发。

`TRUSTED_PROXY_CIDRS` 是可选项，填写直接连接后端的反向代理 IP/CIDR，多个值以逗号分隔；直连部署留空。只有 TCP 对端属于这些网段时，应用才会解析 `X-Forwarded-For`，并从右向左跳过可信代理。不要把用户可直接访问的网段配置为可信代理。来源限流按 IPv4 地址或 IPv6 `/64` 聚合，每个来源固定窗口每小时最多20次验证码请求；过期的 IP 摘要记录在后续请求中清理。

### 4.2 注册与修改密码邮箱验证码

注册流程先调用 `POST /api/v1/auth/registration-codes`，后端将一次性 6 位验证码发送到请求邮箱；`POST /api/v1/auth/register` 必须同时提交验证码。登录仍只需邮箱和密码。已登录用户调用 `POST /api/v1/auth/password-change-codes` 给当前账号邮箱发码，再用 `PATCH /api/v1/auth/password` 提交当前密码、新密码、确认密码和验证码。改密成功后删除当前 Cookie，并递增用户令牌版本，使其他旧会话同时失效。

MySQL 表 `email_verification_codes` 只保存按邮箱和用途绑定的 HMAC 摘要、签发/过期/消费时间和次数，不保存明文验证码；`email_verification_ip_limits` 保存按服务端 JWT 密钥派生的来源 IP HMAC 摘要及限流计数，不保存原始 IP。验证码 10 分钟有效，60 秒内不能重发，每邮箱每用途每小时最多 5 次，每来源 IP 每小时最多 20 次，连续 5 次错误后失效，重发会让旧码失效且成功后只能消费一次。公开注册验证码请求对已注册与新邮箱返回相同响应；注册提交必须先提供有效验证码，重复邮箱返回通用验证码错误。发信失败不创建账号或修改密码。

迁移验证命令（macOS/Ubuntu）：

```bash
cd /srv/iso/backend
./.venv/bin/python MigrateEmailVerification.py --env-file ../.env.test
cd ..
./backend/.venv/bin/python tests/RunE2e.py tests/e2e/EmailVerification.spec.ts tests/e2e/Registration.spec.ts tests/e2e/Auth.spec.ts
cd backend
./.venv/bin/python MigrateEmailVerification.py
```

Windows 使用 `.venv/Scripts/python.exe`。正式库迁移使用正式 `.env` 并显式添加 `--allow-production`。部署后使用真实可收信邮箱手动测试注册邮件；测试收件箱仅验证本机 SMTP/TLS 和应用流程，不能替代外部邮件送达验证。

## 五、功能发布与使用边界

### 5.1 跨文档参数联动

在「模板与编写」点击「跨文档参数联动」，选择 1～20 份已保存草稿，填写需要统一的组织、项目、产品或型号及变更原因。
先预览每份草稿的旧值、新值和修订号，再点击应用；提交时重新校验所有草稿权限及版本，任一过期或不可访问时整批拒绝，避免部分更新。
应用会按每份草稿原模板重新生成全部章节，覆盖人工或 AI 修改；旧修订可下载，独立的文件编号、文件版本及其他参数保留。
只影响明确选择的草稿；不修改已上传原件、历史预筛依据快照或组织正式发布文件。修改预览输入后须重新预览。
后端每批一次 IN 查询、按主键顺序锁行、一次 executemany 批量更新，在同一事务保存所有修订及审计记录。

### 5.2 模拟内审

预筛完成后，在结果下方点击「生成内审问题清单」或「下载问题清单 Word」。
服务按历史预筛任务的规则结果、关联检查和正式依据快照生成清单，不重新读取被修改的草稿或调用模型，也不改变原预筛分数。
取证问题覆盖规则缺项、待补引用、跨文件要求冲突以及文本通过项的实际执行核实，导出预留责任人、期限、实际证据和有效性验证记录。
旧任务的持久化规则记录只保存文件类型，多个同类型文件时清单展示该类型的相关文件范围，不臆测原文属于哪一份文件。
仅任务所有者及管理员可读取和导出清单，导出留审计记录；此功能不构成正式内审发现、不符合项定性或标准完整性保证。

### 5.3 大模型首次配置与维护

更新后端依赖时仍使用项目虚拟环境执行 `python -m pip install -r requirements.lock`；官方 OpenAI SDK 版本锁定在 `requirements.lock`（3.57.0），不要单独升级。
管理员登录后打开「模型配置」，填写 OpenAI 兼容 API 的服务地址（含服务商要求的前缀）、模型标识、API Key、单次超时、最大输出 token 和温度，并启用。
配置仅保存在 MySQL 的既有 `llm_configs` 表，`.env` 不设置这些调用参数或任何回退值。
API Key 使用后端 `.env` 的 `CONFIG_ENCRYPTION_KEY` 加密，不回传明文或密文；输入留空保留已有值，更换服务地址时必须重新提交密钥。
备份数据库和加密主密钥时分开保管；主密钥变更后必须重新填写 API Key，否则调用明确报解密失败。
正式站点及模型服务地址使用 HTTPS。超时范围 5～600 秒，最大输出 256～65,536 token，温度 0～2；最多重试 1 次，输出被截断、JSON 异常或缺章时不保存新修订。
产品资料最多 100,000 字符、AI 编写要求最多 30,000 字符、单章正文最多 120,000 字符。系统提示及序列化请求合计最多 1,000,000 字符，响应最多 400,000 字符；超限明确拒绝，不静默截断。
这些是应用限制，字符数不等同于 token 数；实际输入加输出仍须符合服务商模型的上下文窗口与输出额度。已有 MySQL 模型配置值保留，管理员可通过网页调整，无需改动 `.env`。
长文生成需按实际耗时配置反向代理的读取超时，并考虑最多一次重试；SDK 的超时配置按每次请求生效，不是整个任务的总时限。
没有配置时模板编写与预筛正常使用。审核员只读取模型是否就绪，不读取配置；管理员可读写配置，保存有脱敏审计记录。
AI 入口在已保存草稿内，明确告知会向所配置服务发送草稿及编写要求；用户点击后才调用，成功保存新修订，失败保留原草稿并提示继续人工编辑。
AI 来源和模型标识保存在修订快照；不自动填写批准、生效日期和检验限值，实际生成内容仍需人工逐项复核。

### 5.4 模板编写与 Word 导出（1.2.0）

已有数据库先按第三节在测试副本验证 `MigrateDocumentDrafts.py --env-file ../.env.test`，确认通过后再迁移开发库；部署后重启后端并重新构建前端。
模板入口为登录后的「模板与编写」，示例模板随代码版本发布；模板并非标准官方文件。
参数更新按模板重建当前草稿的全部章节，会覆盖当前人工正文，旧修订保留供下载。每份草稿最多保存 50 次修订。
生成文件包含参考手册风格的封面、更改历史、目录、文件信息、表格页眉、正文、批准占位与动态页码，不自动填入批准或检验结果。页码与目录由 Word/WPS 更新域；服务端仅使用既有 python-docx，无需办公软件。后端部署须保留 `App/Assets/Documents/ManualLayout.docx`，不依赖本机原始参考件。

### 5.5 文件集审查与正式版（1.1.0）

本次新增 `document_reviews` 表（审查标识、创建者索引、修订号、JSON 快照、创建时间），以及 `validation_runs.review_snapshot` 可空 JSON 列。初始空库通过既有 `InitDb.py` 建表；已有库使用版本化入口 `MigrateDocumentReviews.py`，不删表重建，不改写已有预筛结果。

新增 API：

- `POST /api/v1/document-reviews`：JSON `file_uids`、`as_of_date` 和可选 `overrides`（文件标识 → 校正字段）。一次批量读取文件；校正支持编号、修订、生效日、类别、层级、状态，保存于审查快照，不改原件。
- `GET /api/v1/document-reviews/{review_uid}`：读取本人或管理员可访问的快照。
- `PATCH /api/v1/document-reviews/{review_uid}/decisions`：JSON `revision`、`kind`（version/requirement）、`issue_id`、`file_uid`、`reason`。通过权限、候选、日期状态及乐观锁校验后更新，追加历史与审计日志。
- `POST /api/v1/validations` 增加 Form 字段 `review_uid` / `review_revision`。提交审查时两者须对应最新修订，按确认范围预筛并保存冻结快照。旧调用未提交审查时仍可处理无检测冲突文件；检测到版本或明确期限冲突会返回 409，不能绕过确认。
- 上传和类型修改响应新增 `control_metadata`；预筛新增 `excluded_versions`、`document_review`。原有字段保留，前后端须一同发布。

错误码：1601 审查不存在（404）、1602 审查已更新（409）、1603 文件集/类型已变化（409）、1604 冲突未确认（409）；非法元数据或不允许的候选使用 1001（400），越权使用 1104（403）。本次无需新增环境变量或大模型配置。

界面中的正式版是本次预筛采用依据，不能替代组织受控批准发布。内容比较只覆盖明确同编号的数字保存期限；完整语义冲突与法规适用性仍需人工复核。详见 `Docs/DocumentControl.md`。

### 5.6 文件类型识别与预筛响应（1.0.1）

本次无数据库结构变更，既有数据库无需迁移。部署后重启后端并重新构建前端，规则包版本为 1.0.1。

- `POST /api/v1/documents` 省略 `document_type` 时默认为 `auto`；手动类型继续兼容。响应新增 `type_detection`（类型、标签、线索来源、置信度和说明）。
- 新增 `PATCH /api/v1/documents/{file_uid}`，JSON 为 `{"document_type":"auto"}` 或已有类型；仅允许上传者或管理员且具备写权限时修改。响应返回实际类型和识别信息。反向代理如限制方法，需允许 PATCH；后端已同步允许该跨域方法。
- `POST /api/v1/validations` 保留原有响应，新增 `documents`、`duplicate_files`；相同内容相同类型只判定一次，相同内容不同类型返回 HTTP 400 / code 1001，不创建预筛记录。
- 自动分类只决定当前专用规则的适用范围，不区分完整的文件层级，不提供跨文件关联结论；后续建设方案见 `Docs/DocumentSetDesign.md`。

### 5.7 整套手册迁移与发布（1.3.0）

先确认测试配置 `APP_ENV=test` 且库名以 `_codextest` 结尾。以下命令在 `backend` 目录、项目虚拟环境内执行，适用于 macOS/Ubuntu；Windows 使用 `.venv/Scripts/python.exe` 代替 `.venv/bin/python`。

```bash
./.venv/bin/python MigrateManualSuites.py --env-file ../.env.test
```

回到根目录运行隔离浏览器验证 `./backend/.venv/bin/python tests/RunE2e.py tests/e2e/ManualSuites.spec.ts`。
通过后，在后端目录运行 `./.venv/bin/python MigrateManualSuites.py`，使用既有开发 `.env`。
正式发布仅在获授权后使用正式 `.env` 和 `--allow-production` 应用同一脚本。
此脚本幂等创建 `manual_suites` 表，不修改既有业务表；新环境初始化也注册此模型。
先迁移数据库，再重启后端并构建/发布前端；发布时保留 `App/Assets/Documents/ManualLayout.docx`。
前后端与数据库仍可独立部署，沿用既有 API 地址、CORS、存储及端口环境配置。
跨域配置新增 DELETE，用于移出套册成员。回退应用时保留新表和上传原件，不删除用户档案。
套册正文快照存于 MySQL，导入原件仍依赖受限上传目录；数据库与原件需配套备份。
每套 100 份、400 万字符；ZIP 中导入原件总计上限 200 MB。规则检查与生成件适用边界见 `Docs/ManualSuites.md`。

### 5.8 ISO 13485 生成和审核规则（2.0.0）

上线时使用同一版本的前端产物和后端。后端发布包须包含 `App/Rules/core.json`、`App/Rules/Requirements/Iso13485.json` 及已有的 Word 排版资产。配置自定义规则目录时，同步更新需要启用新版的规则包。旧规则包保持原结果展示。

新版依赖已发布的草稿、文件集审核、套册表结构。此前已完成对应迁移的数据库可直接使用既有 JSON 字段，无本次新增迁移及环境配置。

- `POST /api/v1/validations` 新增可选 Form 字段 `context`，内容为 JSON。套册 `POST /api/v1/manual-suites/{uid}/inspections` 可在请求 JSON 中传同名对象。主要字段为审核范围、范围说明、基准日、适用条件、文件用途和不适用理由。
- 新版报告附带 `prescreen` 和 `assessment_status`，保留 `status` 字段。草稿和套册生成件响应增加条款依据、自检和待补信息。
- 套册保留当前检查和最近三次归档检查。详情返回历史摘要，`GET /api/v1/manual-suites/{uid}/inspections/{revision}` 可按档案修订读取检查快照。
- 在 MySQL 8.4 测试副本验证模板生成、两种审核范围、冲突结果、模拟内审及打包。核对网页规则手册显示 2.0.0。使用方式见 `tests/README.md`。

### 5.9 AI 文件阅读审核

本功能沿用网页“模型配置”中的 OpenAI 兼容服务，不新增模型环境变量、依赖或监听端口。既有数据库先在 MySQL 8.4 的 `_codextest` 副本迁移并回归；以下命令在 `backend` 目录执行，Windows 将 `.venv/bin/python` 替换为 `.venv/Scripts/python.exe`：

```bash
./.venv/bin/python MigrateAiReviews.py --env-file ../.env.test
```

从项目根目录运行 `./backend/.venv/bin/python tests/RunE2e.py tests/e2e/AiReview.spec.ts`。确认 AI 两种模式、原文行号、决定留痕、分数不变和权限隔离后，再对开发库运行 `./.venv/bin/python MigrateAiReviews.py`。正式库只可在获得发布授权后使用正式 `.env` 和 `--allow-production` 迁移。

迁移幂等创建 `ai_reviews` 与 `ai_review_decisions` 两张表；新环境由初始化导入模型后建表。回退应用时保留审阅记录，不删除数据库表。`POST /api/v1/validations/{run_uid}/ai-reviews` 创建单规则、单文件分析，`GET` 读取该任务记录，`PATCH /api/v1/ai-reviews/{review_uid}/decision` 追加人工决定。所有文件必须来自已完成任务，且受任务所有者/管理员权限约束。

已有页面出现 `Failed to fetch` 时，先检查后端日志：若 MySQL 报1146且缺少上述表，应按本节迁移对应环境，不能用修改模型地址或放宽 CORS 代替迁移。新版将此情况返回503、业务码1502及中文迁移说明；500等异常也携带允许来源的 CORS 响应头，未知来源仍无访问许可。迁移后点击“重新检查并加载记录”，不用重新执行预筛。

模型配置只允许当前数据库角色为 `admin` 的有效账号读取和修改；普通账号可以使用已启用模型，不可访问配置地址、参数或密钥。网页先复核当前账号，后端独立鉴权。AI 尚未配置或被停用时，审阅面板提示联系管理员并禁用发起；配置完成后可重新检查。模型调用失败返回502/1402，已有审阅记录和预筛结果保持。

结果接口的 `documents` 对象新增 `file_uid`，用于让用户选择本次预筛中的文件；原文件名、文件类型和其他字段保持。AI 引用需要在指定抽取片段中逐字匹配，位置仅表示抽取文本行号。AI 结果不写回预筛快照、Finding、分数或覆盖率。AI 配置及数据保留策略按现有 MySQL 和安全配置备份制度维护。

### 5.10 个人中心与管理后台

既有 MySQL 8.4 环境需先在独立 `_codextest` 副本依次运行两项迁移，再执行账户、分组和后台 E2E：

```bash
cd /srv/iso/backend
.venv/bin/python MigratePersonalFiles.py --env-file ../.env.test
.venv/bin/python MigrateAdmin.py --env-file ../.env.test
cd /srv/iso
./backend/.venv/bin/python tests/RunE2e.py tests/e2e/PersonalFiles.spec.ts tests/e2e/AccountAdmin.spec.ts
```

PowerShell 命令：先执行 Set-Location D:\iso\backend，再运行 .\.venv\Scripts\python.exe MigratePersonalFiles.py --env-file ..\.env.test 和 .\.venv\Scripts\python.exe MigrateAdmin.py --env-file ..\.env.test；然后执行 Set-Location D:\iso，再运行 .\backend\.venv\Scripts\python.exe tests/RunE2e.py tests/e2e/PersonalFiles.spec.ts tests/e2e/AccountAdmin.spec.ts。E2E 入口会自动执行幂等迁移；单独迁移命令用于验证升级流程。

测试通过后再对开发库分别执行两项迁移并重启后端、重新构建前端。正式环境只能在获发布授权后，使用正式 `.env` 并分别附加 `--allow-production`。普通用户不能访问后台接口；大模型配置仍由原网页配置存储管理，密钥不回显。访客统计使用 HttpOnly 匿名 Cookie，不保存原始 Cookie 或访客 IP；在线口径为最近5分钟内活跃，登录前后的活动归并到同一访客，统计从功能发布后开始累计。
