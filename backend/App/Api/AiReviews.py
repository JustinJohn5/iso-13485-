"""AI 文件审阅接口：候选分析独立保存，人工决定追加留痕。"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from App.Api.Dependencies import current_user, require_writer
from App.Api.System import rule_loader
from App.Dao.AiReviewDao import AiReviewDao
from App.Dao.AuditLogDao import AuditLogDao
from App.Dao.ValidationDao import ValidationDao
from App.Db.Session import get_db
from App.Models.AiReview import AiReview, AiReviewDecision
from App.Models.User import User
from App.Models.ValidationRun import STATUS_SUCCEEDED
from App.Schemas.AiReview import AiReviewDecisionRequest, AiReviewRequest
from App.Services.AiReview.EvidenceSearch import search_evidence
from App.Services.AiReview.RequirementReview import review_requirements
from App.Utils.Errors import ApiError
from App.Utils.Response import success
from App.Utils.TimeUtils import to_iso

router = APIRouter(prefix="/api/v1", tags=["AI 文件审阅"])
MAX_AI_REVIEWS_PER_RUN = 100
MAX_DECISIONS_PER_REVIEW = 500


def _accessible_run(db: Session, run_uid: str, user: User):
    run = ValidationDao.get_by_uid(db, run_uid)
    if run is None:
        raise ApiError(1302)
    if user.role != "admin" and run.created_by != user.id:
        raise ApiError(1104)
    if run.status != STATUS_SUCCEEDED or not run.review_snapshot or not run.review_snapshot.get("prescreen"):
        raise ApiError(1303)
    return run


def _rule_for_run(run, rule_id: str):
    rules = rule_loader().get(run.rule_set_id)
    if rules.version != run.rule_set_version:
        raise ApiError(1306)
    rule = next((item for item in rules.rules if item.rule_id == rule_id), None)
    if rule is None:
        raise ApiError(1001, "检查项不属于本次校验使用的规则包")
    return rule


def _decision_dict(row: AiReviewDecision) -> dict:
    return {
        "decision": row.decision,
        "note": row.note,
        "edited_result": row.edited_result,
        "decided_by": row.decided_by,
        "created_at": to_iso(row.created_at),
    }


def _review_dict(row: AiReview, decisions: list[AiReviewDecision]) -> dict:
    return {
        "review_uid": row.review_uid,
        "mode": row.mode,
        "rule_id": row.rule_id,
        "rule_title": row.rule_title,
        "clause": row.clause,
        "rule_set_version": row.rule_set_version,
        "file_uid": row.file_uid,
        "file_name": row.file_name,
        "text_status": row.text_status,
        "model": row.model_name,
        "latency_ms": row.latency_ms,
        "result": row.result,
        "created_by": row.created_by,
        "created_at": to_iso(row.created_at),
        "decisions": [_decision_dict(item) for item in decisions],
    }


def _decision_map(db: Session, rows: list[AiReview]) -> dict[int, list[AiReviewDecision]]:
    result = {row.id: [] for row in rows}
    for decision in AiReviewDao.list_decisions(db, list(result)):
        result[decision.review_id].append(decision)
    return result


@router.post("/validations/{run_uid}/ai-reviews")
def create_ai_review(
    run_uid: str,
    payload: AiReviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    require_writer(user)
    run = _accessible_run(db, run_uid, user)
    rule = _rule_for_run(run, payload.rule_id)
    file = AiReviewDao.file_in_run(db, run.id, payload.file_uid)
    if file is None:
        raise ApiError(1203, "所选文件不属于本次已完成的预筛任务")
    if not file.extracted_text.strip() or file.text_status in {"insufficient", "failed"}:
        raise ApiError(1205, "文件没有可供 AI 审阅的已抽取文本")
    if AiReviewDao.count_for_run(db, run.id) >= MAX_AI_REVIEWS_PER_RUN:
        raise ApiError(1307)

    try:
        if payload.mode == "evidence_search":
            result, model, latency = search_evidence(db, rule, file.file_uid, file.extracted_text)
        else:
            result, model, latency = review_requirements(db, rule, file.file_uid, file.extracted_text)
    except ApiError:
        AuditLogDao.add(db, user_id=user.id, action="ai_review_failed", target_type="validation_run",
                        target_id=run_uid, detail=f"{payload.mode}:{payload.rule_id}")
        db.commit()
        raise

    row = AiReview(
        review_uid=str(uuid4()), run_id=run.id, created_by=user.id, mode=payload.mode,
        rule_id=rule.rule_id, rule_title=rule.title, clause=rule.clause,
        rule_set_version=run.rule_set_version, file_uid=file.file_uid,
        file_name=file.original_name, text_status=file.text_status,
        model_name=model, latency_ms=latency, result=result,
    )
    AiReviewDao.create(db, row)
    AuditLogDao.add(db, user_id=user.id, action="ai_review_create", target_type="ai_review",
                    target_id=row.review_uid, detail=f"{payload.mode}:{rule.rule_id}:{file.file_uid}")
    db.commit()
    db.refresh(row)
    return success(_review_dict(row, []), "AI 候选审阅已生成，请人工核对原文件")


@router.get("/validations/{run_uid}/ai-reviews")
def list_ai_reviews(
    run_uid: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    run = _accessible_run(db, run_uid, user)
    rows = AiReviewDao.list_for_run(db, run.id)
    decisions = _decision_map(db, rows)
    return success([_review_dict(row, decisions[row.id]) for row in rows])


@router.patch("/ai-reviews/{review_uid}/decision")
def add_ai_review_decision(
    review_uid: str,
    payload: AiReviewDecisionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    require_writer(user)
    row = AiReviewDao.get_by_uid(db, review_uid)
    if row is None:
        raise ApiError(1002, "AI 审阅记录不存在")
    run = ValidationDao.get_by_id(db, row.run_id)
    if run is None or (user.role != "admin" and run.created_by != user.id):
        raise ApiError(1104)
    if payload.decision == "accepted_edited" and not payload.edited_result:
        raise ApiError(1001, "修改后采纳必须填写修改后的审阅内容")
    if payload.decision != "accepted_edited" and payload.edited_result:
        raise ApiError(1001, "只有修改后采纳可以填写修改后的审阅内容")
    decisions = AiReviewDao.list_decisions(db, [row.id])
    if len(decisions) >= MAX_DECISIONS_PER_REVIEW:
        raise ApiError(1001, "本条审阅的人工决定次数过多")

    decision = AiReviewDecision(
        review_id=row.id, decided_by=user.id, decision=payload.decision,
        note=payload.note, edited_result=payload.edited_result,
    )
    AiReviewDao.add_decision(db, decision)
    AuditLogDao.add(db, user_id=user.id, action="ai_review_decision", target_type="ai_review",
                    target_id=row.review_uid, detail=payload.decision)
    db.commit()
    db.refresh(decision)
    return success(_decision_dict(decision), "人工决定已保存并留痕")
