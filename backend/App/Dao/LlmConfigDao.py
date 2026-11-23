"""大模型配置数据访问。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from App.Models.LlmConfig import LlmConfig


class LlmConfigDao:
    """llm_configs 表读写（单条默认配置）。"""

    DEFAULT_NAME = "default"

    @staticmethod
    def get_default(db: Session) -> LlmConfig | None:
        return db.execute(
            select(LlmConfig).where(LlmConfig.name == LlmConfigDao.DEFAULT_NAME)
        ).scalar_one_or_none()

    @staticmethod
    def get_or_create(db: Session) -> LlmConfig:
        config = LlmConfigDao.get_default(db)
        if config is None:
            config = LlmConfig(name=LlmConfigDao.DEFAULT_NAME)
            db.add(config)
            db.flush()
        return config
