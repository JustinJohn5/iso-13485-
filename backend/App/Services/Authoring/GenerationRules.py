"""生成草稿的固定依据与保守文本自检；不证明真实活动或体系符合性。"""
from copy import deepcopy
import re

from App.Services.Rules.RequirementCatalog import load_catalog, requirements_for_template
from App.Services.DocumentControl.Metadata import ID_PATTERN

PENDING = re.compile(r'待(?:确认|填写|提供|补充|核实|批准|填)(?:[：:]?[^。；;\n]*)|_{2,}|□|［\s*］|\[\s*\]')
VAGUE_REFERENCE = re.compile(r'(?:参照|依据|按照|按|见)(?:相关|有关|适用)(?:受控)?(?:文件|标准|法规|程序)')
NUMBERED_REFERENCE = re.compile(r'(?:依据|按照|参照|引用|见|按)\s*(?:文件|程序|规范)?\s*' + ID_PATTERN)
ACTION = re.compile(r'应|须|负责|检查|记录|评审|制定|保存|执行|核对|提交|验证|确认|隔离|通知|归档|追溯')
ARRANGEMENT = re.compile(r'应|必须|须|负责|当.+时|在.+前|发生.+时|(?:人员|负责人|管理者)[^，。；\n]{0,12}(?:按|将|核对|维护|记录|检查)')
NON_SUBSTANTIVE = re.compile(r'(?:以下|如下|下列)(?:安排|内容|要素|要求|事项)|(?:应|须)(?:包括|规定|涵盖)的(?:内容|要素|要求)|(?:不应|无需|不必|不用|不予)(?:执行|开展|实施|进行|记录|保留|批准|评审|控制)')
CLAIMS = (
    ('日期待核实', re.compile(r'\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}日?')),
    ('签署身份待核实', re.compile(r'(?:由[^，。；\n]{1,20}(?:签字|签署|批准)|(?:签字|签署|批准人)[：:]\s*[^，。；\n]{1,20})')),
    ('实际结果待核实', re.compile(r'(?:全部|所有)[^。；\n]{0,30}(?:达到要求|满足要求|合格|通过)|(?:试验|检验|验证|确认|评审)[^。；\n]{0,15}(?:已完成|已经完成|通过|合格)|已(?:批准|实施)')),
    ('数值或技术限值待核实', re.compile(r'(?:限值|允差|抽样量)[：:\s]*\d+(?:\.\d+)?(?:\s*(?:%|％|℃|°C|MPa|mm|天|个月|年))?|\d+(?:\.\d+)?\s*(?:%|％|℃|°C|MPa|mm|天|个月|年)')),
    ('标准法规依据待核实', re.compile(r'(?:ISO|IEC|GB(?:/T)?|YY(?:/T)?)\s*\d+(?:[-:]\d+)?(?:第\d+条)?', re.I)),
)
BOUNDARY = '本自检仅提供文本待补和人工核实线索；不验证批准真实性、实际执行、法规适用性或体系符合性。'


def legacy_basis(snapshot: dict) -> dict:
    """旧草稿没有冻结目录时明确保留未知依据，不补套新版条款。"""
    return {'version': snapshot.get('template_version', 'legacy'), 'requirements': [],
            'source': '历史草稿未保存条款目录，须人工核对原依据', 'legacy': True}


def requirement_text(template_id: str, requirements: list[dict] | None = None) -> str:
    """用于新模板的编写清单，清单本身不作为已完成要素的证据。"""
    rows = requirements_for_template(template_id) if requirements is None else requirements
    return '\n'.join(f"待确认：{row['clause']} {row['title']}的本文件承载安排：{row['generation']}；"
                     '责任角色：待确认；所需依据：适用事实、受控文件编号版本及组织确认。'
                     for row in rows)


def enrich_snapshot(snapshot: dict) -> dict:
    result = deepcopy(snapshot)
    if 'requirements_basis' not in result:
        catalog = load_catalog()
        result['requirements_basis'] = {'version': catalog['version'], 'source': deepcopy(catalog['source']),
                                        'requirements': requirements_for_template(result['template_id'])}
    basis = result['requirements_basis']
    pending, reference_gaps, missing, manual = [], [], [], []
    substantive = []
    for section in result['sections']:
        for line in section['body'].splitlines():
            if NON_SUBSTANTIVE.search(line):
                manual.append({'section_id': section['id'], 'item': '否定或非实质清单', 'quote': line[:1000],
                               'reason': '仅列举应有内容或否定执行，不能作为已规定可执行控制的线索'})
            for item, pattern in CLAIMS:
                for match in pattern.finditer(line):
                    manual.append({'section_id': section['id'], 'item': item, 'quote': match.group(),
                                   'reason': '需逐项核对来源、对象、适用版本及真实证据；文本相同也不能证明来源已批准'})
            for match in PENDING.finditer(line):
                pending.append({'section_id': section['id'], 'item': match.group(),
                                'reason': '占位或未确认信息，不能视为真实记录或批准依据'})
            if VAGUE_REFERENCE.search(line):
                reference_gaps.append({'section_id': section['id'], 'item': line,
                                       'reason': '引用不能定位，请补充受控文件编号、版本及适用范围'})
            for match in NUMBERED_REFERENCE.finditer(line):
                if match.group(1) != result.get('parameters', {}).get('number'):
                    reference_gaps.append({'section_id': section['id'], 'item': match.group(1),
                                           'reason': '尚未验证引用目标、适用版本及范围，请提供受控原件或可取证索引'})
            # 清单、标题、占位及孤立关键词不作为可执行安排的线索。
            if (not PENDING.search(line) and not NON_SUBSTANTIVE.search(line) and len(line) > 20 and ACTION.search(line)
                    and ARRANGEMENT.search(line) and re.search(r'[，,；;。]', line)):
                substantive.append((section['id'], line))
    for requirement in basis.get('requirements', []):
        groups = requirement.get('terms', [])
        missing_terms = [group[0] for group in groups
                         if not any(any(term.casefold() in line.casefold() for term in group) for _, line in substantive)]
        if not groups or missing_terms:
            missing.append({'rule_id': requirement['rule_id'], 'clause': requirement['clause'],
                            'item': requirement['title'], 'missing_terms': missing_terms,
                            'reason': '未定位到覆盖全部要素的实质安排，需补充或人工核对明确引用'})
        if requirement.get('conditions'):
            manual.append({'rule_id': requirement['rule_id'], 'clause': requirement['clause'],
                           'item': '适用性待确认', 'reason': '需确认条件：' + '、'.join(requirement['conditions']) + '；外包不免除责任'})
        if requirement.get('uncertainty'):
            manual.append({'rule_id': requirement['rule_id'], 'clause': requirement['clause'],
                           'item': '来源疑点', 'reason': str(requirement['uncertainty'])})
    manual.append({'item': '授权、来源与实际执行核实', 'reason': BOUNDARY})
    if basis.get('legacy'):
        manual.append({'item': '历史依据待核对', 'reason': basis['source']})
    result['generation_review'] = {'status': 'needs_review', 'pending_count': len(pending), 'pending': pending,
                                   'reference_gaps': reference_gaps, 'missing_requirements': missing,
                                   'manual_review': manual, 'basis_version': basis['version'], 'boundary': BOUNDARY}
    return result
