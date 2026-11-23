"""大模型唯一调用入口；配置仅来自 MySQL，失败时不更改原草稿。"""
import json
import logging
from time import monotonic

from openai import APIError, OpenAI

from App.Constants.AuthoringLimits import MAX_INPUT_CHARS, MAX_RESPONSE_CHARS
from App.Dao.LlmConfigDao import LlmConfigDao
from App.Services.Llm.Failure import failure, provider_failure
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
        if not response.choices:
            raise failure('output_empty')
        finish = response.choices[0].finish_reason
        if finish == 'length':
            raise failure('output_truncated')
        if finish == 'content_filter':
            raise failure('output_filtered')
        if finish != 'stop':
            raise failure('output_incomplete')
        text = response.choices[0].message.content or ''
        if not isinstance(text, str):
            raise failure('output_structure')
        if not text.strip():
            raise failure('output_empty')
        if len(text) > MAX_RESPONSE_CHARS:
            raise failure('output_too_long')
        if text.strip().startswith('```'):
            text = '\n'.join(text.strip().splitlines()[1:-1])
        try:
            result = json.loads(text)
        except ValueError:
            raise failure('output_json') from None
        if not isinstance(result, dict):
            raise failure('output_json')
        logger.info('大模型调用成功 model=%s latency_ms=%s tokens=%s', config.model,
                    int((monotonic() - started) * 1000), response.usage.total_tokens if response.usage else 0)
        return result, config.model
    except (APIError, ApiError, ValueError, TypeError, IndexError, AttributeError) as exc:
        if isinstance(exc, ApiError):
            error = exc
        elif isinstance(exc, APIError):
            error = provider_failure(exc)
        else:
            error = failure('output_structure')
        # 异常文本可能来自服务商且含请求内容，不记录原始异常、URL、密钥或正文。
        logger.warning('大模型调用失败 model=%s latency_ms=%s error_type=%s reason=%s provider_status=%s', config.model,
                       int((monotonic() - started) * 1000), type(exc).__name__,
                       error.data['reason'], error.data.get('provider_status', '-'))
        raise error from None
