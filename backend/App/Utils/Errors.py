"""业务错误码与统一异常。

错误码按模块分段（见 AGENTS.md 5.1）：
- 1xxx 通用
- 11xx 认证与权限
- 12xx 文件
- 13xx 规则与校验任务
- 14xx 大模型配置
- 15xx 基础设施
"""

from __future__ import annotations

from typing import Any

ERROR_DEFINITIONS: dict[int, tuple[str, int]] = {
    # 通用
    1001: ("参数校验失败", 400),
    1002: ("资源不存在", 404),
    1003: ("操作不被允许", 403),
    1004: ("服务器内部错误", 500),
    # 认证与权限
    1101: ("邮箱或密码错误", 401),
    1102: ("账号已被临时锁定，请稍后再试", 423),
    1103: ("登录状态已失效，请重新登录", 401),
    1104: ("当前账号无权执行该操作", 403),
    1105: ("新密码不符合安全要求", 400),
    1106: ("账号已被禁用", 403),
    # 文件
    1201: ("不支持的文件类型", 400),
    1202: ("文件超出大小限制", 413),
    1203: ("文件不存在或已被删除", 404),
    1204: ("文件内容解析失败", 422),
    1205: ("文件为空或内容不足", 400),
    1206: ("文件校验失败（扩展名与内容不一致）", 400),
    # 规则与校验任务
    1301: ("规则包不存在", 404),
    1302: ("校验任务不存在", 404),
    1303: ("校验任务尚未完成，请稍后再试", 409),
    1304: ("校验任务执行失败", 500),
    1305: ("规则包内容不合法", 500),
    # 大模型配置
    1401: ("大模型尚未配置，请先在配置页完成配置", 409),
    1402: ("大模型调用失败", 502),
    1403: ("大模型配置解密失败，请重新填写 API Key", 500),
    # 基础设施
    1501: ("数据库操作失败", 500),
}


class ApiError(Exception):
    """业务异常：由异常中间件统一转换为 {code, message, data} 响应。"""

    def __init__(
        self,
        code: int,
        message: str | None = None,
        *,
        data: Any = None,
        http_status: int | None = None,
    ) -> None:
        default_message, default_status = ERROR_DEFINITIONS.get(code, ("未知错误", 500))
        self.code = code
        self.message = message or default_message
        self.data = data
        self.http_status = http_status or default_status
        super().__init__(self.message)


def param_error(message: str = "参数校验失败", *, data: Any = None) -> ApiError:
    """构造参数错误。"""
    return ApiError(1001, message, data=data)
