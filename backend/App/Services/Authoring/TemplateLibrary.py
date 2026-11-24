"""项目自有示例模板目录；模板版本随发布锁定，不宣称为官方标准文本。"""
from copy import deepcopy
import re

from App.Constants.AuthoringLimits import MAX_REQUIREMENTS_CHARS, MAX_SECTION_CHARS
from App.Services.Authoring.GenerationRules import enrich_snapshot, legacy_basis, requirement_text
from App.Utils.Errors import ApiError

COMMON_FIELDS = [
    {'key': 'company', 'label': '组织名称'},
    {'key': 'project', 'label': '项目名称'},
    {'key': 'product', 'label': '产品名称'},
    {'key': 'model', 'label': '产品型号'},
    {'key': 'number', 'label': '文件编号'},
    {'key': 'version', 'label': '文件版本'},
]


def template(key, title, category, description, fields, sections):
    return {'id': key, 'title': title, 'category': category, 'version': '2.0',
            'description': description, 'fields': COMMON_FIELDS + fields,
            'sections': [{'id': f's{index}', 'title': heading, 'body': body}
                         for index, (heading, body) in enumerate(sections, 1)]}


TEMPLATES = [
    template('market-research', '市场调研报告', '设计开发', '整理产品定位、客户需求与调研结论，未知事实保留待确认项。',
             [{'key': 'requirements', 'label': '调研要求与已知事实', 'multiline': True}], [
        ('目的与范围', '组织：{company}\n项目：{project}\n本报告用于整理{product}（{model}）的市场调研输入与产品定位。'),
        ('调研输入', '{requirements}\n调研负责人应逐项登记资料来源、取得时间、样本范围、方法及局限，区分已确认事实与法规线索，不补造销量或访谈。\n待确认：预期用途、目标使用者、使用情形及资料真实性；责任角色：调研负责人；所需依据：原始资料及组织确认。'),
        ('需求分析', '围绕{product}（{model}），调研负责人按顾客明示与交付后要求、预期用途必需要求、适用法规线索、安全性能所需培训及组织附加要求分类。每项分析须关联来源，未知或矛盾项提交需求评审，不直接认定法规合规。\n待确认：实际数据、分析方法和局限；责任角色：调研负责人；所需依据：来源编号及原始资料。'),
        ('结论与设计输入', '需求负责人将已确认需求转化为{project}的设计输入，赋予追溯标识、核对完整明确可验证且无矛盾后提交评审；记录输入版本、交接对象和未解决事项，未经确认不进入确定性结论。\n待确认：需求编号、验收依据和交接记录；责任角色：需求负责人；所需依据：已确认需求及受控索引。'),
    ]),
    template('finished-inspection', '成品检验规程', '技术文件', '根据产品技术要求生成检验文件框架，不自动编造检验限值。',
             [{'key': 'requirements', 'label': '产品技术要求与检验依据', 'multiline': True}], [
        ('目的与适用范围', '{company}的{project}项目，适用于{product}（{model}）的成品检验。'),
        ('检验依据', '{requirements}\n检验负责人在使用前核对技术要求的受控编号、版本、适用产品与检验阶段，发生版本冲突时停止使用并提交技术评审。\n待确认：引用文件编号、版本及适用范围；责任角色：检验负责人；所需依据：批准的技术要求。'),
        ('检验项目与方法', '检验人员按{product}（{model}）已批准技术要求逐项登记检验特性、方法、设备识别、抽样依据、接收准则及记录字段。数值、单位、公差和抽样量必须引用技术依据，不在本规程推测填写；使用前检查设备适用性及校准状态，设备异常时停止测量并评价既往结果。\n待确认：限值、单位、抽样依据及适用设备；责任角色：检验负责人；所需依据：批准的检验规范；不得仅凭本草稿放行产品。'),
        ('结果判定与记录', '检验人员记录{product}（{model}）批次、实测结果、接收依据、适当的设备识别及执行人；完成策划检验并确认满足接收准则后，授权放行人员方可决定放行。植入产品另核对检验试验人员身份要求。检验未完成、不满足接收准则或设备异常时应隔离、评审并按不合格控制处理，返工后重新验证。\n待确认：放行权限、记录编号、保存依据及异常接口；责任角色：检验负责人；所需依据：受控授权和相关程序。空白记录不得预填“合格”。'),
    ]),
    template('design-plan', '设计开发计划', '设计开发', '建立阶段、交付物、职责和追溯安排。',
             [{'key': 'requirements', 'label': '项目要求、里程碑与分工', 'multiline': True}], [
        ('项目概况', '{company} / {project}\n产品：{product}\n型号：{model}'),
        ('计划输入', '{requirements}\n项目负责人应识别需求与用途、法规标准、风险管理输出及适当的类似设计信息，核对输入完整、明确、可验证且无矛盾；输入冲突须提交评审后决定。\n待确认：设计适用范围、引用编号版本和输入批准权限；责任角色：项目负责人；所需依据：确认事实及设计控制程序。'),
        ('阶段及交付物', '为{product}（{model}），项目负责人按输入、输出、阶段评审、验证、确认和转换策划里程碑、接口与交付物；为各阶段配置权限、人员能力及资源，并随进展适当更新计划。\n验证计划应追溯输出是否满足输入，确认计划应评价产品是否满足预期用途；分别明确方法、接收准则、适当统计抽样依据及连接组合。确认应说明代表性产品及选择理由、适用评价，并安排在交付使用前完成。转换前评价制造规范适宜性与生产能力。\n待确认：阶段交付物、准则、资源和计划日期；责任角色：项目负责人；所需依据：批准的项目安排。本计划不替代实际评审、验证、确认或转换报告。'),
        ('变更与追溯', '项目负责人维护{project}输入、风险、输出、评审、验证、确认、转换及变更记录的追溯索引，并按器械类型或器械族维护设计开发文件。更改实施前应评价对组件、在制及已交付产品、风险和实现过程的影响，完成评审、验证、适当确认及批准；缺证时暂停受影响活动并升级处理。\n待确认：输出到输入追溯方法、变更权限及文件索引；责任角色：项目负责人；所需依据：受控设计程序与组织授权。'),
    ]),
    template('document-control', '文件控制程序', '体系文件', '形成文件编制、审批、变更与回收的过程框架。',
             [{'key': 'requirements', 'label': '适用范围与组织管理要求', 'multiline': True}], [
        ('目的与范围', '适用于{company}的{project}项目及{product}（{model}）相关文件。'),
        ('组织要求', '{requirements}'),
        ('编制、审核与发布', '编制人员应核对适用范围和引用版本，文件发布前由授权角色评审充分性并批准；文控人员识别编号、修订状态和生效状态，在使用处提供适用版本并保持清晰可识别。未批准或版本冲突时暂停发布，提交授权角色处理。\n文件编号：{number}；文件版本：{version}。批准、生效信息应由授权人员据实填写。\n待确认：编制审核批准权限与发布渠道；责任角色：文控负责人；所需依据：组织授权及受控发布安排。'),
        ('变更、回收与记录', '文控人员在更改时保留背景信息，由原批准职能或已指定的授权职能评审批准，必要时更新并重新批准；同步引用文件、标识修订并通知使用处。识别外来文件并控制分发，防止退化遗失，回收作废版本并保留防误用标识。\n至少保留一份作废受控文件，确保制造及试验文件按器械寿命期和记录要求可获得，并结合适用法规确定安排。记录控制应另规定标识、存储、安全完整、检索、保密、变更可识别和处置；已填写记录不得以表单换版覆盖原痕迹。保存要求须核对组织确定的寿命期、从产品放行日起两年及适用法规，不统一写成保存两年后删除。\n待确认：作废文件与业务记录各自保存对象、起算事件、期限及法规关系；责任角色：文控负责人；所需依据：寿命期、放行日期、受控法规和记录程序。'),
    ]),
]


