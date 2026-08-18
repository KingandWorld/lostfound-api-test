# lostfound-api-test — 失物招领系统接口自动化测试框架

基于 `pytest + requests + allure-pytest + python-dotenv + pymysql` 的接口自动化测试项目
（第2周 Day8 起搭建，配套文档：`示例/week2_day8_示例-项目搭建与运行手册.md`、
`示例/week2_day9_示例-接口用例扩展开发手册.md`、
`示例/week2_day10_示例-数据驱动与数据库校验开发手册.md`、
`示例/week2_day11_示例-Allure报告深度定制开发手册.md`、
`示例/week2_day12_示例-接口自动化套件验收开发手册.md`、
`示例/week2_day13_示例-Jenkins集成开发手册.md`、
`示例/week2_day14_示例-中期复盘与资源调整手册.md`）。

## 测试覆盖（Day12 验收版，55 条用例）

| 模块 | 用例数 | 说明 |
|------|:------:|------|
| 认证（登录/注册） | 12 | 正常/异常/参数化 7 组（Day8+Day10） |
| 物品管理（CRUD） | 20 | 列表/详情/发布/编辑/删除 + 参数化 10 组（Day9+Day10） |
| 物品搜索 | 10 | 关键词/分类/分页 + 参数化 5 组（Day9+Day10） |
| 认领管理 | 5 | 发起/重复/自己物品/无效物品/状态（Day9） |
| 数据库校验 | 4 | 注册入库/发布入库/删除出库/登录更新（Day10；2026-08-16 起经 SSH 隧道连通真实库，4/4 通过） |
| **端到端场景** | **4** | 招领发布/认领全流程/用户管理/物品生命周期（**Day12 新增**） |
| 框架演示 | 1 | 失败自动附加演示（allure_demo 标记，默认不运行） |

端到端场景（`testcases/test_e2e.py`，`@pytest.mark.e2e`）覆盖核心业务流程完整链路：
- **招领发布流程**：注册 → 登录被"待审核"拦截（业务规则验收）→ 已审核账号登录 → 发布 → 搜索 → 详情 → 清理；
- **认领全流程**：用户A发布 → 用户B登录搜索 → 发起认领 → 用户A查看申请 → 审核通过 → 物品状态变"已认领" → 清理；
- **用户管理流程**：查看个人信息 → 修改 name → 验证生效 → 还原；
- **物品生命周期**：发布 → 列表 → 详情 → 编辑 → 查看变更 → 删除 → 确认删除。
认领流程需要两个已审核账号：用户B 配置在 `.env` 的 `E2E_USERNAME`/`E2E_PASSWORD`
（新注册用户会被"待审核"拦截，无法登录——已作为业务规则在用例中验证）；未配置时
认领用例跳过。端到端链路较长，类级别配置 `@pytest.mark.flaky(reruns=2, reruns_delay=1)`
（pytest-rerunfailures）对偶发超时重试兜底。

## 接口契约（Day6 API 文档 + 2026-08-03 对真实后端实测修正）

> 与 Day6 文档不同的地方已用「⚠️」标出，均为实测确认，测试代码已按真实契约编写。

- 登录：`POST /api/user/login`，请求体 `{"username": "xxx", "password": "xxx"}`；
  成功响应 `{"code": "200", "data": {"token": "xxx", ...}}`；
  认证方式：后续请求在 Header 携带自定义 `token: <token>`（**非 Bearer**）
- 物品列表/搜索：`GET /api/lost-item/page`；分页参数为 `currentPage`/`size`
  （源码确认），响应分页字段为 `records/total/size/current/pages`
- 筛选参数为 `title` / `categoryId` / `status` / `userId`（API 文档 v3.3 源码确认；
  ⚠️ **无 `keyword` 参数**，初版误用已修正）；`title` 留空=不筛选；`categoryId`
  筛选有效，不存在的分类返回空列表
