"""全局 fixture：base_url / api_session / login_token / test_data / unique_username / temp_item / published_item_id；
Day11 新增 Allure 定制钩子：environment.properties 自动生成 / categories.json 注入 / 失败用例自动附加请求响应。

说明：
- conftest.py 中的 fixture 对该目录下所有用例自动可见，无需 import；
- 与 week2_day8.md 任务三、week2_day9.md 任务一、week2_day10.md 任务三、
  week2_day11.md 任务二/三对应；
- 认证通过自定义 Header `token` 携带（非 Bearer），与 Day6 API 文档一致；
- login_token 为 session 级：整个测试会话只登录一次，token 注入 session 后自动携带；
- published_item_id（Day9 新增）：发布一个已知物品供搜索/详情/认领用例复用，
  会话结束自动删除；只读数据，删除/编辑用例请自造数据，不要动它；
- unique_username / temp_item（Day10 新增）：唯一用户名生成 + 临时物品自造自删，
  配合参数化用例做数据隔离；
- pytest_sessionstart（Day11 新增）：测试开始前把 environment.properties（环境信息）
  和 allure/categories.json（自定义缺陷分类）写入 allure-results 目录，
  生成报告时 Allure 自动读取；
- pytest_runtest_makereport（Day11 新增）：用例失败时自动附加该用例最近一次
  请求/响应详情（截断 2000 字符），与 utils/allure_helper.py 配合避免重复附加。
"""

import os
import shutil
import sys
from datetime import datetime

import allure
import pytest
import requests

from config.settings import BASE_URL, TEST_USERNAME, TEST_PASSWORD
from utils.allure_helper import (
    attach_request_response,
    get_last_response,
    has_attached_in_test,
    reset_for_test,
)


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
            # 源码确认（week1_day6 API 文档 v3.3）：列表筛选参数为 title / categoryId /
            # status / userId，无 keyword 参数（初版误用 keyword，已按 API 文档修正）；
            # title 留空=不筛选；"无结果"场景用不存在的分类 ID 实现
            "no_result_category_id": 99999,
        },
        "claim": {
            # 已实测：itemType=1 为认领失物（提交归还申请），0 为认领招领物品（从前端确认）
            "item_type": 1,
            "description": "这是我的学生证，学号与照片完全吻合，请求归还。",
        },
    }


@pytest.fixture()
def unique_username():
    """生成唯一用户名（注册类用例防冲突）。

    按 API 文档（week1_day6 v3.3）：注册 POST /api/user/add，username 为
    3-50 位字母数字（不含下划线），email 唯一且必填——用户名取字母+时间戳。
    注册入库用例在数据库可达时使用；当前 DB 不可达，用例整体跳过。
    """
    import time

    return f"auto{int(time.time() * 1000)}"


@pytest.fixture()
def temp_item(api_session, base_url, first_category_id):
    """创建一个临时物品，测试结束后自动删除（Day10 新增）。

    替代"发布→按标题回查→用例内 finally 删除"的重复三步：
    setup  用唯一标题发布物品（POST /api/lost-item），按标题回查列表拿到 ID；
    yield  {"id": 物品ID, "title": 标题}；
    teardown 删除该物品（已删过的场景（删除用例）容错忽略）。

    注意：发布响应不含物品 ID（已实测契约），ID 需翻页回查（_find_item 逻辑）。
    """
    import time

    title = f"临时物品_{int(time.time() * 1000)}"
    try:
        resp = api_session.post(
            f"{base_url}/api/lost-item",
            json={
                "title": title,
                "description": "temp_item fixture 发布的临时物品，描述足够详细以通过内容完整性校验。",
                "categoryId": first_category_id,
                "lostPlace": "测试地点-自习室",
                "lostTime": "2026-08-01 12:00:00",
                "images": "",
                "contactName": "测试联系人",
                "contactPhone": "13800000000",
            },
            timeout=10,
        )
        body = resp.json()
        assert body.get("code") == "200", f"发布临时物品失败: {body}"
    except requests.exceptions.RequestException as exc:
        pytest.skip(f"后端不可达，跳过依赖前置数据的用例: {exc}")
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
    assert item_id, f"发布后未按标题回查到临时物品: {title}"
    yield {"id": item_id, "title": title}
    # teardown：删除临时物品；删除用例可能已删过（返回 code=-1），容错忽略
    try:
        api_session.delete(f"{base_url}/api/lost-item/{item_id}", timeout=10)
    except requests.exceptions.RequestException:
        pass


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
                "images": "",
                "contactName": "测试联系人",
                "contactPhone": "13800000000",
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


# ---------------------------------------------------------------------------
# Day11：Allure 报告定制钩子
# ---------------------------------------------------------------------------

def pytest_sessionstart(session):
    """测试会话开始前，把环境信息与自定义分类写入 allure-results。

    - environment.properties：Allure Overview 页面的环境信息块（环境名/BaseURL/
      Python 版本/平台/测试人员/测试日期/服务器规格）；
    - categories.json：自定义缺陷分类（接口超时/环境不可达/断言失败/已知Bug），
      模板放在项目 allure/ 目录，复制到结果目录后生成报告时生效。

    为什么用 pytest_sessionstart 而不是 pytest_configure（week2_day11.md
    任务二原方案）：addopts 中带 --clean-alluredir 时，allure-pytest 会在
    pytest_configure 阶段清空结果目录——不同版本清空与写入的先后顺序不稳定，
    可能把刚写好的 environment.properties 清掉。sessionstart 在配置完成后、
    首个用例执行前触发，与 clean 时序天然无冲突。
    """
    allure_dir = session.config.getoption("--alluredir") or "./allure-results"
    os.makedirs(allure_dir, exist_ok=True)

    env_props = f"""\
TestEnvironment=测试环境（真实后端）
BaseURL={BASE_URL}
PythonVersion={sys.version.split()[0]}
Platform={sys.platform}
Tester=测试学员
TestDate={datetime.now().strftime("%Y-%m-%d %H:%M")}
ServerMemory=4G轻量云服务器
"""
    with open(os.path.join(allure_dir, "environment.properties"), "w", encoding="utf-8") as f:
        f.write(env_props)

    categories = os.path.join(os.path.dirname(__file__), "allure", "categories.json")
    if os.path.exists(categories):
        shutil.copy(categories, os.path.join(allure_dir, "categories.json"))


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """用例失败时自动附加最近一次请求/响应详情（Day11 任务三）。

    机制（与 utils/allure_helper.py 配合）：
    - 每个用例开始时 reset_for_test() 清空记录；
    - 用例内 attach_request_response(resp) 会"附加 + 记录"；remember_response(resp)
      只记录不附加（模拟用例未主动附加的场景）；
    - 用例失败时：若本用例还没主动附加过，就把最近一次记录的响应补一份附件
      （名为"失败用例自动附加的请求/响应详情"）；完全没有响应可附加时（如
      fixture 阶段失败），附加一条说明文本，避免空失败无从查起。
    """
    outcome = yield
    report = outcome.get_result()
    if report.when == "setup":
        reset_for_test()
    if report.failed and report.when in ("call", "teardown"):
        resp = get_last_response()
        if resp is not None and not has_attached_in_test():
            attach_request_response(resp, name="失败用例自动附加的请求/响应详情")
        elif resp is None:
            allure.attach(
                "该用例在发送请求前失败（如 fixture 阶段异常），没有可附加的响应。",
                "失败说明",
                allure.attachment_type.TEXT,
            )
