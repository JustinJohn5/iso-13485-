"""AI 合同、失败保留及敏感日志回归，不调用外部真实模型。"""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from App.Schemas.LlmSettings import LlmSettingsUpdate
from App.Schemas.LlmSettings import AiDraftRequest
from App.Constants.AuthoringLimits import (MAX_INPUT_CHARS, MAX_RESPONSE_CHARS, MAX_REQUIREMENTS_CHARS,
                                          MAX_INSTRUCTIONS_CHARS, MAX_OUTPUT_TOKENS, MAX_TIMEOUT_SECONDS)
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


@pytest.mark.parametrize('body', ['产品：其他产品；型号：TYPE-B。', '其他产品（TYPE-B）的全部检验已经完成。'])
def test_ai_obvious_parameter_conflict_is_rejected_without_mutation(body, monkeypatch):
    snapshot = sample()
    original = deepcopy(snapshot)
    sections = {row['id']: body for row in snapshot['sections']}
    monkeypatch.setattr(AiDraft, 'complete_json', lambda *args: ({'sections': sections}, 'test-model'))
    with pytest.raises(ApiError) as error:
        AiDraft.generate_ai_draft(None, snapshot, '细化草稿')
    assert error.value.code == 1402 and snapshot == original


def test_ai_specific_claims_are_individually_flagged_for_source_verification(monkeypatch):
    snapshot = sample()
    original = deepcopy(snapshot)
    sections = {row['id']: '2026-01-01由张三签字。全部样本均达到要求。验收限值99.9%。依据ISO 99999第1条执行。'
                for row in snapshot['sections']}
    monkeypatch.setattr(AiDraft, 'complete_json', lambda *args: ({'sections': sections}, 'test-model'))
    result = AiDraft.generate_ai_draft(None, snapshot, '细化草稿')
    manual = result['generation_review']['manual_review']
    for quoted in ['2026-01-01', '张三签字', '全部样本均达到要求', '99.9%', 'ISO 99999']:
        assert any(quoted in row.get('quote', '') and row.get('section_id') for row in manual)
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


def test_long_ai_input_and_response_are_preserved_without_truncation(monkeypatch):
    snapshot = sample()
    snapshot['parameters']['requirements'] = '资' * (MAX_REQUIREMENTS_CHARS - 4) + '输入末尾'
    snapshot['sections'][1]['body'] = snapshot['parameters']['requirements']
    original = deepcopy(snapshot)
    sections = {item['id']: '文' * 20000 + '输出末尾' for item in snapshot['sections']}
    calls = mock_client(monkeypatch, text=json.dumps({'sections': sections}, ensure_ascii=False))
    instructions = '要' * (MAX_INSTRUCTIONS_CHARS - 4) + '要求末尾'
    AiDraftRequest(revision=1, instructions=instructions)
    result = AiDraft.generate_ai_draft(None, snapshot, instructions)
    sent = json.loads(calls['request']['messages'][1]['content'])
    assert sent['parameters']['requirements'] == original['parameters']['requirements']
    assert sent['sections'] == original['sections'] and sent['instructions'] == instructions
    assert {item['id']: item['body'] for item in result['sections']} == sections
    assert result['origin'] == 'ai' and snapshot == original


def test_input_boundary_includes_system_and_rejects_overflow_before_request(monkeypatch):
    calls = mock_client(monkeypatch)
    system = '系统提示'
    overhead = len(json.dumps({'facts': ''}, ensure_ascii=False)) + len(system)
    payload = {'facts': '资' * (MAX_INPUT_CHARS - overhead)}
    Client.complete_json(None, system, payload)
    assert len(calls['request']['messages'][1]['content']) + len(system) == MAX_INPUT_CHARS
    calls.pop('request')
    with pytest.raises(ApiError) as error:
        Client.complete_json(None, system, {'facts': payload['facts'] + '超'})
    assert error.value.code == 1001 and 'request' not in calls


@pytest.mark.parametrize('overflow', [False, True])
def test_response_size_boundary_is_not_silently_truncated(monkeypatch, overflow):
    content = '{"sections":{}}'
    content += ' ' * (MAX_RESPONSE_CHARS - len(content) + int(overflow))
    mock_client(monkeypatch, text=content)
    if overflow:
        with pytest.raises(ApiError) as error:
            Client.complete_json(None, '系统要求', {})
        assert error.value.code == 1402
    else:
        assert Client.complete_json(None, '系统要求', {})[0] == {'sections': {}}


def test_expanded_settings_and_instruction_boundaries():
    settings = dict(enabled=True, base_url='https://test.invalid/v1', model='test',
                    timeout_seconds=MAX_TIMEOUT_SECONDS, max_tokens=MAX_OUTPUT_TOKENS, temperature=0.2)
    assert LlmSettingsUpdate(**settings).max_tokens == MAX_OUTPUT_TOKENS
    for field in ('timeout_seconds', 'max_tokens'):
        with pytest.raises(ValidationError):
            LlmSettingsUpdate(**{**settings, field: settings[field] + 1})
    with pytest.raises(ValidationError):
        AiDraftRequest(revision=1, instructions='要' * (MAX_INSTRUCTIONS_CHARS + 1))