- ⚠️ 发布物品：`POST /api/lost-item`（**不是** `/api/lost-item/add`），请求体字段
  `title/categoryId/lostPlace/lostTime/description/images/contactName/contactPhone`
  （API 文档 v3.3 源码确认；⚠️ `contactEmail`/`status` 后端实体无此字段，已从代码
  移除）；description 过短返回 `code=-1`"发布内容过于简单"；userId 可省略
  （服务端从 token 解析）；⚠️ 发布成功响应**不返回物品 ID**，需按标题回查列表定位
- ⚠️ 编辑：`PUT /api/lost-item/{id}`；删除：`DELETE /api/lost-item/{id}`
  （**不是** `/delete/{id}`）；删除后回查返回 `code=-1`（非 HTTP 404）
- ⚠️ 发起认领：`POST /api/claim`，body `{itemId, itemType, description}`，
  `itemType` 1=认领失物、0=认领招领物品（**不是** `/api/claim-application/add`）；
  认领自己物品/重复认领/不存在物品均返回 `code=-1` + 提示
- ⚠️ 认领列表：`GET /api/claim/my`（status 0=待审核、3=已取消）；
  取消认领：`PUT /api/claim/cancel/{id}`
- ⚠️ 发布者查看"他人对我的认领申请"：`GET /api/claim/page`（返回记录含
  itemId/itemTitle/username/status 等展示字段）；审核：`PUT /api/claim/audit`，
  body `{"id":N,"status":1,"auditRemark":""}`，1=通过 2=拒绝；**审核通过后物品
  状态自动变为 1（已认领）**；已处理认领的物品仍可删除（均 Day12 实测）
- ⚠️ 系统缺陷（已实测）：物品一旦被认领（即使已取消）仍不能再次认领——
  认领用例从种子物品池动态选取未认领过的他人物品，池子用尽会 skip
- 未登录请求返回 HTTP `401`"认证失败，请重新登录"
- ⚠️ 登录失败计数（Day10 实测）：账号连续 5 次密码错误触发 **15 分钟账号锁定**
  （"还剩 N 次尝试机会"递减提示），**成功登录即重置计数**——参数化登录用例
  将计数型失败组放最后并用宽断言兼容锁定提示
- ⚠️ 发布标题长度（Day10 实测）：**≥2 且 ≤100 字符**（1 字符"不能少于2个字符"、
  101+ 字符"不能超过100个字符"；50/51 字符均可发布，旧文档"1-50 字符"不准确）；
  空标题 / 缺 categoryId / 过短 description 均被拒绝
- 注册：`POST /api/user/add`（公开；API 文档 v3.3 源码确认，⚠️ 初版误用
  `/api/user/register`——接口不存在返回 500，已修正）；必填 `username`(3-50位
  字母数字)/`password`/`email`(唯一)/`name` + `agreementAccepted=true`；
  注册入库用例（test_db_checks.py）在数据库可达时启用（SSH 隧道连通后即启用，见
  「数据库连接」章节）；
  ⚠️ 注册后用户状态为**待审核**，登录返回 code=-1"待审核: 请等待管理员审核..."，
  需管理员审核通过才能登录（Day12 实测；端到端用例将验证该业务规则，
  认领流程的用户B 用 .env 的 E2E_USERNAME/E2E_PASSWORD 已审核账号）
- ⚠️ 用户信息：`GET /api/user/current` 获取当前用户（需 token）；
  `PUT /api/user/{id}` 更新部分字段（如 `{"name": "xxx"}`）→"更新成功"（Day12 实测）

## 目录结构

