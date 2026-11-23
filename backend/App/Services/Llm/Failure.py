"""只根据状态与已知特征分类上游错误，不向日志或页面传递原始响应。"""
import json

from openai import APIConnectionError, APITimeoutError

from App.Utils.Errors import ApiError

MESSAGES = {
    'invalid_model': '模型标识无效或服务商不支持，请在“模型配置”填写服务商提供的真实 API 模型 ID',
    'authentication': '模型服务认证失败，请在“模型配置”检查或重新填写 API Key',
    'permission': '模型服务拒绝访问，请检查 API Key 的模型权限及服务商访问限制',
    'quota': '模型服务额度或余额不足，请检查服务商账户',
    'rate_limit': '模型服务请求过于频繁，请稍后重试',
    'context_limit': '请求超出所选模型的上下文窗口，请减少资料或改用支持更长上下文的模型',
    'output_limit': '最大输出 token 超出所选模型允许范围，请在“模型配置”调低该值',
    'invalid_parameters': '模型服务拒绝请求参数，请检查模型标识、最大输出 token、温度及接口兼容性',
    'endpoint': '模型接口不存在，请检查服务地址及服务商要求的 API 路径前缀',
    'timeout': '模型服务调用超时，请稍后重试，或在“模型配置”按需增加单次超时',
    'connection': '无法连接模型服务，请检查服务地址、网络及代理配置',
    'upstream': '模型服务暂时异常，请稍后重试',
    'request_failed': '模型服务调用失败，请检查配置或稍后重试',
    'output_truncated': '模型输出达到长度限制，正文未完整生成；请按模型能力增加最大输出 token，或缩小本次编写范围',
    'output_filtered': '模型服务因内容限制未返回完整正文，请检查资料及编写要求',
    'output_empty': '模型服务未返回正文，请重试或检查模型兼容性',
    'output_incomplete': '模型输出未正常结束，请重试或检查模型兼容性',
    'output_too_long': '模型响应超过应用允许长度，请缩小本次编写范围',
    'output_json': '模型未按要求返回有效 JSON，请明确要求按模板章节输出，或更换兼容模型',
    'output_structure': '模型返回结构不兼容，请检查接口是否支持 Chat Completions 格式',
}


def failure(reason: str, provider_status: int | None = None) -> ApiError:
    data = {'reason': reason}
    if provider_status is not None:
        data['provider_status'] = provider_status
    return ApiError(1402, f'{MESSAGES[reason]}；原草稿已保留', data=data)


def provider_failure(exc) -> ApiError:
    if isinstance(exc, APITimeoutError):
        return failure('timeout')
    if isinstance(exc, APIConnectionError):
        return failure('connection')
    status = getattr(exc, 'status_code', None)
    if status == 401:
        return failure('authentication', status)
    if status == 403:
        return failure('permission', status)
    if status == 402:
        return failure('quota', status)

    # 原文只在内存中参与分类，绝不写入返回值或日志，防止服务商回显密钥/正文。
    body = getattr(exc, 'body', None)
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except ValueError:
            body = {'message': body}
    error = body.get('error', body) if isinstance(body, dict) else {}
    error = error if isinstance(error, dict) else {}
    code = str(error.get('code', getattr(exc, 'code', '')) or '').casefold()
    message = str(error.get('message', '')).casefold()
    text = f'{code} {message}'
    signatures = [
        ('quota', ('insufficient_quota', 'insufficient_balance', 'insufficient balance', 'insufficient credits')),
        ('context_limit', ('context_length_exceeded', 'context length', 'context window', 'maximum context')),
        ('invalid_model', ('model_not_found', 'model_not_exist', 'invalid_model', 'unknown model',
                           'model not exist', 'model does not exist', 'model not found', 'invalid model',
                           'supported api model names')),
        ('output_limit', ('max_tokens', 'max_completion_tokens', 'max_output_tokens')),
    ]
    # 只解读参数/资源/额度类错误，5xx 仍归为服务商异常。
    if status in (400, 404, 422, 429):
        for reason, phrases in signatures:
            if any(phrase in text for phrase in phrases):
                return failure(reason, status)
    if status == 429:
        return failure('rate_limit', status)
    if status == 404:
        return failure('endpoint', status)
    if status in (400, 422):
        return failure('invalid_parameters', status)
    if isinstance(status, int) and status >= 500:
        return failure('upstream', status)
    return failure('request_failed', status)
