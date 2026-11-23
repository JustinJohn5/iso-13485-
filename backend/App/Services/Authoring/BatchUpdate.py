"""批量查询与 executemany 更新；任一草稿过期或无权访问时整批拒绝。"""
from sqlalchemy import select

from App.Models.AuditLog import AuditLog
from App.Models.DocumentDraft import DocumentDraft
from App.Services.Authoring.DraftStore import history_entry
from App.Services.Authoring.TemplateLibrary import build_snapshot
from App.Utils.Errors import ApiError


def build_batch_plan(rows, payload, user):
    selected = {item.draft_uid: item.revision for item in payload.drafts}
    if len(selected) != len(payload.drafts):
        raise ApiError(1001, '批量草稿不可重复')
    if len(rows) != len(selected):
        raise ApiError(1702)
    plan = []
    for row in rows:
        if row.created_by != user.id and user.role != 'admin':
            raise ApiError(1104)
        if row.revision != selected[row.draft_uid]:
            raise ApiError(1703)
        changes = {key: {'before': row.snapshot['parameters'][key], 'after': value.strip()}
                   for key, value in payload.parameters.items() if row.snapshot['parameters'][key] != value.strip()}
        if not changes:
            continue
        if len(row.history) >= 50:
            raise ApiError(1001, '所选草稿中有修订达到50次的文件，请先新建草稿')
        snapshot = build_snapshot(row.snapshot['template_id'], {**row.snapshot['parameters'], **payload.parameters})
        plan.append({'row': row, 'snapshot': snapshot, 'changes': changes})
    if not plan:
        raise ApiError(1001, '参数没有变化，无需重新生成草稿')
    return plan


def load_batch(db, user, payload, *, lock=False):
    # 每批最多20份：1次 IN 查询；提交时按主键顺序锁行，防止并发批次互相覆盖。
    statement = select(DocumentDraft).where(DocumentDraft.draft_uid.in_([item.draft_uid for item in payload.drafts])).order_by(DocumentDraft.id)
    if lock:
        statement = statement.with_for_update()
    rows = db.execute(statement).scalars().all()
    return build_batch_plan(rows, payload, user)


def preview(plan):
    return [{'draft_uid': item['row'].draft_uid, 'title': item['snapshot']['title'],
             'revision': item['row'].revision, 'next_revision': item['row'].revision + 1,
             'changes': item['changes']} for item in plan]


def apply_batch(db, user, payload):
    plan = load_batch(db, user, payload, lock=True)
    result = preview(plan)
    updates = [{'id': item['row'].id, 'revision': item['row'].revision + 1, 'snapshot': item['snapshot'],
                'history': item['row'].history + [history_entry(item['row'].revision + 1, item['snapshot'], user.id, payload.reason)]}
               for item in plan]
    # SQLAlchemy 对同列集合使用一次 executemany；禁止在循环里逐份查询或提交。
    db.bulk_update_mappings(DocumentDraft, updates)
    db.add_all([AuditLog(user_id=user.id, action='draft_batch_update', target_type='document_draft',
                         target_id=item['row'].draft_uid, detail=f"revision={item['row'].revision + 1};共享参数联动")
                for item in plan])
    db.commit()
    return result