```text
lostfound-api-test/
├── .env / .env.example     # 环境变量（.env 不提交 Git）
├── .gitignore
├── requirements.txt
├── pytest.ini              # testpaths / addopts（Allure + 默认排除 allure_demo 标记）
├── conftest.py             # 全局 fixture：base_url / api_session / login_token / test_data
│                           #   / unique_username / temp_item / published_item_id；
│                           #   Day11 钩子：environment.properties 自动生成 /
│                           #   categories.json 注入 / 失败用例自动附加请求响应
├── config/settings.py      # python-dotenv 加载 .env（含 DB_HOST / DB_PORT 等 DB_* 连接信息）
├── start-db-tunnel.bat     # 一键开启数据库 SSH 隧道（见「数据库连接」章节）
├── allure/
│   └── categories.json     # 自定义缺陷分类模板（Day11，注入 allure-results 后生效）
├── utils/
│   ├── api_client.py       # requests 封装（Base URL + token 注入）
│   ├── db_utils.py         # 数据库工具（Day10：DBUtils 查询/断言封装）
│   ├── allure_helper.py    # Allure 附件辅助（Day11：attach_request_response /
│   │                       #   remember_response / 失败自动附加记录）
│   └── ci_guard.py         # CI 模式守卫（Day13：环境不可达时学习模式跳过 / CI 模式失败）
├── scripts/                # 独立工具脚本（Day14，不参与 pytest 用例收集）
│   ├── playwright_smoke.py #   Playwright 环境自检（Day15 UI 自动化预热）
│   └── cos_upload_check.py #   COS 上传权限验证（Day19 Allure 报告上传预热）
└── testcases/
    ├── test_login.py       # 登录用例（Day8 5 条 + Day10 参数化 7 组）
    ├── test_items.py       # 物品用例（Day9 10 条 + Day10 参数化 10 组）
    ├── test_search.py      # 搜索用例（Day9 5 条 + Day10 参数化 5 组）
    ├── test_claims.py      # 认领用例（Day9，5 条）
    ├── test_db_checks.py   # 数据库校验用例（Day10，4 条；表结构已对齐真实库 user/update_time）
    ├── test_e2e.py         # 端到端场景用例（Day12，4 条；e2e 标记 + 失败重试）
    └── test_allure_failure_demo.py  # 故意失败的演示用例（Day11，allure_demo 标记，
                                     #   默认不参与全量，验证失败自动附加）
```

## Allure 报告定制（Day11）

- **步骤与附件**：每个用例的关键操作都在 `allure.step` 中展示；主请求/响应通过
  `utils/allure_helper.py::attach_request_response` 附加进报告（统一截断 2000 字符，
  请求头敏感字段 token 自动掩码）；
- **环境信息**：`conftest.py::pytest_sessionstart` 在测试开始前自动生成
  `environment.properties`（环境名/BaseURL/Python 版本/平台/测试人员/测试日期/
  服务器规格）写入 allure-results，报告 Overview 页面展示；
- **自定义缺陷分类**：`allure/categories.json` 模板自动注入结果目录，失败用例按
  接口超时 / 环境不可达 / 断言失败 / 已知Bug / 测试跳过 分类展示；
- **失败自动附加**：`pytest_runtest_makereport` 钩子在用例失败时自动附加该用例
  最近一次请求/响应详情（已附加过则避免重复）；
- **演示用例**：`pytest -m allure_demo --alluredir=./allure-results-demo` 单独运行
  故意失败的演示用例，验证失败自动附加生效（该用例默认不参与全量运行）。

## Jenkins / CI 集成（Day13）

代码已推送双远程仓库，Jenkins 自由风格项目拉取后自动执行"安装依赖 → 生成 .env →
跑 pytest → 生成 Allure 报告"：

| 项 | 值 |
|----|----|
| Gitee 仓库 | `https://gitee.com/novaforge/lostfound-api-test.git`（main 分支） |
| GitHub 仓库 | `https://github.com/KingandWorld/lostfound-api-test.git`（main 分支） |
| 构建环境 | 4G 轻量云服务器（CentOS 7），Jenkins 自由风格项目 `lostfound-api-test`，`http://<服务器IP>:8082` |
| 标签 | `v1.0`=Day8~10 功能基线、`v1.1`=Day12 套件验收版、`v1.2`=Day13 CI 集成版 |

