"""认证成功及退出时记录审计，并解除访客身份关联。"""

from types import SimpleNamespace

from fastapi import Response
from starlette.requests import Request


class _Session:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


def test_successful_login_updates_last_seen_and_adds_safe_audit(monkeypatch):
    from App.Api import Auth

    user = SimpleNamespace(id=9, email='tester@example.com', display_name='测试员', role='admin',
                           is_active=True, token_version=1, last_login_at=None, password_hash='hash')
    records = []
    session = _Session()
    monkeypatch.setattr(Auth.UserDao, 'get_by_email', lambda db, email: user)
    monkeypatch.setattr(Auth, 'verify_password', lambda password, saved: True)
    monkeypatch.setattr(Auth, 'create_access_token', lambda *args: ('synthetic-token', 3600))
    monkeypatch.setattr(Auth, '_client_ip', lambda request: '192.0.2.9')
    monkeypatch.setattr(Auth, 'AuditLogDao', SimpleNamespace(add=lambda db, **event: records.append(event)),
                        raising=False)

    result = Auth.login(Auth.LoginRequest(email=user.email, password='synthetic-password'), Response(), session)

    assert result['data']['id'] == user.id
    assert user.last_login_at is not None
    assert [(record['action'], record['target_id']) for record in records] == [('user_login', '9')]
    assert 'synthetic-password' not in str(records)
    assert session.commits == 1


def test_logout_unlinks_current_visitor_and_records_user(monkeypatch):
    from App.Api import Auth
    user = SimpleNamespace(id=9, token_version=3, is_active=True)
    request = Request({
        'type': 'http', 'http_version': '1.1', 'method': 'POST', 'scheme': 'http',
        'server': ('testserver', 80), 'client': ('127.0.0.1', 1234), 'root_path': '',
        'path': '/api/v1/auth/logout', 'query_string': b'',
        'headers': [(b'cookie', b'iso_access_token=synthetic; iso_visitor=' + b'a' * 43)],
    })
    records, cleared = [], []
    session = _Session()
    monkeypatch.setattr(Auth, 'decode_access_token', lambda token: {'sub': '9', 'ver': 3})
    monkeypatch.setattr(Auth.UserDao, 'get_by_id', lambda db, user_id: user)
    monkeypatch.setattr(Auth, '_client_ip', lambda request: '192.0.2.9')
    monkeypatch.setattr(Auth, 'clear_visitor_identity', lambda request, db: cleared.append((request, db)),
                        raising=False)
    monkeypatch.setattr(Auth, 'AuditLogDao', SimpleNamespace(add=lambda db, **event: records.append(event)),
                        raising=False)

    Auth.logout(request, Response(), session)

    assert cleared == [(request, session)]
    assert [(record['action'], record['target_id']) for record in records] == [('user_logout', '9')]
    assert session.commits == 1


def test_logout_does_not_attribute_revoked_session(monkeypatch):
    from App.Api import Auth
    from App.Utils.Errors import ApiError

    request = Request({
        'type': 'http', 'http_version': '1.1', 'method': 'POST', 'scheme': 'http',
        'server': ('testserver', 80), 'client': ('127.0.0.1', 1234), 'root_path': '',
        'path': '/api/v1/auth/logout', 'query_string': b'',
        'headers': [(b'cookie', b'iso_access_token=revoked; iso_visitor=' + b'a' * 43)],
    })
    user = SimpleNamespace(id=9, token_version=4, is_active=True)
    monkeypatch.setattr(Auth, 'decode_access_token', lambda token: {'sub': '9', 'ver': 3})
    monkeypatch.setattr(Auth.UserDao, 'get_by_id', lambda db, user_id: user)
    monkeypatch.setattr(Auth, '_client_ip', lambda request: 'unknown')
    events, cleared = [], []
    monkeypatch.setattr(Auth, 'clear_visitor_identity', lambda request, db: cleared.append(True), raising=False)
    monkeypatch.setattr(Auth, 'AuditLogDao', SimpleNamespace(add=lambda db, **event: events.append(event)),
                        raising=False)

    Auth.logout(request, Response(), _Session())

    assert cleared == [True]
    assert events == []
