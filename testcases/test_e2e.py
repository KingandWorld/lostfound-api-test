"""端到端场景测试（Day12 任务一）：核心业务流程全链路验收，共 4 条。

设计说明：
- 每条用例覆盖 3+ 个接口的完整调用链（真实工作流，非单接口验证）；
- 数据全部自造自清（唯一标题 + teardown 删除），用例间互不干扰；
- 端到端链路多接口串联，偶发超时更易出现 → 类级别加
  @pytest.mark.flaky(reruns=2, reruns_delay=1) 重试兜底（Day12 任务二机制）；
- 认领流程需要两个已审核账号：用户A=TEST_USERNAME（.env），用户B=E2E_USERNAME
  （.env 新增 E2E_USERNAME/E2E_PASSWORD，缺失时跳过）——新注册用户会被
  "待审核"拦截无法登录（真实业务规则，见流程1中的验证步骤）。

已实测契约（2026-08-12 对真实后端探测确认，与 API 文档 v3.3 一致）：
- 注册：POST /api/user/add（公开）→ code=200"创建成功"；新用户状态"待审核"，
  登录返回 code=-1"待审核: 请等待管理员审核..."（非登录成功）；
- 当前用户：GET /api/user/current → data.id / data.name；更新信息：
  PUT /api/user/{id}，body 传部分字段即可（如 {"name": "xxx"}）→"更新成功"；
- 发布者查看"他人对我的认领申请"：GET /api/claim/page（返回记录含
  itemId/itemTitle/username/status 等展示字段，status 0=待审核）；
- 审核认领：PUT /api/claim/audit，body {"id":N,"status":1,"auditRemark":""}，
  1=通过 2=拒绝；通过后物品状态自动变为 1（已认领）；
- 已处理认领的物品仍可删除（实测清理通过）；
- 列表/搜索：GET /api/lost-item/page，筛选参数 title（无 keyword）；
- 发布成功响应不含物品 ID，需按标题回查（_find_item）；
- 编辑：PUT /api/lost-item/{id}，body 同发布；删除：DELETE /api/lost-item/{id}。
"""

import time

import allure
import pytest
import requests

from config.settings import E2E_PASSWORD, E2E_USERNAME, TEST_PASSWORD, TEST_USERNAME
from utils.allure_helper import attach_request_response
from utils.ci_guard import guard_unreachable  # Day13：环境不可达统一出口（学习模式跳过 / CI 模式失败）


def _request(session, method, url, **kwargs):
    """发送请求；后端不可达时跳过用例（沿用其他测试文件写法）。"""
    kwargs.setdefault("timeout", 10)
    try:
        return session.request(method, url, **kwargs)
    except requests.exceptions.RequestException as exc:
        guard_unreachable(exc)


def _item_payload(title: str, category_id) -> dict:
    """构造发布/编辑物品请求体（与 test_items.py 契约一致）。"""
    return {
        "title": title,
        "description": "这是一条用于端到端流程测试的失物描述，内容足够详细，"
                       "包含物品颜色、品牌、丢失时间等特征信息，"
                       "用于通过发布接口的内容完整性校验。",
        "categoryId": category_id,
        "lostPlace": "测试地点-图书馆三楼",
        "lostTime": "2026-08-01 12:00:00",
        "images": "",
        "contactName": "测试联系人",
        "contactPhone": "13800000000",
    }


def _find_item(session, base_url, title, max_pages=5):
    """发布接口不返回物品 ID，按标题翻页回查列表定位记录。"""
    for page in range(1, max_pages + 1):
        resp = _request(session, "GET", f"{base_url}/api/lost-item/page",
                        params={"currentPage": page, "size": 50})
        records = (resp.json().get("data") or {}).get("records") or []
        for rec in records:
            if rec.get("title") == title:
                return rec
        if len(records) < 50:
            break
    return None