def get_template(template_id: str) -> dict:
    found = next((item for item in TEMPLATES if item['id'] == template_id), None)
    if not found:
        raise ApiError(1701)
    result = deepcopy(found)
    result['sections'][-1]['body'] += '\n' + requirement_text(template_id)
    return result


def search_templates(query: str = '', category: str = '') -> list[dict]:
    words = query.casefold().split()
    return [deepcopy(item) for item in TEMPLATES
            if (not category or item['category'] == category)
            and all(word in (item['title'] + item['category'] + item['description']).casefold() for word in words)]


def clean_parameters(source: dict, parameters: dict[str, str]) -> dict:
    keys = {field['key'] for field in source['fields']}
    if set(parameters) != keys:
        raise ApiError(1001, '请填写模板的全部参数，且不要提交未定义字段')
    cleaned = {}
    for key, value in parameters.items():
        limit = MAX_REQUIREMENTS_CHARS if key == 'requirements' else 120
        if not isinstance(value, str) or not value.strip() or len(value) > limit or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', value):
            raise ApiError(1001, '模板参数为空、过长或包含不支持的控制字符')
        cleaned[key] = value.strip()
    return cleaned


def build_snapshot(template_id: str, parameters: dict[str, str]) -> dict:
    source = get_template(template_id)
    cleaned = clean_parameters(source, parameters)
    sections = [{**section, 'body': section['body'].format_map(cleaned)} for section in source['sections']]
    return enrich_snapshot({'template_id': source['id'], 'template_version': source['version'], 'title': source['title'],
                            'parameters': cleaned, 'sections': sections, 'origin': 'template', 'status': 'draft'})


