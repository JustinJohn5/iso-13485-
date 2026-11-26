"""个人文件列表、受控下载与事务化分组；所有查询均校验当前所有者。"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from App.Api.System import rule_loader
from App.Dao.AuditLogDao import AuditLogDao
from App.Models.FileGroup import FileGroup, FileGroupMember
from App.Models.UploadedFile import UploadedFile
from App.Models.User import User
from App.Schemas.PersonalFiles import GroupMembers, GroupName
from App.Services.DocumentClassifier import detect_document_type
from App.Services.DocumentControl.Metadata import extract_metadata
from App.Utils.Errors import ApiError
from App.Utils.TimeUtils import to_iso


def _group(db: Session, user: User, uid: str, *, lock: bool = False) -> FileGroup:
    query = select(FileGroup).where(FileGroup.group_uid == uid, FileGroup.owner_id == user.id)
    if lock:
        query = query.with_for_update()
    row = db.execute(query).scalar_one_or_none()
    if row is None:
        raise ApiError(1207, '文件分组不存在', http_status=404)
    return row


def _group_summary(row: FileGroup, count: int) -> dict:
    return {'group_uid': row.group_uid, 'name': row.name, 'file_count': count, 'created_at': to_iso(row.created_at)}


def _member_count(db: Session, group_id: int) -> int:
    return int(db.execute(select(func.count()).select_from(FileGroupMember)
                          .where(FileGroupMember.group_id == group_id)).scalar_one())


def _file_summaries(db: Session, user: User, rows: list[UploadedFile]) -> list[dict]:
    if not rows:
        return []
    # 本页所有分组一次取回，避免每份文件单独查组。
    associations = db.execute(select(FileGroupMember.file_id, FileGroup.group_uid, FileGroup.name)
                              .join(FileGroup, FileGroup.id == FileGroupMember.group_id)
                              .where(FileGroup.owner_id == user.id, FileGroupMember.file_id.in_([row.id for row in rows]))
                              .order_by(FileGroup.name, FileGroup.id)).all()
    groups: dict[int, list[dict]] = {}
    for association in associations:
        groups.setdefault(association.file_id, []).append({'group_uid': association.group_uid, 'name': association.name})
    rules = rule_loader().get()
    return [{
        'file_uid': row.file_uid, 'name': row.original_name, 'document_type': row.document_type,
        'size_bytes': row.size_bytes, 'text_status': row.text_status, 'created_at': to_iso(row.created_at),
        'groups': groups.get(row.id, []),
        'control_metadata': extract_metadata(row.original_name, row.extracted_text, row.document_type),
        'type_detection': detect_document_type(row.original_name, row.extracted_text, rules).to_dict(),
    } for row in rows]


def list_files(db: Session, user: User, *, page: int, page_size: int, keyword: str = '',
               document_type: str = '', group_uid: str = '') -> dict:
    filters = [UploadedFile.uploaded_by == user.id]
    if keyword.strip():
        filters.append(UploadedFile.original_name.contains(keyword.strip(), autoescape=True))
    if document_type:
        if document_type not in {item.type for item in rule_loader().get().document_types}:
            raise ApiError(1001, '请选择有效的文件类型')
        filters.append(UploadedFile.document_type == document_type)
    if group_uid:
        filters.append(select(FileGroupMember.file_id).join(FileGroup, FileGroup.id == FileGroupMember.group_id)
                       .where(FileGroupMember.file_id == UploadedFile.id, FileGroup.group_uid == group_uid,
                              FileGroup.owner_id == user.id).exists())
    total = int(db.execute(select(func.count()).select_from(UploadedFile).where(*filters)).scalar_one())
    rows = list(db.execute(select(UploadedFile).where(*filters)
                           .order_by(UploadedFile.created_at.desc(), UploadedFile.id.desc())
                           .offset((page - 1) * page_size).limit(page_size)).scalars())
    return {'items': _file_summaries(db, user, rows), 'total': total, 'page': page, 'page_size': page_size}


def _validated_uids(values: list[str], *, limit: int = 100) -> list[str]:
    try:
        result = GroupMembers(file_uids=values).file_uids
    except ValidationError as exc:
        raise ApiError(1001, '请提交有效且不重复的文件标识') from exc
    if len(result) > limit:
        raise ApiError(1001, f'每次最多选择{limit}份文件')
    return result


def selection_files(db: Session, user: User, file_uids: list[str]) -> list[dict]:
    file_uids = _validated_uids(file_uids, limit=20)
    rows = list(db.execute(select(UploadedFile).where(UploadedFile.uploaded_by == user.id,
                                                     UploadedFile.file_uid.in_(file_uids))).scalars())
    by_uid = {row.file_uid: row for row in rows}
    if len(by_uid) != len(file_uids):
        raise ApiError(1203)
    return _file_summaries(db, user, [by_uid[uid] for uid in file_uids])


def download_file(db: Session, user: User, uid: str, upload_dir: Path) -> tuple[UploadedFile, Path]:
    row = db.execute(select(UploadedFile).where(UploadedFile.file_uid == uid,
                                               UploadedFile.uploaded_by == user.id)).scalar_one_or_none()
    if row is None:
        raise ApiError(1203)
    base = upload_dir.resolve()
    # 存储名只允许直接子文件，不允许目录、符号链接或越界解析；外部只收到统一404。
    if not row.stored_name or '/' in row.stored_name or '\\' in row.stored_name:
        raise ApiError(1203)
    candidate = base / row.stored_name
    try:
        path = candidate.resolve(strict=True)
        valid = not candidate.is_symlink() and path.parent == base and path.is_file()
    except (OSError, RuntimeError):
        valid = False
    if not valid:
        raise ApiError(1203, '文件原件不存在或不可下载')
    return row, path


def list_groups(db: Session, user: User, *, page: int, page_size: int) -> dict:
    total = int(db.execute(select(func.count()).select_from(FileGroup).where(FileGroup.owner_id == user.id)).scalar_one())
    counts = select(FileGroupMember.group_id, func.count().label('file_count')).group_by(FileGroupMember.group_id).subquery()
    rows = db.execute(select(FileGroup, func.coalesce(counts.c.file_count, 0))
                      .outerjoin(counts, counts.c.group_id == FileGroup.id).where(FileGroup.owner_id == user.id)
                      .order_by(FileGroup.created_at.desc(), FileGroup.id.desc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return {'items': [_group_summary(row, int(count)) for row, count in rows],
            'total': total, 'page': page, 'page_size': page_size}


def _name(value: str) -> tuple[str, str]:
    try:
        name = GroupName(name=value).name
    except ValidationError as exc:
        raise ApiError(1001, '请输入有效的分组名称') from exc
    return name, sha256(name.casefold().encode('utf-8')).hexdigest()


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if getattr(exc.orig, 'args', [None])[0] == 1062:
            raise ApiError(1208, '相同名称的文件分组已存在', http_status=409) from exc
        raise


def create_group(db: Session, user: User, name: str) -> dict:
    name, identity = _name(name)
    row = FileGroup(group_uid=str(uuid4()), owner_id=user.id, name=name, name_identity=identity)
    db.add(row)
    AuditLogDao.add(db, user_id=user.id, action='file_group_create', target_type='file_group', target_id=row.group_uid)
    _commit(db)
    return _group_summary(row, 0)


def rename_group(db: Session, user: User, uid: str, name: str) -> dict:
    name, identity = _name(name)
    row = _group(db, user, uid, lock=True)
    row.name, row.name_identity = name, identity
    AuditLogDao.add(db, user_id=user.id, action='file_group_rename', target_type='file_group', target_id=uid)
    _commit(db)
    return _group_summary(row, _member_count(db, row.id))


def delete_group(db: Session, user: User, uid: str) -> None:
    row = _group(db, user, uid, lock=True)
    db.execute(delete(FileGroupMember).where(FileGroupMember.group_id == row.id))
    db.delete(row)
    AuditLogDao.add(db, user_id=user.id, action='file_group_delete', target_type='file_group', target_id=uid)
    _commit(db)


def change_members(db: Session, user: User, uid: str, file_uids: list[str], *, add: bool) -> dict:
    file_uids = _validated_uids(file_uids)
    try:
        # 分组行锁串行化同组变更；所有权批量校验先于任何成员写入。
        group = _group(db, user, uid, lock=True)
        file_ids = list(db.execute(select(UploadedFile.id).where(UploadedFile.uploaded_by == user.id,
                                                                UploadedFile.file_uid.in_(file_uids))
                                   .order_by(UploadedFile.id).with_for_update()).scalars())
        if len(file_ids) != len(file_uids):
            raise ApiError(1203)
        if add:
            existing = set(db.execute(select(FileGroupMember.file_id).where(FileGroupMember.group_id == group.id,
                                                                            FileGroupMember.file_id.in_(file_ids))
                                      .with_for_update()).scalars())
            missing = [{'group_id': group.id, 'file_id': file_id} for file_id in file_ids if file_id not in existing]
            if missing:
                db.execute(insert(FileGroupMember), missing)
        else:
            db.execute(delete(FileGroupMember).where(FileGroupMember.group_id == group.id, FileGroupMember.file_id.in_(file_ids)))
        AuditLogDao.add(db, user_id=user.id, action='file_group_add' if add else 'file_group_remove',
                        target_type='file_group', target_id=uid, detail=f'文件数量={len(file_ids)}')
        _commit(db)
    except Exception:
        db.rollback()
        raise
    return _group_summary(group, _member_count(db, group.id))
