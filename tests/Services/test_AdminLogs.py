"""后台日志读取边界与秘密脱敏回归。"""
from pathlib import Path

import pytest


def test_authorization_and_structured_secrets_are_redacted():
    from App.Services.AdminLogs import redact

    assert redact('Authorization: Bearer abc.def.ghi') == 'Authorization: [已脱敏]'
    text = ('api_key="secret-key" password=hunter2 token=tok Cookie: private-cookie '
            'mysql+pymysql://user:dsnsecret@host/db')
    result = redact(text)
    for secret in ('secret-key', 'hunter2', 'tok ', 'private-cookie', 'dsnsecret'):
        assert secret not in result
    assert '[已脱敏]' in result


@pytest.mark.parametrize('source', ['../App.log', 'App.log', 'app/../../secret', 'error.log', ''])
def test_log_sources_reject_arbitrary_paths(tmp_path, source):
    from App.Services.AdminLogs import read_logs
    from App.Utils.Errors import ApiError

    with pytest.raises(ApiError) as error:
        read_logs(tmp_path, source=source)
    assert error.value.http_status == 400


def test_tail_is_bounded_and_filters_after_redaction(tmp_path):
    from App.Services.AdminLogs import read_logs

    path = tmp_path / 'App.log'
    path.write_text(''.join(f'2026-11-26 12:00:00 | INFO | rid=abc | row={i}\n' for i in range(1200))
                    + '2026-11-26 12:00:00 | ERROR | rid=xyz | api_key=private\n', encoding='utf-8')
    result = read_logs(tmp_path, source='app', level='ERROR', request_id='xyz', date='2026-11-26')
    assert len(result['lines']) == 1
    assert 'private' not in result['lines'][0]
    assert result['truncated'] is True
    assert read_logs(tmp_path, source='app', keyword='private')['lines'] == []


def test_rotation_reading_rejects_symlinks_and_ignores_uncontrolled_files(tmp_path):
    from App.Services.AdminLogs import read_logs
    from App.Utils.Errors import ApiError

    (tmp_path / 'App.log').write_text('2026-11-26 | INFO | current\n', encoding='utf-8')
    (tmp_path / 'App.log.2026-11-25').write_text('2026-11-25 | INFO | rotated\n', encoding='utf-8')
    (tmp_path / 'App.log.secret').write_text('UNCONTROLLED', encoding='utf-8')
    result = read_logs(tmp_path, source='app', date='2026-11-25')
    assert len(result['lines']) == 1 and 'rotated' in result['lines'][0]
    outside = tmp_path.parent / f'{tmp_path.name}-outside.log'
    outside.write_text('SECRET', encoding='utf-8')
    link = tmp_path / 'Error.log'
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip('当前 Windows 账户未获符号链接权限')
    with pytest.raises(ApiError):
        read_logs(tmp_path, source='error')


def test_missing_log_has_chinese_error(tmp_path):
    from App.Services.AdminLogs import read_logs
    from App.Utils.Errors import ApiError

    with pytest.raises(ApiError, match='日志'):
        read_logs(tmp_path, source='error')
