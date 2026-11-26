"""初始化 MySQL 业务表；仅适用于空的开发/测试数据库。"""

from App.Config.Settings import get_settings
from App.Db.Base import Base
from App.Db.Session import get_engine
from App.Models import AiReview, AiReviewDecision, AuditLog, EmailVerificationCode, EmailVerificationIpLimit, Finding, LlmConfig, UploadedFile, User, ValidationDocument, ValidationRun
from App.Utils.Logger import configure_logging, get_logger

logger = get_logger(__name__)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_dir, settings.log_level)
    Base.metadata.create_all(bind=get_engine())
    logger.info("数据库表已初始化；此命令不会修改已存在表结构")


if __name__ == "__main__":
    main()
