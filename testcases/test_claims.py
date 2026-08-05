"""认领模块接口测试（Day9）：正常 / 重复 / 自己物品 / 不存在物品 / 认领状态，共 5 条。

已实测契约（2026-08-03 对真实后端探测确认）：
- 发起认领：POST /api/claim，body {itemId, itemType, description}；
  itemType=1 为认领失物（提交归还申请），0 为认领招领物品（从前端确认）；
- 认领自己发布的物品：返回 code=-1"不能认领自己发布的物品"（系统禁止）；
- 重复认领：返回 code=-1"该物品已被认领，请勿重复认领"；
- 认领不存在的物品：返回 code=-1"失物信息不存在"；
- 认领列表：GET /api/claim/my（分页参数 currentPage/size），记录 status 0=待审核、
  3=已取消；取消认领：PUT /api/claim/cancel/{id}（用于 teardown 清理）。

系统缺陷（已实测，测试报告中记录）：物品一旦被认领（即使已取消）仍不能再次认领，
"正常/重复/状态"用例从种子物品池动态选取从未被认领过的他人物品，池子用尽时
skip 并提示在后台重置；"认领自己物品"用 conftest 的 published_item_id。
"""

import allure
import pytest
import requests

from config.settings import TEST_USERNAME
from utils.allure_helper import attach_request_response


def _request(session, method, url, **kwargs):
    """发送请求；后端不可达时跳过用例（沿用 Day8 写法）。"""
    kwargs.setdefault("timeout", 10)
    try:
        return session.request(method, url, **kwargs)
    except requests.exceptions.RequestException as exc:
        pytest.skip(f"后端不可达，跳过真实请求: {exc}")


def _claim_payload(item_id: int, item_type: int = 1) -> dict:
    """构造认领请求体（字段与 itemType 已实测：1=认领失物，0=认领招领物品）。"""
    return {
        "itemId": item_id,
        "itemType": item_type,
        "description": "这是我的学生证，学号与照片完全吻合，请求归还。",
    }


def _cancel_claims_on(api_session, base_url, item_id):
    """取消对指定物品发起的全部认领单（查询 claim/my → 逐个 cancel）。"""
    resp = _request(api_session, "GET", f"{base_url}/api/claim/my",
                    params={"currentPage": 1, "size": 50})
    records = (resp.json().get("data") or {}).get("records") or []
    for rec in records:
        if rec.get("itemId") == item_id:
            _request(api_session, "PUT", f"{base_url}/api/claim/cancel/{rec['id']}")


def _my_claimed_item_ids(api_session, base_url):
    """本账号认领过的全部物品 ID（含已取消——系统对曾认领物品永久拒绝再次认领）。"""
    claimed = set()
    for page in range(1, 6):
        resp = _request(api_session, "GET", f"{base_url}/api/claim/my",
                        params={"currentPage": page, "size": 50})
        records = (resp.json().get("data") or {}).get("records") or []
        for rec in records:
            claimed.add(rec.get("itemId"))
        if len(records) < 50:
            break
    return claimed


def _find_claimable_others_item(api_session, base_url):
    """在失物/招领列表中找其他用户发布、待认领且本账号从未认领过的物品。"""
    claimed = _my_claimed_item_ids(api_session, base_url)
    for endpoint in ("lost-item", "found-item"):
        for page in range(1, 4):
            resp = _request(api_session, "GET", f"{base_url}/api/{endpoint}/page",
                            params={"currentPage": page, "size": 50})
            records = (resp.json().get("data") or {}).get("records") or []
            for rec in records:
                if (rec.get("username") != TEST_USERNAME
                        and rec.get("status") == 0
                        and rec.get("id") not in claimed):
                    return {"id": rec["id"],
                            "item_type": 1 if endpoint == "lost-item" else 0}
            if len(records) < 50:
                break
    return None


@pytest.fixture()
def others_item(api_session, base_url):
    """其他用户发布的可认领物品（认领"正常/重复/状态"用例用）。

    系统缺陷（已实测）：物品一旦被认领（即使已取消）仍不能再次认领。
    因此从种子物品池动态选取从未被认领过的；池子用尽时 skip 并提示。
    teardown 取消本轮认领单，保证不遗留待审核数据。
    """
    cand = _find_claimable_others_item(api_session, base_url)
    if not cand:
        pytest.skip("无可认领的其他用户种子物品（均被认领过或状态非待认领），"
                    "请在系统后台重置")
    yield cand
    _cancel_claims_on(api_session, base_url, cand["id"])


