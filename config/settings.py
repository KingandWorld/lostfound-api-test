"""配置加载：统一从项目根目录 .env 读取环境变量。

用法：from config.settings import BASE_URL, TEST_USERNAME
全项目唯一配置入口；切换环境（测试/预发/生产）只改 .env，代码零改动。
"""

import os

from dotenv import load_dotenv

# 默认读取当前工作目录下的 .env（pytest 在项目根目录运行即可生效）
load_dotenv()

BASE_URL = os.getenv("BASE_URL")
TEST_USERNAME = os.getenv("TEST_USERNAME")
TEST_PASSWORD = os.getenv("TEST_PASSWORD")
# Day12 新增：端到端认领流程的"用户B"账号（需已审核，新注册用户会被待审核拦截）
E2E_USERNAME = os.getenv("E2E_USERNAME")
E2E_PASSWORD = os.getenv("E2E_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
