"""
P0 认证安全测试。

覆盖:
  1. 未携带 token 访问受保护接口 -> 401
  2. 随机未知 Bearer token -> 401, resolve_token 返回 None
  3. 非 admin token 访问 admin audit -> 403
  4. 未配置 admin demo token 时, kb-admin-demo 不再有效
  5. 配置 demo token 时, demo 登录可用
  6. 生产模式下 demo token 被拒绝
  7. 密码注册/登录使用 bcrypt
  8. 旧 sha256 用户登录后升级为 bcrypt
  9. import kb.auth 不自动创建 demo/admin 账号 (无 import 期写库副作用)

测试环境 (tests/conftest.py) 显式开启 KB_DEMO_MODE 并配置 KB_DEMO_TOKEN/KB_ADMIN_TOKEN,
使 demo 通道在非生产环境下可控生效。
"""

from __future__ import annotations

import hashlib
import secrets as _secrets
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# 让 seed 脚本可被导入 (scripts/ 不是包)
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import seed_enterprise_chain as chain  # noqa: E402
from api.main import create_app  # noqa: E402
import kb.auth as auth_mod  # noqa: E402
from kb.auth import (  # noqa: E402
    KbUser,
    _hash_password,
    _verify_password,
    issue_token,
    login,
    register,
    resolve_token,
)
from kb.db import session_scope  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module", autouse=True)
def _offline_rag():
    """离线兜底: 关闭 LLM + Milvus, 避免 import/启动副作用。"""
    with patch("kb.rag.llm_available", return_value=False), \
            patch("kb.config.milvus_available", return_value=False):
        yield


@pytest.fixture(scope="module", autouse=True)
def _setup_db(_offline_rag):
    """建表 + 幂等写入企业种子 (供 demo-login 测试查询公司)。"""
    chain.init_db()
    try:
        chain.upsert_companies()
    except Exception as e:
        pytest.skip(f"企业种子不可用 (允许): {e}")
    yield


@pytest.fixture(scope="module")
def client(_setup_db):
    app = create_app()
    with TestClient(app) as c:
        yield c


def _unique_account(prefix: str = "sec") -> str:
    return f"{prefix}-{_secrets.token_hex(4)}@matchforge.ai"


