"""通过 SMTP 发送邮箱验证码；不在日志中保留邮件或凭据内容。"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage

from App.Config.Settings import Settings, get_settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """邮件投递失败。"""


def send_verification_email(email: str, code: str, *, settings: Settings | None = None) -> None:
    config = settings or get_settings()
    message = EmailMessage()
    message["Subject"] = "ISO 13485 文件预筛平台邮箱验证码"
    message["From"] = config.email_from_address
    message["To"] = email
    message.set_content(f"您的邮箱验证码为：{code}\n验证码 10 分钟内有效，请勿向他人透露。\n如非本人操作，请忽略此邮件。")

    try:
        context = ssl.create_default_context()
        if config.email_smtp_ssl:
            connection = smtplib.SMTP_SSL(config.email_smtp_host, config.email_smtp_port,
                                          timeout=config.email_smtp_timeout_seconds, context=context)
        else:
            connection = smtplib.SMTP(config.email_smtp_host, config.email_smtp_port,
                                      timeout=config.email_smtp_timeout_seconds)
        with connection as smtp:
            if config.email_smtp_starttls:
                smtp.starttls(context=context)
            smtp.login(config.email_smtp_username, config.email_smtp_password)
            refused = smtp.send_message(message, from_addr=config.email_from_address, to_addrs=[email])
            if refused:
                raise EmailDeliveryError("收件服务器拒收")
    except Exception as exc:  # noqa: BLE001 - 不输出 SMTP 异常文本，避免回显收件人或凭据
        logger.warning("验证码邮件投递失败，异常类型=%s", type(exc).__name__)
        raise EmailDeliveryError("SMTP 邮件投递失败") from None
