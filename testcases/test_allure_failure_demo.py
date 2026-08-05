"""Day11 任务三验证用例：故意失败，验证"失败用例自动附加请求/响应"已生效。

设计（与 week2_day11.md 任务三第 3 步对应）：
- 用例先发一次真实请求（正确账号登录，必然成功），但只"记录"不主动附加
  （remember_response，模拟用例漏写 attach 的场景）；
- 随后故意断言一个错误条件触发失败——conftest 的 pytest_runtest_makereport
  钩子应在失败时自动附加名为"失败用例自动附加的请求/响应详情"的附件；
- 标记 allure_demo：默认不参与全量运行（pytest.ini addopts 中
  -m "not allure_demo"），不影响交付基线；验证完可保留作示例，也可删除。

运行方式：
    pytest -m allure_demo --alluredir=./allure-results-demo
    allure serve ./allure-results-demo
然后在报告中展开该用例，检查"Attachments"中是否出现自动附加的请求/响应详情。

注意：该用例会"失败"（exit code 1）——这是预期行为，目的就是制造一次失败；
后端不可达时用例会跳过（_request 的既有行为），无法演示失败附加。
"""

import allure
import pytest
import requests

from utils.allure_helper import remember_response


def _request(session, method, url, **kwargs):
    """发送请求；后端不可达时跳过用例（沿用其他测试文件写法）。"""
    kwargs.setdefault("timeout", 10)
    try:
        return session.request(method, url, **kwargs)
    except requests.exceptions.RequestException as exc:
        pytest.skip(f"后端不可达，跳过真实请求: {exc}")


@allure.feature("框架验证")
class TestFailureAttachDemo:

    @allure.story("失败自动附加验证")
    @allure.title("故意失败的用例：验证失败时自动附加请求/响应详情")
    @pytest.mark.allure_demo
    def test_deliberate_failure_for_attach_demo(self, api_session, base_url, test_data):
        with allure.step("发送一次真实登录请求（正确账号，必然成功）"):
            resp = _request(api_session, "POST", f"{base_url}/api/user/login",
                            json=test_data["login"]["success"])
        with allure.step("只记录响应不主动附加（模拟用例漏写 attach 的场景）"):
            remember_response(resp)
        with allure.step("故意断言错误条件，触发失败自动附加"):
            assert resp.json().get("code") == "999", \
                f"故意失败：验证失败用例自动附加请求/响应详情（实际 code={resp.json().get('code')}）"
