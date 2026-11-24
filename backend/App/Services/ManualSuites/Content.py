"""整套成员的生成与导入快照；只做内存计算，不访问数据库。"""
from copy import deepcopy
from hashlib import sha256
import re
from uuid import uuid4

from App.Constants.AuthoringLimits import MAX_REQUIREMENTS_CHARS
from App.Services.Authoring.TemplateLibrary import edit_sections, rewrite_parameter_text
from App.Services.Authoring.GenerationRules import enrich_snapshot, legacy_basis
from App.Services.DocumentControl.Metadata import extract_metadata
from App.Services.ManualSuites.Catalog import catalog, suite_template
from App.Utils.Errors import ApiError

MAX_ITEMS = 100
MAX_TEXT = 4_000_000


def check_capacity(items: list[dict]) -> list[dict]:
    if len(items) > MAX_ITEMS or sum(len(row['text']) for row in items) > MAX_TEXT:
        raise ApiError(1001, '每套最多100份文件、400万正文字符，请按范围拆分套册')
    return items


def clean_value(value: str, limit=120) -> str:
    if not value.strip() or len(value) > limit or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', value):
        raise ApiError(1001, '参数为空、过长或包含不支持的控制字符')
    return value.strip()


def snapshot_text(snapshot: dict) -> str:
    values = snapshot['parameters']
    return (f"{snapshot['title']}\n文件编号：{values['number']}\n版本：{values['version']}\n文件状态：草稿\n"
            '编制：待填写\n审核：待填写\n批准：待填写\n' +
            '\n'.join(item['title'] + '\n' + item['body'] for item in snapshot['sections']))


def generate_items(existing: list[dict], keys: list[str], parameters: dict, version: str) -> list[dict]:
    directory = {row['key']: row for row in catalog()}
    if not keys or len(set(keys)) != len(keys) or any(key not in directory for key in keys):
        raise ApiError(1001, '请选择不重复的有效目录项目')
    if set(parameters) != {'company', 'project', 'product', 'model', 'requirements'}:
        raise ApiError(1001, '请填写组织、项目、产品、型号和已知输入')
    if any(row['catalog_key'] in keys for row in existing):
        raise ApiError(1001, '所选目录已存在文件，请先核对或移除，避免重复生成')
    cleaned = {key: clean_value(value, MAX_REQUIREMENTS_CHARS if key == 'requirements' else 120)
               for key, value in parameters.items()}
    version = clean_value(version, 32)
    result = deepcopy(existing)
    for key in keys:
        entry, template = directory[key], suite_template(key)
        values = {**cleaned, 'number': entry['number'], 'version': version}
        sections = [{**row, 'body': row['body'].format_map(values)} for row in template['sections']]
        snapshot = dict(template_id=key, template_version=template['version'], title=template['title'],
                        parameters=values, sections=sections, origin='template', status='draft')
        snapshot = enrich_snapshot(snapshot)
        text = snapshot_text(snapshot)
        result.append(dict(id=str(uuid4()), title=entry['title'], number=entry['number'], file_version=version,
                           catalog_key=key, document_type=entry['document_type'], origin='generated',
                           text=text, snapshot=snapshot, revision=1, sha256=sha256(text.encode()).hexdigest()))
    return check_capacity(result)


def import_items(existing: list[dict], files: list) -> list[dict]:
    seen = {row['sha256'] for row in existing}
    result = deepcopy(existing)
    for source in files:
        if source.sha256 in seen:
            raise ApiError(1001, '本套已有相同内容，未重复归档；请核对原文件')
        seen.add(source.sha256)
        metadata = extract_metadata(source.original_name, source.extracted_text, source.document_type)
        matches = [row['key'] for row in catalog() if row['title'] in source.original_name]
        key = matches[0] if len(matches) == 1 else 'quality-manual' if source.document_type == 'quality_manual' else ''
        result.append(dict(id=str(uuid4()), title=source.original_name, number=metadata['number'],
                           file_version=metadata['revision'], catalog_key=key, document_type=source.document_type,
                           origin='imported', text=source.extracted_text, sha256=source.sha256,
                           file_uid=source.file_uid, stored_name=source.stored_name, size_bytes=source.size_bytes,
                           text_status=getattr(source, 'text_status', 'ok')))
    return check_capacity(result)


def revise_item(items: list[dict], item_id: str, catalog_key: str, file_version: str, *, sections=None) -> list[dict]:
    if catalog_key and catalog_key not in {row['key'] for row in catalog()}:
        raise ApiError(1001, '目录项目无效')
    result = deepcopy(items)
    row = next((row for row in result if row['id'] == item_id), None)
    if row is None:
        raise ApiError(1801, '套册成员不存在')
    previous_version = row['file_version']
    row['catalog_key'] = catalog_key
    row['file_version'] = clean_value(file_version, 32) if file_version else ''
    if catalog_key:
        row['document_type'] = next(item['document_type'] for item in catalog() if item['key'] == catalog_key)
    if sections is not None:
        if row['origin'] != 'generated':
            raise ApiError(1001, '导入原件不可改写，请修订原文件后重新导入')
        row['snapshot'] = edit_sections(row['snapshot'], sections)
    if row['origin'] == 'generated' and (sections is not None or previous_version != row['file_version']):
        row['snapshot']['parameters']['version'] = clean_value(file_version, 32)
        if previous_version != row['file_version']:
            values = row['snapshot']['parameters']
            previous_values = {**values, 'version': previous_version}
            for section in row['snapshot']['sections']:
                section['body'] = rewrite_parameter_text(section['body'], previous_values, values)
        row['revision'] = row.get('revision', 1) + 1
        row['snapshot'].setdefault('requirements_basis', legacy_basis(row['snapshot']))
        row['snapshot'] = enrich_snapshot(row['snapshot'])
        row['text'] = snapshot_text(row['snapshot'])
        row['sha256'] = sha256(row['text'].encode()).hexdigest()
    return check_capacity(result)
