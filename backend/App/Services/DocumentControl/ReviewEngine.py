"""文件集快照、引用关系与确认决策；纯内存计算，不执行数据库操作。"""
from copy import deepcopy
from datetime import date

from App.Services.DocumentControl.Metadata import extract_metadata, extract_references
from App.Services.DocumentControl.Requirements import build_retention_review, retention_facts
from App.Services.DocumentControl.Versions import build_version_groups, ineligible, selected_documents
from App.Utils.Errors import ApiError
from App.Utils.TimeUtils import now


def refresh_relations(snapshot: dict) -> None:
    selected = selected_documents(snapshot)
    by_number = {}
    for row in selected:
        number = row['metadata']['number']
        if number and row['metadata']['layer'] != 'record':
            targets = by_number.setdefault(number, [])
            if not any(target['sha256'] == row['sha256'] for target in targets):
                targets.append(row)
    unresolved = {group['number'] for group in snapshot['version_groups'] if not group['decision']}
    references = []
    for row in selected:
        for ref in row['references']:
            targets = by_number.get(ref['number'], [])
            state = 'pending' if ref['number'] in unresolved or len(targets) > 1 else 'linked' if targets else 'missing'
            references.append({**ref, 'source_file_uid': row['file_uid'],
                               'target_file_uids': [target['file_uid'] for target in targets], 'status': state})
    snapshot['references'] = references
    previous = {item['id']: item for item in snapshot.get('requirement_conflicts', [])}
    issues, manual = build_retention_review(selected)
    for issue in issues:
        old = previous.get(issue['id'])
        if old and old['facts'] == issue['facts']:
            issue['decision'] = old.get('decision')
    snapshot['requirement_conflicts'] = issues
    snapshot['requirement_manual'] = manual


def build_review(files: list, as_of: date, overrides: dict[str, dict]) -> dict:
    documents = []
    for row in files:
        metadata = extract_metadata(row.original_name, row.extracted_text, row.document_type)
        changes = overrides.get(row.file_uid, {})
        for key, value in changes.items():
            metadata[key] = value
            metadata['sources'] = [source for source in metadata['sources'] if source['field'] != key]
            metadata['sources'].append({'field': key, 'quote': '用户校正元数据，需以原件核对', 'line': 0})
        document = {'file_uid': row.file_uid, 'name': row.original_name, 'sha256': row.sha256,
                          'document_type': row.document_type, 'metadata': metadata, 'text': row.extracted_text,
                          'references': extract_references(row.extracted_text, metadata['number'])}
        document['retention_facts'] = retention_facts(document)
        documents.append(document)
    snapshot = {'as_of_date': as_of.isoformat(), 'documents': documents,
                'version_groups': build_version_groups(documents, as_of.isoformat()), 'decision_history': []}
    refresh_relations(snapshot)
    # 快照只保留必要证据，不再复制全部正文。
    for row in documents:
        row.pop('text')
    return snapshot


def decide(snapshot: dict, kind: str, issue: str, file_uid: str, reason: str, user_id: int) -> dict:
    result = deepcopy(snapshot)
    group_key = 'version_groups' if kind == 'version' else 'requirement_conflicts'
    group = next((item for item in result[group_key] if item['id'] == issue), None)
    if not group or file_uid not in group['file_uids']:
        raise ApiError(1001, '选择的文件不属于当前冲突')
    row = next(item for item in result['documents'] if item['file_uid'] == file_uid)
    if kind == 'version' and (problem := ineligible(row, result['as_of_date'])):
        raise ApiError(1001, problem)
    if kind == 'requirement':
        facts = [fact for fact in group['facts'] if fact['file_uid'] == file_uid]
        if len({(fact['months'], fact['minimum']) for fact in facts}) != 1:
            raise ApiError(1001, '该文件内部也存在不同保存期限，请先修正原件')
    decision = {'file_uid': file_uid, 'reason': reason.strip(), 'user_id': user_id, 'confirmed_at': now().isoformat(),
                'kind': kind, 'issue_id': issue}
    group['decision'] = decision
    result['decision_history'].append(decision)
    if kind == 'version':
        refresh_relations(result)
    return result


def review_ready(snapshot: dict) -> bool:
    return all(group.get('decision') for group in snapshot['version_groups'] + snapshot['requirement_conflicts'])
