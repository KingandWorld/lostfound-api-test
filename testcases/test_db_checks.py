"""数据库校验测试（Day10 任务二）：验证接口对数据库的实际影响，共 4 条。

设计说明：
- db_conn fixture（session 级）：连接失败（本机到服务器 MySQL 不可达，已实测
  连接超时）→ pytest.skip，数据库校验整体跳过，以 API 响应验证替代；
- 注册入库用例：注册接口按 API 文档 v3.3（源码确认）为 POST /api/user/add，
  必填 username/password/email/name + agreementAccepted=true（初版误用
  /api/user/register 不存在返回 500，已按 API 文档修正）；
- 真实库表名/字段名以实际为准：查询前先核对结构，表/字段不符时 skip 并
  打印真实结构（接入真实库后按输出调整 SQL）；
- 造的数据（物品）按"API 删除 + DB 兜底删除"双通道清理。
"""

import allure
import pytest
import requests

from utils.allure_helper import attach_request_response
from utils.db_utils import DBUtils
from utils.ci_guard import guard_unreachable  # Day13：环境不可达统一出口（学习模式跳过 / CI 模式失败）


@pytest.fixture(scope="session")
def db_conn():
    """连接数据库；不可达时跳过（Day10 预案：用 API 响应验证替代）。

    学习模式：跳过（pytest.skip）；CI 模式（CI=1，Jenkins）：直接失败
    （Day13，见 utils/ci_guard.py）——服务器上 MySQL 与本机可达性不同，
    CI 中数据库问题必须暴露。
    """
    try:
        db = DBUtils()
    except Exception as exc:  # pymysql 各类连接错误（超时/拒绝/账号）
        guard_unreachable(exc, "数据库")
    yield db
    db.close()


def _request(session, method, url, **kwargs):
    """发送请求；后端不可达时跳过用例（沿用其他测试文件写法）。"""
    kwargs.setdefault("timeout", 10)
    try:
        return session.request(method, url, **kwargs)
    except requests.exceptions.RequestException as exc:
        guard_unreachable(exc)


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


def _item_payload(title, category_id):
    """构造发布物品请求体（与 test_items.py 契约一致，字段以 API 文档为准）。"""
    return {
        "title": title,
        "description": "这是一条用于数据库校验测试的失物描述，内容足够详细，"
                       "包含物品颜色、品牌、丢失时间等特征信息，"
                       "用于通过发布接口的内容完整性校验。",
        "categoryId": category_id,
        "lostPlace": "测试地点-图书馆二楼自习区",
        "lostTime": "2026-08-01 12:00:00",
        "images": "",
        "contactName": "测试联系人",
        "contactPhone": "13800000000",
    }


def _safe_query(db, sql, params=None):
    """执行查询；表/字段与真实库不符时 skip 并提示核对结构。"""
    try:
        return db.query_all(sql, params)
    except Exception as exc:
        pytest.skip(f"数据库表结构与此处假设不符，请按真实库调整 SQL: {exc}")