def _new_session():
    """全新 requests.Session（不带 token，用于流程中的显式登录步骤）。"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


def _login(session, base_url, username, password):
    """登录并把 token 注入 session 头，返回登录响应（供调用方断言/附加）。"""
    resp = _request(session, "POST", f"{base_url}/api/user/login",
                    json={"username": username, "password": password})
    body = resp.json()
    if body.get("code") == "200":
        session.headers["token"] = body["data"]["token"]
    return resp


@pytest.fixture()
def second_user_session(base_url):
    """端到端认领流程的用户B会话（Day12 新增）。

    已实测：新注册用户状态为"待审核"，无法登录（流程1验证该业务规则），
    因此认领流程的用户B复用 .env 中配置的已审核账号 E2E_USERNAME/E2E_PASSWORD；
    未配置时跳过认领用例（teardown 清理已通过测试完成的申请/物品）。
    """
    if not E2E_USERNAME or not E2E_PASSWORD:
        pytest.skip("未配置 E2E_USERNAME/E2E_PASSWORD（.env），跳过认领全流程用例")
    session = _new_session()
    resp = _login(session, base_url, E2E_USERNAME, E2E_PASSWORD)
    assert resp.json().get("code") == "200", f"用户B登录失败: {resp.json()}"
    return session


@allure.feature("端到端场景")
@pytest.mark.e2e
@pytest.mark.flaky(reruns=2, reruns_delay=1)  # Day12：端到端链路长，偶发超时重试兜底
class TestE2E:

    @allure.story("招领发布完整流程")
    @allure.title("端到端：注册→审核拦截→登录→发布→搜索→详情")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_publish_and_search_flow(self, base_url, first_category_id):
        """流程1（招领）：注册 → 登录 → 发布招领 → 搜索该物品 → 查看详情。"""
        register_session = _new_session()
        with allure.step("① 注册新用户（POST /api/user/add）"):
            username = f"e2e_reg_{int(time.time() * 1000)}"
            resp = _request(register_session, "POST", f"{base_url}/api/user/add",
                            json={"username": username,
                                  "password": "E2ePass123",
                                  "email": f"{username}@test.com",
                                  "name": "端到端注册用户",
                                  "agreementAccepted": True})
            attach_request_response(resp)
            assert resp.json().get("code") == "200", resp.json()
        with allure.step("② 新用户登录被拦截（业务规则：注册后需管理员审核）"):
            resp = _request(register_session, "POST", f"{base_url}/api/user/login",
                            json={"username": username, "password": "E2ePass123"})
            attach_request_response(resp)
            body = resp.json()
            assert body.get("code") != "200", f"待审核用户不应登录成功: {body}"
            assert "审核" in (body.get("msg") or ""), f"应返回待审核提示: {body}"
        session = _new_session()
        with allure.step("③ 已审核账号登录（POST /api/user/login）"):
            resp = _login(session, base_url, TEST_USERNAME, TEST_PASSWORD)
            attach_request_response(resp)
            assert resp.json().get("code") == "200", f"登录失败: {resp.json()}"
        title = f"端到端招领发布物品_{int(time.time() * 1000)}"
        item_id = None
        try:
            with allure.step("④ 发布招领物品（POST /api/lost-item）"):
                resp = _request(session, "POST", f"{base_url}/api/lost-item",
                                json=_item_payload(title, first_category_id))
                attach_request_response(resp)
                assert resp.json().get("code") == "200", resp.json()
            with allure.step("⑤ 按标题搜索该物品（GET /api/lost-item/page?title=）"):
                resp = _request(session, "GET", f"{base_url}/api/lost-item/page",
                                params={"title": title, "currentPage": 1, "size": 10})
                attach_request_response(resp)
                records = (resp.json().get("data") or {}).get("records") or []
                assert any(rec.get("title") == title for rec in records), records
                rec = _find_item(session, base_url, title)
                assert rec, f"搜索未找到刚发布的物品: {title}"
                item_id = rec["id"]
            with allure.step("⑥ 查看物品详情（GET /api/lost-item/{id}）"):
                resp = _request(session, "GET", f"{base_url}/api/lost-item/{item_id}")
                attach_request_response(resp)
                data = resp.json().get("data") or {}
                assert data.get("id") == item_id, resp.json()
                assert data.get("title") == title, resp.json()
        finally:
            with allure.step("⑦ 清理：删除流程中发布的物品"):
                if item_id:
                    _request(session, "DELETE", f"{base_url}/api/lost-item/{item_id}")

    @allure.story("认领完整流程")
    @allure.title("端到端：用户A发布→用户B认领→用户A审核→物品状态变更")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_claim_full_flow(self, base_url, first_category_id, second_user_session):
        """流程2（认领）：用户A发布物品 → 用户B登录 → 搜索 → 发起认领 →
        用户A查看认领 → 处理认领（审核通过）→ 验证物品状态变为已认领。"""
        session_a = _new_session()
        with allure.step("① 用户A（发布者）登录"):
            resp = _login(session_a, base_url, TEST_USERNAME, TEST_PASSWORD)
            attach_request_response(resp)
            assert resp.json().get("code") == "200", f"用户A登录失败: {resp.json()}"
        title = f"端到端认领物品_{int(time.time() * 1000)}"
        item_id = None
        try:
            with allure.step("② 用户A发布招领物品"):
                resp = _request(session_a, "POST", f"{base_url}/api/lost-item",
                                json=_item_payload(title, first_category_id))
                attach_request_response(resp)
                assert resp.json().get("code") == "200", resp.json()
                rec = _find_item(session_a, base_url, title)
                assert rec, f"未回查到发布的物品: {title}"
                item_id = rec["id"]
            with allure.step("③ 用户B按标题搜索到该物品"):
                resp = _request(second_user_session, "GET", f"{base_url}/api/lost-item/page",
                                params={"title": title, "currentPage": 1, "size": 10})
                attach_request_response(resp)
                records = (resp.json().get("data") or {}).get("records") or []
                assert any(rec.get("id") == item_id for rec in records), records
            with allure.step("④ 用户B发起认领（POST /api/claim，itemType=1 认领失物）"):
                resp = _request(second_user_session, "POST", f"{base_url}/api/claim",
                                json={"itemId": item_id, "itemType": 1,
                                      "description": "我是失主，请求归还，物品特征完全吻合。"})
                attach_request_response(resp)
                assert resp.json().get("code") == "200", resp.json()
            with allure.step("⑤ 用户A查看认领申请（GET /api/claim/page）"):
                resp = _request(session_a, "GET", f"{base_url}/api/claim/page",
                                params={"currentPage": 1, "size": 50})
                attach_request_response(resp)
                records = (resp.json().get("data") or {}).get("records") or []
                target = next((r for r in records if r.get("itemId") == item_id), None)
                assert target, f"发布者未看到对该物品的认领申请: {records}"
                assert target.get("status") == 0, f"新认领申请应为待审核: {target}"
                claim_id = target["id"]
            with allure.step("⑥ 用户A审核通过（PUT /api/claim/audit，status=1）"):
                resp = _request(session_a, "PUT", f"{base_url}/api/claim/audit",
                                json={"id": claim_id, "status": 1, "auditRemark": "审核通过"})
                attach_request_response(resp)
                assert resp.json().get("code") == "200", resp.json()
            with allure.step("⑦ 验证物品状态变为已认领（status=1）"):
                resp = _request(session_a, "GET", f"{base_url}/api/lost-item/{item_id}")
                attach_request_response(resp)
                data = resp.json().get("data") or {}
                assert data.get("status") == 1, f"审核通过后物品应为已认领: {resp.json()}"
        finally:
            with allure.step("⑧ 清理：用户A删除流程中的物品"):
                if item_id:
                    _request(session_a, "DELETE", f"{base_url}/api/lost-item/{item_id}")

    @allure.story("用户管理流程")
    @allure.title("端到端：查看个人信息→修改信息→验证修改生效→还原")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_user_profile_flow(self, base_url):
        """流程3（用户管理）：登录 → 查看个人信息 → 修改信息 → 验证修改生效。"""
        session = _new_session()
        with allure.step("① 登录并获取当前用户信息（GET /api/user/current）"):
            resp = _login(session, base_url, TEST_USERNAME, TEST_PASSWORD)
            attach_request_response(resp)
            assert resp.json().get("code") == "200", f"登录失败: {resp.json()}"
            resp = _request(session, "GET", f"{base_url}/api/user/current")
            attach_request_response(resp)
            data = resp.json().get("data") or {}
            assert data.get("username") == TEST_USERNAME, resp.json()
            user_id = data["id"]
            original_name = data.get("name", "")
        new_name = f"{original_name}_e2e_{int(time.time() % 1000)}"
        try:
            with allure.step(f"② 修改个人信息 name（PUT /api/user/{user_id}）"):
                resp = _request(session, "PUT", f"{base_url}/api/user/{user_id}",
                                json={"name": new_name})
                attach_request_response(resp)
                assert resp.json().get("code") == "200", resp.json()
            with allure.step("③ 重新获取个人信息，验证修改已生效"):
                resp = _request(session, "GET", f"{base_url}/api/user/current")
                attach_request_response(resp)
                data = resp.json().get("data") or {}
                assert data.get("name") == new_name, resp.json()
        finally:
            with allure.step("④ 还原个人信息，不影响后续用例/人工使用"):
                _request(session, "PUT", f"{base_url}/api/user/{user_id}",
                         json={"name": original_name})

    @allure.story("物品生命周期流程")
    @allure.title("端到端：发布→列表→详情→编辑→查看变更→删除→确认删除")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_item_lifecycle_flow(self, base_url, first_category_id):
        """流程4（物品生命周期）：发布 → 查看列表 → 查看详情 → 编辑 →
        查看变更 → 删除 → 确认删除（每步都断言真实接口响应）。"""
        session = _new_session()
        with allure.step("① 登录"):
            resp = _login(session, base_url, TEST_USERNAME, TEST_PASSWORD)
            attach_request_response(resp)
            assert resp.json().get("code") == "200", f"登录失败: {resp.json()}"
        title = f"端到端生命周期物品_{int(time.time() * 1000)}"
        item_id = None
        try:
            with allure.step("② 发布物品"):
                resp = _request(session, "POST", f"{base_url}/api/lost-item",
                                json=_item_payload(title, first_category_id))
                attach_request_response(resp)
                assert resp.json().get("code") == "200", resp.json()
                rec = _find_item(session, base_url, title)
                assert rec, f"未回查到发布的物品: {title}"
                item_id = rec["id"]
            with allure.step("③ 物品列表中出现该物品"):
                resp = _request(session, "GET", f"{base_url}/api/lost-item/page",
                                params={"title": title, "currentPage": 1, "size": 10})
                records = (resp.json().get("data") or {}).get("records") or []
                assert any(r.get("id") == item_id for r in records), records
            with allure.step("④ 查看物品详情"):
                resp = _request(session, "GET", f"{base_url}/api/lost-item/{item_id}")
                data = resp.json().get("data") or {}
                assert data.get("id") == item_id and data.get("title") == title, resp.json()
            new_title = f"{title}_已编辑"
            with allure.step("⑤ 编辑物品标题（PUT /api/lost-item/{id}）"):
                resp = _request(session, "PUT", f"{base_url}/api/lost-item/{item_id}",
                                json=_item_payload(new_title, first_category_id))
                attach_request_response(resp)
                assert resp.json().get("code") == "200", resp.json()
            with allure.step("⑥ 重新获取详情，验证标题变更已生效"):
                resp = _request(session, "GET", f"{base_url}/api/lost-item/{item_id}")
                attach_request_response(resp)
                data = resp.json().get("data") or {}
                assert data.get("title") == new_title, resp.json()
            with allure.step("⑦ 删除物品（DELETE /api/lost-item/{id}）"):
                resp = _request(session, "DELETE", f"{base_url}/api/lost-item/{item_id}")
                attach_request_response(resp)
                assert resp.json().get("code") == "200", resp.json()
            with allure.step("⑧ 再次获取详情，确认已删除（code=-1）"):
                resp = _request(session, "GET", f"{base_url}/api/lost-item/{item_id}")
                assert resp.json().get("code") != "200", resp.json()
                item_id = None  # 已删除，清理步骤跳过
        finally:
            with allure.step("⑨ 清理兜底：删除流程中残留物品"):
                if item_id:
                    _request(session, "DELETE", f"{base_url}/api/lost-item/{item_id}")
