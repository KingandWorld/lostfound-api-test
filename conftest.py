"""全局 fixture：base_url / api_session / login_token / test_data / published_item_id。

说明：
- conftest.py 中的 fixture 对该目录下所有用例自动可见，无需 import；
- 与 week2_day8.md 任务三、week2_day9.md 任务一对应；
- 认证通过自定义 Header `token` 携带（非 Bearer），与 Day6 API 文档一致；
- login_token 为 session 级：整个测试会话只登录一次，token 注入 session 后自动携带；
- published_item_id（Day9 新增）：发布一个已知物品供搜索/详情/认领用例复用，
  会话结束自动删除；只读数据，删除/编辑用例请自造数据，不要动它。
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


@pytest.fixture(scope="session", autouse=True)
def _ensure_login(login_token):
    """session 级 autouse：整个会话开始时先登录一次，token 注入 api_session。

    Day8 时用例都集中在 test_login.py（其中一条依赖 login_token 恰好触发登录）；
    Day9 新增的物品/搜索/认领用例只依赖 api_session，若不自动触发登录，
    这些用例会因 session 未携带 token 而返回 401"认证失败"。
    """
    return login_token


@pytest.fixture(scope="session")
def first_category_id(api_session, base_url):
    """分类列表第一个分类的 ID（发布物品必填 categoryId，已实测"分类无效"校验）。"""
    try:
        resp = api_session.get(f"{base_url}/api/category/list", timeout=10)
    except requests.exceptions.RequestException as exc:
        pytest.skip(f"后端不可达，跳过依赖分类数据的用例: {exc}")
    categories = resp.json().get("data") or []
    if not categories:
        pytest.skip("系统无分类数据，发布物品用例无法构造合法请求")
    return categories[0]["id"]


@pytest.fixture(scope="session")
def test_data():
    """测试数据：账号 + 登录场景 + 物品/搜索/认领参数（Day9 补充）。"""
    return {
        "user": {"username": TEST_USERNAME, "password": TEST_PASSWORD},
        "login": {
            "success": {"username": TEST_USERNAME, "password": TEST_PASSWORD},
            "wrong_password": {"username": TEST_USERNAME, "password": "WrongPass123"},
            "empty_fields": {"username": "", "password": ""},
            "nonexistent_user": {"username": "no_such_user_888", "password": "Test123456"},
        },
        "items": {
            # 发布接口必填字段校验：缺 title 应被拒绝（title 必填，已实测）
            "missing_required": {"description": "缺少标题的物品"},
        },
        "search": {
            # 已实测（2026-08-03）：后端忽略 keyword 参数（过滤未实现，已知缺陷）；
            # "无结果"场景改用不存在的分类 ID 实现
            "no_result_category_id": 99999,
        },
        "claim": {
            # 已实测：itemType=1 为认领失物（提交归还申请），0 为认领招领物品（从前端确认）
            "item_type": 1,
            "description": "这是我的学生证，学号与照片完全吻合，请求归还。",
        },
    }


@pytest.fixture(scope="session")
def published_item_id(api_session, base_url, first_category_id):
    """发布一个已知物品，供搜索/详情/认领"自己物品"用例复用。

    返回 {"id": 物品ID, "title": 标题, "category_id": 分类ID}；
    分类取 first_category_id（/api/category/list 第一个分类，data 为数组）。

    已实测契约（2026-08-03 对真实后端探测确认）：
    - 发布：POST /api/lost-item（前端实际路径），必填 title/description/categoryId/
      lostTime/contactName 等，description 过短会返回 code=-1"发布内容过于简单"；
      userId 可省略（服务端从 token 解析）；
    - 发布成功响应不含物品 ID（data 为提示字符串），需按标题回查列表拿到 ID；
    - 列表分页参数为 currentPage/size（page/pageSize 会被忽略）；
    - 删除：DELETE /api/lost-item/{id}。
    """
    import time

    title = f"自动化搜索物品_{int(time.time() * 1000)}"
    try:
        resp = api_session.post(
            f"{base_url}/api/lost-item",
            json={
                "title": title,
                "description": "conftest 发布的前置数据物品，描述足够详细以通过发布接口的内容完整性校验。",
                "categoryId": first_category_id,
                "lostPlace": "测试地点-图书馆二楼",
                "lostTime": "2026-08-01 12:00:00",
                "contactName": "测试联系人",
                "contactPhone": "13800000000",
                "contactEmail": "test@test.com",
                "status": 0,
            },
            timeout=10,
        )
        body = resp.json()
        assert body.get("code") == "200", f"发布前置物品失败: {body}"
        # 发布响应不含 ID，翻页回查列表按标题定位
        item_id = None
        for page in range(1, 6):
            page_resp = api_session.get(
                f"{base_url}/api/lost-item/page",
                params={"currentPage": page, "size": 50},
                timeout=10,
            )
            records = (page_resp.json().get("data") or {}).get("records") or []
            for rec in records:
                if rec.get("title") == title:
                    item_id = rec["id"]
                    break
            if item_id or len(records) < 50:
                break
        assert item_id, f"发布后未按标题回查到物品: {title}"
    except requests.exceptions.RequestException as exc:
        pytest.skip(f"后端不可达，跳过依赖前置数据的用例: {exc}")
    yield {"id": item_id, "title": title, "category_id": first_category_id}
    # teardown：会话结束删除，避免污染后续天数的数据
    api_session.delete(f"{base_url}/api/lost-item/{item_id}", timeout=10)
