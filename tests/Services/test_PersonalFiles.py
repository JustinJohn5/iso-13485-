"""个人文件合同与真实 MySQL 所有权、事务及分组并发回归。"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from dotenv import dotenv_values
from pydantic import ValidationError
from sqlalchemy import create_engine, delete, event, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


def test_group_input_rejects_blank_controls_and_extra_fields():
    from App.Schemas.PersonalFiles import GroupName
    for payload in ({'name': '   '}, {'name': '采购\n记录'}, {'name': 'a', 'owner_id': 7}):
        with pytest.raises(ValidationError):
            GroupName(**payload)
    assert GroupName(name='  采购文件  ').name == '采购文件'


def test_member_input_rejects_empty_duplicate_and_excessive_uids():
    from App.Schemas.PersonalFiles import GroupMembers
    for values in ([], ['a', 'a'], [' '], ['a'] * 101):
        with pytest.raises(ValidationError):
            GroupMembers(file_uids=values)


@pytest.fixture
def database():
    """仅连接现有测试副本；随机账号数据用 finally 定向清理。"""
    from App.Models.FileGroup import FileGroup, FileGroupMember
    from App.Models.AuditLog import AuditLog
    from App.Models.UploadedFile import UploadedFile
    from App.Models.User import User
    config = dotenv_values(Path(__file__).resolve().parents[2] / '.env.test')
    url = config.get('DATABASE_URL', '')
    assert config.get('APP_ENV') == 'test' and (make_url(url).database or '').endswith('_codextest')
    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as connection:
        assert connection.execute(text('SELECT VERSION()')).scalar_one().startswith('8.4.')
    FileGroup.__table__.create(engine, checkfirst=True)
    FileGroupMember.__table__.create(engine, checkfirst=True)
    with Session(engine, expire_on_commit=False) as db:
        users = [User(email=f'personal-{uuid4().hex}@example.com', display_name='隔离测试',
                      password_hash='synthetic-unused', role=role) for role in ('admin', 'auditor')]
        db.add_all(users)
        db.flush()
        files = [UploadedFile(file_uid=str(uuid4()), original_name=name, stored_name=f'{uuid4().hex}.txt',
                              extension='.txt', document_type='procedure', mime_type='text/plain', size_bytes=9,
                              sha256='a' * 64, extracted_text='文件编号：QP-01', uploaded_by=owner.id)
                 for name, owner in [('采购程序.txt', users[0]), ('质量程序.txt', users[0]), ('他人文件.txt', users[1])]]
        db.add_all(files)
        db.commit()
        ids = [user.id for user in users]
        try:
            yield db, engine, users, files
        finally:
            db.rollback()
            db.execute(delete(FileGroupMember).where(FileGroupMember.group_id.in_(select(FileGroup.id).where(FileGroup.owner_id.in_(ids)))))
            db.execute(delete(FileGroup).where(FileGroup.owner_id.in_(ids)))
            db.execute(delete(AuditLog).where(AuditLog.user_id.in_(ids)))
            db.execute(delete(UploadedFile).where(UploadedFile.uploaded_by.in_(ids)))
            db.execute(delete(User).where(User.id.in_(ids)))
            db.commit()
    engine.dispose()


def test_admin_personal_list_is_owned_searchable_and_has_bounded_queries(database):
    from App.Services.PersonalFiles import create_group, list_files, change_members
    db, engine, users, files = database
    group = create_group(db, users[0], '采购')
    change_members(db, users[0], group['group_uid'], [files[0].file_uid], add=True)
    statements = []
    def record(*args):
        statements.append(args[2])
    event.listen(engine, 'before_cursor_execute', record)
    try:
        result = list_files(db, users[0], page=1, page_size=10, keyword='采购', document_type='procedure', group_uid=group['group_uid'])
    finally:
        event.remove(engine, 'before_cursor_execute', record)
    assert result['total'] == 1 and result['items'][0]['file_uid'] == files[0].file_uid
    assert result['items'][0]['groups'] == [{'group_uid': group['group_uid'], 'name': '采购'}]
    assert {'control_metadata', 'type_detection', 'created_at', 'text_status'} <= result['items'][0].keys()
    assert not {'stored_name', 'extracted_text', 'uploaded_by'} & result['items'][0].keys()
    assert len(statements) <= 4
    assert list_files(db, users[0], page=1, page_size=10)['total'] == 2
    assert list_files(db, users[0], page=1, page_size=10, keyword='%')['total'] == 0


def test_selection_preserves_order_and_rejects_other_owner_even_admin(database):
    from App.Services.PersonalFiles import selection_files
    from App.Utils.Errors import ApiError
    db, _, users, files = database
    result = selection_files(db, users[0], [files[1].file_uid, files[0].file_uid])
    assert [item['file_uid'] for item in result] == [files[1].file_uid, files[0].file_uid]
    for values in ([], [files[0].file_uid] * 2, [str(uuid4()) for _ in range(21)]):
        with pytest.raises(ApiError) as caught:
            selection_files(db, users[0], values)
        assert caught.value.http_status == 400
    with pytest.raises(ApiError) as caught:
        selection_files(db, users[0], [files[0].file_uid, files[2].file_uid])
    assert caught.value.http_status == 404


def test_group_duplicate_rename_ownership_and_delete_keep_files(database):
    from App.Models.UploadedFile import UploadedFile
    from App.Services.PersonalFiles import create_group, rename_group, delete_group, list_groups, change_members
    from App.Utils.Errors import ApiError
    db, _, users, files = database
    group = create_group(db, users[0], '采购')
    with pytest.raises(ApiError) as caught:
        create_group(db, users[0], ' 采购 ')
    assert caught.value.http_status == 409
    second = create_group(db, users[0], '质量')
    with pytest.raises(ApiError) as caught:
        rename_group(db, users[0], second['group_uid'], '采购')
    assert caught.value.http_status == 409
    with pytest.raises(ApiError) as caught:
        change_members(db, users[1], group['group_uid'], [files[2].file_uid], add=True)
    assert caught.value.http_status == 404
    change_members(db, users[0], group['group_uid'], [files[0].file_uid], add=True)
    assert list_groups(db, users[0], page=1, page_size=10)['items'][1]['file_count'] == 1
    rename_group(db, users[0], group['group_uid'], '已归档')
    delete_group(db, users[0], group['group_uid'])
    assert db.execute(select(func.count()).select_from(UploadedFile).where(UploadedFile.id == files[0].id)).scalar_one() == 1


def test_member_batch_is_atomic_and_concurrent_add_is_idempotent(database):
    from App.Services.PersonalFiles import create_group, change_members, list_groups
    from App.Utils.Errors import ApiError
    db, engine, users, files = database
    group = create_group(db, users[0], '并发')
    with pytest.raises(ApiError):
        change_members(db, users[0], group['group_uid'], [files[0].file_uid, files[2].file_uid], add=True)
    assert list_groups(db, users[0], page=1, page_size=10)['items'][0]['file_count'] == 0
    db.rollback()
    actor = SimpleNamespace(id=users[0].id, role='admin')
    uid = files[0].file_uid
    def add_member(_):
        with Session(engine, expire_on_commit=False) as session:
            return change_members(session, actor, group['group_uid'], [uid], add=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(add_member, range(2)))
    assert [item['file_count'] for item in results] == [1, 1]
    with pytest.raises(ApiError):
        change_members(db, users[0], group['group_uid'], [uid, files[2].file_uid], add=False)
    assert list_groups(db, users[0], page=1, page_size=10)['items'][0]['file_count'] == 1
    change_members(db, users[0], group['group_uid'], [uid], add=False)
    assert list_groups(db, users[0], page=1, page_size=10)['items'][0]['file_count'] == 0


def test_download_only_accepts_owned_existing_regular_file(database, tmp_path):
    from App.Services.PersonalFiles import download_file
    from App.Utils.Errors import ApiError
    db, _, users, files = database
    original = tmp_path / files[0].stored_name
    original.write_text('原件', encoding='utf-8')
    row, path = download_file(db, users[0], files[0].file_uid, tmp_path)
    assert row.file_uid == files[0].file_uid and path.read_text(encoding='utf-8') == '原件'
    for uid in (files[1].file_uid, files[2].file_uid):
        with pytest.raises(ApiError) as caught:
            download_file(db, users[0], uid, tmp_path)
        assert caught.value.http_status == 404
    files[0].stored_name = '../outside.txt'
    with pytest.raises(ApiError) as caught:
        download_file(db, users[0], files[0].file_uid, tmp_path)
    assert caught.value.http_status == 404
