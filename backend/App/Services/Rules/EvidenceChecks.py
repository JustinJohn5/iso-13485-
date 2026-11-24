"""可解释的文本线索检查；保留抽取行及原文，不推断真实批准或实施有效性。"""
from dataclasses import dataclass, field
from datetime import date
import re
import unicodedata

from App.Utils.TimeUtils import now
from App.Services.Rules.Applicability import check_boundary

PLACEHOLDER = re.compile(r'待(?:填写|填|确认|补充|批准|定|核实)|_{2,}|[×Xx]{3,}|某某|示例|\[.*?待.*?\]')
NEGATIVE = re.compile(r'未(?:进行|开展|规定|确定|保存|实施|建立|提供|批准|审核|签署)|没有|无需|不予|不(?:保存|执行|建立|调查)')
CONTROL = re.compile(r'不得|禁止|不允许|未经|方可|应当|必须')
RECORD_DATE = re.compile(r'(\d{4})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})')
SEGMENTS = re.compile(r'[。；;！？!?]|[，,](?=\s*(?:但|然而|不过))')
OBJECT = re.compile(r'产品\s*([A-Za-z0-9]+)')
FUTURE = re.compile(r'未来需要时|今后再|将另行|拟另行')
MAX_LOCATIONS = 3


def uniform_checks(rule, state, detail):
    return [dict(id=f'{index:02d}', element=group[0], assessment_status=state, matched_term='',
                 locations=[], detail=detail) for index, group in enumerate(rule.check.terms, 1)]


def apply_boundaries(rule, checks, context):
    for check in checks:
        state, detail = check_boundary(rule, check['element'], context)
        if state:
            check.update(assessment_status=state, detail=detail, applicability_unknown=state == 'pending_input')
    if rule.clause == '7.5.6' and rule.uncertainty:
        checks.append(dict(id='trigger', element='过程确认触发条件', assessment_status='manual_review',
                           matched_term='', locations=[], detail=rule.uncertainty))
    return checks


def _record_date_valid(text, baseline):
    if re.search(r'计划|预计|拟定|将于', text):
        return False
    for matched in RECORD_DATE.finditer(text):
        try:
            if date(*map(int, matched.groups())) <= baseline:
                return True
        except ValueError:
            continue
    return False


def _record_has_filled_fields(text, baseline):
    lines = [line for line in text.splitlines() if not PLACEHOLDER.search(line) and not NEGATIVE.search(line)]
    return (any(_record_date_valid(line, baseline) for line in lines)
            and any(re.search(r'(?:结果|结论|实测|完成)\s*[:：]\s*\S{2,}', line) for line in lines)
            and any(re.search(r'(?:执行人|记录人|负责人|签名|审核人)\s*[:：]\s*\S{2,}', line) for line in lines))


@dataclass
class EvidenceOutcome:
    assessment_status: str
    detail: str
    evidence: str = ''
    matched_terms: list[str] = field(default_factory=list)
    missing_terms: list[str] = field(default_factory=list)
    locations: list[dict] = field(default_factory=list)
    manual_review: list[str] = field(default_factory=list)
    checks: list[dict] = field(default_factory=list)


def normalized(text):
    return unicodedata.normalize('NFKC', text).casefold()


def line_location(document, number, line, segment=None):
    quote = line if len(line) <= 300 else (segment or line)[:300]
    return dict(file_uid=document.file_uid, kind='extracted_line', line=number, quote=quote,
                excerpted=quote != line, note='抽取文本行号；不是原件页码或表格单元格坐标')


def _substantive(line, term):
    remaining = re.sub(r'[\W\d_]+', '', normalized(line).replace(normalized(term), ''))
    # 标题、仅字段名称或关键词堆叠不证明具体安排。
    if re.search(r'(?:以下|如下|包括|内容为|应规定的内容).*[:：,，]|不应执行以下|无需|没有|未规定', line):
        return False
    return len(remaining) >= 5 and bool(re.search(r'负责|应当|必须|由|采用|规定|开展|记录|保存|实施|评审|分析|执行|承担|确定|安排', line))


def _segments(document):
    for number, line in enumerate(document.text.splitlines(), 1):
        for segment in SEGMENTS.split(line):
            if segment.strip():
                yield number, line, segment, normalized(segment)


