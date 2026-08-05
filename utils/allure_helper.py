"""Allure 附件辅助（Day11 实现）：attach_request_response / remember_response。

用途：
- attach_request_response(resp)：把一次 HTTP 请求的完整信息（URL/方法/请求体/
  响应状态/响应头/响应体）附加进 Allure 报告，并**记录为失败自动附加的候选**；
- remember_response(resp)：只记录不附加——供"失败用例自动附加"演示/兜底用，
  测试失败时由 conftest 的 pytest_runtest_makereport 钩子统一附加；
- 所有内容统一截断（max_len=2000，与 week2_day11.md 任务三一致），避免超大
  响应（如几百条列表数据）撑爆报告；
- 请求头中的敏感字段（token/authorization/cookie）统一掩码，避免 token 泄漏
  到报告中（面试可讲：报告对外分享前的敏感信息脱敏）。

与 conftest 的配合：
- 每个用例开始时 conftest 调用 reset_for_test() 清空记录；
- 用例内 attach_request_response() 主动附加（报告中每个用例都能看到请求/响应）；
- 若用例失败且未主动附加（如 fixture 阶段异常、或只 remember 未 attach），
  钩子用 get_last_response() 取最近一次响应补一份"失败用例自动附加的请求/响应详情"。
"""

import json

import allure

# 最近一次被记录/附加的响应（模块级：本项目未用 xdist 并行，单线程安全）
_last_response = None
# 当前测试是否已主动附加过（避免失败时钩子重复附加同一份内容）
_attached_in_test = False

# 敏感请求头：附加时统一掩码，防止 token 等凭据进入报告
_SENSITIVE_HEADERS = {"token", "authorization", "cookie", "set-cookie"}


def reset_for_test():
    """每个用例开始时调用，清空上一条记录的响应（conftest 调用）。"""
    global _last_response, _attached_in_test
    _last_response = None
    _attached_in_test = False


def _truncate(content, max_len=2000):
    """把请求/响应内容转成可读文本并截断（bytes/None/dict 统一处理）。"""
    if content is None:
        return "(无内容)"
    if isinstance(content, bytes):
        try:
            content = content.decode("utf-8", errors="replace")
        except Exception:
            content = repr(content)
    if not isinstance(content, str):
        try:
            content = json.dumps(content, ensure_ascii=False, indent=2)
        except Exception:
            content = str(content)
    if len(content) <= max_len:
        return content
    return f"{content[:max_len]}\n...（已截断，完整内容 {len(content)} 字符）"


def _mask_headers(headers):
    """响应头转文本；敏感字段值掩码。"""
    if headers is None:
        return "(无响应头)"
    lines = []
    for key, value in headers.items():
        if key.lower() in _SENSITIVE_HEADERS:
            value = "***（敏感字段，已掩码）"
        lines.append(f"{key}: {value}")
    return "\n".join(lines) or "(无响应头)"


def attach_request_response(resp, name="请求/响应详情", max_len=2000):
    """附加一次请求/响应的完整信息，并记录为失败自动附加的候选。

    用法：用例发出主请求后立即调用
        attach_request_response(resp)
    报告对应 step 下会出现名为 name 的 TEXT 附件；
    附件内容统一截断 max_len 字符（默认 2000）。
    """
    global _last_response, _attached_in_test
    _last_response = resp
    _attached_in_test = True
    if resp is None:
        return
    req = getattr(resp, "request", None)
    method = getattr(req, "method", "")
    url = getattr(req, "url", "")
    text = (
        f"URL: {method} {url}\n"
        f"Request Body: {_truncate(getattr(req, 'body', None), max_len)}\n"
        f"Response Status: {resp.status_code}\n"
        f"Response Headers:\n{_mask_headers(resp.headers)}\n"
        f"Response Body: {_truncate(resp.text, max_len)}"
    )
    allure.attach(text, name, allure.attachment_type.TEXT)


def remember_response(resp):
    """只记录不附加（失败自动附加演示用）：模拟"用例未主动附加"的场景，
    测试失败时由 conftest 钩子统一附加。"""
    global _last_response
    _last_response = resp


def get_last_response():
    """取最近一次记录的响应（conftest 失败钩子用）。"""
    return _last_response


def has_attached_in_test():
    """当前测试是否已主动附加过（避免钩子重复附加）。"""
    return _attached_in_test
