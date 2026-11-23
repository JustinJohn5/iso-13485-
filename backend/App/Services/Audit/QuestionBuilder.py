"""将已保存的预筛证据转成内审准备问题，不新增标准条款或作符合性判定。"""
from hashlib import sha256
from io import BytesIO

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Cm, Pt


def build_questions(run_uid: str, findings: list[dict], review: dict | None) -> dict:
    questions = []
    seen = set()

    def add(kind, title, clause, evidence, question, action, document=''):
        fingerprint = (kind, title, clause, evidence, document)
        if fingerprint in seen:
            return
        seen.add(fingerprint)
        uid = sha256(repr(fingerprint).encode()).hexdigest()[:16]
        questions.append({'id': uid, 'kind': kind, 'title': title, 'clause': clause, 'document': document,
                          'evidence': evidence, 'question': question, 'action': action})

    for finding in findings:
        if finding['status'] == 'skipped':
            continue
        failed = finding['status'] == 'fail'
        add('gap' if failed else 'verification', finding['title'], finding['clause'], finding.get('evidence', ''),
            f"针对“{finding['title']}”，{ '缺少的内容是否在原件或配套记录中存在？请展示具体位置及依据。' if failed else '请展示实际执行记录，说明该文件要求如何实施、由谁复核。'}",
            finding.get('suggestion', '') if failed else '抽取实际记录，核对批准、执行和追溯证据；文本命中不能证明过程有效。',
            finding.get('document', ''))
    if review:
        names = {item['file_uid']: item['name'] for item in review.get('documents', [])}
        selected = {uid for group in review.get('version_groups', []) if group.get('decision')
                    for uid in group['file_uids'] if uid != group['decision']['file_uid']}
        for ref in review.get('references', []):
            if ref['source_file_uid'] in selected or ref['status'] == 'linked':
                continue
            add('reference', f"引用文件待核对：{ref['number']}", '', ref.get('quote', ''),
                f"请提供 {ref['number']} 的适用受控版本，并确认引用内容、版本与当前文件一致。",
                '补充文件后重新执行关联检查；本批次未提供不表示文件不存在。', names.get(ref['source_file_uid'], ''))
        for group in review.get('requirement_conflicts', []):
            evidence = '\n'.join(f"{names.get(fact['file_uid'], fact['file_uid'])}：{fact['quote']}" for fact in group['facts'])
            add('conflict', f"跨文件要求冲突：{group['number']} / {group['field']}", '', evidence,
                '不同文件的要求为何不同？本次采用的依据是否已获确认，源文件修订与相关引用更新是否完成？',
                '依据适用要求确认取舍，修订源文件并复核所有引用；选择本次依据并不消除原文矛盾。')
    summary = {kind: sum(item['kind'] == kind for item in questions) for kind in ('gap', 'reference', 'conflict', 'verification')}
    return {'run_uid': run_uid, 'questions': questions, 'summary': summary,
            'basis': '已保存的预筛规则命中与文件集依据快照；不重新调用模型，不改变原预筛结果。',
            'disclaimer': '本清单用于模拟内审准备，缺项和冲突是待核实线索，不构成不符合项定性、完整标准审核或认证结论。'}


def export_questions(report: dict) -> bytes:
    document = Document()
    normal = document.styles['Normal']
    normal.font.name = 'Arial'
    normal.font.size = Pt(10.5)
    normal.element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), '宋体')
    document.sections[0].left_margin = document.sections[0].right_margin = Cm(2.3)
    document.add_heading('模拟内审问题清单', 0)
    document.add_paragraph('预筛任务：' + report['run_uid'])
    document.add_paragraph(report['basis'])
    document.add_paragraph(report['disclaimer'])
    labels = {'gap': '规则缺项', 'reference': '引用待核对', 'conflict': '跨文件冲突', 'verification': '实施取证'}
    for index, item in enumerate(report['questions'], 1):
        document.add_heading(f"{index}. {item['title']}", 1)
        document.add_paragraph(f"类型：{labels[item['kind']]}　条款：{item['clause'] or '文件集关联线索'}")
        document.add_paragraph('相关文件：' + (item['document'] or '见依据快照'))
        document.add_paragraph('文本依据：' + (item['evidence'] or '当前可提取文本未检出；请核对原件'))
        document.add_paragraph('审核提问：' + item['question'])
        document.add_paragraph('建议跟进：' + item['action'])
        document.add_paragraph('责任人：待填写　计划完成日期：待填写\n实际证据与结果：待填写\n复核人及有效性验证：待填写')
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()