# ============================================================
# 1. 未携带 token -> 401
# ============================================================
def test_no_token_returns_401(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


# ============================================================
# 2. 未知 Bearer token -> 401, resolve_token 返回 None
# ============================================================
def test_unknown_token_rejected(client):
    unknown = "totally-random-unknown-token-xyz-12345"
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {unknown}"})
    assert r.status_code == 401
    assert resolve_token(unknown) is None
    # 带前缀形式同样拒绝
    assert resolve_token(f"Bearer {unknown}") is None


# ============================================================
# 3. 非 admin token 访问 admin audit -> 403
# ============================================================
def test_non_admin_audit_forbidden(client):
    # KB_DEMO_TOKEN (role=user) 不能访问 admin 审核队列
    r = client.get(
        "/api/v1/admin/audit-queue",
        headers={"Authorization": f"Bearer {auth_mod.KB_DEMO_TOKEN}"},
    )
    assert r.status_code == 403


# ============================================================
# 4. 未配置 admin demo token 时, kb-admin-demo 不再有效
# ============================================================
def test_admin_demo_token_invalid_when_not_configured(monkeypatch):
    monkeypatch.setattr(auth_mod, "KB_ADMIN_TOKEN", None)
    # demo 模式仍开启, 但 admin demo token 未配置 -> kb-admin-demo 被拒绝
    assert resolve_token("kb-admin-demo") is None


# ============================================================
# 5. 配置 demo token 时, demo 登录可用
# ============================================================
def test_demo_login_enabled(client):
    # KB_DEMO_TOKEN 已配置 + demo 模式开启 (conftest)
    r = client.post("/api/v1/auth/demo-login", json={"company_id": 9003})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["is_demo"] is True
    assert data["token"]
    assert data["role"] == "user"
    # 签发的 token 是真实会话, resolve_token 可解析
    user = resolve_token(data["token"])
    assert user is not None
    assert user["role"] == "user"


def test_demo_login_unknown_company_404(client):
    r = client.post("/api/v1/auth/demo-login", json={"company_id": 999999})
    assert r.status_code == 404


# ============================================================
# 6. 生产模式下 demo token 被拒绝
# ============================================================
def test_demo_tokens_rejected_in_production(monkeypatch, client):
    monkeypatch.setenv("APP_ENV", "production")
    try:
        # 静态 demo/admin demo token 失效
        assert resolve_token(auth_mod.KB_DEMO_TOKEN) is None
        assert resolve_token(auth_mod.KB_ADMIN_TOKEN) is None
        # demo-login 接口关闭
        r = client.post("/api/v1/auth/demo-login", json={"company_id": 9003})
        assert r.status_code == 404
    finally:
        monkeypatch.delenv("APP_ENV", raising=False)


def test_demo_tokens_rejected_when_demo_mode_off(monkeypatch):
    monkeypatch.setenv("KB_DEMO_MODE", "false")
    try:
        assert resolve_token(auth_mod.KB_DEMO_TOKEN) is None
        assert resolve_token(auth_mod.KB_ADMIN_TOKEN) is None
    finally:
        monkeypatch.delenv("KB_DEMO_MODE", raising=False)


# ============================================================
# 7. 密码注册/登录使用 bcrypt
# ============================================================
def test_password_hash_is_bcrypt():
    h = _hash_password("Sup3rSecret!")
    assert h.startswith("$2"), "密码哈希应为 bcrypt ($2 前缀)"
    assert _verify_password("Sup3rSecret!", h) is True
    assert _verify_password("wrong-password", h) is False
    # 不同次哈希使用不同 salt (结果不同)
    assert _hash_password("Sup3rSecret!") != h


def test_register_login_use_bcrypt():
    acc = _unique_account("reg")
    token = register("Sec Test", acc, "Sup3rSecret!", "TestCo", "user")
    assert token is not None
    # 存储的哈希为 bcrypt
    with session_scope() as s:
        u = s.query(KbUser).filter_by(account=acc).first()
        assert u is not None
        assert u.password_hash.startswith("$2")
        assert u.salt == ""
    # 登录成功 + 签发 token
    tok2 = login(acc, "Sup3rSecret!")
    assert tok2 is not None
    assert resolve_token(tok2) is not None
    # 错误密码失败
    assert login(acc, "wrong-password") is None


# ============================================================
# 8. 旧 sha256 用户登录后升级为 bcrypt
# ============================================================
def test_legacy_sha256_upgraded_on_login():
    acc = _unique_account("legacy")
    password = "OldPass123"
    salt = _secrets.token_hex(16)
    legacy_hash = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
    uid = f"u-{_secrets.token_hex(8)}"
    with session_scope() as s:
        s.add(KbUser(
            id=uid, account=acc, name="Legacy", password_hash=legacy_hash,
            salt=salt, company="C", role="user",
        ))

    # 旧 sha256 仍可验证 (兼容期)
    assert _verify_password(password, legacy_hash, salt) is True
    # 登录成功并触发升级
    tok = login(acc, password)
    assert tok is not None
    with session_scope() as s:
        u = s.query(KbUser).filter_by(account=acc).first()
        assert u.password_hash.startswith("$2"), "登录后应升级为 bcrypt"
        assert u.salt == "", "升级后应清空旧 salt"
    # 升级后旧 sha256 哈希不再用于校验 (bcrypt 路径)
    assert _verify_password(password, u.password_hash) is True
    # 错误密码失败
    assert login(acc, "wrong-password") is None


# ============================================================
# 9. import kb.auth 不自动创建 demo/admin 账号
# ============================================================
def test_import_does_not_auto_seed_users(tmp_path):
    """import kb.auth 不产生数据库写副作用: 在独立进程 + 全新 SQLite 库中
    导入 kb.auth 并 init_db(), 断言 kb_users 仍为空 (无 import 期种子)。"""
    db_file = tmp_path / "import_no_seed.db"
    code = (
        "import os\n"
        f"os.environ['KB_DATABASE_URL'] = 'sqlite:///{db_file.as_posix()}'\n"
        "os.environ['KB_DEMO_MODE'] = 'false'\n"
        "os.environ['APP_ENV'] = 'development'\n"
        "import kb.auth  # 不应建表、不应种子账号\n"
        "from kb.db import init_db, session_scope\n"
        "from kb.auth import KbUser\n"
        "init_db()  # 显式建表 (空)\n"
        "with session_scope() as s:\n"
        "    print('COUNT=' + str(s.query(KbUser).count()))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT),
    )
    assert result.returncode == 0, f"subprocess failed: {result.stderr}"
    assert "COUNT=0" in result.stdout, (
        f"import kb.auth 不应自动创建用户, 但检测到非空: {result.stdout} {result.stderr}"
    )
