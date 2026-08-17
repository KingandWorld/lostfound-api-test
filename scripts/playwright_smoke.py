"""Playwright 环境自检脚本（Day14 预习，为 Day15 UI 自动化热身）。

用途：
    - 验证 Playwright 已正确安装、Chromium 可正常启动（headless）；
    - 用百度首页做一个最简冒烟：打开页面 → 打印标题 → 可选截图；
    - 跑通后即具备 Day15 起 UI 自动化的最小环境（选择器/操作/等待后续学习）。

用法：
    python scripts/playwright_smoke.py                # 默认打开百度，只打印标题
    python scripts/playwright_smoke.py --screenshot    # 额外截图保存到 screenshots/playwright_smoke.png
    python scripts/playwright_smoke.py --url https://<目标站点>   # 换成目标站点（示例占位，勿填真实域名）

环境要求（Day14 手册第 3 步）：
    pip install playwright -i https://pypi.tuna.tsinghua.edu.cn/simple
    playwright install chromium        # 下载失败时先设 PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/
"""

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

DEFAULT_URL = "https://www.baidu.com"
DEFAULT_SCREENSHOT = Path(__file__).resolve().parent.parent / "screenshots" / "playwright_smoke.png"


def main() -> int:
    parser = argparse.ArgumentParser(description="Playwright 环境自检：打开页面 → 打印标题 → 可选截图")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"要打开的 URL（默认 {DEFAULT_URL}）")
    parser.add_argument("--screenshot", action="store_true", help="打开页面后截图保存")
    args = parser.parse_args()

    try:
        with sync_playwright() as p:
            # headless=True：服务器/本地无界面环境均可运行（Day18 服务器方案同样适用）
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            # 打开页面并等待加载完成（含 JS 渲染的页面也能拿到真实标题）
            page.goto(args.url, wait_until="load", timeout=30_000)
            print(f"页面标题: {page.title()}")
            if args.screenshot:
                DEFAULT_SCREENSHOT.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(DEFAULT_SCREENSHOT))
                print(f"截图已保存: {DEFAULT_SCREENSHOT}")
            browser.close()
    except Exception as exc:
        # 常见原因：playwright 未安装 / chromium 未下载 / 网络不通，按提示处理
        print(f"[FAIL] Playwright 自检失败: {exc}", file=sys.stderr)
        print("提示: 确认已执行 `pip install playwright` 与 `playwright install chromium`", file=sys.stderr)
        return 1

    print("[OK] Playwright 环境自检通过 —— Day15 可以开始 UI 自动化了")
    return 0


if __name__ == "__main__":
    sys.exit(main())
