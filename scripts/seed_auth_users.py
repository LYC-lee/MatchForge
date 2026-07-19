"""
认证账号种子脚本 (显式, 非自动)。

创建本地演示用的 demo / admin 账号 (bcrypt 哈希)。
- 不在 kb.auth 模块 import 时执行; 必须显式运行此脚本。
- 密码来自环境变量, 源码不硬编码密码:
    DEMO_USER_PASSWORD  demo 用户密码 (demo@matchforge.ai, role=user)
    DEMO_ADMIN_PASSWORD admin 用户密码 (admin@matchforge.ai, role=admin)
  未设置对应环境变量则跳过该账号。

用法:
    DEMO_USER_PASSWORD=demo12345 DEMO_ADMIN_PASSWORD=admin12345 \
        python scripts/seed_auth_users.py

注意: 生产环境不应运行此脚本; 账号应由运维或真实注册流程创建。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 让项目根目录可导入 (scripts/ 不是包)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from kb.db import init_db  # noqa: E402
from kb.auth import seed_demo_users  # noqa: E402


def main() -> None:
    init_db()  # 确保 kb_users / kb_sessions 表存在
    seed_demo_users()
    print("认证账号种子完成 (仅创建已配置密码的账号; 未配置环境变量的账号跳过)。")


if __name__ == "__main__":
    main()
