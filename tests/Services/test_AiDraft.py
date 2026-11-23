"""AI 合同、失败保留及敏感日志回归，不调用外部真实模型。"""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from App.Schemas.LlmSettings import LlmSettingsUpdate
from App.Services.Authoring import AiDraft
from App.Services.Authoring.TemplateLibrary import build_snapshot
from App.Services.Llm import Client
from App.Utils.Errors import ApiError


def sample():
    return build_snapshot('design-plan', {'company': '测试组织', 'project': '测试项目', 'product': '测试产品',
                                         'model': 'TYPE-A', 'number': 'DP-01', 'version': '01', 'requirements': '测试要求'})


def test_ai_uses_validated_sections_and_preserves_parameters_and_original(monkeypatch):
    snapshot = sample()
    original = deepcopy(snapshot)
    sections = {item['id']: '待确认：请依据实际项目补全此章节。' for item in snapshot['sections']}
    monkeypatch.setattr(AiDraft, 'complete_json', lambda *args: ({'sections': sections}, 'test-model'))
    result = AiDraft.generate_ai_draft(None, snapshot, '细化项目计划及追溯记录')
    assert result['origin'] == 'ai' and result['ai_model'] == 'test-model'
    assert result['parameters'] == original['parameters'] and result['status'] == 'draft'
    assert snapshot == original


@pytest.mark.parametrize('output', [{}, {'sections': []}, {'sections': {'s1': '只有一个章节'}},
                                    {'sections': {f's{i}': 123 for i in range(1, 5)}},
                                    {'sections': {f's{i}': '' for i in range(1, 5)}}])
def test_invalid_ai_output_rejected_without_mutating_draft(output, monkeypatch):
    snapshot = sample()
    original = deepcopy(snapshot)
    monkeypatch.setattr(AiDraft, 'complete_json', lambda *args: (output, 'test-model'))
    with pytest.raises(ApiError) as error:
        AiDraft.generate_ai_draft(None, snapshot, '合法的测试编写要求')
    assert error.value.code == 1402 and snapshot == original


def mock_client(monkeypatch, text='{"sections":{}}', finish='stop'):
    config = SimpleNamespace(enabled=True, base_url='https://test.invalid/v1', model='test-model',
                             api_key_cipher='encrypted-placeholder', timeout_seconds=10, max_tokens=1000, temperature=0.2)
    monkeypatch.setattr(Client.LlmConfigDao, 'get_default', lambda db: config)
    monkeypatch.setattr(Client, 'decrypt_secret', lambda value: 'synthetic-test-key')
    calls = {}

    class FakeClient:
        def __init__(self, **kwargs):
            calls.update(kwargs)
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **kwargs):
            calls['request'] = kwargs
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish, message=SimpleNamespace(content=text))],
                                   usage=SimpleNamespace(total_tokens=20))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(Client, 'OpenAI', FakeClient)
    return calls


def test_sdk_has_timeout_retry_limit_and_redacted_logs(monkeypatch, caplog):
    calls = mock_client(monkeypatch)
    with caplog.at_level('INFO'):
        data, model = Client.complete_json(None, '系统要求', {'private': 'private-input-for-test'})
    assert data == {'sections': {}} and model == 'test-model'
    assert calls['timeout'] == 10 and calls['max_retries'] == 1
    assert calls['request']['max_tokens'] == 1000
    assert 'synthetic-test-key' not in caplog.text and 'private-input-for-test' not in caplog.text
    assert 'tokens=20' in caplog.text


@pytest.mark.parametrize(('text', 'finish'), [('not-json', 'stop'), ('{}', 'length'), ('[]', 'stop')])
def test_sdk_rejects_truncated_or_malformed_response(monkeypatch, text, finish):
    mock_client(monkeypatch, text, finish)
    with pytest.raises(ApiError) as error:
        Client.complete_json(None, '系统要求', {})
    assert error.value.code == 1402


def test_unconfigured_model_is_explicitly_rejected(monkeypatch):
    monkeypatch.setattr(Client.LlmConfigDao, 'get_default', lambda db: None)
    with pytest.raises(ApiError) as error:
        Client.complete_json(None, '系统要求', {})
    assert error.value.code == 1401


@pytest.mark.parametrize('url', ['file:///etc/passwd', 'https://user:key@test.invalid/v1', 'https://test.invalid/v1?key=test', 'https://test.invalid:99999'])
def test_config_rejects_invalid_service_urls(url):
    with pytest.raises(ValidationError):
        LlmSettingsUpdate(enabled=True, base_url=url, model='test', api_key='test-only', timeout_seconds=10, max_tokens=1000, temperature=0.2)
