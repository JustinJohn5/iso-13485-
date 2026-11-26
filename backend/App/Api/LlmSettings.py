"""大模型网页管理，仅管理员可以读写地址和调用参数。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from App.Api.Dependencies import current_user, require_admin, require_writer
from App.Config.Settings import get_settings
from App.Dao.AuditLogDao import AuditLogDao
from App.Dao.LlmConfigDao import LlmConfigDao
from App.Db.Session import get_db
from App.Models.User import User
from App.Schemas.LlmSettings import AiDraftRequest, LlmSettingsUpdate
from App.Services.Authoring.AiDraft import generate_ai_draft
from App.Services.Authoring.DraftStore import accessible_draft, save_revision
from App.Utils.Crypto import encrypt_secret
from App.Utils.Errors import ApiError
from App.Utils.Response import success

router = APIRouter(prefix='/api/v1', tags=['大模型配置与编写'])


def public_config(config):
    return {'enabled': config.enabled if config else False, 'base_url': config.base_url if config else '',
            'model': config.model if config else '', 'api_key_configured': bool(config and config.api_key_cipher),
            'timeout_seconds': config.timeout_seconds if config else 60,
            'max_tokens': config.max_tokens if config else 4000,
            'temperature': float(config.temperature) if config else 0.2}


@router.get('/llm-status')
def status(db: Session = Depends(get_db), user: User = Depends(current_user)):
    config = LlmConfigDao.get_default(db)
    return success({'ready': bool(config and config.enabled and config.api_key_cipher and config.base_url and config.model)})


@router.get('/llm-settings')
def read(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return success(public_config(LlmConfigDao.get_default(db)))


@router.patch('/llm-settings')
def configure(payload: LlmSettingsUpdate, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    if get_settings().is_prod and not payload.base_url.startswith('https://'):
        raise ApiError(1001, '正式环境大模型服务地址必须使用 HTTPS')
    config = LlmConfigDao.get_or_create(db)
    if payload.enabled and not payload.api_key and not config.api_key_cipher:
        raise ApiError(1001, '启用大模型前请先填写 API Key')
    # 更换服务地址必须明确提交新凭据，防止旧服务密钥被发送到新服务。
    if config.api_key_cipher and config.base_url != payload.base_url and not payload.api_key:
        raise ApiError(1001, '更换服务地址时请同时重新填写 API Key')
    for key, value in payload.model_dump(exclude={'api_key'}).items():
        setattr(config, key, value)
    if payload.api_key:
        config.api_key_cipher = encrypt_secret(payload.api_key)
    config.updated_by = user.id
    AuditLogDao.add(db, user_id=user.id, action='llm_settings_update', target_type='llm_config',
                    target_id='default', detail='配置保存成功；敏感值不记录')
    db.commit()
    return success(public_config(config), '大模型配置已保存')


@router.post('/document-drafts/{uid}/ai-draft')
def ai_draft(uid: str, payload: AiDraftRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_writer(user)
    row = accessible_draft(db, user, uid)
    if row.revision != payload.revision:
        raise ApiError(1703)
    try:
        snapshot = generate_ai_draft(db, row.snapshot, payload.instructions)
    except ApiError:
        AuditLogDao.add(db, user_id=user.id, action='draft_ai_failed', target_type='document_draft', target_id=uid,
                        detail='AI 编写失败，原草稿未修改')
        db.commit()
        raise
    return success(save_revision(db, row, payload.revision, snapshot, user, 'AI 按用户要求辅助编写，待人工复核'))
