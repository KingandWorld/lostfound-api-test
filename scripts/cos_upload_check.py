"""腾讯云 COS 上传权限验证脚本（Day14 预习，为 Day19 把 Allure 报告上传 COS 预热）。

用途：
    - 验证 COS Python SDK（cos-python-sdk-v5）已安装、凭据可用；
    - 上传一个最小的测试文件到指定桶，确认「写入」权限（Day19 上传 Allure 报告
      需要同样的权限：上传对象 + 获取对象 URL）；
    - 验证通过后即可放心准备 Day19 的 COS 上传集成。

用法：
    python scripts/cos_upload_check.py                # 用 .env 里的 COS_* 配置
    python scripts/cos_upload_check.py --file xxx.zip # 默认上传一个 4 字节文本文件

配置（复制 .env.example 的 COS_* 段到 .env，或导出环境变量）：
    COS_SECRET_ID=<你的 SecretId>
    COS_SECRET_KEY=<你的 SecretKey>
    COS_BUCKET=<桶名，如 my-bucket-1250000000>
    COS_REGION=<地域，如 ap-guangzhou>          # 看桶的所属地域

安全提示：
    - SecretKey 与密码同等重要：只放 .env（已被 .gitignore 排除），绝不提交 Git；
    - 建议使用子账号/临时密钥（最小权限），不要用主账号密钥。
"""

import sys
from pathlib import Path

# 项目根目录（scripts/ 的上一级），保证 import config.settings 可用
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from qcloud_cos import CosConfig, CosS3Client  # noqa: E402

from config.settings import (  # noqa: E402
    COS_BUCKET,
    COS_REGION,
    COS_SECRET_ID,
    COS_SECRET_KEY,
)

TEST_CONTENT = "lostfound-api-test cos check\n"  # 测试文件内容（Day19 换成 Allure 报告 zip）


def main() -> int:
    missing = [k for k, v in (("COS_SECRET_ID", COS_SECRET_ID), ("COS_SECRET_KEY", COS_SECRET_KEY),
                              ("COS_BUCKET", COS_BUCKET), ("COS_REGION", COS_REGION)) if not v]
    if missing:
        print(f"[SKIP] 缺少配置: {', '.join(missing)} —— 请复制 .env.example 的 COS_* 段到 .env 后重试")
        return 1

    # 1) 初始化客户端（凭据只在内存中，不落盘）
    config = CosConfig(Region=COS_REGION, SecretId=COS_SECRET_ID, SecretKey=COS_SECRET_KEY)
    client = CosS3Client(config)

    # 2) 上传测试文件（key 带日期前缀，方便区分与清理）
    key = f"lostfound-api-test/cos_check_{Path(__file__).parent.name}.txt"
    try:
        # put_object 成功返回即 HTTP 200（失败会抛异常进入 except），
        # 返回的 dict 不含 HTTPStatusCode 字段（区别于 boto3 的 ResponseMetadata），
        # 因此状态码不必单独打印，以"上传成功"为准
        response = client.put_object(Bucket=COS_BUCKET, Body=TEST_CONTENT.encode("utf-8"), Key=key)
        print(f"上传成功: cos://{COS_BUCKET}/{key}（HTTP 200）")
        print(f"ETag: {response.get('ETag', '-')}")
        print(f"请求 ID: {response.get('x-cos-request-id', '-')}")
        print(f"访问 URL: https://{COS_BUCKET}.cos.{COS_REGION}.myqcloud.com/{key}")
    except Exception as exc:
        print(f"[FAIL] COS 上传失败: {exc}")
        print("排查: ① SecretId/SecretKey 是否正确 ② 桶名是否含数字后缀 ③ 地域是否正确 "
              "④ 子账号是否有该桶的 PutObject 权限", file=sys.stderr)
        return 1

    print("[OK] COS 上传权限验证通过 —— Day19 可以上传 Allure 报告了")
    return 0


if __name__ == "__main__":
    sys.exit(main())
