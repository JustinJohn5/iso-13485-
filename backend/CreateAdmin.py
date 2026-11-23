"""交互式创建首个管理员账号。"""

from getpass import getpass

from sqlalchemy import select

from App.Db.Session import session_scope
from App.Models.User import ROLE_ADMIN, User
from App.Utils.Security import hash_password, validate_password_policy
from App.Utils.Logger import configure_logging, get_logger

logger = get_logger(__name__)


def main() -> None:
    from App.Config.Settings import get_settings
    settings = get_settings()
    configure_logging(settings.log_dir, settings.log_level)
    email = input("管理员邮箱：").strip().lower()
    display_name = input("显示名称：").strip()
    password = getpass("管理员密码（至少 8 位，含字母和数字）：")
    validate_password_policy(password)
    with session_scope() as db:
        exists = db.execute(select(User.id).where(User.email == email)).scalar_one_or_none()
        if exists:
            raise SystemExit("该邮箱已存在")
        db.add(User(email=email, display_name=display_name, password_hash=hash_password(password), role=ROLE_ADMIN))
    logger.info("管理员账号创建完成：%s", email)


if __name__ == "__main__":
    main()
