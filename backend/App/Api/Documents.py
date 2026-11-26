"""文档上传与规则校验接口。"""

from __future__ import annotations

import hashlib
import json
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from App.Api.Dependencies import current_user, require_writer
from App.Api.System import rule_loader
from App.Config.Settings import get_settings
from App.Dao.FileDao import FileDao
from App.Dao.AuditLogDao import AuditLogDao
from App.Dao.ValidationDao import ValidationDao
from App.Db.Session import get_db
from App.Models.Finding import Finding, SOURCE_RULE, STATUS_PASS
from App.Models.UploadedFile import UploadedFile
from App.Models.FileGroup import FileGroupMember
from App.Models.User import User
from App.Models.ValidationDocument import ValidationDocument
from App.Models.ValidationRun import STATUS_SUCCEEDED, ValidationRun
from App.Schemas.Prescreen import PrescreenContext, freeze_context
from App.Services.Extraction.ExtractorRegistry import extract
from App.Services.DocumentClassifier import resolve_document_type
from App.Services.DocumentControl.Metadata import extract_metadata
from App.Services.DocumentControl.ReviewStore import validation_scope
from App.Services.Rules.RuleEngine import DocumentInput, RuleEngine
from App.Services.Rules.PrescreenReport import build_prescreen_report, evaluation_dict
from App.Services.ScoringService import build_score
from App.Services.PersonalFiles import owned_group
from App.Utils.Errors import ApiError
from App.Utils.FileGuard import (
    build_storage_path,
    canonical_mime,
    ensure_inside,
    ensure_supported_extension,
    sanitize_filename,
    verify_signature,
)
from App.Utils.Response import success
from App.Utils.TimeUtils import now

router = APIRouter(prefix="/api/v1", tags=["文档"])
_CHUNK_SIZE = 1024 * 1024


class DocumentTypeUpdate(BaseModel):
    document_type: str


