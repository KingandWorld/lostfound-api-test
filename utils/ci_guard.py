"""CI 模式守卫（Day13 新增）：环境不可达时，学习模式跳过、CI 模式直接失败。

背景：Day8 起，conftest 与各测试文件的 _request 在后端/数据库不可达时
pytest.skip，避免学习阶段环境问题中断；Jenkins 集成后，环境不可达必须
暴露为构建失败（否则绿色构建是假绿灯——后端挂了一天 CI 照样"全绿"）。

用法：所有"环境不可达"场景统一走 guard_unreachable()，替代散落的
`pytest.skip("后端不可达...")`。CI 模式由 Jenkins 构建脚本导出 `CI=1`
触发（config/settings.py 的 CI_MODE），本地运行不导出 CI 时行为与
Day8~12 完全一致。
"""

import pytest

from config.settings import CI_MODE


def guard_unreachable(exc, context="后端"):
    """环境不可达的统一出口：学习模式跳过、CI 模式失败。

    - 学习模式（默认，未导出 CI）：pytest.skip —— 与 Day8~12 行为完全一致，
      Allure 报告中显示为 SKIPPED（categories.json 的"测试跳过"分类）；
    - CI 模式（CI=1，Jenkins 导出）：raise AssertionError —— 后端/数据库
      不可达直接判失败，Allure 报告中按 categories.json 的"环境不可达"分类，
      构建结果与报告一致地暴露环境问题。
    """
    if CI_MODE:
        raise AssertionError(f"CI 模式：{context}不可达，环境问题不允许跳过: {exc}") from exc
    pytest.skip(f"{context}不可达，用例跳过（CI 模式将直接失败）: {exc}")
