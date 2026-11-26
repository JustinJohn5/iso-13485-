"""管理员审计接口不返回自由文本详情。"""

from datetime import datetime
from types import SimpleNamespace

import pytest


class _Result:
    def __init__(self, *, count=None, rows=None):
        self._count = count
        self._rows = rows

    def scalar_one(self):
        return self._count

    def all(self):
        return self._rows


class _Session:
    def __init__(self, log):
        self.log = log
        self.calls = 0

    def execute(self, _statement):
        self.calls += 1
        if self.calls == 1:
            return _Result(count=1)
        return _Result(rows=[(self.log, '管理员')])


@pytest.mark.parametrize('detail', [
    'revision=3;reason=用户填写的变更原因',
    '正文包含内部流程和个人信息',
    'api_key=不得出现在后台响应',
])
def test_admin_audit_endpoint_hides_unstructured_details(detail):
    from App.Api.Admin import get_audit_logs

    log = SimpleNamespace(id=1, user_id=1, action='suite_update', target_type='manual_suite',
                          target_id='suite-1', detail=detail, created_at=datetime(2026, 11, 26))
    response = get_audit_logs(page=1, page_size=20, db=_Session(log))
    returned = response['data']['items'][0]['detail']

    assert returned == '详情已省略'
    assert detail not in str(response)


def test_admin_audit_endpoint_preserves_known_fixed_authentication_details():
    from App.Api.Admin import get_audit_logs

    log = SimpleNamespace(id=1, user_id=1, action='user_login', target_type='user',
                          target_id='1', detail='账号登录成功', created_at=datetime(2026, 11, 26))
    response = get_audit_logs(page=1, page_size=20, db=_Session(log))

    assert response['data']['items'][0]['detail'] == '账号登录成功'
