# lostfound-api-test — 失物招领系统接口自动化测试框架

基于 `pytest + requests + allure-pytest + python-dotenv + pymysql` 的接口自动化测试项目
（第2周 Day8 起搭建，配套文档：`示例/week2_day8_示例-项目搭建与运行手册.md`、
`示例/week2_day9_示例-接口用例扩展开发手册.md`、
`示例/week2_day10_示例-数据驱动与数据库校验开发手册.md`）。

## 接口契约（Day6 API 文档 + 2026-08-03 对真实后端实测修正）

> 与 Day6 文档不同的地方已用「⚠️」标出，均为实测确认，测试代码已按真实契约编写。

- 登录：`POST /api/user/login`，请求体 `{"username": "xxx", "password": "xxx"}`；
  成功响应 `{"code": "200", "data": {"token": "xxx", ...}}`；
  认证方式：后续请求在 Header 携带自定义 `token: <token>`（**非 Bearer**）
- 物品列表/搜索：`GET /api/lost-item/page`；⚠️ 分页参数为 `currentPage`/`size`
  （`page`/`pageSize` 会被后端忽略），响应分页字段为 `records/total/size/current/pages`
- ⚠️ `keyword` 参数被后端忽略（过滤未实现，已知缺陷）；`categoryId` 筛选有效；
  不存在的分类返回空列表
- ⚠️ 发布物品：`POST /api/lost-item`（**不是** `/api/lost-item/add`），必填
  `title/description/categoryId/lostTime/contactName`；description 过短返回
  `code=-1`"发布内容过于简单"；userId 可省略（服务端从 token 解析）；
  ⚠️ 发布成功响应**不返回物品 ID**，需按标题回查列表定位
- ⚠️ 编辑：`PUT /api/lost-item/{id}`；删除：`DELETE /api/lost-item/{id}`
  （**不是** `/delete/{id}`）；删除后回查返回 `code=-1`（非 HTTP 404）
- ⚠️ 发起认领：`POST /api/claim`，body `{itemId, itemType, description}`，
  `itemType` 1=认领失物、0=认领招领物品（**不是** `/api/claim-application/add`）；
  认领自己物品/重复认领/不存在物品均返回 `code=-1` + 提示
- ⚠️ 认领列表：`GET /api/claim/my`（status 0=待审核、3=已取消）；
  取消认领：`PUT /api/claim/cancel/{id}`
- ⚠️ 系统缺陷（已实测）：物品一旦被认领（即使已取消）仍不能再次认领——
  认领用例从种子物品池动态选取未认领过的他人物品，池子用尽会 skip
- 未登录请求返回 HTTP `401`"认证失败，请重新登录"
- ⚠️ 登录失败计数（Day10 实测）：账号连续 5 次密码错误触发 **15 分钟账号锁定**
  （"还剩 N 次尝试机会"递减提示），**成功登录即重置计数**——参数化登录用例
  将计数型失败组放最后并用宽断言兼容锁定提示
- ⚠️ 发布标题长度（Day10 实测）：**≥2 且 ≤100 字符**（1 字符"不能少于2个字符"、
  101+ 字符"不能超过100个字符"；50/51 字符均可发布，旧文档"1-50 字符"不准确）；
  空标题 / 缺 categoryId / 过短 description 均被拒绝
- ⚠️ 注册接口暂不可用（Day10 实测）：`POST /api/user/register` 任意参数组合
  均返回 `code=500`"系统错误"（含 GET）——后端缺陷，注册入库用例与 temp_user
  fixture 已做 skip 保护，修复后自动恢复

## 目录结构

```text
lostfound-api-test/
├── .env / .env.example     # 环境变量（.env 不提交 Git）
├── .gitignore
├── requirements.txt
├── pytest.ini              # testpaths / addopts（Allure）
├── conftest.py             # 全局 fixture：base_url / api_session / login_token / test_data
│                           #   / unique_username / temp_item / published_item_id
├── config/settings.py      # python-dotenv 加载 .env（含 DB_* 连接信息）
├── utils/
│   ├── api_client.py       # requests 封装（Base URL + token 注入）
│   └── db_utils.py         # 数据库工具（Day10：DBUtils 查询/断言封装）
└── testcases/
    ├── test_login.py       # 登录用例（Day8 5 条 + Day10 参数化 7 组）
    ├── test_items.py       # 物品用例（Day9 10 条 + Day10 参数化 10 组）
    ├── test_search.py      # 搜索用例（Day9 5 条 + Day10 参数化 5 组）
    ├── test_claims.py      # 认领用例（Day9，5 条）
    └── test_db_checks.py   # 数据库校验用例（Day10，4 条；DB 不可达时跳过）
```

## 快速开始

```bash
# 1. 创建并激活虚拟环境（Windows Git Bash 可一键执行 示例/week2_day8_环境搭建与初始化脚本.sh）
python -m venv venv
venv\Scripts\activate        # Windows；Linux/Mac 用 source venv/bin/activate

# 2. 安装依赖（国内可用清华镜像加速）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 配置环境变量
#    复制 .env.example 为 .env，填写 BASE_URL / 测试账号 / 数据库信息

# 4. 运行测试并生成 Allure 报告
pytest
allure serve ./allure-results
```

## 开发节奏

| 节点 | 内容 | 提交信息 |
|------|------|---------|
| Day8 | 环境搭建 + 登录用例（本目录） | `init: 接口自动化项目初始化` → `feat: add conftest and test_login (5 cases)` |
| Day9 | test_items.py / test_search.py / test_claims.py 用例（20 条） | `feat: add test_items and test_claims` |
| Day10 | 参数化数据驱动（22 组）+ db_utils.py 数据库校验 + fixture 数据隔离 | `feat: 添加数据驱动测试(22组参数)和数据库校验工具，优化fixture数据隔离` |
| Day13 | Jenkins 集成接口测试 + Allure 报告 | `ci: integrate jenkins and allure report` |