def rewrite_parameter_text(body: str, previous: dict[str, str], cleaned: dict[str, str]) -> str:
    """优先按明确字段替换；同值多义时拒绝猜测，短数字不做全文替换。"""
    labels = {'company': '组织(?:名称)?|公司(?:名称)?', 'project': '项目(?:名称)?',
              'product': '产品(?:名称)?', 'model': '产品型号|型号', 'number': '文件编号',
              'version': '文件版本|版本', 'requirements': '已知输入|组织要求|计划输入'}
    changed = {key: value for key, value in previous.items() if key in cleaned and value != cleaned[key]}
    if not changed:
        return body
    alternatives = []
    for key, old in changed.items():
        prefix = rf'(?:^|(?<=[。；;\n]))[ \t]*(?:{labels[key]})[ \t]*[：:][ \t]*'
        if key == 'model' and previous.get('product'):
            prefix = rf'(?:{prefix}|{re.escape(previous["product"])}[（(])'
        alternatives.append(rf'(?P<{key}>(?P<{key}_prefix>{prefix}){re.escape(old)})(?![A-Za-z0-9._/-])')
    labeled = re.compile('|'.join(alternatives))
    unlabeled = labeled.sub('', body)
    targets = {}
    for key, old in previous.items():
        targets.setdefault(old, set()).add(cleaned.get(key, old))
    ambiguous = {old for old in changed.values() if len(targets[old]) > 1}
    if any(old in unlabeled for old in ambiguous):
        raise ApiError(1001, '历史正文中参数同值但含义不同，无法确定替换位置；原草稿已保留，请先明确字段或人工修订')
    literals = {old: cleaned[key] for key, old in changed.items()
                if key not in {'version', 'requirements'} and old not in ambiguous and not re.fullmatch(r'[\d\W]+', old)}
    if literals:
        alternatives.append(r'(?P<literal>(?<![A-Za-z0-9._/-])(?:' + '|'.join(re.escape(old) for old in sorted(literals, key=len, reverse=True))
                            + r')(?![A-Za-z0-9._/-]))')
    pattern = re.compile('|'.join(alternatives))

    def replace(match):
        if match.groupdict().get('literal') is not None:
            return literals[match.group('literal')]
        key = next(key for key in changed if match.group(key) is not None)
        return match.group(key + '_prefix') + cleaned[key]

    return pattern.sub(replace, body)


def regenerate_snapshot(snapshot: dict, parameters: dict[str, str]) -> dict:
    """更新参数并重新自检；历史模板和依据不会因新版发布静默替换。"""
    source = next((deepcopy(row) for row in TEMPLATES if row['id'] == snapshot['template_id']), None)
    if source is None:
        raise ApiError(1701)
    cleaned = clean_parameters(source, parameters)
    basis = deepcopy(snapshot.get('requirements_basis', legacy_basis(snapshot)))
    if snapshot.get('template_version') == source['version']:
        source['sections'][-1]['body'] += '\n' + requirement_text(snapshot['template_id'], basis['requirements'])
        result = {**deepcopy(snapshot), 'parameters': cleaned, 'origin': 'template',
                  'sections': [{**row, 'body': row['body'].format_map(cleaned)} for row in source['sections']]}
    else:
        result = deepcopy(snapshot)
        previous = snapshot['parameters']
        for section in result['sections']:
            section['body'] = rewrite_parameter_text(section['body'], previous, cleaned)
        result['parameters'] = cleaned
        result['origin'] = 'template'
    result['requirements_basis'] = basis
    return enrich_snapshot(result)


def edit_sections(snapshot: dict, changes: dict[str, str]) -> dict:
    result = deepcopy(snapshot)
    ids = {section['id'] for section in result['sections']}
    if not changes or not set(changes).issubset(ids):
        raise ApiError(1001, '正文必须对应现有模板章节')
    for section in result['sections']:
        if section['id'] not in changes:
            continue
        body = changes[section['id']].strip()
        if not body or len(body) > MAX_SECTION_CHARS or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', body):
            raise ApiError(1001, '章节内容为空、过长或包含不支持的控制字符')
        section['body'] = body
    result['origin'] = 'manual'
    result.setdefault('requirements_basis', legacy_basis(snapshot))
    return enrich_snapshot(result)
