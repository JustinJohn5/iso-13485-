"""注册输入校验：强密码、UTF-8 边界和禁止自行提升权限。"""
import pytest
from pydantic import ValidationError


def registration(**changes):
    from App.Schemas.Registration import RegistrationRequest
    values = dict(email='  New.User@EXAMPLE.com  ', display_name='  新用户  ',
                  password='RegisterPass2026', password_confirmation='RegisterPass2026')
    return RegistrationRequest(**{**values, **changes})


def test_normalize_identity_and_hide_password_in_representation():
    value = registration()
    assert str(value.email) == 'new.user@example.com'
    assert value.display_name == '新用户'
    assert value.password.get_secret_value() == 'RegisterPass2026'
    assert 'RegisterPass2026' not in repr(value)


@pytest.mark.parametrize('changes', [
    {'email': 'wrong-email'},
    {'display_name': '  '},
    {'display_name': '姓' * 65},
    {'password': '12345678', 'password_confirmation': '12345678'},
    {'password': 'abcdefgh', 'password_confirmation': 'abcdefgh'},
    {'password': 'Ab12345', 'password_confirmation': 'Ab12345'},
    {'password_confirmation': 'OtherPass2026'},
    {'password': 'A1' + '中' * 24, 'password_confirmation': 'A1' + '中' * 24},
    {'password': 'A1' + 'b' * 71, 'password_confirmation': 'A1' + 'b' * 71},
    {'role': 'admin'},
    {'is_active': False},
    {'token_version': 0},
])
def test_invalid_input_is_rejected(changes):
    with pytest.raises(ValidationError):
        registration(**changes)


def test_password_at_bcrypt_byte_limit_is_preserved():
    password = 'A1b' + '中' * 23
    assert len(password.encode('utf-8')) == 72
    value = registration(password=password, password_confirmation=password)
    assert value.password.get_secret_value() == password
