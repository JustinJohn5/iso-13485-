"""仅在本机回环地址提供合成 OpenAI 兼容响应的测试服务。"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread


class MockLlmServer:
    """返回可确定引用输入候选片段的合成模型结果。"""

    def __init__(self) -> None:
        self.server: ThreadingHTTPServer | None = None
        self.thread: Thread | None = None

    @property
    def base_url(self) -> str:
        if self.server is None:
            raise RuntimeError("模拟模型服务尚未启动")
        return f"http://127.0.0.1:{self.server.server_address[1]}/v1"

    def start(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path != "/v1/chat/completions":
                    self.send_error(404)
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length < 1 or length > 1_500_000:
                        raise ValueError("请求长度非法")
                    request = json.loads(self.rfile.read(length))
                    messages = request["messages"]
                    payload = json.loads(messages[-1]["content"])
                    snippets = payload.get("候选片段", [])
                    elements = payload.get("必需要素")
                    if elements is not None:
                        reviews = []
                        for element in elements:
                            if snippets:
                                snippet = snippets[0]
                                quote = snippet["text"][:min(160, len(snippet["text"]))]
                                reviews.append({
                                    "element_id": element["element_id"], "status": "supporting_signal",
                                    "support": [{"snippet_id": snippet["snippet_id"], "quote": quote,
                                                 "reason": "模拟模型为测试生成的候选说明。"}],
                                    "contrary": [], "rationale": "只针对输入候选片段的测试意见。",
                                    "questions": [],
                                })
                            else:
                                reviews.append({
                                    "element_id": element["element_id"], "status": "not_found_in_candidates",
                                    "support": [], "contrary": [],
                                    "rationale": "本次候选片段中未找到相关表述，须检查原文件其余内容。",
                                    "questions": ["请人工核对原文件其余内容。"],
                                })
                        result = {"summary": "测试模拟结果，仅用于验证接口和引用校验。", "reviews": reviews}
                    else:
                        claims = []
                        if snippets:
                            snippet = snippets[0]
                            claims.append({
                                "signal": "support", "snippet_id": snippet["snippet_id"],
                                "quote": snippet["text"][:min(160, len(snippet["text"]))],
                                "reason": "模拟模型为测试生成的候选说明。",
                            })
                        result = {
                            "summary": "测试模拟结果，仅用于验证接口和引用校验。",
                            "claims": claims,
                            "questions": [] if claims else ["请人工核对原文件其余内容。"],
                        }
                    content = json.dumps(result, ensure_ascii=False)
                    response = json.dumps({
                        "id": "chatcmpl-e2e", "object": "chat.completion", "created": 0,
                        "model": request.get("model", "e2e-review"),
                        "choices": [{"index": 0, "finish_reason": "stop",
                                     "message": {"role": "assistant", "content": content}}],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                    }).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(response)))
                    self.end_headers()
                    self.wfile.write(response)
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    self.send_error(400)

            def log_message(self, _format, *_args):
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.thread is not None:
            self.thread.join(timeout=2)
            self.thread = None
