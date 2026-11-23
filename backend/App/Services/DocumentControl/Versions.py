"""同编号版本冲突：建议与人工正式版确认分离，不以类别顺序裁决。"""
from collections import defaultdict
from hashlib import sha256


def issue_id(kind: str, value: str) -> str:
    return kind + '-' + sha256(value.encode()).hexdigest()[:16]


def ineligible(document: dict, as_of: str) -> str:
    metadata = document['metadata']
    if metadata['layer'] in {'record', 'unknown'}:
        return '需先确认文件层级；已填写记录不参与正式版本替换'
    if metadata['status'] in {'draft', 'obsolete'}:
        return '草稿、未批准或作废文件不能确认为本次正式版'
    if metadata['effective_date'] and metadata['effective_date'] > as_of:
        return '尚未到生效日期'
    return ''


def build_version_groups(documents: list[dict], as_of: str) -> list[dict]:
    numbered = defaultdict(list)
    for document in documents:
        metadata = document['metadata']
        # 模板编号经常出现在每一份实际记录上，不能据此删除记录实例。
        if metadata['number'] and metadata['layer'] != 'record':
            numbered[metadata['number']].append(document)
    result = []
    for number, rows in numbered.items():
        if len({row['sha256'] for row in rows}) < 2:
            continue
        reasons = {row['file_uid']: ineligible(row, as_of) for row in rows}
        eligible = [row for row in rows if not reasons[row['file_uid']]]
        suggested, explanation = '', '证据不足或层级未确认，请核对原件后选择'
        revisions = defaultdict(set)
        for row in rows:
            revisions[row['metadata']['revision']].add(row['sha256'])
        same_revision = any(revision and len(hashes) > 1 for revision, hashes in revisions.items())
        if same_revision:
            explanation = '同编号同版本存在不同内容，不按日期自动推荐'
        elif len(eligible) == 1:
            suggested = eligible[0]['file_uid']
            explanation = '其余候选存在明确排除条件；仍需核对批准和适用性'
        elif eligible and all(row['metadata']['effective_date'] for row in eligible):
            latest = max(row['metadata']['effective_date'] for row in eligible)
            newest = [row for row in eligible if row['metadata']['effective_date'] == latest]
            if len(newest) == 1:
                suggested = newest[0]['file_uid']
                explanation = '按审核日期内的最新生效日期建议；不按上传时间或文件类别排序'
        result.append({'id': issue_id('version', number), 'number': number,
                       'file_uids': [row['file_uid'] for row in rows], 'ineligible': reasons,
                       'suggested_file_uid': suggested, 'explanation': explanation, 'decision': None})
    return result


def selected_documents(snapshot: dict) -> list[dict]:
    excluded = set()
    for group in snapshot['version_groups']:
        decision = group.get('decision')
        if decision:
            excluded.update(uid for uid in group['file_uids'] if uid != decision['file_uid'])
    return [row for row in snapshot['documents'] if row['file_uid'] not in excluded]
