"""明确指向同一编号的记录保存期限对照；不猜测无主语的语义关系。"""
import re
from collections import defaultdict

from App.Services.DocumentControl.Metadata import ID_PATTERN, normalize_number, text_lines
from App.Services.DocumentControl.Versions import issue_id


def retention_facts(document: dict) -> list[dict]:
    result = []
    for line, quote in text_lines(document['text']):
        match = re.search(r'保存(?:期限|年限|期|时间)?\s*(?:应|不应|须)?\s*(不少于|至少|不低于|为|是)?\s*[:：]?\s*(\d{1,3})\s*(年|个月|月)', quote)
        if not match:
            continue
        # 期限后的“按 QP-xx 执行”是执行依据，不是被保存记录的编号。
        ids = {normalize_number(value) for value in re.findall(ID_PATTERN, quote[:match.start()])}
        if not ids and re.search(r'本(?:记录|表单|文件)', quote):
            ids = {document['metadata']['number']} - {''}
        if len(ids) != 1:
            continue
        months = int(match.group(2)) * (12 if match.group(3) == '年' else 1)
        minimum = match.group(1) in {'不少于', '至少', '不低于'}
        result.append({'file_uid': document['file_uid'], 'number': next(iter(ids)), 'months': months,
                       'minimum': minimum, 'value': match.group(0), 'quote': quote[:350], 'line': line})
        if len(result) >= 200:
            document['metadata']['warnings'].append('仅提取前200条明确期限线索，请人工复核其余内容')
            break
    return result


def build_requirement_conflicts(documents: list[dict]) -> list[dict]:
    targets = defaultdict(list)
    for document in documents:
        facts = document['retention_facts'] if 'retention_facts' in document else retention_facts(document)
        for fact in facts:
            targets[fact['number']].append(fact)
    conflicts = []
    for number, facts in targets.items():
        different = any(a['file_uid'] != b['file_uid'] and
                        ((not a['minimum'] and not b['minimum'] and a['months'] != b['months']) or
                         (a['minimum'] and not b['minimum'] and b['months'] < a['months']))
                        for a in facts for b in facts)
        if different:
            conflicts.append({'id': issue_id('retention', number), 'number': number, 'field': '记录保存期限',
                              'facts': facts, 'file_uids': list(dict.fromkeys(fact['file_uid'] for fact in facts)),
                              'explanation': '同一编号存在不一致的明确保存期限；选择依据后仍需修订冲突文件', 'decision': None})
    return conflicts
