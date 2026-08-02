# lostfound-api-test — 失物招领系统接口自动化测试框架

基于 `pytest + requests + allure-pytest + python-dotenv` 的接口自动化测试项目
（第2周 Day8 起搭建，配套文档：`示例/week2_day8_示例-项目搭建与运行手册.md`）。

## 接口契约（与 Day6 API 文档一致）

- 登录：`POST /api/user/login`，请求体 `{"username": "xxx", "password": "xxx"}`
- 成功响应：`{"code": "200", "data": {"token": "xxx", ...}}`
- 认证方式：后续请求在 Header 携带自定义 `token: <token>`（**非 Bearer**）

## 目录结构

```text
lostfound-api-test/
├── .env / .env.example     # 环境变量（.env 不提交 Git）
├── .gitignore
├── requirements.txt
├── pytest.ini              # testpaths / addopts（Allure）
├── conftest.py             # 全局 fixture：base_url / api_session / login_token / test_data
├── config/settings.py      # python-dotenv 加载 .env
├── utils/
│   ├── api_client.py       # requests 封装（Base URL + token 注入）
│   └── db_utils.py         # 数据库工具（Day10）
└── testcases/
    ├── test_login.py       # 登录用例（Day8，5 条）
    ├── test_items.py       # 物品用例（Day9）
    └── test_claims.py      # 认领用例（Day9）
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
| Day9 | test_items.py / test_claims.py 用例 | `feat: add test_items and test_claims` |
| Day10 | utils/db_utils.py 数据库断言 | `feat: add db_utils for db assertion` |
| Day13 | Jenkins 集成接口测试 + Allure 报告 | `ci: integrate jenkins and allure report` |
