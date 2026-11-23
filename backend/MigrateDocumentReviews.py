"""1.1.0 增量迁移：先在 _codextest 验证，再用于本地开发库。"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url


def migrate(*, allow_production: bool = False) -> None:
    from App.Config.Settings import get_settings
    from App.Db.Session import get_engine
    from App.Models.DocumentReview import DocumentReview

    settings = get_settings()
    name = make_url(settings.database_url).database or ''
    if settings.app_env == 'prod' and not allow_production:
        raise SystemExit('正式环境迁移须先获发布授权，再显式传入 --allow-production')
    if settings.app_env == 'test' and not name.endswith('_codextest'):
        raise SystemExit('测试迁移仅允许 _codextest 数据库')
    engine = get_engine()
    with engine.connect() as connection:
        if not connection.execute(text('SELECT VERSION()')).scalar_one().startswith('8.4.'):
            raise SystemExit('迁移要求 MySQL 8.4')
    DocumentReview.__table__.create(bind=engine, checkfirst=True)
    columns = {column['name'] for column in inspect(engine).get_columns('validation_runs')}
    if 'review_snapshot' not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE validation_runs ADD COLUMN review_snapshot JSON NULL COMMENT '本次文件集正式依据的冻结快照'"))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, help='可选测试环境文件；不输出凭据')
    parser.add_argument('--allow-production', action='store_true', help='仅在取得正式发布授权后使用')
    args = parser.parse_args()
    if args.env_file:
        os.environ.update({key: value for key, value in dotenv_values(args.env_file).items() if value is not None})
    migrate(allow_production=args.allow_production)
