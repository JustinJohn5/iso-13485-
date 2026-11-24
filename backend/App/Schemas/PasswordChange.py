"""登录用户修改密码时的必要验证字段。"""
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from App.Utils.Errors import ApiError
from App.Utils.Security import validate_password_policy


class PasswordChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: SecretStr = Field(min_length=1, max_length=72)
    password: SecretStr = Field(min_length=8, max_length=72)
    password_confirmation: SecretStr = Field(min_length=8, max_length=72)
    email_verification_code: str = Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")

    @model_validator(mode="after")
    def check_password(self):
        password = self.password.get_secret_value()
        if password != self.password_confirmation.get_secret_value():
            raise ValueError("两次密码不一致")
        if len(password.encode("utf-8")) > 72:
            raise ValueError("密码 UTF-8 编码后不能超过72字节")
        try:
            validate_password_policy(password)
        except ApiError as exc:
            raise ValueError(exc.message) from exc
        return self
