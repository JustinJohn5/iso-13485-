"""ISO 13485 共用要求目录；仅提供副本，避免草稿与审核互相修改依据。"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

from App.Utils.Errors import ApiError


CATALOG_PATH = Path(__file__).resolve().parents[2] / 'Rules' / 'Requirements' / 'Iso13485.json'
TEMPLATE_IDS = frozenset({
    'quality-manual', 'quality-policy', 'document-control', 'record-control',
    'management-review', 'training', 'infrastructure', 'risk-management',
    'purchasing', 'production', 'traceability', 'monitoring', 'complaints',
    'internal-audit', 'nonconformity', 'corrective-action', 'record-forms',
    'design-plan', 'finished-inspection', 'market-research',
})
ALLOWED_CONDITIONS = frozenset({
    'design', 'sterile', 'implant', 'installation', 'servicing', 'outsourcing',
    'software', 'cleaning', 'process_validation', 'customer_property',
})
DOCUMENT_TYPES = frozenset({
    '*', 'quality_manual', 'procedure', 'management_review', 'internal_audit',
    'risk_management', 'design_control', 'purchasing', 'nonconformity', 'other',
})
REQUIREMENT_FIELDS = frozenset({
    'rule_id', 'clause', 'title', 'document_types', 'templates', 'topics',
    'conditions', 'terms', 'generation', 'evidence', 'source', 'uncertainty',
})


def _expected_clauses() -> set[str]:
    ranges = {
        '4.1': 6, '4.2': 5, '5.4': 2, '5.5': 3, '5.6': 3,
        '6.4': 2, '7.2': 3, '7.3': 10, '7.4': 3, '7.5': 8,
        '7.5.9': 2, '8.2': 6, '8.3': 4, '8.5': 3,
    }
    result = {f'{prefix}.{i}' for prefix, count in ranges.items() for i in range(1, count + 1)}
    return result | {'5.1', '5.2', '5.3', '6.1', '6.2', '6.3', '7.1',
                     '7.5.10', '7.5.11', '7.6', '8.1', '8.4'}


def _fail(message: str) -> None:
    raise ApiError(1305, f'ISO 13485 要求目录不合法：{message}')


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_list(value: object, *, empty_allowed: bool = False) -> bool:
    return (isinstance(value, list) and (empty_allowed or bool(value))
            and all(_text(item) for item in value)
            and len(value) == len(set(value)))


def _validate_requirement(row: object) -> None:
    if not isinstance(row, dict) or row.keys() != REQUIREMENT_FIELDS:
        _fail('条款字段缺失或包含未知字段')
    clause = row['clause']
    if not _text(clause) or row['rule_id'] != f'R-{clause}':
        _fail('条款号与规则编号不一致')
    for key in ('title', 'generation', 'evidence', 'source'):
        if not _text(row[key]):
            _fail(f'{clause} 的 {key} 为空或类型错误')
    if '物理页' not in row['source'] or clause not in row['source']:
        _fail(f'{clause} 缺少原件物理页或条款定位')
    if not isinstance(row['uncertainty'], str):
        _fail(f'{clause} 的来源疑点必须为字符串')
    if clause in {'7.5.6', '8.5.3'} and not row['uncertainty'].strip():
        _fail(f'{clause} 不得丢失译文疑点')
    for key, allowed in (('templates', TEMPLATE_IDS), ('conditions', ALLOWED_CONDITIONS),
                         ('document_types', DOCUMENT_TYPES)):
        if not _string_list(row[key], empty_allowed=key == 'conditions'):
            _fail(f'{clause} 的 {key} 必须是有效且不重复的字符串列表')
        if not set(row[key]) <= allowed:
            _fail(f'{clause} 的 {key} 包含未定义值')
    if not _string_list(row['topics']) or any(len(topic) < 2 for topic in row['topics']):
        _fail(f'{clause} 缺少具体主题路由')
    if (not isinstance(row['terms'], list) or not row['terms']
            or not all(_string_list(group) for group in row['terms'])):
        _fail(f'{clause} 的必须概念组为空、重复或类型错误')


def _validate_catalog(payload: object) -> dict:
    if not isinstance(payload, dict) or payload.keys() != {'version', 'source', 'requirements'}:
        _fail('根对象字段必须为 version、source、requirements')
    if payload['version'] != '2.0.0':
        _fail('版本必须为 2.0.0')
    source = payload['source']
    if not isinstance(source, dict) or source.get('standard') != 'ISO 13485:2016':
        _fail('缺少标准来源信息')
    for key in ('pdf', 'docx', 'matrix', 'rules_version', 'interpretation'):
        if not _text(source.get(key)):
            _fail(f'缺少来源字段 {key}')
    for key in ('pdf_sha256', 'docx_sha256'):
        if not isinstance(source.get(key), str) or not re.fullmatch(r'[a-f0-9]{64}', source[key]):
            _fail(f'来源字段 {key} 不是有效 SHA256')
    if source.get('pdf_physical_pages') != 41:
        _fail('原件必须记录为41个物理页')
    requirements = payload['requirements']
    if not isinstance(requirements, list) or len(requirements) != 72:
        _fail('必须包含72项末级条款')
    for row in requirements:
        _validate_requirement(row)
    if {row['clause'] for row in requirements} != _expected_clauses():
        _fail('条款重复、缺失或编号超出已确认矩阵')
    if {key for row in requirements for key in row['templates']} != TEMPLATE_IDS:
        _fail('未完整映射现有20项模板')
    return payload


def load_catalog() -> dict:
    """加载并校验固定版本目录；每次返回独立的嵌套对象。"""
    try:
        payload = json.loads(CATALOG_PATH.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ApiError(1305, 'ISO 13485 要求目录无法读取或不是有效 UTF-8 JSON') from exc
    return deepcopy(_validate_catalog(payload))


def requirements_for_template(template_id: str) -> list[dict]:
    """按具体模板选择承载要求；未知模板属于参数错误。"""
    if not isinstance(template_id, str) or template_id not in TEMPLATE_IDS:
        raise ApiError(1001, '未知的条款要求模板，请选择现有模板')
    return [row for row in load_catalog()['requirements'] if template_id in row['templates']]
