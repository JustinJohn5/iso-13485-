"""大模型唯一调用入口；配置仅来自 MySQL，失败时不更改原草稿。"""
import json
import logging
from time import monotonic

from openai import APIError, OpenAI

from App.Constants.AuthoringLimits import MAX_INPUT_CHARS, MAX_RESPONSE_CHARS
from App.Dao.LlmConfigDao import LlmConfigDao
from App.Utils.Crypto import decrypt_secret
from App.Utils.Errors import ApiError

logger = logging.getLogger(__name__)


def complete_json(db, system: str, payload: dict) -> tuple[dict, str]:
    config = LlmConfigDao.get_default(db)
    if config is None or not config.enabled or not config.base_url or not config.model or not config.api_key_cipher:
        raise ApiError(1401)
    key = decrypt_secret(config.api_key_cipher)
    content = json.dumps(payload, ensure_ascii=False)
    if len(system) + len(content) > MAX_INPUT_CHARS:
        raise ApiError(1001, f'AI 请求总输入超过 {MAX_INPUT_CHARS:,} 字符，请减少资料或分批编写；原草稿未修改')
    started = monotonic()
    # 禁止 SDK/HTTP 的 DEBUG 请求日志记录正文及认证头。
    for name in ('openai', 'httpx', 'httpx2', 'httpcore'):
        logging.getLogger(name).setLevel(logging.WARNING)
    try:
        # 总计最多两次尝试，每次显式超时，重试由官方 SDK 统一处理。
        with OpenAI(base_url=config.base_url, api_key=key, timeout=float(config.timeout_seconds), max_retries=1) as client:
            response = client.chat.completions.create(
                model=config.model,
                messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': content}],
                max_tokens=config.max_tokens,
                temperature=float(config.temperature),
            )
        if not response.choices or response.choices[0].finish_reason != 'stop':
            raise ValueError('模型输出不完整')
        text = response.choices[0].message.content or ''
        if len(text) > MAX_RESPONSE_CHARS:
            raise ValueError('模型输出过长')
        if text.strip().startswith('```'):
            text = '\n'.join(text.strip().splitlines()[1:-1])
        result = json.loads(text)
        if not isinstance(result, dict):
            raise ValueError('模型未返回 JSON 对象')
        logger.info('大模型调用成功 model=%s latency_ms=%s tokens=%s', config.model,
                    int((monotonic() - started) * 1000), response.usage.total_tokens if response.usage else 0)
        return result, config.model
    except (APIError, ValueError, TypeError, IndexError, AttributeError) as exc:
        # 异常文本可能来自服务商且含请求内容，不记录原始异常、URL、密钥或正文。
        logger.warning('大模型调用失败 model=%s latency_ms=%s error_type=%s', config.model,
                       int((monotonic() - started) * 1000), type(exc).__name__)
        raise ApiError(1402, 'AI 编写失败或输出格式异常，原草稿已保留，可继续人工编写或稍后重试') from None
