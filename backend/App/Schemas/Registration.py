"""公开注册字段；角色、账号状态等由服务端决定。"""
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator, model_validator

from App.Utils.Errors import ApiError
from App.Utils.Security import validate_password_policy


class RegistrationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    email: EmailStr = Field(max_length=190)
    email_verification_code: str = Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")
    display_name: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=8, max_length=72)
    password_confirmation: SecretStr = Field(min_length=8, max_length=72)

    @field_validator('email', 'display_name', mode='before')
    @classmethod
    def normalize_identity(cls, value, info):
        if isinstance(value, str):
            value = value.strip()
            return value.lower() if info.field_name == 'email' else value
        return value

    @model_validator(mode='after')
    def check_password(self):
        password = self.password.get_secret_value()
        if password != self.password_confirmation.get_secret_value():
            raise ValueError('两次密码不一致')
        if len(password.encode('utf-8')) > 72:
            raise ValueError('密码 UTF-8 编码后不能超过72字节')
        try:
            validate_password_policy(password)
        except ApiError as exc:
            raise ValueError(exc.message) from exc
        return self


class RegistrationCodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr = Field(max_length=190)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value
