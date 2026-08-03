"""物品模块接口测试（Day9）：列表 / 详情 / 发布 / 编辑 / 删除，共 10 条。

已实测契约（2026-08-03 对真实后端探测确认）：
- 发布：POST /api/lost-item（前端实际路径），必填 title/description/categoryId/
  lostTime/contactName，description 过短返回 code=-1"发布内容过于简单"；
  userId 可省略（服务端从 token 解析）；
- 发布成功响应不含物品 ID（data 为提示字符串），需按标题回查列表拿 ID（_find_item）；
- 列表分页参数为 currentPage/size（page/pageSize 被忽略），响应分页字段为 total；
- 详情：无效 ID 返回 code=-1 且无 data（非 HTTP 404）；
- 编辑：PUT /api/lost-item/{id}，body 同发布；
- 删除：DELETE /api/lost-item/{id}，删除后回查返回 code=-1。
"""

import time

import allure
import pytest
import requests


def _request(session, method, url, **kwargs):
    """发送请求；后端不可达时跳过用例（沿用 Day8 写法）。"""
    kwargs.setdefault("timeout", 10)
    try:
        return session.request(method, url, **kwargs)
    except requests.exceptions.RequestException as exc:
        pytest.skip(f"后端不可达，跳过真实请求: {exc}")


def _item_payload(title: str, category_id, **overrides) -> dict:
    """构造发布/编辑物品请求体（字段与校验规则已实测）。

    注意：categoryId 必填（缺失返回 code=-1"分类无效"）；
    description 需足够详细（过短返回 code=-1"发布内容过于简单"）。
    """
    payload = {
        "title": title,
        "description": "这是一条用于接口自动化测试的失物描述，内容足够详细，"
                       "包含物品颜色、品牌、丢失时间等特征信息，"
                       "用于通过发布接口的内容完整性校验。",
        "categoryId": category_id,
        "lostPlace": "测试地点-图书馆二楼自习区",
        "lostTime": "2026-08-01 12:00:00",
        "contactName": "测试联系人",
        "contactPhone": "13800000000",
        "contactEmail": "test@test.com",
        "status": 0,
    }
    payload.update(overrides)
    return payload


def _find_item(api_session, base_url, title, max_pages=5):
    """发布接口不返回物品 ID，按标题翻页回查列表定位记录。"""
    for page in range(1, max_pages + 1):
        resp = _request(api_session, "GET", f"{base_url}/api/lost-item/page",
                        params={"currentPage": page, "size": 50})
        records = (resp.json().get("data") or {}).get("records") or []
        for rec in records:
            if rec.get("title") == title:
                return rec
        if len(records) < 50:
            break
    return None


@allure.feature("物品管理")
class TestItemList:

    @allure.story("物品列表")
    @allure.title("不带参数获取物品列表，返回分页结构")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_get_items_list(self, api_session, base_url):
        with allure.step("发送 GET /api/lost-item/page"):
            resp = _request(api_session, "GET", f"{base_url}/api/lost-item/page")
        with allure.step("断言响应码为 200"):
            body = resp.json()
            assert body.get("code") == "200", f"获取列表失败: {body}"
        with allure.step("断言返回分页结构（已实测：records/total/size/current/pages）"):
            data = body.get("data") or {}
            assert isinstance(data.get("records"), list), data
            assert "total" in data, data

    @allure.story("物品列表")
    @allure.title("携带 currentPage/size 分页参数，返回数量不超过 size")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_get_items_with_pagination(self, api_session, base_url):
        with allure.step("发送带分页参数的请求（已实测：参数名为 currentPage/size）"):
            resp = _request(
                api_session, "GET", f"{base_url}/api/lost-item/page",
                params={"currentPage": 1, "size": 2},
            )
        with allure.step("断言返回数量不超过 2 条"):
            body = resp.json()
            records = (body.get("data") or {}).get("records") or []
            assert body.get("code") == "200" and len(records) <= 2, body

    @allure.story("物品列表")
    @allure.title("请求超出范围的页码，返回空列表而非报错")
    @allure.severity(allure.severity_level.NORMAL)
    def test_get_items_empty_page(self, api_session, base_url):
        with allure.step("请求超大页码（已实测：超范围返回空 records）"):
            resp = _request(
                api_session, "GET", f"{base_url}/api/lost-item/page",
                params={"currentPage": 99999, "size": 10},
            )
        with allure.step("断言返回空列表"):
            body = resp.json()
            assert body.get("code") == "200", body
            records = (body.get("data") or {}).get("records") or []
            assert len(records) == 0, f"超出范围的页码应返回空列表: {body}"


