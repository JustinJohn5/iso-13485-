"""真实 ASGI 错误响应回归；仅注入依赖故障，不连接业务数据库。"""

import importlib
import secrets
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pymysql.err import ProgrammingError as MysqlProgrammingError
from sqlalchemy.exc import ProgrammingError


@pytest.fixture
def client(monkeypatch, tmp_path):
    from App.Config.Settings import get_settings

    values = {
        "APP_ENV": "test", "LOG_LEVEL": "ERROR", "LOG_DIR": str(tmp_path / "Logs"),
        "BACKEND_HOST": "127.0.0.1", "BACKEND_PORT": "8400", "CORS_ORIGINS": "http://frontend.test",
        "DATABASE_URL": "mysql+pymysql://synthetic:synthetic@database.invalid/asgi_codextest",
        "CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode(), "JWT_SECRET": secrets.token_urlsafe(48),
        "UPLOAD_DIR": str(tmp_path / "Uploads"),
        "RULE_SET_DIR": str(Path(__file__).resolve().parents[2] / "backend" / "App" / "Rules"),
        "EMAIL_SMTP_HOST": "", "EMAIL_SMTP_PORT": "", "EMAIL_SMTP_USERNAME": "",
        "EMAIL_SMTP_PASSWORD": "", "EMAIL_FROM_ADDRESS": "",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    import Main
    importlib.reload(Main)
    from App.Api.Dependencies import current_user
    from App.Db.Session import get_db

    api_app = getattr(Main, "api_app", Main.app)
    failure = {"error": RuntimeError("synthetic-private-detail")}

    def broken_database():
        raise failure["error"]
        yield  # 保留请求级生成器依赖的生命周期。

    api_app.dependency_overrides[get_db] = broken_database
    api_app.dependency_overrides[current_user] = lambda: SimpleNamespace(id=1, role="auditor")
    try:
        with TestClient(Main.app, raise_server_exceptions=False) as browser:
            yield browser, failure
    finally:
        api_app.dependency_overrides.clear()
        get_settings.cache_clear()


@pytest.mark.parametrize("table", ["ai_reviews", "ai_review_decisions"])
def test_missing_migration_has_actionable_json_and_cors(client, table):
    browser, failure = client
    failure["error"] = ProgrammingError(
        "synthetic SQL", {}, MysqlProgrammingError(1146, f"Table 'synthetic.{table}' doesn't exist")
    )
    response = browser.get("/api/v1/validations/task/ai-reviews", headers={"Origin": "http://frontend.test"})
    assert response.status_code == 503
    assert response.json()["code"] == 1502
    assert "迁移" in response.json()["message"]
    assert response.headers["access-control-allow-origin"] == "http://frontend.test"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "synthetic" not in response.text


@pytest.mark.parametrize("origin", ["http://frontend.test", "http://untrusted.test"])
def test_unexpected_errors_keep_json_without_leaking_details_and_respect_cors(client, origin):
    browser, _ = client
    response = browser.get("/api/v1/validations/task/ai-reviews", headers={"Origin": origin})
    assert response.status_code == 500
    assert response.json()["code"] == 1004
    assert "synthetic-private-detail" not in response.text
    assert response.headers.get("access-control-allow-origin") == (
        "http://frontend.test" if origin == "http://frontend.test" else None
    )
