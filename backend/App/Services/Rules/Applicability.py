"""根据明确条件与文件承载范围路由，未知事实不能作为不适用。"""
import re


def applicable_targets(rule, documents, purpose_for):
    if '*' in rule.document_types:
        return documents
    selected = []
    for document in documents:
        # 正文中偶然出现业务词不构成承载关系。模板与明确文件标题优先。
        headings = [line for line in document.text.splitlines()[:2]
                    if len(line.strip()) < 45 and not re.search(r'[。；：:]|负责|执行|通知', line)]
        title = document.name + '\n' + '\n'.join(headings)
        explicit_topic = any(term.casefold() in title.casefold() for term in rule.topics)
        purpose = purpose_for(document)
        if (rule.clause.startswith('7.3.') and document.document_type == 'design_control'
                and not document.template_id and purpose in ('plan', 'record', 'form', 'report', 'instruction')):
            if purpose == 'plan' and rule.clause in ('7.3.1', '7.3.2') or explicit_topic:
                selected.append(document)
            continue
        if document.template_id and document.template_id in rule.templates:
            selected.append(document)
        elif document.document_type in rule.document_types:
            if document.document_type not in ('procedure', 'other') or explicit_topic:
                selected.append(document)
        elif document.document_type in ('procedure', 'other') and explicit_topic:
            selected.append(document)
    return selected


def condition_state(rule, context):
    """多个条件按保守OR处理；复合条款拆分前禁止因一个条件为否免除整体。"""
    if not rule.conditions:
        return None, ''
    facts = context.get('facts', {})
    values = [facts.get(key, 'unknown') for key in rule.conditions]
    if 'yes' in values:
        return None, ''
    if 'unknown' in values:
        return 'pending_input', '适用条件待确认：' + '、'.join(rule.conditions)
    if rule.clause.startswith('4.'):
        return 'out_of_scope', '本次已声明无触发对象；仍保留第4章要求，新增对象时应重新评估'
    decision = next((row for row in context.get('decisions', []) if row['clause'] == rule.clause), None)
    if not decision:
        return 'pending_input', '条件声明为不适用，但尚未提供条款理由和依据'
    if 'design' in rule.conditions:
        return 'manual_review', '设计开发删减须核对适用法规允许依据；外包不能免除组织责任'
    if not decision.get('confirmed_by') or not decision.get('confirmed_at'):
        return 'manual_review', '不适用声明须由有权限人员提交并由服务端记录确认'
    return 'not_applicable', f"不适用理由：{decision['reason']}；依据：{decision['basis']}"


def check_boundary(rule, element, context):
    """拆开复合条款的条件和译文疑点，保留其他子项原有判定。"""
    fact = None
    if rule.clause == '7.5.6':
        fact = 'software' if element.startswith('软件') else 'process_validation'
    elif rule.clause == '6.4.2' and element in (
            '无菌专用要求', '微生物控制', '微粒控制', '装配清洁度', '包装清洁度'):
        fact = 'sterile'
    if rule.uncertainty and (rule.clause == '8.5.3' and element == '不利影响核查'
                            or rule.clause not in ('6.4.2', '7.5.6', '8.5.3')):
        return 'manual_review', rule.uncertainty
    if not fact:
        return None, ''
    value = context.get('facts', {}).get(fact, 'unknown')
    if value == 'unknown':
        return 'pending_input', '此要素的适用条件待确认：' + fact
    if value == 'no':
        return 'manual_review', '已声明当前无对应对象，请核对范围和依据；本声明不排除整条要求'
    return None, ''