@allure.feature("物品管理")
class TestItemDetail:

    @allure.story("物品详情")
    @allure.title("使用有效 ID 获取物品详情，返回完整字段")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_get_item_detail(self, api_session, base_url, published_item_id):
        with allure.step(f"请求详情：GET /api/lost-item/{published_item_id['id']}"):
            resp = _request(api_session, "GET",
                            f"{base_url}/api/lost-item/{published_item_id['id']}")
        with allure.step("断言返回目标物品且标题一致"):
            body = resp.json()
            assert body.get("code") == "200", body
            data = body.get("data") or {}
            assert data.get("id") == published_item_id["id"], body
            assert data.get("title") == published_item_id["title"], body

    @allure.story("物品详情")
    @allure.title("使用不存在的 ID 获取详情，返回失败提示")
    @allure.severity(allure.severity_level.NORMAL)
    def test_get_item_invalid_id(self, api_session, base_url):
        with allure.step("请求超大 ID 的详情"):
            resp = _request(api_session, "GET", f"{base_url}/api/lost-item/999999999")
        with allure.step("断言返回失败（已实测：code=-1 且无 data）"):
            body = resp.json()
            assert body.get("code") != "200", body


@allure.feature("物品管理")
class TestItemCreate:

    @allure.story("发布物品")
    @allure.title("完整参数发布物品，回查列表确认发布成功")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_create_item_success(self, api_session, base_url, first_category_id):
        with allure.step("构造唯一标题并发布（POST /api/lost-item）"):
            title = f"自动化发布物品_{int(time.time() * 1000)}"
            resp = _request(api_session, "POST", f"{base_url}/api/lost-item",
                            json=_item_payload(title, first_category_id))
        with allure.step("断言发布成功"):
            body = resp.json()
            assert body.get("code") == "200", f"发布失败: {body}"
        with allure.step("回查列表找到刚发布的物品"):
            rec = _find_item(api_session, base_url, title)
            assert rec, f"发布成功但未在列表回查到: {title}"
        with allure.step("清理：删除刚发布的物品"):
            _request(api_session, "DELETE", f"{base_url}/api/lost-item/{rec['id']}")

    @allure.story("发布物品")
    @allure.title("缺少必填字段（标题）发布，返回参数校验提示")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_create_item_missing_required(self, api_session, base_url, test_data):
        with allure.step("发送缺少标题的请求体"):
            resp = _request(api_session, "POST", f"{base_url}/api/lost-item",
                            json=test_data["items"]["missing_required"])
        with allure.step("断言发布失败并返回校验提示"):
            body = resp.json()
            assert body.get("code") != "200", f"缺少必填字段不应发布成功: {body}"
            assert body.get("msg"), f"应返回校验提示: {body}"

    @allure.story("发布物品")
    @allure.title("未登录发布物品，返回 401")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_create_item_without_login(self, base_url, first_category_id):
        with allure.step("使用不带 token 的全新 Session 发送请求"):
            anon = requests.Session()  # 未注入 token 头
            resp = _request(anon, "POST", f"{base_url}/api/lost-item",
                            json=_item_payload("匿名发布物品", first_category_id))
        with allure.step("断言返回 401（已实测：未登录返回 HTTP 401 认证失败）"):
            assert resp.status_code == 401, (resp.status_code, resp.text[:200])


@allure.feature("物品管理")
class TestItemUpdate:

    @allure.story("编辑物品")
    @allure.title("修改已发布物品的标题，重新获取详情确认更新成功")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_update_item(self, api_session, base_url, first_category_id):
        with allure.step("准备：发布一个临时物品"):
            title = f"待编辑物品_{int(time.time() * 1000)}"
            resp = _request(api_session, "POST", f"{base_url}/api/lost-item",
                            json=_item_payload(title, first_category_id))
            assert resp.json().get("code") == "200", resp.json()
            rec = _find_item(api_session, base_url, title)
            assert rec, f"未回查到临时物品: {title}"
            item_id = rec["id"]
        try:
            with allure.step("PUT 修改标题"):
                new_title = f"{title}_已编辑"
                resp = _request(api_session, "PUT", f"{base_url}/api/lost-item/{item_id}",
                                json=_item_payload(new_title, first_category_id))
                assert resp.json().get("code") == "200", resp.json()
            with allure.step("重新获取详情确认标题已更新"):
                resp = _request(api_session, "GET", f"{base_url}/api/lost-item/{item_id}")
                data = resp.json().get("data") or {}
                assert data.get("title") == new_title, resp.json()
        finally:
            with allure.step("清理：删除临时物品"):
                _request(api_session, "DELETE", f"{base_url}/api/lost-item/{item_id}")


@allure.feature("物品管理")
class TestItemDelete:

    @allure.story("删除物品")
    @allure.title("删除已发布物品，再次获取确认已删除")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_delete_item(self, api_session, base_url, first_category_id):
        with allure.step("准备：发布一个待删除物品"):
            title = f"待删除物品_{int(time.time() * 1000)}"
            resp = _request(api_session, "POST", f"{base_url}/api/lost-item",
                            json=_item_payload(title, first_category_id))
            assert resp.json().get("code") == "200", resp.json()
            rec = _find_item(api_session, base_url, title)
            assert rec, f"未回查到临时物品: {title}"
            item_id = rec["id"]
        with allure.step("DELETE 删除该物品"):
            resp = _request(api_session, "DELETE", f"{base_url}/api/lost-item/{item_id}")
            assert resp.json().get("code") == "200", resp.json()
        with allure.step("再次获取详情，确认已删除（已实测：返回 code=-1）"):
            resp = _request(api_session, "GET", f"{base_url}/api/lost-item/{item_id}")
            assert resp.json().get("code") != "200", resp.json()
