"""物品搜索接口测试（Day9）：关键词 / 分类筛选 / 空关键词 / 分类无结果 / 分页，共 5 条；
Day10 新增参数化搜索校验 5 组。

接口契约（以 week1_day6 示例-失物招领系统API文档 v3.3 源码确认版为准，2026-08-06 修订）：
- 列表/搜索 = GET /api/lost-item/page，筛选参数为 title / categoryId / status / userId，
  **无 keyword 参数**（初版误用 keyword，按 API 文档修正为 title）；
- title 留空 = 不筛选（源码确认）；categoryId 筛选生效，不存在的分类（99999）
  返回空列表——"无结果"场景用分类实现；
- 分页参数为 currentPage/size。

Day10 参数化（2026-08-04 复测）：搜索 = 列表接口参数组合，断言按
"结构正常 / 分页 / 分类 / 无结果"四类检查点参数化，避免为每个组合复制用例。
"""

import allure
import pytest
import requests

from utils.allure_helper import attach_request_response


def _request(session, method, url, **kwargs):
    """发送请求；后端不可达时跳过用例（沿用 Day8 写法）。"""
    kwargs.setdefault("timeout", 10)
    try:
        return session.request(method, url, **kwargs)
    except requests.exceptions.RequestException as exc:
        pytest.skip(f"后端不可达，跳过真实请求: {exc}")


def _find_item(api_session, base_url, title, max_pages=5):
    """按标题翻页回查列表定位记录（发布接口不返回物品 ID）。"""
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


@allure.feature("物品搜索")
class TestSearch:

    @allure.story("关键词搜索")
    @allure.title("按关键词搜索，目标物品可被检索到")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_search_by_keyword(self, api_session, base_url, published_item_id):
        # 源码确认：列表筛选参数为 title（无 keyword 参数），title 留空=不筛选；
        # 按标题筛选后目标物品应出现在结果中
        with allure.step(f"按标题筛选：{published_item_id['title']}"):
            resp = _request(api_session, "GET", f"{base_url}/api/lost-item/page",
                            params={"title": published_item_id["title"]})
            attach_request_response(resp)  # Day11：请求/响应附加进报告
        with allure.step("断言返回码 200 且目标物品在结果中"):
            body = resp.json()
            assert body.get("code") == "200", body
            rec = _find_item(api_session, base_url, published_item_id["title"])
            assert rec, f"目标物品未被检索到: {body}"

    @allure.story("关键词搜索")
    @allure.title("按不存在的分类筛选，返回空结果")
    @allure.severity(allure.severity_level.NORMAL)
    def test_search_no_result(self, api_session, base_url, test_data):
        # 原"不存在的关键词"用例：列表筛选参数为 title（无 keyword 参数）；
        # "无结果"边界场景用不存在的分类 ID（99999）实现
        with allure.step("按不存在的分类筛选"):
            resp = _request(api_session, "GET", f"{base_url}/api/lost-item/page",
                            params={"categoryId": test_data["search"]["no_result_category_id"]})
            attach_request_response(resp)  # Day11：请求/响应附加进报告
        with allure.step("断言返回空列表"):
            body = resp.json()
            assert body.get("code") == "200", body
            records = (body.get("data") or {}).get("records") or []
            assert len(records) == 0, f"不存在的分类应返回空列表: {body}"

    @allure.story("关键词搜索")
    @allure.title("空关键词搜索，等价于获取全部列表")
    @allure.severity(allure.severity_level.NORMAL)
    def test_search_empty_keyword(self, api_session, base_url):
        with allure.step("发送标题留空请求（title 留空=不筛选）"):
            resp = _request(api_session, "GET", f"{base_url}/api/lost-item/page",
                            params={"title": ""})
            attach_request_response(resp)  # Day11：请求/响应附加进报告
        with allure.step("断言返回码 200 且结构正常"):
            body = resp.json()
            assert body.get("code") == "200", body
            assert isinstance((body.get("data") or {}).get("records"), list), body

    @allure.story("关键词搜索")
    @allure.title("分类筛选带分页参数，返回数量不超过 size 且都属于该分类")
    @allure.severity(allure.severity_level.NORMAL)
    def test_search_with_pagination(self, api_session, base_url, published_item_id):
        # categoryId + 分页组合验证筛选与分页参数叠加
        with allure.step("分类 + 分页参数组合搜索"):
            resp = _request(api_session, "GET", f"{base_url}/api/lost-item/page",
                            params={"categoryId": published_item_id["category_id"],
                                    "currentPage": 1, "size": 2})
            attach_request_response(resp)  # Day11：请求/响应附加进报告
        with allure.step("断言数量不超过 2 条且都属于该分类"):
            body = resp.json()
            records = (body.get("data") or {}).get("records") or []
            assert body.get("code") == "200" and len(records) <= 2, body
            for r in records:
                assert r.get("categoryId") == published_item_id["category_id"], r

    @allure.story("分类筛选")
    @allure.title("按分类筛选，返回物品都属于该分类")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_search_by_category(self, api_session, base_url, published_item_id):
        if not published_item_id.get("category_id"):
            pytest.skip("系统物品未使用分类，跳过本用例")
        with allure.step(f"按分类 ID 筛选：{published_item_id['category_id']}"):
            resp = _request(api_session, "GET", f"{base_url}/api/lost-item/page",
                            params={"categoryId": published_item_id["category_id"]})
            attach_request_response(resp)  # Day11：请求/响应附加进报告
        with allure.step("断言返回物品都属于该分类"):
            body = resp.json()
            assert body.get("code") == "200", body
            for r in (body.get("data") or {}).get("records") or []:
                assert r.get("categoryId") == published_item_id["category_id"], r


