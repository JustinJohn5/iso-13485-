"""提取文件控制线索；行号指抽取文本，不冒充原件页码。"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from App.Utils.TimeUtils import parse_date

CATEGORIES = {
    'policy': 'a) 质量方针和质量目标', 'manual': 'b) 质量手册',
    'required': 'c) 标准要求的程序和记录', 'organization': 'd) 组织所需文件和记录',
    'regulatory': 'e) 适用法规要求的其他文件', 'unclassified': '待确认类别',
}
LAYERS = {'document': '受控文件', 'template': '空白表单模板', 'record': '已填写记录', 'unknown': '层级待确认'}
STATUSES = {'unknown': '批准状态待核实', 'controlled': '标注为现行/受控', 'draft': '草稿/待批准', 'obsolete': '已作废'}
ID_PATTERN = r'(?<![A-Za-z0-9])([A-Za-z]{1,12}(?:[-_/][A-Za-z0-9]{1,16}){1,4})(?![A-Za-z0-9])'
DATE_PATTERN = r'\d{4}\s*[年./-]\s*\d{1,2}\s*[月./-]\s*\d{1,2}\s*日?'


def normalize_number(value: str) -> str:
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', value)).upper()


def text_lines(text: str) -> list[tuple[int, str]]:
    return [(i, unicodedata.normalize('NFKC', line).strip()) for i, line in enumerate(text.splitlines(), 1) if line.strip()]


def extract_metadata(name: str, text: str, document_type: str) -> dict:
    lines = text_lines(text)
    header = lines[:40]
    metadata = {'number': '', 'revision': '', 'effective_date': '', 'status': 'unknown',
                'category': 'unclassified', 'layer': 'unknown', 'sources': [], 'warnings': []}
    patterns = {
        'number': r'(?:文件|文档|表单|记录)\s*(?:编号|号|代码|no\.?)\s*[:：#]?\s*([A-Za-z0-9][A-Za-z0-9._/-]{1,63})',
        'revision': r'(?:版本|修订|revision|version)\s*(?:号|编号|等级|level)?\s*[:：#]?\s*([A-Za-z0-9][A-Za-z0-9._/-]{0,31})',
        'effective_date': rf'(?:生效(?:日期)?|实施日期|effective\s+date)\s*[:：]?\s*({DATE_PATTERN})',
    }
    for field, pattern in patterns.items():
        hits = [(line, value, match.group(1)) for line, value in header if (match := re.search(pattern, value, re.I))]
        distinct = {value for _, _, value in hits}
        if len(distinct) > 1:
            metadata['warnings'].append(f'{field} 存在多个线索，请核对封面及修订历史')
        if hits:
            line, quote, value = hits[0]
            if field == 'effective_date':
                parsed = parse_date(re.sub(r'\s+', '', value))
                value = parsed.date().isoformat() if parsed else ''
                if not value:
                    metadata['warnings'].append('生效日期无效，请人工修正')
            metadata[field] = normalize_number(value) if field == 'number' else value
            metadata['sources'].append({'field': field, 'quote': quote[:300], 'line': line})
    for status, pattern in [('obsolete', r'^(?:(?:文件状态|状态)\s*[:：]\s*)?(?:已作废|已废止|作废版本)\s*$'),
                            ('draft', r'^(?:(?:文件状态|状态)\s*[:：]\s*)?(?:草稿|待批准|未批准|DRAFT)\s*$'),
                            ('controlled', r'^(?:(?:文件状态|状态)\s*[:：]\s*)?(?:现行有效|现行版本|已批准)\s*$|^受控状态\s*[:：]\s*受控\s*$')]:
        hit = next(((line, value) for line, value in header if re.search(pattern, value, re.I)), None)
        if hit:
            metadata['status'] = status
            metadata['sources'].append({'field': 'status', 'quote': hit[1][:300], 'line': hit[0]})
            break
    title = unicodedata.normalize('NFKC', Path(name).stem)
    if re.search('质量方针|质量目标', title):
        metadata['category'] = 'policy'
    elif document_type == 'quality_manual':
        metadata['category'] = 'manual'
    elif re.search('法规|法律|条例|监管要求', title):
        metadata['category'] = 'regulatory'
    # c 与 d 取决于具体要求，不能仅凭名称自动认定由标准强制要求。
    elif document_type != 'other':
        metadata['category'] = 'organization'
    if re.search('空白|模板', title):
        metadata['layer'] = 'template'
    elif re.search('记录|报告', title) and not re.search('程序|办法|规程', title):
        metadata['layer'] = 'unknown'
        metadata['warnings'].append('名称含记录/报告，请确认是空白模板还是已填写记录')
    else:
        metadata['layer'] = 'document'
    if not metadata['number']:
        metadata['warnings'].append('未找到明确文件编号，不自动合并为同一文件的不同版本')
    return metadata


def extract_references(text: str, own_number: str) -> list[dict]:
    result, seen = [], set()
    for line, quote in text_lines(text):
        if re.match(r'^(?:(?:文件|文档|表单|记录)\s*(?:编号|号|代码)|版本|修订)\s*[:：]', quote):
            continue
        for match in re.finditer(ID_PATTERN, quote):
            number = normalize_number(match.group(1))
            if number == own_number or number in seen:
                continue
            seen.add(number)
            result.append({'number': number, 'quote': quote[:350], 'line': line})
            if len(result) >= 100:
                return result
    return result
