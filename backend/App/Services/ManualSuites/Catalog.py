"""整套示例目录与模板；不包含标准原文，不编造已实施记录。"""
from copy import deepcopy

from App.Services.Authoring.TemplateLibrary import COMMON_FIELDS, get_template
from App.Services.Authoring.GenerationRules import requirement_text


# 编号保持独立；目录描述适用内容，是否适用仍由组织核对。
ENTRIES = [
    ('quality-manual', '质量手册', 'QM-01', 'quality_manual', '质量体系', [
        ('体系范围与适用性', '说明组织、场所、产品及适用要求；逐项论证不适用要求。'),
        ('过程及相互关系', '列出过程输入输出、职责、资源、过程顺序和相互作用，以及外包过程控制。'),
        ('文件体系与引用', '列出程序文件编号、版本、适用范围及受控文件清单；建立记录追溯。'),
        ('管理、资源与产品实现', '明确管理承诺、方针目标、资源配置、产品实现、测量分析及改进的安排。')]),
    ('quality-policy', '质量方针与目标', 'QO-01', 'other', '质量体系', [
        ('方针与承诺', '依据组织宗旨、产品特点和适用法规拟定质量方针，提交管理者批准。'),
        ('目标及评价', '逐项填写可测量目标、责任人、统计口径、评价频次及改进安排。')]),
    ('record-control', '记录控制程序', 'QP-02', 'procedure', '程序文件', [
        ('标识与保存', '规定记录标识、填写、更正、存储、防护、检索、保存期限及处置职责。'),
        ('访问与保密', '确认电子记录访问控制、备份恢复及保密要求，保存期限依据产品和法规逐项填写。')]),
    ('management-review', '管理评审程序', 'QP-03', 'management_review', '程序文件', [
        ('评审安排与输入', '填写评审频次、参加人员、审核结果、反馈投诉、过程绩效、纠正措施及法规变化输入。'),
        ('评审输出与跟进', '记录质量体系和产品改进、资源需求、责任人、完成期限及跟进验证。')]),
    ('training', '人力资源与培训程序', 'QP-04', 'procedure', '程序文件', [
        ('能力要求', '确定影响产品质量岗位的教育、培训、技能和经验要求。'),
        ('培训及评价', '制定培训计划，评价措施有效性，保留能力、培训和意识记录。')]),
    ('infrastructure', '基础设施与工作环境程序', 'QP-05', 'procedure', '程序文件', [
        ('设施维护', '列出设备、建筑、辅助设施及维护要求和职责。'),
        ('环境与污染控制', '按产品风险确认工作环境、健康清洁及污染控制要求，记录监测和异常处置。')]),
    ('risk-management', '风险管理程序', 'QP-06', 'risk_management', '程序文件', [
        ('计划与风险分析', '确定风险管理范围、职责、方法及风险可接受准则，开展危害识别和风险分析。'),
        ('控制与评审', '定义风险控制、验证、剩余风险评价及生产和生产后信息的反馈与更新。')]),
    ('purchasing', '采购与供应商控制程序', 'QP-07', 'purchasing', '程序文件', [
        ('供应商评价', '按采购产品风险规定供应商选择、评价、监视和重新评价准则。'),
        ('采购信息与验证', '填写采购要求、批准职责、变更沟通、进货验证及不合格跟进记录。')]),
    ('production', '生产与服务控制程序', 'QP-08', 'procedure', '程序文件', [
        ('过程控制', '规定作业文件、设备、人员、环境、过程参数及生产记录，数值须来自已批准技术依据。'),
        ('特殊过程与服务', '确认适用的过程验证、安装、服务、清洁和灭菌要求，保留验证及再验证记录。')]),
    ('traceability', '标识与可追溯性程序', 'QP-09', 'procedure', '程序文件', [
        ('标识与状态', '规定物料、在制品、成品及检验状态的标识和职责，防止混淆。'),
        ('追溯与防护', '确定批次、序列号和流向记录，管理顾客财产、储存、防护及交付。')]),
    ('monitoring', '监视与测量设备控制程序', 'QP-10', 'procedure', '程序文件', [
        ('设备与校准', '建立设备清单、量程及精度要求、校准或检定计划、状态标识和使用记录。'),
        ('异常与软件', '规定失准影响评价、已测产品追溯，以及相关软件确认与变更控制。')]),
    ('complaints', '反馈投诉与法规报告程序', 'QP-11', 'procedure', '程序文件', [
        ('反馈与投诉', '规定反馈收集、投诉登记、调查、评价、职责分工及纠正措施衔接。'),
        ('法规报告', '依据适用市场法规明确报告判定、时限、审批和记录，不自动假定法规适用性。')]),
    ('internal-audit', '内部审核程序', 'QP-12', 'internal_audit', '程序文件', [
        ('审核策划', '依据过程状态及既往结果制定审核计划，明确范围、准则、方法及独立性。'),
        ('实施与跟进', '规定审核取证、报告、不符合项、纠正措施及有效性验证的职责和记录。')]),
    ('nonconformity', '不合格品控制程序', 'QP-13', 'nonconformity', '程序文件', [
        ('识别隔离与评审', '明确不合格品标识、隔离、评审和处置授权，防止非预期使用。'),
        ('处置与追溯', '规定返工、让步、报废及交付后不合格处理，验证处置结果并保存记录。')]),
    ('corrective-action', '纠正预防措施与数据分析程序', 'QP-14', 'procedure', '程序文件', [
        ('分析与原因调查', '确定反馈、过程、产品及供应商数据的收集和分析方法，识别改进和措施需求。'),
        ('措施与有效性', '开展原因分析、措施策划、实施和验证，评价对安全性能及法规符合性的影响。')]),
    ('record-forms', '体系记录表单清单与填写要求', 'QR-01', 'other', '记录框架', [
        ('表单目录', '列出培训、评审、审核、采购、检验、不合格及措施等适用表单编号和版本。'),
        ('填写与证据', '逐项设置日期、对象、执行人、结果、复核及附件字段。此处仅为空白记录框架，不生成虚构记录。')]),
]