def _target_evidence(target, terms, program_reference, prepared):
    for number, line, segment, content in prepared[target.file_uid]:
        term = next((term for term, key in terms if key in content), '')
        if (term or program_reference and re.search(r'^\s*(?:\d+\s*[.、]\s*)?[^：:]*?(?:负责|应当|必须|由)', segment)) and (
                not PLACEHOLDER.search(segment) and not NEGATIVE.search(segment)
                and not re.search(r'参见|参照|引用|依据', segment) and _substantive(segment, term or '程序')):
            return line_location(target, number, line, segment)
    return None


def _group_check(document, group, index, prepared, references):
    samples = {state: [] for state in ('usable', 'pending', 'negative', 'unverified')}
    location_count = 0
    matched_term = ''
    objects = set()
    terms = [(term, normalized(term)) for term in group]
    for number, line, segment, content in prepared[document.file_uid]:
        term = next((term for term, key in terms if key in content), None)
        if not term:
            continue
        target_location = None
        if PLACEHOLDER.search(segment):
            kind = 'pending'
        elif NEGATIVE.search(segment) or FUTURE.search(segment):
            kind = 'negative'
        else:
            is_reference, target = references.locate(document.file_uid, segment)
            if target:
                target_location = _target_evidence(target, terms, group[0] == '程序引用', prepared)
                kind = 'usable' if target_location else 'unverified'
            elif is_reference:
                kind = 'pending'
            elif _substantive(segment, term) and not re.search(r'(?:以下|如下|包括|内容为)\s*[：:]', line):
                kind = 'usable'
            else:
                continue
        location_count += 1 + bool(target_location)
        if kind == 'usable':
            matched_term = matched_term or term
            objects.update(OBJECT.findall(segment))
            if target_location:
                objects.update(OBJECT.findall(target_location['quote']))
        if len(samples[kind]) < MAX_LOCATIONS:
            samples[kind].append(line_location(document, number, line, segment))
            if target_location and len(samples[kind]) < MAX_LOCATIONS:
                samples[kind].append(target_location)
    usable, pending, negative, unverified = samples.values()
    if negative and not usable and not pending and not unverified:
        state, detail = 'gap', '发现否定或拟执行表述，请核对完整上下文'
    elif negative or unverified:
        state, detail = 'manual_review', '请核对否定表述、例外或已找到引用的具体承载关系'
    elif pending:
        state, detail = 'pending_input', '存在占位或未提供可核对版本的引用依据'
    elif usable:
        state, detail = 'evidence_found', '检出有上下文的要求线索'
    else:
        state, detail = 'gap', '本次可抽取文本中未检出实质要素'
    sample_locations = {}
    for bucket in (usable[:2], pending[:1], negative[:1], unverified[:1], usable, pending, negative, unverified):
        for row in bucket:
            sample_locations[(row['file_uid'], row['line'], row['quote'])] = row
    selected = list(sample_locations.values())[:MAX_LOCATIONS]
    return dict(id=f'{index:02d}', element=group[0], assessment_status=state,
                matched_term=matched_term if state == 'evidence_found' else '',
                locations=selected, location_count=location_count, detail=detail), objects


def prepare_documents(documents):
    return {row.file_uid: list(_segments(row)) for row in documents}


