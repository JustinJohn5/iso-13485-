"""个人中心与管理后台的 API 路由必须由实际应用公开。"""


def test_application_registers_personal_files_visitor_and_admin_endpoints():
    import Main
    from fastapi.testclient import TestClient

    with TestClient(Main.app) as browser:
        paths = set(browser.get("/openapi.json").json()["paths"])
    assert {
        "/api/v1/my/files",
        "/api/v1/my/files/selection",
        "/api/v1/my/file-groups",
        "/api/v1/visits",
        "/api/v1/admin/overview",
        "/api/v1/admin/visitors",
        "/api/v1/admin/logs",
        "/api/v1/admin/audit-logs",
    } <= paths


def test_group_error_codes_are_registered():
    from App.Utils.Errors import ERROR_DEFINITIONS

    assert ERROR_DEFINITIONS[1207] == ("文件分组不存在", 404)
    assert ERROR_DEFINITIONS[1208] == ("相同名称的文件分组已存在", 409)
