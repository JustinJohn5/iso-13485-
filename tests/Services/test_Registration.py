"""注册输入校验：强密码、UTF-8 边界和禁止自行提升权限。"""
import pytest
from pydantic import ValidationError


def registration(**changes):
    from App.Schemas.Registration import RegistrationRequest
    values = dict(email='  New.User@EXAMPLE.com  ', display_name='  新用户  ',
                  password='RegisterPass2026', password_confirmation='RegisterPass2026',
                  email_verification_code='012345')
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


@pytest.mark.parametrize('code', ['', '12345', '1234567', '12a456', '１２３４５６'])
def test_registration_requires_six_ascii_digit_email_code(code):
    with pytest.raises(ValidationError):
        registration(email_verification_code=code)


def test_password_change_requires_current_password_new_password_and_email_code():
    from App.Schemas.PasswordChange import PasswordChangeRequest

    payload = PasswordChangeRequest(current_password='CurrentPass2026', password='NewPass2026',
                                    password_confirmation='NewPass2026', email_verification_code='012345')
    assert payload.email_verification_code == '012345'
    assert payload.password.get_secret_value() == 'NewPass2026'


@pytest.mark.parametrize('code', ['', '12345', '1234567', '12a456', '１２３４５６'])
def test_password_change_rejects_invalid_email_code(code):
    from App.Schemas.PasswordChange import PasswordChangeRequest

    with pytest.raises(ValidationError):
        PasswordChangeRequest(current_password='CurrentPass2026', password='NewPass2026',
                              password_confirmation='NewPass2026', email_verification_code=code)
