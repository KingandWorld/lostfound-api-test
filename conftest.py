"""全局 fixture：base_url / api_session / login_token / test_data。

说明：
- conftest.py 中的 fixture 对该目录下所有用例自动可见，无需 import；
- 与 week2_day8.md 任务三一一对应；
- 认证通过自定义 Header `token` 携带（非 Bearer），与 Day6 API 文档一致；
- login_token 为 session 级：整个测试会话只登录一次，token 注入 session 后自动携带。
"""

import pytest
import requests

from config.settings import BASE_URL, TEST_USERNAME, TEST_PASSWORD


@pytest.fixture(scope="session")
def base_url():
    """基础地址：来自 .env 的 BASE_URL。"""
    return BASE_URL


@pytest.fixture(scope="session")
def api_session():
    """requests.Session：连接复用；login_token 注入后自动携带 token。"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="session")
def login_token(api_session, base_url):
    """只登录一次，把 token 写入 session headers（自定义 Header `token`，非 Bearer）。

    学习阶段：后端不可达时跳过（见 pytest.skip），避免环境问题中断学习；
    接入 Jenkins 前，建议将不可达场景改为直接失败。
    """
    try:
        resp = api_session.post(
            f"{base_url}/api/user/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
            timeout=10,
        )
    except requests.exceptions.RequestException as exc:
        pytest.skip(f"后端不可达，跳过依赖登录的用例: {exc}")
    body = resp.json()
    assert body.get("code") == "200", f"登录失败: {body}"
    token = body["data"]["token"]
    api_session.headers["token"] = token
    return token


@pytest.fixture(scope="session")
def test_data():
    """测试数据：账号信息 + 登录场景参数（物品/认领数据 Day9 补充）。"""
    return {
        "user": {"username": TEST_USERNAME, "password": TEST_PASSWORD},
        "login": {
            "success": {"username": TEST_USERNAME, "password": TEST_PASSWORD},
            "wrong_password": {"username": TEST_USERNAME, "password": "WrongPass123"},
            "empty_fields": {"username": "", "password": ""},
            "nonexistent_user": {"username": "no_such_user_888", "password": "Test123456"},
        },
    }