- **CI 模式**：Jenkins 构建脚本导出 `CI=1` 后，后端/数据库不可达时用例**直接失败**
  而不是跳过（学习模式默认跳过）——环境挂掉时构建必须红，不允许假绿灯；
  统一出口 `utils/ci_guard.py::guard_unreachable`（学习模式 `pytest.skip` / CI 模式
  `raise AssertionError`），本地开发不导出 `CI` 时行为与 Day8~12 完全一致；
- **敏感信息**：`.env` 不入库（.gitignore），构建脚本从 Jenkins 凭据/环境变量现场
  生成；`.env.example` 只放占位符；
- **稳定性**：端到端用例类级别 `@pytest.mark.flaky(reruns=2, reruns_delay=1)` 重试
  兜底（pytest-rerunfailures），其余用例不加重试（避免掩盖真实缺陷）；
- 构建脚本、Allure 插件配置等完整步骤见 `示例/week2_day13_示例-Jenkins集成开发手册.md`。

## Day14 预习脚本与资源决策

休息调整日沉淀的工具与决策（详见 `示例/week2_day14_示例-中期复盘与资源调整手册.md`）：

| 项 | 说明 |
|----|------|
| `scripts/playwright_smoke.py` | Playwright 环境自检：打开页面 → 打印标题 → 可选截图。`python scripts/playwright_smoke.py --screenshot`（Day15 UI 自动化预热，本地实测通过） |
| `scripts/cos_upload_check.py` | COS 上传权限验证：上传测试文件确认写入权限。运行前把 `.env.example` 的 `COS_*` 段填入 `.env`（Day19 Allure 报告上传预热） |
| COS 配置 | `config/settings.py` 新增 `COS_SECRET_ID` / `COS_SECRET_KEY` / `COS_BUCKET` / `COS_REGION`（只放 .env，不入库） |
| 资源决策 | **方案C（混合）**：接口测试跑服务器 Jenkins CI，UI 测试本地运行后手动合并 Allure——4G 服务器上 headless Chromium（500MB-1GB）会导致 OOM，本地 Agent 不便面试展示，混合方案务实折中且面试可讲"考虑资源限制后的架构取舍" |

**注意**：Playwright / cos-python-sdk-v5 只装在本地 venv，**未加入 requirements.txt**——Jenkins CI 只跑接口测试，不加 UI 依赖避免拖慢构建（UI 测试按方案C在本地运行，Day15 起单独管理依赖）。

## Day15 UI 自动化项目（独立仓库）

UI 测试是**独立项目**（`../lostfound-ui-test-示例/`，Playwright + pytest + Allure + Page Object），
与本站同用一套测试账号与登录契约（token 存 localStorage、自定义 Header `token`、5 次失败锁定）：

- 项目结构与用例详见 `../../示例/week3_day15_示例-UI自动化框架选型与第一个脚本开发手册.md`；
- 登录用例 5 条实测 3 轮全绿（headless 15.6~16.8s），Allure 报告本地生成；
- 本仓库保持**零 UI 依赖**：CI 构建不装 Playwright，接口测试与 UI 测试职责清晰（方案C）。

## 快速开始

```bash
# 1. 创建并激活虚拟环境（Windows Git Bash 可一键执行 示例/week2_day8_环境搭建与初始化脚本.sh）
python -m venv venv
venv\Scripts\activate        # Windows；Linux/Mac 用 source venv/bin/activate

# 2. 安装依赖（国内可用清华镜像加速；⚠️ 2026-08-17 起清华镜像对本机 HTTP 403，
#    报错时换阿里云：-i https://mirrors.aliyun.com/pypi/simple/）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 配置环境变量
#    复制 .env.example 为 .env，填写 BASE_URL / 测试账号 / 数据库信息

# 4. 开启数据库 SSH 隧道（数据库校验用例需要；API 用例不需要）
#    Windows 双击 start-db-tunnel.bat（保持窗口开着），或手动执行：
#    ssh -N -L 13306:127.0.0.1:3306 root@<服务器IP>

# 5. 运行测试并生成 Allure 报告
pytest
allure serve ./allure-results
```

