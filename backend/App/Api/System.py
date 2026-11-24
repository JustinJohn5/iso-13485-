"""健康检查与规则包目录。"""

from fastapi import APIRouter, Depends

from App.Api.Dependencies import current_user
from App.Models.User import User

from App.Config.Settings import get_settings
from App.Services.Rules.RuleSetLoader import RuleSetLoader
from App.Utils.Response import success

router = APIRouter(prefix="/api/v1", tags=["系统"])
_loader: RuleSetLoader | None = None


def rule_loader() -> RuleSetLoader:
    global _loader
    if _loader is None:
        _loader = RuleSetLoader(get_settings().rule_set_dir)
    return _loader


@router.get("/health")
def health():
    return success({"status": "ok"})


@router.get("/rule-sets")
def rule_sets():
    return success(rule_loader().summaries())


@router.get("/document-types")
def document_types():
    rule_set = rule_loader().get()
    return success([item.model_dump() for item in rule_set.document_types])


@router.get('/rule-sets/{rule_set_id}')
def rule_handbook(rule_set_id: str, user: User = Depends(current_user)):
    return success(rule_loader().get(rule_set_id).model_dump())
