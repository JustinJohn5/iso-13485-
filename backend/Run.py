"""按环境配置启动后端服务。"""

import uvicorn

from App.Config.Settings import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run("Main:app", host=settings.backend_host, port=settings.backend_port)


if __name__ == "__main__":
    main()
