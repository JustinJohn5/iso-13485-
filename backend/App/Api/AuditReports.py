"""从历史预筛快照生成和导出模拟内审清单。"""
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from App.Api.Dependencies import current_user
from App.Dao.AuditLogDao import AuditLogDao
from App.Dao.ValidationDao import ValidationDao
from App.Db.Session import get_db
from App.Models.UploadedFile import UploadedFile
from App.Models.User import User
from App.Models.ValidationDocument import ValidationDocument
from App.Services.Audit.QuestionBuilder import build_questions, export_questions
from App.Utils.Errors import ApiError
from App.Utils.Response import success

router = APIRouter(prefix='/api/v1/validations', tags=['模拟内审'])


def report_for(db, user, run_uid):
    run = ValidationDao.get_by_uid(db, run_uid)
    if run is None:
        raise ApiError(1302)
    if user.role != 'admin' and run.created_by != user.id:
        raise ApiError(1104)
    if run.status != 'succeeded':
        raise ApiError(1303)
    if run.review_snapshot and run.review_snapshot.get('prescreen'):
        # 新任务只读取冻结的新状态、原文及文件标识，避免把兼容status误解为实施证据。
        frozen = run.review_snapshot['prescreen']
        values = [{**item, 'document': item.get('document_name', '')} for item in frozen['items']]
        return build_questions(run_uid, values, run.review_snapshot)
    findings = ValidationDao.list_findings(db, run.id)
    # 一次 JOIN 获取本次任务的文件标识，无逐条查询。旧任务同类型多文档时不臆测证据所属文件。
    rows = db.execute(select(ValidationDocument.document_type, UploadedFile.original_name)
                      .join(UploadedFile, UploadedFile.id == ValidationDocument.file_id)
                      .where(ValidationDocument.run_id == run.id)).all()
    names = {}
    for document_type, name in rows:
        names.setdefault(document_type, []).append(name)
    values = [{'status': item.status, 'title': item.title, 'clause': item.clause, 'evidence': item.evidence,
               'suggestion': item.suggestion, 'document': '；'.join(names.get(item.document_type, []))}
              for item in findings if item.source == 'rule']
    return build_questions(run_uid, values, run.review_snapshot)


@router.get('/{run_uid}/audit-report')
def report(run_uid: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return success(report_for(db, user, run_uid))


@router.get('/{run_uid}/audit-report/download')
def download(run_uid: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    data = report_for(db, user, run_uid)
    content = export_questions(data)
    AuditLogDao.add(db, user_id=user.id, action='audit_report_export', target_type='validation', target_id=run_uid)
    db.commit()
    filename = quote('模拟内审问题清单.docx')
    return Response(content, media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    headers={'Content-Disposition': f"attachment; filename*=UTF-8''{filename}", 'Cache-Control': 'no-store'})
