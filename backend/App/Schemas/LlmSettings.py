"""管理员维护的 OpenAI 兼容配置，不接受额外字段。"""
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from App.Constants.AuthoringLimits import MAX_INSTRUCTIONS_CHARS, MAX_OUTPUT_TOKENS, MAX_TIMEOUT_SECONDS


class LlmSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool
    base_url: str = Field(min_length=8, max_length=255)
    model: str = Field(min_length=1, max_length=128)
    api_key: str | None = Field(default=None, max_length=256)
    timeout_seconds: int = Field(ge=5, le=MAX_TIMEOUT_SECONDS)
    max_tokens: int = Field(ge=256, le=MAX_OUTPUT_TOKENS)
    temperature: float = Field(ge=0, le=2)

    @field_validator('base_url')
    @classmethod
    def url_valid(cls, value):
        value = value.strip().rstrip('/')
        parts = urlsplit(value)
        if parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError('服务地址须为不含凭据、查询参数或片段的 HTTP(S) URL')
        try:
            parts.port
        except ValueError as exc:
            raise ValueError('服务端口非法') from exc
        return value

    @field_validator('model')
    @classmethod
    def model_valid(cls, value):
        value = value.strip()
        if not value or any(ord(char) < 32 for char in value):
            raise ValueError('模型名称非法')
        return value

    @field_validator('api_key')
    @classmethod
    def key_valid(cls, value):
        if value is None or value == '':
            return None
        if not value.strip() or any(ord(char) < 33 for char in value):
            raise ValueError('API Key 不得为空白或含控制字符')
        return value


class AiDraftRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=1)
    instructions: str = Field(min_length=5, max_length=MAX_INSTRUCTIONS_CHARS)

    @field_validator('instructions')
    @classmethod
    def instructions_valid(cls, value):
        if len(value.strip()) < 5:
            raise ValueError('编写要求至少5字')
        return value.strip()
