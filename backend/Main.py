"""FastAPI 应用入口。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from App.Api import AiReviews, AuditReports, Auth, Authoring, DocumentReviews, Documents, DraftBatches, LlmSettings, ManualSuites, PersonalFiles, System
from App.Config.Settings import SettingsError, get_settings
from App.Services.Rules.RuleSetLoader import RuleSetLoader
from App.Utils.Errors import ApiError
from App.Utils.Logger import configure_logging, request_id_var
from App.Utils.Response import failure, success


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        settings = get_settings()
        configure_logging(settings.log_dir, settings.log_level)
        RuleSetLoader(settings.rule_set_dir).load_all()
    except SettingsError as exc:
        raise RuntimeError(str(exc)) from exc
    yield


app = FastAPI(title="ISO 13485 文件预筛平台", version="1.3.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    import uuid

    token = request_id_var.set(uuid.uuid4().hex[:12])
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id_var.get()
        return response
    finally:
        request_id_var.reset(token)


@app.exception_handler(ApiError)
async def handle_api_error(_: Request, exc: ApiError):
    return JSONResponse(status_code=exc.http_status, content=failure(exc.code, exc.message, exc.data))


@app.exception_handler(RequestValidationError)
async def handle_request_validation(_: Request, exc: RequestValidationError):
    fields = [".".join(str(part) for part in issue.get("loc", ())) for issue in exc.errors()]
    return JSONResponse(
        status_code=400,
        content=failure(1001, "请求参数不完整或格式不正确", {"fields": fields}),
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(_: Request, exc: Exception):
    logging.getLogger(__name__).exception("未处理的接口异常")
    return JSONResponse(status_code=500, content=failure(1004, "服务器内部错误"))


@app.get("/")
def root():
    return success({"name": "ISO 13485 文件预筛平台", "docs": "/docs"})


app.include_router(System.router)
app.include_router(Auth.router)
app.include_router(Documents.router)
app.include_router(DocumentReviews.router)
app.include_router(Authoring.router)
app.include_router(LlmSettings.router)
app.include_router(AuditReports.router)
app.include_router(DraftBatches.router)
app.include_router(ManualSuites.router)
app.include_router(AiReviews.router)
app.include_router(PersonalFiles.router)