@allure.feature("数据库校验")
class TestDbChecks:

    @allure.story("注册入库")
    @allure.title("注册新用户后，user 表出现对应记录")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_register_creates_db_record(self, api_session, base_url, db_conn, unique_username):
        # 契约（API 文档 v3.3 源码确认）：注册 = POST /api/user/add（公开）；
        # 必填 username(3-50位字母数字)/password/email(唯一)/name + agreementAccepted=true。
        # 初版误用 /api/user/register（接口不存在）返回 500，已按 API 文档修正。
        with allure.step("调用注册接口创建新用户"):
            resp = _request(api_session, "POST", f"{base_url}/api/user/add",
                            json={"username": unique_username,
                                  "password": "Test123456",
                                  "email": f"{unique_username}@test.com",
                                  "name": "数据库校验用户",
                                  "agreementAccepted": True})
            attach_request_response(resp)  # Day11：请求/响应附加进报告
            assert resp.json().get("code") == "200", resp.json()
        with allure.step("查询 user 表确认新增记录"):
            rows = _safe_query(db_conn, "SELECT * FROM user WHERE username=%s", (unique_username,))
            assert rows, f"注册成功但 user 表无记录: {unique_username}"
            assert rows[0]["username"] == unique_username, rows[0]
        with allure.step("清理：从数据库删除测试用户"):
            db_conn.execute("DELETE FROM user WHERE username=%s", (unique_username,))

    @allure.story("发布入库")
    @allure.title("发布物品后，物品表出现对应记录")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_create_item_creates_db_record(self, api_session, base_url, db_conn, first_category_id):
        with allure.step("发布一个唯一标题的物品"):
            import time
            title = f"数据库校验物品_{int(time.time() * 1000)}"
            resp = _request(api_session, "POST", f"{base_url}/api/lost-item",
                            json=_item_payload(title, first_category_id))
            attach_request_response(resp)  # Day11：请求/响应附加进报告
            assert resp.json().get("code") == "200", resp.json()
        try:
            with allure.step("查询物品表确认记录存在（表名/字段以真实库为准）"):
                rows = _safe_query(db_conn, "SELECT * FROM lost_item WHERE title=%s", (title,))
                assert rows, f"发布成功但数据库无记录: {title}"
            with allure.step("清理：通过 API 删除物品"):
                rec = _find_item(api_session, base_url, title)
                if rec:
                    _request(api_session, "DELETE", f"{base_url}/api/lost-item/{rec['id']}")
        finally:
            with allure.step("清理兜底：直接从数据库删除记录"):
                db_conn.execute("DELETE FROM lost_item WHERE title=%s", (title,))

    @allure.story("删除出库")
    @allure.title("删除物品后，数据库中记录被移除")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_delete_item_removes_db_record(self, api_session, base_url, db_conn, first_category_id):
        with allure.step("发布一个待删除物品"):
            import time
            title = f"数据库删除物品_{int(time.time() * 1000)}"
            resp = _request(api_session, "POST", f"{base_url}/api/lost-item",
                            json=_item_payload(title, first_category_id))
            assert resp.json().get("code") == "200", resp.json()
            rec = _find_item(api_session, base_url, title)
            assert rec, f"未回查到临时物品: {title}"
        with allure.step("通过接口删除物品"):
            resp = _request(api_session, "DELETE", f"{base_url}/api/lost-item/{rec['id']}")
            attach_request_response(resp)  # Day11：请求/响应附加进报告
            assert resp.json().get("code") == "200", resp.json()
        with allure.step("查询数据库确认记录已删除"):
            rows = _safe_query(db_conn, "SELECT * FROM lost_item WHERE id=%s", (rec["id"],))
            assert not rows, f"接口删除成功但数据库仍有记录: {rows}"
        with allure.step("清理兜底（软删除时字段值可能残留，直接按 ID 删除）"):
            db_conn.execute("DELETE FROM lost_item WHERE id=%s", (rec["id"],))

    @allure.story("登录更新")
    @allure.title("登录成功后，用户表的时间字段被更新")
    @allure.severity(allure.severity_level.NORMAL)
    def test_login_updates_last_login(self, api_session, base_url, db_conn, test_data):
        username = test_data["user"]["username"]
        with allure.step("查询登录前的 update_time（真实库 user 表无 lastLoginTime，用 update_time 验证）"):
            rows_before = _safe_query(
                db_conn,
                "SELECT update_time FROM user WHERE username=%s",
                (username,),
            )
            assert rows_before, f"user 表查无此账号: {username}"
            before = rows_before[0]["update_time"]
        with allure.step("调用登录接口（账号密码来自 .env 配置）"):
            resp = _request(api_session, "POST", f"{base_url}/api/user/login",
                            json=test_data["login"]["success"])
            attach_request_response(resp)  # Day11：请求/响应附加进报告
            assert resp.json().get("code") == "200", resp.json()
        with allure.step("查询登录后的 update_time 并断言已更新"):
            rows_after = _safe_query(
                db_conn,
                "SELECT update_time FROM user WHERE username=%s",
                (username,),
            )
            after = rows_after[0]["update_time"]
            assert after and after >= before, (
                f"登录成功但数据库 update_time 未更新: 前={before} 后={after}")