## 数据库连接（SSH 隧道，2026-08-16 起生效）

数据库校验用例（test_db_checks.py）需要连接服务器 MySQL（`lost_found_db`）。
服务器 MySQL 出于安全仅监听本机（bind-address=127.0.0.1）且 ufw 未放行 3306、
`lost_found_user` 仅授权 `@'localhost'`，**远程直连不可行**——本方案用 SSH 隧道，
从服务器本机发起连接，天然匹配 localhost 授权，**零服务器配置改动、零安全风险**。

```text
本机 pytest (pymysql) ──> 127.0.0.1:13306 ──SSH 隧道──> 服务器 127.0.0.1:3306 ──> lost_found_db
```

| 项 | 值 | 说明 |
|----|----|------|
| 隧道命令 | `ssh -N -L 13306:127.0.0.1:3306 root@<服务器IP>` | Windows 一键：双击 `start-db-tunnel.bat`（关窗口=关隧道；该脚本为本机工具，已 gitignore 不入库，真实 IP 自行填写） |
| .env | `DB_HOST=127.0.0.1` / `DB_PORT=13306` | ⚠️ 本机也装有 MySQL 占用 3306，所以隧道必须用 **13306**，不要用 3306 |
| 凭据 | `lost_found_user` / `lost_found_db`（与后端应用同一账号） | 见 .env，不入库 |
| 真实库结构 | 表名 `user`（**单数**，非 users）；登录时间用 `update_time`（无 lastLoginTime） | test_db_checks.py 已按真实结构对齐 |

隧道未开启时：数据库校验用例按 Day10 预案跳过（学习模式），其余 API 用例不受影响。

## 开发节奏

| 节点 | 内容 | 提交信息 |
|------|------|---------|
| Day8 | 环境搭建 + 登录用例（本目录） | `init: 接口自动化项目初始化` → `feat: add conftest and test_login (5 cases)` |
| Day9 | test_items.py / test_search.py / test_claims.py 用例（20 条） | `feat: add test_items and test_claims` |
| Day10 | 参数化数据驱动（22 组）+ db_utils.py 数据库校验 + fixture 数据隔离 | `feat: 添加数据驱动测试(22组参数)和数据库校验工具，优化fixture数据隔离` |
| Day11 | Allure 报告深度定制：step/attach、environment.properties、categories.json、失败自动附加 | `feat: Allure 报告深度定制（attach/环境信息/缺陷分类/失败自动附加）` |
| 08-06 契约修正 | 按 API 文档 v3.3 修正接口契约：列表筛选 keyword→title、注册 /api/user/register→/api/user/add、物品请求体去 contactEmail/status | `fix: 按API文档v3.3修正接口契约（列表筛选keyword→title、注册改/api/user/add、物品请求体移除contactEmail/status）` |
| Day12 | 接口自动化套件验收：test_e2e.py 端到端 4 条（招领发布/认领全流程/用户管理/物品生命周期）+ 失败重试 + README 补全 | `feat: 端到端测试用例（覆盖核心业务流程完整链路）与套件验收` |
| Day13 | Jenkins 集成接口测试 + Allure 报告 | `ci: integrate jenkins and allure report` |
| 08-16 隧道连通 | 数据库校验经 SSH 隧道连通并对齐真实表结构（user/update_time） | `feat: 数据库校验经SSH隧道连通并对齐真实表结构（user/update_time）` |
| Day14 | 中期复盘与资源调整：scripts/ 预习脚本（Playwright 环境自检 / COS 上传验证）、COS_* 配置、资源决策（方案C 混合：接口 CI + UI 本地） | `feat: 中期复盘与资源调整（Day14 预习脚本与资源决策）` |
| Day15 | UI 自动化项目独立化：`lostfound-ui-test-示例/`（Playwright 登录 5 用例 3 轮全绿）；本仓库 README 同步指引，接口/UI 依赖彻底隔离 | `docs: Day15 UI 项目独立化说明（README 同步）` |