@allure.feature("认领管理")
class TestClaim:

    @allure.story("发起认领")
    @allure.title("对他人的待认领物品正常发起认领")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_create_claim(self, api_session, base_url, others_item):
        with allure.step("发起认领请求（POST /api/claim）"):
            resp = _request(api_session, "POST", f"{base_url}/api/claim",
                            json=_claim_payload(others_item["id"], others_item["item_type"]))
            attach_request_response(resp)  # Day11：请求/响应附加进报告
        with allure.step("断言认领成功"):
            body = resp.json()
            assert body.get("code") == "200", f"认领失败: {body}"
        with allure.step("断言认领单出现在我的认领列表中"):
            resp = _request(api_session, "GET", f"{base_url}/api/claim/my",
                            params={"currentPage": 1, "size": 50})
            records = (resp.json().get("data") or {}).get("records") or []
            assert any(r.get("itemId") == others_item["id"] for r in records), records

    @allure.story("发起认领")
    @allure.title("重复认领同一物品，第二次被拒绝")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_create_claim_duplicate(self, api_session, base_url, others_item):
        with allure.step("第一次认领"):
            resp1 = _request(api_session, "POST", f"{base_url}/api/claim",
                             json=_claim_payload(others_item["id"], others_item["item_type"]))
            assert resp1.json().get("code") == "200", resp1.json()
        with allure.step("第二次认领同一物品"):
            resp2 = _request(api_session, "POST", f"{base_url}/api/claim",
                             json=_claim_payload(others_item["id"], others_item["item_type"]))
            attach_request_response(resp2)  # Day11：请求/响应附加进报告
            body2 = resp2.json()
        with allure.step("断言第二次被拒绝并返回原因"):
            assert body2.get("code") != "200", f"重复认领不应成功: {body2}"
            assert body2.get("msg"), f"应返回拒绝原因: {body2}"

    @allure.story("发起认领")
    @allure.title("认领自己发布的物品，被系统拒绝")
    @allure.severity(allure.severity_level.NORMAL)
    def test_create_claim_own_item(self, api_session, base_url, published_item_id):
        # 已实测：系统返回 code=-1"不能认领自己发布的物品"
        with allure.step(f"认领自己发布的物品 {published_item_id['id']}"):
            resp = _request(api_session, "POST", f"{base_url}/api/claim",
                            json=_claim_payload(published_item_id["id"]))
            attach_request_response(resp)  # Day11：请求/响应附加进报告
        with allure.step("断言被系统拒绝"):
            body = resp.json()
            assert body.get("code") != "200", f"认领自己的物品应被拒绝: {body}"
            assert body.get("msg"), f"应返回拒绝原因: {body}"

    @allure.story("发起认领")
    @allure.title("认领不存在的物品，返回错误提示")
    @allure.severity(allure.severity_level.NORMAL)
    def test_create_claim_invalid_item(self, api_session, base_url):
        with allure.step("认领一个不存在的物品 ID"):
            resp = _request(api_session, "POST", f"{base_url}/api/claim",
                            json=_claim_payload(999999999))
            attach_request_response(resp)  # Day11：请求/响应附加进报告
        with allure.step("断言返回错误提示"):
            body = resp.json()
            assert body.get("code") != "200", f"认领不存在物品不应成功: {body}"
            assert body.get("msg"), f"应返回错误提示: {body}"

    @allure.story("认领状态")
    @allure.title("发起认领后查询认领单状态，返回待审核")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_get_claim_status(self, api_session, base_url, others_item):
        with allure.step("发起认领"):
            resp = _request(api_session, "POST", f"{base_url}/api/claim",
                            json=_claim_payload(others_item["id"], others_item["item_type"]))
            attach_request_response(resp)  # Day11：请求/响应附加进报告
            assert resp.json().get("code") == "200", resp.json()
        with allure.step("查询我的认领列表，断言认领单存在且状态为待审核"):
            resp = _request(api_session, "GET", f"{base_url}/api/claim/my",
                            params={"currentPage": 1, "size": 50})
            body = resp.json()
            assert body.get("code") == "200", body
            records = (body.get("data") or {}).get("records") or []
            target = next((r for r in records if r.get("itemId") == others_item["id"]), None)
            assert target, f"认领单未出现在列表中: {body}"
            # 已实测：0=待审核，3=已取消
            assert target.get("status") == 0, target