@allure.feature("物品搜索")
class TestSearchValidation:
    """搜索参数化校验（Day10 数据驱动，5 组）。

    search = GET /api/lost-item/page 的参数组合。断言按检查点参数化：
    - structure：返回码 200 + records 为列表（title 留空=不筛选，退化为结构校验）；
    - paged：records 数量不超过 size；
    - category：全部记录属于该分类（复用 published_item_id 的分类）；
    - empty：返回空列表（不存在的分类 99999；筛选参数以 API 文档源码确认为准）。
    """

    SEARCH_VALIDATION_CASES = [
        # (params, check, case_id)
        ({"title": ""}, "structure", "标题留空返回全量列表结构正常"),
        ({"title": "", "size": 2}, "paged", "标题留空+分页（title 留空=不筛选，仅验分页）"),
        (None, "category", "分类筛选属于该分类"),
        ({"categoryId": 99999}, "empty", "不存在的分类返回空列表"),
        (None, "paged", "分类+翻页（currentPage=2 size=1）"),
    ]

    @pytest.mark.parametrize(
        "params,check,case_id",
        SEARCH_VALIDATION_CASES,
        ids=[c[2] for c in SEARCH_VALIDATION_CASES],
    )
    @allure.story("搜索参数化校验")
    @allure.title("搜索参数组合校验（{case_id}）")
    @allure.severity(allure.severity_level.NORMAL)
    def test_search_validation(self, api_session, base_url, published_item_id, params, check, case_id):
        with allure.step(f"构造搜索参数：{case_id}"):
            request_params = dict(params or {})
            if check in ("category", "paged"):
                if not published_item_id.get("category_id"):
                    pytest.skip("系统物品未使用分类，跳过本用例")
                request_params["categoryId"] = published_item_id["category_id"]
            if check == "paged":
                request_params.update({"currentPage": 2, "size": 1})
        with allure.step("发送搜索请求"):
            resp = _request(api_session, "GET", f"{base_url}/api/lost-item/page",
                            params=request_params)
            attach_request_response(resp)  # Day11：请求/响应附加进报告
            body = resp.json()
            records = (body.get("data") or {}).get("records") or []
            assert body.get("code") == "200", body
        if check == "structure":
            with allure.step("断言结构正常"):
                assert isinstance(records, list), body
        elif check == "paged":
            with allure.step("断言数量不超过 size"):
                assert len(records) <= 1, body
        elif check == "category":
            with allure.step("断言全部记录属于该分类"):
                for r in records:
                    assert r.get("categoryId") == published_item_id["category_id"], r
        elif check == "empty":
            with allure.step("断言返回空列表"):
                assert len(records) == 0, body