@router.patch("/documents/{file_uid}")
def update_document_type(
    file_uid: str,
    payload: DocumentTypeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    require_writer(user)
    row = FileDao.get_by_uid(db, file_uid)
    if row is None:
        raise ApiError(1203)
    if user.role != "admin" and row.uploaded_by != user.id:
        raise ApiError(1104)
    resolved, detection = resolve_document_type(
        payload.document_type, row.original_name, row.extracted_text, rule_loader().get(),
    )
    row.document_type = resolved
    db.commit()
    return success({"file_uid": row.file_uid, "document_type": resolved,
                    "type_detection": detection.to_dict(),
                    "control_metadata": extract_metadata(row.original_name, row.extracted_text, resolved)}, "文件类型已更新")


@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form("auto"),
    group_uid: str = Form("", max_length=36),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    require_writer(user)
    rule_set = rule_loader().get()
    valid_types = {item.type for item in rule_set.document_types}
    if document_type != "auto" and document_type not in valid_types:
        raise ApiError(1001, "请选择有效的文件类型")

    settings = get_settings()
    original_name = sanitize_filename(file.filename or "上传文件")
    extension = ensure_supported_extension(original_name)
    stored_name, raw_path = build_storage_path(settings.upload_dir, extension)
    path = ensure_inside(raw_path, settings.upload_dir)
    digest = hashlib.sha256()
    size = 0
    head = bytearray()
    try:
        group = owned_group(db, user, group_uid, lock=True) if group_uid else None
        with path.open("xb") as stream:
            while chunk := await file.read(_CHUNK_SIZE):
                size += len(chunk)
                if size > settings.max_upload_size_bytes:
                    raise ApiError(1202)
                if len(head) < 4096:
                    head.extend(chunk[: 4096 - len(head)])
                digest.update(chunk)
                stream.write(chunk)
        verify_signature(extension, bytes(head), path)
        extracted = extract(path, extension)
        if extracted.status != "ok":
            extracted.warnings.append('原件已保留，但文本无法可靠判定；请补充OCR或可读文件后重新检查')
        resolved_type, detection = resolve_document_type(document_type, original_name, extracted.text, rule_set)
        row = UploadedFile(
            file_uid=str(uuid4()),
            original_name=original_name,
            stored_name=stored_name,
            extension=extension,
            document_type=resolved_type,
            mime_type=canonical_mime(extension),
            size_bytes=size,
            sha256=digest.hexdigest(),
            page_count=extracted.page_count,
            char_count=extracted.char_count,
            text_status=extracted.status,
            extracted_text=extracted.text,
            uploaded_by=user.id,
        )
        FileDao.create(db, row)
        if group is not None:
            db.add(FileGroupMember(group_id=group.id, file_id=row.id))
            AuditLogDao.add(db, user_id=user.id, action='file_group_upload', target_type='file_group',
                            target_id=group_uid, detail='文件数量=1')
        db.commit()
        return success({
            "file_uid": row.file_uid,
            "name": row.original_name,
            "document_type": resolved_type,
            "type_detection": detection.to_dict(),
            "control_metadata": extract_metadata(original_name, extracted.text, resolved_type),
            "size_bytes": row.size_bytes,
            "char_count": row.char_count,
            "page_count": row.page_count,
            "warnings": extracted.warnings,
            "text_status": extracted.status,
        }, "文件已解析")
    except Exception:
        path.unlink(missing_ok=True)
        db.rollback()
        raise
    finally:
        await file.close()


@router.post("/validations")
def validate_documents(
    file_uids: list[str] = Form(...),
    review_uid: str = Form(''),
    review_revision: int | None = Form(None),
    context: str = Form(''),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    require_writer(user)
    if not file_uids or len(file_uids) > 20 or len(set(file_uids)) != len(file_uids):
        raise ApiError(1001, "请提交 1 至 20 个不重复文件")
    files = FileDao.get_by_uids(db, file_uids)
    by_uid = {row.file_uid: row for row in files}
    if len(by_uid) != len(file_uids):
        raise ApiError(1203)
    if user.role != "admin" and any(row.uploaded_by != user.id for row in files):
        raise ApiError(1104)
    try:
        if len(context) > 100000:
            raise ValueError('审核上下文过长')
        parsed_context = PrescreenContext.model_validate(json.loads(context)) if context else PrescreenContext()
        frozen_context = freeze_context(parsed_context, user_id=user.id, file_uids=file_uids)
    except (ValueError, ValidationError) as exc:
        raise ApiError(1001, '审核范围、适用条件或用途不合法，请检查条款理由和依据') from exc
    selected_uids, review_snapshot = validation_scope(db, user, [by_uid[uid] for uid in file_uids], review_uid, review_revision,
                                                       frozen_context['as_of_date'], frozen_context['purposes'])
    excluded_versions = [by_uid[uid].original_name for uid in file_uids if uid not in selected_uids]
    file_uids = selected_uids
    rule_set = rule_loader().get()
    # 一次批量查询后在内存中按内容摘要去重，避免重复文件重复计分。
    unique_uids: list[str] = []
    seen: dict[str, UploadedFile] = {}
    duplicates: list[dict[str, str]] = []
    for uid in file_uids:
        row = by_uid[uid]
        previous = seen.get(row.sha256)
        if previous:
            if previous.document_type != row.document_type or frozen_context['purposes'].get(previous.file_uid, 'auto') != frozen_context['purposes'].get(uid, 'auto'):
                raise ApiError(1001, "相同内容的文件选择了不同类型或用途，请统一后重试")
            duplicates.append({"name": row.original_name, "kept_name": previous.original_name})
            continue
        seen[row.sha256] = row
        unique_uids.append(uid)
    file_uids = unique_uids
    inputs = [
        DocumentInput(
            file_id=by_uid[uid].id,
            file_uid=uid,
            name=by_uid[uid].original_name,
            document_type=by_uid[uid].document_type,
            text=by_uid[uid].extracted_text if by_uid[uid].text_status != 'insufficient' else '',
            page_count=by_uid[uid].page_count,
            char_count=by_uid[uid].char_count,
            text_status=by_uid[uid].text_status,
        )
        for uid in file_uids
    ]
    evaluations = RuleEngine(rule_set).evaluate(inputs, frozen_context, review=review_snapshot)
    prescreen = build_prescreen_report(rule_set, evaluations, frozen_context, review=review_snapshot)
    score = build_score(rule_set, evaluations, document_conflicts=bool(review_snapshot and review_snapshot.get('requirement_conflicts')))
    timestamp = now()
    run = ValidationRun(
        run_uid=str(uuid4()), rule_set_id=rule_set.rule_set_id,
        rule_set_version=rule_set.version, status=STATUS_SUCCEEDED,
        score=score.score, verdict=score.verdict, passed_count=score.passed_count,
        failed_count=score.failed_count, skipped_count=score.skipped_count,
        critical_count=score.critical_count, major_count=score.major_count,
        minor_count=score.minor_count, observation_count=score.observation_count,
        total_count=score.total_count, created_by=user.id, started_at=timestamp, finished_at=timestamp,
        review_snapshot={**(review_snapshot or {}), 'prescreen': prescreen},
    )
    ValidationDao.create_run(db, run)
    ValidationDao.add_documents(db, [
        ValidationDocument(run_id=run.id, file_id=by_uid[uid].id, document_type=item.document_type,
                           char_count=item.char_count, page_count=item.page_count)
        for uid, item in zip(file_uids, inputs, strict=True)
    ])
    ValidationDao.add_findings(db, [
        Finding(
            run_id=run.id, rule_id=item.rule.rule_id, title=item.rule.title,
            clause=item.rule.clause, clause_title=item.rule.clause_title,
            severity=item.rule.severity, status=item.status,
            document_type=item.document_type, evidence=item.evidence or item.detail,
            suggestion=item.rule.suggestion, source=SOURCE_RULE,
            passed=item.status == STATUS_PASS, sort_order=item.order,
        )
        for item in evaluations
    ])
    db.commit()
    return success({
        "run_uid": run.run_uid,
        "rule_set": {"title": rule_set.title, "standard": rule_set.standard, "version": rule_set.version},
        "score": score.to_dict(),
        "duplicate_files": duplicates,
        "excluded_versions": excluded_versions,
        "document_review": review_snapshot if review_uid else None,
        "prescreen": prescreen,
        "documents": [{"file_uid": item.file_uid, "name": item.name, "document_type": item.document_type,
                       "type_label": rule_set.document_type_label(item.document_type)} for item in inputs],
        "findings": [evaluation_dict(item) for item in evaluations],
        "disclaimer": "本结果仅为基于文本规则的预筛查，不构成 ISO 13485 认证、审核结论或法规符合性声明。",
    }, "校验完成")


