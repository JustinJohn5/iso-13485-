"""敏感配置加解密（大模型 API Key 等）。

加密主密钥只存在于后端 .env，不得与密文一同入库。
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from App.Config.Settings import get_settings
from App.Utils.Errors import ApiError


def _fernet() -> Fernet:
    return Fernet(get_settings().config_encryption_key.encode("utf-8"))


def encrypt_secret(plain_text: str) -> str:
    """加密敏感字段，返回可入库的密文字符串。"""
    return _fernet().encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_secret(cipher_text: str) -> str:
    """解密敏感字段；密钥变更或密文损坏时抛 1403。"""
    if not cipher_text:
        raise ApiError(1403)
    try:
        return _fernet().decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise ApiError(1403, "大模型 API Key 解密失败，请在配置页重新填写") from exc


def mask_secret(plain_text: str) -> str:
    """仅用于日志/提示的脱敏展示，永不返回完整密钥。"""
    if not plain_text:
        return ""
    if len(plain_text) <= 8:
        return "*" * len(plain_text)
    return f"{plain_text[:4]}{'*' * 6}{plain_text[-2:]}"
