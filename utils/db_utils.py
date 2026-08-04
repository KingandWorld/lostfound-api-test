"""数据库校验工具（Day10 实现）。

用途：验证接口对数据库的实际影响——接口返回成功 ≠ 数据正确落库，
面试常问"接口测试怎么验证数据真的写进去了"即用此工具回答。

约定：
- 连接信息统一从 config.settings 读取（.env 中的 DB_HOST / DB_USER /
  DB_PASSWORD / DB_NAME），与 BASE_URL 同源，切换环境零改动；
- 本机与数据库不可达时（bind-address 限制/未开防火墙），连接会抛
  OperationalError，由调用方（test_db_checks.py 的 db_conn fixture）捕获并
  pytest.skip——数据库校验是进阶内容，连不上时用 API 响应验证替代（见
  week2_day10.md 任务二第 5 条预案）；
- 真实库表名/字段名可能与下面的假设不同（本示例按 users / lost_item 的
  常规命名编写），接入真实库后先 SELECT * FROM xxx LIMIT 1 核对结构。

用法：
    from utils.db_utils import DBUtils
    db = DBUtils()
    row = db.query_one("SELECT id FROM lost_item WHERE title=%s", (title,))
    db.execute("DELETE FROM lost_item WHERE id=%s", (item_id,))
    db.close()
"""

import pymysql

from config.settings import DB_HOST, DB_NAME, DB_PASSWORD, DB_USER


class DBUtils:
    """MySQL 查询封装：query_one / query_all / execute / close。"""

    def __init__(self, autocommit=True):
        self.conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset="utf8mb4",
            connect_timeout=6,
            autocommit=autocommit,
        )

    def query_one(self, sql, params=None):
        """执行查询并返回单条记录（dict 或 None）。"""
        with self.conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(sql, params or ())
            return cur.fetchone()

    def query_all(self, sql, params=None):
        """执行查询并返回所有记录（list[dict]）。"""
        with self.conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()

    def execute(self, sql, params=None):
        """执行增删改操作，返回影响行数。"""
        with self.conn.cursor() as cur:
            rows = cur.execute(sql, params or ())
        return rows

    def close(self):
        """关闭连接（用例 teardown 中调用）。"""
        if getattr(self, "conn", None) and self.conn.open:
            self.conn.close()
