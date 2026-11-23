"""读取隔离环境配置，启动测试服务，运行 Playwright 并清理本次数据。"""
from __future__ import annotations

import logging
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def main() -> int:
    config_path = ROOT / '.env.test'
    if not config_path.exists():
        raise SystemExit('请先按 .env.test.example 创建项目根目录 .env.test')
    config = {key: value for key, value in dotenv_values(config_path).items() if value is not None}
    os.environ.update(config)
    from sqlalchemy import delete, select, text
    from sqlalchemy.engine import make_url
    from App.Config.Settings import get_settings
    from App.Db.Session import get_engine, session_scope
    from App.Models.Finding import Finding
    from App.Models.UploadedFile import UploadedFile
    from App.Models.User import ROLE_ADMIN, User
    from App.Models.ValidationDocument import ValidationDocument
    from App.Models.ValidationRun import ValidationRun
    from App.Utils.Security import hash_password

    settings = get_settings()
    database = make_url(settings.database_url).database or ''
    if settings.app_env != 'test' or not database.endswith('_codextest'):
        raise SystemExit('E2E 只允许使用 APP_ENV=test 和 _codextest 数据库')
    if ROOT / '.local' not in settings.upload_dir.parents:
        raise SystemExit('E2E 上传目录必须位于本项目 .local 内')
    for name in ('BACKEND_PORT', 'FRONTEND_PORT'):
        with socket.socket() as probe:
            if probe.connect_ex((settings.backend_host, int(config[name]))) == 0:
                raise SystemExit(f'{name} 端口被占用，请确认后处理')
    with get_engine().connect() as connection:
        version = connection.execute(text('SELECT VERSION()')).scalar_one()
        if not version.startswith('8.4.'):
            raise SystemExit('测试数据库必须为 MySQL 8.4')

    email = f'e2e-{secrets.token_hex(6)}@example.com'
    password = secrets.token_urlsafe(24)
    with session_scope() as db:
        user = User(email=email, display_name='自动化测试账号', password_hash=hash_password(password), role=ROLE_ADMIN)
        db.add(user)
        db.flush()
        user_id = user.id
    env = {**os.environ, 'E2E_EMAIL': email, 'E2E_PASSWORD': password, 'E2E_PYTHON': sys.executable}
    node = shutil.which('node')
    if not node:
        raise SystemExit('缺少项目要求的 Node.js')
    processes: list[subprocess.Popen] = []
    log_dir = ROOT / '.local' / 'E2eLogs'
    log_dir.mkdir(parents=True, exist_ok=True)
    logs = []
    try:
        commands = [([sys.executable, 'Run.py'], ROOT / 'backend'),
                    ([node, 'node_modules/vite/bin/vite.js', '--host', settings.backend_host, '--mode', 'test'], ROOT / 'frontend')]
        for index, (command, cwd) in enumerate(commands):
            output = (log_dir / f'service-{index}.log').open('w', encoding='utf-8')
            logs.append(output)
            processes.append(subprocess.Popen(command, cwd=cwd, env=env, stdout=output, stderr=output))
        for url in (config['E2E_API_BASE_URL'] + '/api/v1/health', config['E2E_BASE_URL']):
            deadline = time.monotonic() + 25
            while True:
                try:
                    with urlopen(url, timeout=2) as response:
                        if response.status == 200:
                            break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError('测试服务启动失败，请查看 .local/E2eLogs')
                    time.sleep(0.2)
        logger.info('隔离测试服务已就绪，开始 Playwright 验证')
        result = subprocess.run([node, 'node_modules/@playwright/test/cli.js', 'test', *sys.argv[1:]], cwd=ROOT, env=env)
        return result.returncode
    finally:
        for process in reversed(processes):
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        for output in logs:
            output.close()
        with session_scope() as db:
            run_ids = select(ValidationRun.id).where(ValidationRun.created_by == user_id)
            db.execute(delete(Finding).where(Finding.run_id.in_(run_ids)))
            db.execute(delete(ValidationDocument).where(ValidationDocument.run_id.in_(run_ids)))
            db.execute(delete(ValidationRun).where(ValidationRun.created_by == user_id))
            names = db.execute(select(UploadedFile.stored_name).where(UploadedFile.uploaded_by == user_id)).scalars().all()
            db.execute(delete(UploadedFile).where(UploadedFile.uploaded_by == user_id))
            db.execute(delete(User).where(User.id == user_id))
        for name in names:
            path = (settings.upload_dir / name).resolve()
            if path.parent == settings.upload_dir:
                path.unlink(missing_ok=True)
        logger.info('已停止测试服务并清理本次测试账号、记录和上传文件')


if __name__ == '__main__':
    raise SystemExit(main())
