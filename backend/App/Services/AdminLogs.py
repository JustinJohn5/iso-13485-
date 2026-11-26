"""后台只读日志：固定来源、有界尾读取、受控轮转及统一脱敏。"""
from __future__ import annotations

from datetime import date as calendar_date
import os
from pathlib import Path
import re
import stat

from App.Utils.Errors import ApiError, param_error

MAX_BYTES = 256 * 1024
MAX_LINES = 500
MAX_FILES = 31
SOURCES = {'app': 'App.log', 'error': 'Error.log'}
LEVELS = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
_MASK = '[已脱敏]'
_SECRET_KEYS = (
    r'authorization|proxy-authorization|cookie|set-cookie|api[_-]?key|access[_-]?token|'
    r'refresh[_-]?token|token|password|passwd|pwd|jwt[_-]?secret|config[_-]?encryption[_-]?key|'
    r'database[_-]?url|connection[_-]?string|secret|client[_-]?secret|'
    r'prompt|body|document[_-]?text|extracted[_-]?text|content'
)
_SECRET_VALUE = re.compile(
    rf'''(?i)((?:["']?)(?:{_SECRET_KEYS})(?:["']?)\s*[:=]\s*)'''
    r'''("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,;}&]+)'''
)
_HEADERS = re.compile(r'(?i)\b(Authorization|Proxy-Authorization|Cookie|Set-Cookie)(\s*:\s*)[^\r\n]*')
_DSN = re.compile(r'(?i)\b(?:mysql(?:\+[a-z0-9_]+)?|postgres(?:ql)?|redis|mongodb(?:\+srv)?)://[^\s<>"\']+')
_BEARER = re.compile(r'(?i)\bBearer\s+[^\s,;"\']+')
_JWT = re.compile(r'\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b')

_AUDIT_DETAILS = {
    'user_login': '账号登录成功',
    'user_logout': '账号退出登录成功',
    'user_password_change': '账号密码修改成功',
    'user_register': '普通使用账号注册成功',
    'llm_settings_update': '配置保存成功；敏感值不记录',
    'draft_ai_failed': 'AI 编写失败，原草稿未修改',
    'file_group_create': '已创建文件分组',
    'file_group_rename': '已重命名文件分组',
    'file_group_delete': '已删除文件分组',
    'file_group_add': '已批量加入文件',
    'file_group_remove': '已批量移出文件',
    'suite_create': '已创建手册套册',
    'suite_export': '已导出手册套册',
    'draft_create': '已创建草稿',
    'draft_update': '草稿已修订',
    'draft_export': '已导出草稿',
    'draft_batch_update': '已批量修订草稿',
    'review_create': '已创建文件集审查',
    'review_confirm': '已确认文件集依据',
    'ai_review_failed': 'AI 文件审阅失败',
    'ai_review_create': '已生成 AI 文件审阅候选',
    'ai_review_decision': '已记录人工审阅决定',
    'audit_report_export': '已导出审计报告',
    'personal_file_download': '已下载个人文件',
}


def safe_audit_detail(action: str, _detail: str) -> str:
    """审计详情只返回按动作登记的固定说明，不回传用户输入内容。"""
    return _AUDIT_DETAILS.get(action, '详情已省略')


def redact(value: str) -> str:
    """先消除凭据，再进行筛选，避免以关键词探测秘密。"""
    value = _HEADERS.sub(lambda match: match[1] + match[2] + _MASK, value)
    value = _SECRET_VALUE.sub(lambda match: match[1] + _MASK, value)
    value = _DSN.sub(_MASK, value)
    value = _BEARER.sub('Bearer ' + _MASK, value)
    return _JWT.sub(_MASK, value)


def _validate_filters(level: str, keyword: str, request_id: str, date: str) -> str:
    level = level.upper()
    if level and level not in LEVELS:
        raise param_error('日志级别不正确')
    if len(keyword) > 200 or len(request_id) > 128 or any('\n' in item or '\r' in item for item in (keyword, request_id)):
        raise param_error('日志筛选条件超长或包含换行符')
    if date:
        try:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date):
                raise ValueError
            calendar_date.fromisoformat(date)
        except ValueError as exc:
            raise param_error('日志日期须为有效的 YYYY-MM-DD') from exc
    return level


def _safe_directory(directory: Path) -> Path:
    directory = directory.absolute()
    if any(path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction())
           for path in (directory, *directory.parents)):
        raise ApiError(1003, '日志目录不允许使用符号链接')
    if not directory.is_dir():
        raise ApiError(1002, '日志目录不可用')
    return directory.resolve()


def _tail(path: Path, budget: int) -> tuple[list[str], int, bool]:
    """Linux/macOS 用 O_NOFOLLOW，Windows 再比较打开前后的文件身份。"""
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or path.is_symlink():
        raise ApiError(1003, '日志文件不允许使用符号链接或特殊文件')
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0))
    with os.fdopen(descriptor, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino) or not stat.S_ISREG(opened.st_mode):
            raise ApiError(1003, '日志文件在读取前已改变，请重试')
        offset = max(0, opened.st_size - budget)
        stream.seek(offset)
        content = stream.read(budget)
    if offset:
        content = content.split(b'\n', 1)[1] if b'\n' in content else b''
    return content.decode('utf-8', errors='replace').splitlines(), min(opened.st_size, budget), bool(offset)


def read_logs(directory: Path, *, source: str = 'app', level: str = '', keyword: str = '',
              request_id: str = '', date: str = '') -> dict:
    if source not in SOURCES:
        raise param_error('日志来源仅允许 app 或 error')
    level = _validate_filters(level, keyword, request_id, date)
    try:
        root = _safe_directory(Path(directory))
        name = SOURCES[source]
        pattern = re.compile(re.escape(name) + r'(?:\.\d{4}-\d{2}-\d{2})?')
        paths = sorted((path for path in root.iterdir() if pattern.fullmatch(path.name)),
                       key=lambda path: (path.name == name, path.name), reverse=True)
        if not paths:
            raise ApiError(1002, '所选日志文件尚未生成或不可用')
        truncated = len(paths) > MAX_FILES
        lines: list[str] = []
        budget = MAX_BYTES
        for path in paths[:MAX_FILES]:
            if budget <= 0:
                truncated = True
                break
            chunk, used, limited = _tail(path, budget)
            budget -= used
            truncated = truncated or limited
            # 全局先限制行数，不能因筛选未命中而无限读取历史。
            room = MAX_LINES - len(lines)
            if len(chunk) > room:
                truncated = True
            lines = chunk[-room:] + lines if room else lines
            if len(lines) >= MAX_LINES:
                truncated = truncated or path != paths[-1]
                break
        safe_lines = [redact(line) for line in lines]
        safe_lines = [line for line in safe_lines
                      if (not level or re.search(r'\|\s*' + level + r'\s*\|', line))
                      and (not keyword or keyword.casefold() in line.casefold())
                      and (not request_id or re.search(r'\brid=' + re.escape(request_id) + r'(?=\s|\||$)', line))
                      and (not date or line.startswith(date))]
        return {'lines': safe_lines, 'truncated': bool(truncated), 'source': source}
    except ApiError:
        raise
    except (OSError, ValueError) as exc:
        raise ApiError(1004, '日志文件读取失败，请检查服务端日志目录权限') from exc