EXISTING = [
    ('document-control', 'QP-01', 'procedure'),
    ('design-plan', 'DP-01', 'design_control'),
    ('finished-inspection', 'WI-01', 'procedure'),
    ('market-research', 'MR-01', 'design_control'),
]


def catalog() -> list[dict]:
    result = [dict(key=key, title=title, number=number, document_type=kind, category=category)
              for key, title, number, kind, category, _ in ENTRIES]
    for key, number, kind in EXISTING:
        source = get_template(key)
        result.append(dict(key=key, title=source['title'], number=number,
                           document_type=kind, category=source['category']))
    return result


def suite_template(key: str) -> dict:
    found = next((row for row in ENTRIES if row[0] == key), None)
    if not found:
        return get_template(key)
    _, title, _, _, category, sections = found
    prefix = '组织：{company}\n项目：{project}\n产品：{product}（{model}）\n'
    result = deepcopy(dict(id=key, title=title, category=category, version='2.0',
                         fields=COMMON_FIELDS + [dict(key='requirements', label='已知输入')],
                         sections=[dict(id=f's{i}', title=heading, body=prefix +
                                        ('已知输入：{requirements}\n' if i == 1 else '') + '待填写并核实：' + body)
                                   for i, (heading, body) in enumerate(sections, 1)]))
    result['sections'][0]['body'] += ('\n流程责任角色应在活动启动或变更时核对适用范围、输入及受控依据，'
        '按批准准则组织执行，保留对象、版本、日期、执行角色、结果与附件关联；'
        '依据缺失、超限或版本冲突时暂停受影响活动，提交授权角色评审并跟踪处理。'
        '\n待确认：组织活动、职责权限、引用编号版本、实施方法及接收准则；责任角色：待确认；所需依据：组织事实与受控文件。')
    result['sections'][-1]['body'] += '\n' + requirement_text(key)
    if key == 'record-control':
        result['sections'][-1]['body'] += ('\n保存安排须同时识别组织确定的器械寿命期、从产品放行日期起两年及适用法规，'
            '不同起算事件先核对可比到期日，特殊法规关系交人工确认；依据未明不得确定销毁日期。')
    if key == 'record-forms':
        result['sections'][-1]['body'] += '\n日期：____；对象：____；执行人：____；实际结果：待填写；复核：____；附件索引：____。'
    return result
