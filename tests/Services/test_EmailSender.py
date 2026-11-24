"""邮件验证码投递边界：SMTP TLS、发件内容与失败脱敏。"""
from types import SimpleNamespace

import pytest


class FakeSmtp:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.started_tls = False
        self.credentials = None
        self.message = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def starttls(self, context=None):
        self.started_tls = True

    def login(self, username, password):
        self.credentials = (username, password)

    def send_message(self, message, from_addr=None, to_addrs=None):
        self.message = (message, from_addr, to_addrs)


def settings(**changes):
    values = dict(email_smtp_host='smtp.example.test', email_smtp_port=587,
                  email_smtp_username='sender@example.test', email_smtp_password='smtp-secret',
                  email_from_address='no-reply@example.test', email_smtp_starttls=True,
                  email_smtp_ssl=False, email_smtp_timeout_seconds=10)
    return SimpleNamespace(**{**values, **changes})


def test_verification_digest_is_keyed_and_bound_to_email_and_purpose():
    from App.Services.EmailVerification import code_digest

    digest = code_digest('person@example.test', 'registration', '012345', 'test-secret')

    assert len(digest) == 64
    assert '012345' not in digest
    assert digest != code_digest('other@example.test', 'registration', '012345', 'test-secret')
    assert digest != code_digest('person@example.test', 'password_change', '012345', 'test-secret')
    assert digest != code_digest('person@example.test', 'registration', '012345', 'other-secret')


def test_smtp_delivery_uses_tls_and_sends_the_code(monkeypatch):
    from App.Services import EmailSender

    connection = FakeSmtp()
    def connect(*args, **kwargs):
        connection.args = args
        connection.kwargs = kwargs
        return connection
    monkeypatch.setattr(EmailSender.smtplib, 'SMTP', connect)
    EmailSender.send_verification_email('person@example.test', '012345', settings=settings())

    assert connection.args == ('smtp.example.test', 587)
    assert connection.kwargs['timeout'] == 10
    assert connection.started_tls is True
    assert connection.credentials == ('sender@example.test', 'smtp-secret')
    message, sender, recipients = connection.message
    assert message['To'] == 'person@example.test'
    assert sender == 'no-reply@example.test'
    assert recipients == ['person@example.test']
    assert '012345' in message.get_content()


def test_smtp_failure_does_not_log_email_code_or_smtp_password(monkeypatch, caplog):
    from App.Services import EmailSender

    class FailingSmtp(FakeSmtp):
        def send_message(self, *_args, **_kwargs):
            raise OSError('connection refused')

    monkeypatch.setattr(EmailSender.smtplib, 'SMTP', lambda *args, **kwargs: FailingSmtp())
    with pytest.raises(EmailSender.EmailDeliveryError):
        EmailSender.send_verification_email('person@example.test', '654321', settings=settings())

    assert 'person@example.test' not in caplog.text
    assert '654321' not in caplog.text
    assert 'smtp-secret' not in caplog.text
