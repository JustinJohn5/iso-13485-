"""无认证要求的访客事件；凭据由服务端签发，页面为封闭白名单。"""
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from App.Config.Settings import get_settings
from App.Db.Session import get_db
from App.Services.VisitorTracking import (
    ALLOWED_PAGES, COOKIE_MAX_AGE, COOKIE_NAME, issue_visitor_cookie, optional_identity,
    track_visit, valid_visitor_cookie,
)
from App.Utils.Response import success

router = APIRouter(prefix='/api/v1/visits', tags=['访客'])


class VisitRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    page: str = Field(min_length=1, max_length=80)
    event: Literal['pageview', 'heartbeat', 'logout']

    @field_validator('page')
    @classmethod
    def valid_page(cls, value):
        if value not in ALLOWED_PAGES:
            raise ValueError('访客页面仅允许已登记的功能路径')
        return value


@router.post('')
def record_visit(payload: VisitRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    cookie = request.cookies.get(COOKIE_NAME)
    issued = not valid_visitor_cookie(cookie)
    if issued:
        cookie = issue_visitor_cookie()
    identity = None if payload.event == 'logout' else optional_identity(request, db)
    track_visit(db, cookie, page=payload.page, event=payload.event, identity=identity)
    if issued:
        response.set_cookie(COOKIE_NAME, cookie, max_age=COOKIE_MAX_AGE, httponly=True,
                            secure=get_settings().is_prod, samesite='lax', path='/')
    response.headers['Cache-Control'] = 'no-store'
    return success({'recorded': True})