def check_requirement(document, rule, purpose, context, prepared, references):
    if not document.text.strip():
        detail = '本次未取得可判定文本；请检查扫描页、图片和表格并补充可读原件'
        return EvidenceOutcome('unreadable', detail, manual_review=[rule.uncertainty] if rule.uncertainty else [],
                               checks=apply_boundaries(rule, uniform_checks(rule, 'unreadable', detail), context))
    groups = [_group_check(document, group, i, prepared, references) for i, group in enumerate(rule.check.terms, 1)]
    checks = apply_boundaries(rule, [row for row, _ in groups], context)
    states = [row['assessment_status'] for row in checks]
    state = next((state for state in ('pending_input', 'gap', 'manual_review') if state in states), 'evidence_found')
    manual = ['核对原件、授权批准、实际执行记录及过程有效性；文本线索不能证明实施。']
    locations = []
    for row in checks:
        for location in row['locations']:
            if location not in locations:
                locations.append(location)
    # 跨对象、跨章节的概念不能拼成一项完整证据链。
    objects = {obj for row, found in groups if row['assessment_status'] == 'evidence_found' for obj in found}
    if state == 'evidence_found' and len(objects) > 1:
        state = 'manual_review'
        manual.append('线索涉及多个产品对象，请分别核对承载关系；不得跨对象拼接。')
        for check in checks:
            check['assessment_status'] = 'manual_review'
    if purpose in ('report', 'record') and state == 'evidence_found':
        baseline = date.fromisoformat(context['as_of_date']) if context.get('as_of_date') else now().date()
        if not _record_has_filled_fields(document.text, baseline):
            state = 'pending_input'
            manual.append('记录用途尚需具体对象、活动日期、实际结果、执行者和关联附件。')
            checks.append(dict(id='record', element='实际执行记录', assessment_status='pending_input',
                               matched_term='', locations=[], detail='缺少实际记录对象或责任、日期、结果线索'))
    if rule.uncertainty:
        manual.append(rule.uncertainty)
    if rule.clause in ('4.2.4', '4.2.5'):
        manual.append('分别核对作废文件与记录的保存对象、寿命期、法规、放行日及起算事件；不能统一按两年判定。')
    matched = [row['matched_term'] for row in checks if row['assessment_status'] == 'evidence_found']
    missing = [row['element'] for row in checks if row['assessment_status'] != 'evidence_found']
    return EvidenceOutcome(state, '已检出要求线索，待实施取证' if state == 'evidence_found' else
                           '请核对列明的待补要素及原件；未检出不表示实际不存在',
                           '\n'.join(row['quote'] for row in locations)[:6000], matched, missing, locations, manual, checks)


def check_control(document, rule, context):
    if not document.text.strip():
        return EvidenceOutcome('unreadable', '没有可判定的抽取文本')
    matched = None
    for pattern in rule.check.patterns:
        matched = re.search(pattern, document.text, re.I | re.M)
        if matched:
            break
    if not matched:
        return EvidenceOutcome('gap', '本次可抽取文本中未检出控制字段；请核对原件及外部受控记录')
    number = document.text.count('\n', 0, matched.start()) + 1
    line = document.text.splitlines()[number - 1]
    quote = matched.group(0)
    outcome = EvidenceOutcome('evidence_found', '已检出控制信息线索', quote,
                              locations=[line_location(document, number, line)],
                              manual_review=['请核对原件及受控记录；字段和姓名存在不能证明真实有效。'])
    if rule.rule_id == 'DOC-003':
        # 批准标题后须有值；程序中的控制要求与实际批准分别处理。
        tail = document.text[matched.end():].split('\n', 1)[0].lstrip(' ：:')
        value = re.split(r'\s*(?:编制|审核|复核|发布|生效|实施)\s*[:：]', tail)[0].strip()
        if not value or PLACEHOLDER.search(value) or re.match(r'\d{4}[年./-]', value) or (NEGATIVE.search(line) and not CONTROL.search(line)):
            outcome.assessment_status, outcome.detail = 'pending_input', '批准字段没有可核对的批准值或授权依据'
        elif NEGATIVE.search(line) or CONTROL.search(line):
            outcome.assessment_status, outcome.detail = 'manual_review', '检出批准控制安排；请另提供真实批准或外部审批依据'
        else:
            outcome.evidence = quote + '：' + value[:120]
    elif rule.rule_id == 'DOC-004':
        digits = re.search(r'(\d{4})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})', quote)
        try:
            parsed = date(*map(int, digits.groups()))
        except (ValueError, AttributeError):
            outcome.assessment_status, outcome.detail = 'pending_input', '日期不是有效的日历日期，请核对原件'
        else:
            baseline = date.fromisoformat(context['as_of_date']) if context.get('as_of_date') else now().date()
            if parsed > baseline:
                outcome.assessment_status, outcome.detail = 'manual_review', '生效/发布日期晚于审核基准日，请核对本次正式依据；计划里程碑允许未来日期'
    elif PLACEHOLDER.search(quote):
        outcome.assessment_status, outcome.detail = 'pending_input', '控制信息仍为占位，请核对原件'
    return outcome
