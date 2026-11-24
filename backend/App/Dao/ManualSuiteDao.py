"""套册读取与原子修订；成员变更使旧检查结果失效。"""
from sqlalchemy import select, update

from App.Dao.AuditLogDao import AuditLogDao
from App.Models.ManualSuite import ManualSuite
from App.Services.ManualSuites.InspectionHistory import inspection_summaries, restore_findings, unpack_inspections, update_inspections
from App.Utils.Errors import ApiError
from App.Utils.TimeUtils import now, to_iso


def accessible_suite(db, user, uid, revision=None):
    row = db.execute(select(ManualSuite).where(ManualSuite.suite_uid == uid)).scalar_one_or_none()
    if row is None:
        raise ApiError(1801)
    if row.created_by != user.id and user.role != 'admin':
        raise ApiError(1104)
    if revision is not None and row.revision != revision:
        raise ApiError(1802)
    return row


def suite_response(row):
    current, history = unpack_inspections(row.inspection, row.revision)
    return dict(suite_uid=row.suite_uid, name=row.name, version=row.version, revision=row.revision,
                item_count=row.item_count, created_at=to_iso(row.created_at), updated_at=to_iso(row.updated_at),
                items=[{key: value for key, value in item.items()
                        if key not in {'text', 'snapshot', 'stored_name'}} for item in row.items],
                inspection=restore_findings(current), inspection_history=inspection_summaries(history))


def save_suite(db, user, row, revision, *, items=None, inspection=None, action, reason=''):
    values = dict(revision=revision + 1, updated_at=now(),
                  inspection=update_inspections(row.inspection, inspection, revision))
    if items is not None:
        values.update(items=items, item_count=len(items))
    changed = db.execute(update(ManualSuite).where(ManualSuite.id == row.id, ManualSuite.revision == revision)
                         .values(**values).execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        db.rollback()
        raise ApiError(1802)
    AuditLogDao.add(db, user_id=user.id, action=action, target_type='manual_suite', target_id=row.suite_uid,
                    detail=f'revision={revision + 1}' + (f';reason={reason.strip()}' if reason else ''))
    db.commit()
    db.refresh(row)
    return suite_response(row)
