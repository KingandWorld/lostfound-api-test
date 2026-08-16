"""数据库校验工具（Day10 实现）。

用途：验证接口对数据库的实际影响——接口返回成功 ≠ 数据正确落库，
面试常问"接口测试怎么验证数据真的写进去了"即用此工具回答。

约定：
- 连接信息统一从 config.settings 读取（.env 中的 DB_HOST / DB_PORT /
  DB_USER / DB_PASSWORD / DB_NAME），与 BASE_URL 同源，切换环境零改动；
- 本机连服务器 MySQL 用 SSH 隧道（服务器 bind-address=127.0.0.1 +
  防火墙未放行 3306 + 账号仅 localhost 授权，远程直连不可行）：
  `ssh -N -L 13306:127.0.0.1:3306 root@<服务器IP>`（Windows 双击
  start-db-tunnel.bat），.env 配 DB_HOST=127.0.0.1 / DB_PORT=13306
  （⚠️ 本机若装有 MySQL 会占用 3306，所以隧道必须用 13306）；
- 隧道未开/数据库不可达时，连接会抛 OperationalError，由调用方
  （test_db_checks.py 的 db_conn fixture）捕获并 pytest.skip——数据库校验
  是进阶内容，连不上时用 API 响应验证替代（见 week2_day10.md 任务二第 5 条预案）；
- 真实库表结构（2026-08-16 核对）：表名 user（单数，非 users）；登录时间
  用 update_time（无 lastLoginTime/loginTime）；lost_item 表字段齐全。

用法：
    from utils.db_utils import DBUtils
    db = DBUtils()
    row = db.query_one("SELECT id FROM lost_item WHERE title=%s", (title,))
    db.execute("DELETE FROM lost_item WHERE id=%s", (item_id,))
    db.close()
"""

import pymysql

from config.settings import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER


class DBUtils:
    """MySQL 查询封装：query_one / query_all / execute / close。"""

    def __init__(self, autocommit=True):
        self.conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
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
