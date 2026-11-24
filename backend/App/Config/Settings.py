"""应用配置。

所有部署配置从环境变量（backend/.env）读取，严禁硬编码；
启动时校验必需字段与格式，缺失或非法立即抛出中文错误并退出。
"""

from __future__ import annotations

import base64
from ipaddress import ip_network
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import EmailStr, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend 目录（App/Config/Settings.py 向上两级）
BACKEND_DIR = Path(__file__).resolve().parents[2]

_PLACEHOLDER_TOKENS = ("请替换", "example", "change-me", "changeme", "your-")
_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class SettingsError(RuntimeError):
    """配置错误：中文提示，直接终止启动。"""


class Settings(BaseSettings):
    """后端运行配置。

    - 字段名小写，环境变量名大写（alias）。
    - 敏感项不提供任何默认值，缺失即启动失败。
    """

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
        case_sensitive=False,
    )

    # ---------- 运行环境 ----------
    app_env: Literal["dev", "test", "prod"] = Field(alias="APP_ENV")
    log_level: str = Field(alias="LOG_LEVEL")
    log_dir: Path = Field(alias="LOG_DIR")

    # ---------- 服务端口 ----------
    backend_host: str = Field(alias="BACKEND_HOST")
    backend_port: int = Field(alias="BACKEND_PORT")
    frontend_port: int | None = Field(default=None, alias="FRONTEND_PORT")
    cors_origins: str = Field(alias="CORS_ORIGINS")

    # ---------- 数据库 ----------
    database_url: str = Field(alias="DATABASE_URL")
    database_pool_size: int = Field(default=10, alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=20, alias="DATABASE_MAX_OVERFLOW")

    # ---------- 密钥 ----------
    config_encryption_key: str = Field(alias="CONFIG_ENCRYPTION_KEY")
    jwt_secret: str = Field(alias="JWT_SECRET")
    jwt_expire_minutes: int = Field(default=480, alias="JWT_EXPIRE_MINUTES")

    # ---------- 邮箱验证码 ----------
    email_smtp_host: str | None = Field(default=None, alias="EMAIL_SMTP_HOST")
    email_smtp_port: int | None = Field(default=None, alias="EMAIL_SMTP_PORT")
    email_smtp_username: str | None = Field(default=None, alias="EMAIL_SMTP_USERNAME")
    email_smtp_password: str | None = Field(default=None, alias="EMAIL_SMTP_PASSWORD", repr=False)
    email_from_address: EmailStr | None = Field(default=None, alias="EMAIL_FROM_ADDRESS")
    email_smtp_starttls: bool = Field(default=True, alias="EMAIL_SMTP_STARTTLS")
    email_smtp_ssl: bool = Field(default=False, alias="EMAIL_SMTP_SSL")
    email_smtp_timeout_seconds: int = Field(default=10, alias="EMAIL_SMTP_TIMEOUT_SECONDS")
    trusted_proxy_cidrs: str = Field(default="", alias="TRUSTED_PROXY_CIDRS")

    # ---------- 文件与规则 ----------
    upload_dir: Path = Field(alias="UPLOAD_DIR")
    max_upload_size_mb: int = Field(default=40, alias="MAX_UPLOAD_SIZE_MB")
    rule_set_dir: Path = Field(alias="RULE_SET_DIR")

    # ---------- 认证 ----------
    access_token_cookie_name: str = Field(
        default="iso_access_token", alias="ACCESS_TOKEN_COOKIE_NAME"
    )

    # ---------- 派生属性 ----------
    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def access_token_ttl_seconds(self) -> int:
        return self.jwt_expire_minutes * 60

    @property
    def email_smtp_configured(self) -> bool:
        return all((self.email_smtp_host, self.email_smtp_port, self.email_smtp_username,
                    self.email_smtp_password, self.email_from_address))

    # ---------- 校验 ----------
    @field_validator("email_smtp_host", "email_smtp_username", "email_from_address", mode="before")
    @classmethod
    def _normalize_smtp_field(cls, value):
        if isinstance(value, str):
            cleaned = value.strip()
            if "\r" in cleaned or "\n" in cleaned:
                raise ValueError("邮件配置不能包含换行符")
            return cleaned or None
        return value

    @field_validator("email_smtp_password", "email_smtp_port", mode="before")
    @classmethod
    def _empty_smtp_field(cls, value):
        return None if value == "" else value

    @field_validator("backend_port", "frontend_port")
    @classmethod
    def _check_port(cls, value: int | None) -> int | None:
        if value is None:
            return value
        if not 1 <= int(value) <= 65535:
            raise ValueError("端口必须是 1~65535 之间的整数")
        return int(value)

    @field_validator("log_level")
    @classmethod
    def _check_log_level(cls, value: str) -> str:
        level = value.strip().upper()
        if level not in _VALID_LOG_LEVELS:
            raise ValueError(f"LOG_LEVEL 必须是 {sorted(_VALID_LOG_LEVELS)} 之一")
        return level

    @field_validator("database_url")
    @classmethod
    def _check_database_url(cls, value: str) -> str:
        if not value.startswith("mysql+pymysql://"):
            raise ValueError("DATABASE_URL 必须以 mysql+pymysql:// 开头（项目唯一数据库为 MySQL 8.4）")
        return value

    @field_validator("config_encryption_key")
    @classmethod
    def _check_encryption_key(cls, value: str) -> str:
        raw = value.strip()
        if any(token in raw for token in _PLACEHOLDER_TOKENS):
            raise ValueError("CONFIG_ENCRYPTION_KEY 仍是示例占位值，请在 .env 中填入真实密钥")
        try:
            decoded = base64.urlsafe_b64decode(raw.encode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - 统一转成配置错误
            raise ValueError("CONFIG_ENCRYPTION_KEY 必须是 urlsafe base64 字符串") from exc
        if len(decoded) != 32:
            raise ValueError("CONFIG_ENCRYPTION_KEY 解码后必须是 32 字节（Fernet 密钥）")
        return raw

    @field_validator("jwt_secret")
    @classmethod
    def _check_jwt_secret(cls, value: str) -> str:
        raw = value.strip()
        if any(token in raw for token in _PLACEHOLDER_TOKENS):
            raise ValueError("JWT_SECRET 仍是示例占位值，请在 .env 中填入真实密钥")
        if len(raw) < 32:
            raise ValueError("JWT_SECRET 长度不足 32 位，请使用随机密钥")
        return raw

    @field_validator("jwt_expire_minutes")
    @classmethod
    def _check_expire(cls, value: int) -> int:
        if not 5 <= int(value) <= 60 * 24 * 30:
            raise ValueError("JWT_EXPIRE_MINUTES 必须在 5~43200 分钟之间")
        return int(value)

    @field_validator("email_smtp_port")
    @classmethod
    def _check_smtp_port(cls, value: int | None) -> int | None:
        if value is not None and not 1 <= int(value) <= 65535:
            raise ValueError("EMAIL_SMTP_PORT 必须是 1~65535 之间的整数")
        return value

    @field_validator("email_smtp_timeout_seconds")
    @classmethod
    def _check_smtp_timeout(cls, value: int) -> int:
        if not 1 <= int(value) <= 30:
            raise ValueError("EMAIL_SMTP_TIMEOUT_SECONDS 必须在 1~30 秒之间")
        return int(value)

    @field_validator("trusted_proxy_cidrs")
    @classmethod
    def _check_trusted_proxy_cidrs(cls, value: str) -> str:
        cidrs = [item.strip() for item in value.split(",") if item.strip()]
        try:
            for cidr in cidrs:
                ip_network(cidr, strict=False)
        except ValueError as exc:
            raise ValueError("TRUSTED_PROXY_CIDRS 只能包含有效的 IP 地址或 CIDR 网段") from exc
        return ",".join(cidrs)

    @field_validator("max_upload_size_mb")
    @classmethod
    def _check_upload_size(cls, value: int) -> int:
        if not 1 <= int(value) <= 500:
            raise ValueError("MAX_UPLOAD_SIZE_MB 必须在 1~500 之间")
        return int(value)

    @field_validator("cors_origins")
    @classmethod
    def _check_cors(cls, value: str) -> str:
        origins = [item.strip() for item in value.split(",") if item.strip()]
        if not origins:
            raise ValueError("CORS_ORIGINS 不能为空，至少包含一个前端来源")
        for origin in origins:
            if not origin.startswith(("http://", "https://")):
                raise ValueError(f"CORS_ORIGINS 中的来源必须以 http(s):// 开头：{origin}")
        return ",".join(origins)

    @field_validator("upload_dir", "log_dir", "rule_set_dir")
    @classmethod
    def _resolve_path(cls, value: Path) -> Path:
        path = value if value.is_absolute() else (BACKEND_DIR / value)
        return path.resolve()

    @model_validator(mode="after")
    def _check_dirs(self) -> "Settings":
        smtp_fields = (self.email_smtp_host, self.email_smtp_port, self.email_smtp_username,
                       self.email_smtp_password, self.email_from_address)
        if any(smtp_fields) and not all(smtp_fields):
            raise ValueError("邮件配置不完整，请填写 EMAIL_SMTP_HOST、PORT、USERNAME、PASSWORD 和 EMAIL_FROM_ADDRESS")
        if self.email_smtp_ssl and self.email_smtp_starttls:
            raise ValueError("EMAIL_SMTP_SSL 与 EMAIL_SMTP_STARTTLS 不能同时启用")
        if self.email_smtp_configured and not (self.email_smtp_ssl or self.email_smtp_starttls):
            raise ValueError("SMTP 邮件必须启用 SSL 或 STARTTLS 加密")
        if not self.rule_set_dir.exists():
            raise ValueError(f"规则包目录不存在：{self.rule_set_dir}")
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """读取并缓存配置；任何非法配置都以中文异常抛出。"""
    try:
        return Settings()  # type: ignore[call-arg]
    except Exception as exc:  # noqa: BLE001 - 统一包装为启动错误
        raise SettingsError(f"环境变量配置有误，请检查 backend/.env：{exc}") from exc
