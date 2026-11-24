"""新增邮箱验证码状态表；先在 MySQL 8.4 测试副本验证。"""
import argparse
import os
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import text
from sqlalchemy.engine import make_url


def migrate(*, allow_production=False):
    from App.Config.Settings import get_settings
    from App.Db.Session import get_engine
    from App.Models.EmailVerificationCode import EmailVerificationCode
    from App.Models.EmailVerificationIpLimit import EmailVerificationIpLimit

    settings = get_settings()
    database = make_url(settings.database_url).database or ""
    if settings.app_env == "prod" and not allow_production:
        raise SystemExit("正式环境迁移须先获发布授权并传入 --allow-production")
    if settings.app_env == "test" and not database.endswith("_codextest"):
        raise SystemExit("测试迁移仅允许 _codextest 数据库")
    engine = get_engine()
    with engine.connect() as connection:
        if not connection.execute(text("SELECT VERSION()")).scalar_one().startswith("8.4."):
            raise SystemExit("迁移要求 MySQL 8.4")
    EmailVerificationCode.__table__.create(bind=engine, checkfirst=True)
    EmailVerificationIpLimit.__table__.create(bind=engine, checkfirst=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--allow-production", action="store_true")
    args = parser.parse_args()
    if args.env_file:
        os.environ.update({key: value for key, value in dotenv_values(args.env_file).items() if value is not None})
    migrate(allow_production=args.allow_production)
