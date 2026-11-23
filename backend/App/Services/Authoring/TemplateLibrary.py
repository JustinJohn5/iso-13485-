"""项目自有示例模板目录；模板版本随发布锁定，不宣称为官方标准文本。"""
from copy import deepcopy
import re

from App.Constants.AuthoringLimits import MAX_REQUIREMENTS_CHARS, MAX_SECTION_CHARS
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
    return {'id': key, 'title': title, 'category': category, 'version': '1.0',
            'description': description, 'fields': COMMON_FIELDS + fields,
            'sections': [{'id': f's{index}', 'title': heading, 'body': body}
                         for index, (heading, body) in enumerate(sections, 1)]}


TEMPLATES = [
    template('market-research', '市场调研报告', '设计开发', '整理产品定位、客户需求与调研结论，未知事实保留待确认项。',
             [{'key': 'requirements', 'label': '调研要求与已知事实', 'multiline': True}], [
        ('目的与范围', '组织：{company}\n项目：{project}\n本报告用于整理{product}（{model}）的市场调研输入与产品定位。'),
        ('调研输入', '{requirements}\n待确认：信息来源、调研时间、样本范围及数据真实性。'),
        ('需求分析', '围绕{product}（{model}）整理用户场景、使用需求、竞品比较及风险线索。\n待填写：实际调研数据、来源编号和分析结论。'),
        ('结论与设计输入', '将已确认需求转化为{project}的可追溯设计输入。\n待填写：需求编号、验收依据、责任人及确认记录。'),
    ]),
    template('finished-inspection', '成品检验规程', '技术文件', '根据产品技术要求生成检验文件框架，不自动编造检验限值。',
             [{'key': 'requirements', 'label': '产品技术要求与检验依据', 'multiline': True}], [
        ('目的与适用范围', '{company}的{project}项目，适用于{product}（{model}）的成品检验。'),
        ('检验依据', '{requirements}\n待确认：引用文件编号、版本及适用范围。'),
        ('检验项目与方法', '按{product}（{model}）的已批准技术要求逐项填写检验项目、方法、设备、抽样方案和判定准则。\n待填写：经确认的数值限值、单位和检验记录；不得仅凭本草稿放行产品。'),
        ('结果判定与记录', '记录{product}（{model}）的批次、实测结果、检验人和复核人。\n待填写：不合格处置、记录编号和保存要求。'),
    ]),
    template('design-plan', '设计开发计划', '设计开发', '建立阶段、交付物、职责和追溯安排。',
             [{'key': 'requirements', 'label': '项目要求、里程碑与分工', 'multiline': True}], [
        ('项目概况', '{company} / {project}\n产品：{product}\n型号：{model}'),
        ('计划输入', '{requirements}'),
        ('阶段及交付物', '为{product}（{model}）规划输入、输出、评审、验证、确认与转换活动。\n待填写：各阶段交付物、验收依据、责任人和日期。'),
        ('变更与追溯', '维护{project}需求、风险控制、设计输出和验证记录的关联。\n待填写：变更评估、评审批准和记录索引。'),
    ]),
    template('document-control', '文件控制程序', '体系文件', '形成文件编制、审批、变更与回收的过程框架。',
             [{'key': 'requirements', 'label': '适用范围与组织管理要求', 'multiline': True}], [
        ('目的与范围', '适用于{company}的{project}项目及{product}（{model}）相关文件。'),
        ('组织要求', '{requirements}'),
        ('编制、审核与发布', '待填写：编制、审核、批准的职责权限和受控发布渠道。\n文件编号：{number}；文件版本：{version}。批准、生效信息应由授权人员据实填写。'),
        ('变更、回收与记录', '待填写：修订评估、引用文件同步、旧版回收、外来文件控制和记录保留安排。'),
    ]),
]


def get_template(template_id: str) -> dict:
    found = next((item for item in TEMPLATES if item['id'] == template_id), None)
    if not found:
        raise ApiError(1701)
    return deepcopy(found)


def search_templates(query: str = '', category: str = '') -> list[dict]:
    words = query.casefold().split()
    return [deepcopy(item) for item in TEMPLATES
            if (not category or item['category'] == category)
            and all(word in (item['title'] + item['category'] + item['description']).casefold() for word in words)]


def build_snapshot(template_id: str, parameters: dict[str, str]) -> dict:
    source = get_template(template_id)
    keys = {field['key'] for field in source['fields']}
    if set(parameters) != keys:
        raise ApiError(1001, '请填写模板的全部参数，且不要提交未定义字段')
    cleaned = {}
    for key, value in parameters.items():
        limit = MAX_REQUIREMENTS_CHARS if key == 'requirements' else 120
        if not value.strip() or len(value) > limit or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', value):
            raise ApiError(1001, '模板参数为空、过长或包含不支持的控制字符')
        cleaned[key] = value.strip()
    sections = [{**section, 'body': section['body'].format_map(cleaned)} for section in source['sections']]
    return {'template_id': source['id'], 'template_version': source['version'], 'title': source['title'],
            'parameters': cleaned, 'sections': sections, 'origin': 'template', 'status': 'draft'}


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
    return result
