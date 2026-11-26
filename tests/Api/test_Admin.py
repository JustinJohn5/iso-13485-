"""后台路由必须在触及数据和日志前鉴权。"""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient


@pytest.mark.parametrize('path', ['/overview', '/visitors', '/logs?source=../secret', '/audit-logs'])
def test_non_admin_cannot_read_any_admin_endpoint(path):
    from App.Api.Admin import router
    from App.Api.Dependencies import current_user
    from App.Db.Session import get_db
    from App.Utils.Errors import ApiError

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[current_user] = lambda: SimpleNamespace(id=1, role='viewer')
    app.dependency_overrides[get_db] = lambda: None

    @app.exception_handler(ApiError)
    async def denied(_, exc):
        return JSONResponse({'code': exc.code, 'message': exc.message}, status_code=exc.http_status)

    with TestClient(app) as client:
        response = client.get('/api/v1/admin' + path)
    assert response.status_code == 403
    assert response.json()['code'] == 1104


def test_visit_payload_rejects_identity_queries_and_unknown_pages():
    from App.Api.Visits import VisitRequest
    from pydantic import ValidationError

    for payload in ({'page': '/?email=private', 'event': 'pageview'},
                    {'page': '/', 'event': 'pageview', 'user_id': 1},
                    {'page': '/', 'event': 'unknown'}):
        with pytest.raises(ValidationError):
            VisitRequest(**payload)
