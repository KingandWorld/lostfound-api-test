"""登录接口测试用例（week2_day8.md 任务四，≥4 条）。

设计说明：
- 登录正是被测对象，因此本文件用例直接使用 api_session 发裸请求，
  不依赖 login_token（否则"先登录成功再测登录"没有意义）；
- login_token fixture 的正确性由 test_login_token_fixture_works 单独验证，供 Day9 复用；
- 学习阶段：后端不可达时用例自动跳过（见 _request），接入 Jenkins 前建议改为直接失败；
- 断言中出现的字段名（username、token）以实际接口返回为准，不符时打印响应修正。
"""

import allure
import pytest
import requests


def _request(session, method, url, **kwargs):
    """发送请求；后端不可达时跳过用例，避免环境问题中断学习流程。"""
    kwargs.setdefault("timeout", 10)
    try:
        return session.request(method, url, **kwargs)
    except requests.exceptions.RequestException as exc:
        pytest.skip(f"后端不可达，跳过真实请求: {exc}")


@allure.feature("用户认证")
class TestLogin:

    @allure.story("正常登录")
    @allure.title("使用正确的账号密码登录，返回 token 与用户信息")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_login_success(self, api_session, base_url, test_data):
        with allure.step("准备登录参数"):
            payload = test_data["login"]["success"]
        with allure.step(f"发送登录请求：POST {base_url}/api/user/login"):
            resp = _request(api_session, "POST", f"{base_url}/api/user/login", json=payload)
        with allure.step("断言响应码为 200"):
            body = resp.json()
            assert body.get("code") == "200", f"登录失败: {body}"
        with allure.step("断言返回 token 非空"):
            assert body["data"].get("token"), "响应 data.token 为空"
        with allure.step("断言返回用户信息（字段名以实际接口为准）"):
            assert body["data"].get("username") == test_data["user"]["username"], body

    @allure.story("异常登录")
    @allure.title("使用错误的密码登录，返回失败提示且不发放 token")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_login_wrong_password(self, api_session, base_url, test_data):
        with allure.step("准备错误密码参数"):
            payload = test_data["login"]["wrong_password"]
        with allure.step("发送登录请求"):
            resp = _request(api_session, "POST", f"{base_url}/api/user/login", json=payload)
        with allure.step("断言登录不成功"):
            body = resp.json()
            assert body.get("code") != "200", f"错误密码不应登录成功: {body}"
        with allure.step("断言不发放 token（字段名以实际接口为准）"):
            assert not body["data"].get("token"), "错误密码不应返回 token"

    @allure.story("异常登录")
    @allure.title("账号密码为空提交，返回参数校验提示")
    @allure.severity(allure.severity_level.NORMAL)
    def test_login_empty_fields(self, api_session, base_url, test_data):
        with allure.step("准备空表单参数"):
            payload = test_data["login"]["empty_fields"]
        with allure.step("发送登录请求"):
            resp = _request(api_session, "POST", f"{base_url}/api/user/login", json=payload)
        with allure.step("断言登录不成功"):
            body = resp.json()
            assert body.get("code") != "200", f"空表单不应登录成功: {body}"

    @allure.story("异常登录")
    @allure.title("使用不存在的账号登录，返回错误提示")
    @allure.severity(allure.severity_level.NORMAL)
    def test_login_nonexistent_user(self, api_session, base_url, test_data):
        with allure.step("准备不存在账号参数"):
            payload = test_data["login"]["nonexistent_user"]
        with allure.step("发送登录请求"):
            resp = _request(api_session, "POST", f"{base_url}/api/user/login", json=payload)
        with allure.step("断言登录不成功"):
            body = resp.json()
            assert body.get("code") != "200", f"不存在用户不应登录成功: {body}"

    @allure.story("框架验证")
    @allure.title("login_token fixture 登录一次并把 token 注入 session headers")
    @allure.severity(allure.severity_level.NORMAL)
    def test_login_token_fixture_works(self, login_token, api_session):
        with allure.step("断言 login_token 非空"):
            assert login_token, "login_token 为空"
        with allure.step("断言 token 已注入 api_session headers"):
            assert api_session.headers.get("token") == login_token, api_session.headers
