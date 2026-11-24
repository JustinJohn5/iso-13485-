"""明确指向同一编号的记录保存期限对照；不猜测无主语的语义关系。"""
import re
from collections import defaultdict

from App.Services.DocumentControl.Metadata import ID_PATTERN, normalize_number, text_lines
from App.Services.DocumentControl.Versions import issue_id

START = re.compile(r'(?:产品)?(放行|归档|形成|批准|作废|生产|交付|停产)(?:之日|日期|日)?(?:起|开始|后)')
PERIOD = re.compile(r'保存(?:期限|年限|期|时间)?\s*(?:应|不应|须)?\s*(不少于|至少|不低于|为|是)?\s*[:：]?\s*(\d{1,3})\s*(年|个月|月)')


def retention_facts(document: dict) -> list[dict]:
    result = []
    for line, quote in text_lines(document['text']):
        match = PERIOD.search(quote)
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
        starts = set(START.findall(quote))
        start = next(iter(starts)) if len(starts) == 1 else ''
        object_kind = 'obsolete' if '作废文件' in quote else 'record'
        result.append({'file_uid': document['file_uid'], 'number': next(iter(ids)), 'months': months,
                       'minimum': minimum, 'value': match.group(0), 'quote': quote[:350], 'line': line,
                       'start': start, 'object_kind': object_kind})
        if len(result) >= 200:
            document['metadata']['warnings'].append('仅提取前200条明确期限线索，请人工复核其余内容')
            break
    return result


def build_retention_review(documents: list[dict]) -> tuple[list[dict], list[dict]]:
    targets = defaultdict(list)
    for document in documents:
        facts = document['retention_facts'] if 'retention_facts' in document else retention_facts(document)
        for fact in facts:
            targets[fact['number']].append(fact)
    conflicts, manual = [], []
    for number, facts in targets.items():
        groups = defaultdict(list)
        for fact in facts:
            if fact.get('start'):
                groups[(fact['start'], fact.get('object_kind', 'record'))].append(fact)
        for (start, kind), comparable in groups.items():
            different = any(a['file_uid'] != b['file_uid'] and
                            ((not a['minimum'] and not b['minimum'] and a['months'] != b['months']) or
                             (a['minimum'] and not b['minimum'] and b['months'] < a['months']))
                            for a in comparable for b in comparable)
            if different:
                conflicts.append({'id': issue_id('retention', f'{number}:{start}:{kind}'),
                                  'number': number, 'field': '作废文件保存期限' if kind == 'obsolete' else '记录保存期限',
                                  'facts': comparable, 'file_uids': list(dict.fromkeys(fact['file_uid'] for fact in comparable)),
                                  'explanation': f'同一编号及起算事件（{start}）下期限不一致，请核对依据并修订冲突文件', 'decision': None})
        incomparable = any(a['file_uid'] != b['file_uid'] and a['months'] != b['months'] and
                           (not a.get('start') or not b.get('start') or a.get('start') != b.get('start') or
                            a.get('object_kind') != b.get('object_kind')) for a in facts for b in facts)
        if incomparable:
            manual.append({'number': number, 'facts': facts,
                           'explanation': '请确认保存对象、起算事件、寿命期和法规；当前期限证据不能直接比较'})
    return conflicts, manual
