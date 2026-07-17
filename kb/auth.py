"""
服务端鉴权 + 公司访问校验。

- 用户注册 / 登录：bcrypt 密码哈希 (salt 内嵌于 hash); 旧 sha256 哈希在登录时渐进迁移到 bcrypt。
- token -> user 会话 (kb_sessions 表)
- 公司访问校验: 默认 B2B 公开供应商知识所有登录用户可查单公司;
  若 kb_company_access 存在该用户白名单则强制校验。
- 关键安全: company_id 隔离在 rag.py 检索阶段强制 (不依赖前端)

Demo / admin demo token 策略 (P0 安全修复):
  - 源码不硬编码任何 token。KB_DEMO_TOKEN / KB_ADMIN_TOKEN 必须来自环境变量,
    未配置时为 None, 对应 demo/admin demo 登录通道关闭。
  - demo token 仅在 KB_DEMO_MODE=true 且非生产环境 (APP_ENV != production) 时生效。
  - 生产环境 (APP_ENV in {production, prod}) 一律拒绝 demo/admin demo token。
  - 未知 token 一律返回 None (不再兜底放行)。
  - 模块 import 不产生任何数据库写副作用 (不建表、不种子账号); 表由 init_db() 创建,
    demo/admin 账号由显式 seed 脚本 (scripts/seed_auth_users.py) 创建。
"""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime

import bcrypt
from sqlalchemy import Column, String, DateTime

from kb.db import Base, session_scope


# ── 模型 ────────────────────────────────────────────────────────────────────
class KbUser(Base):
    """用户表：存储账号与密码哈希。

    password_hash: bcrypt 哈希 (以 $2 开头); 历史遗留 sha256 哈希为 64 位 hex。
    salt: 仅历史 sha256 哈希使用; bcrypt 用户 salt 内嵌于 hash, 此列置空。
    """
    __tablename__ = "kb_users"

    id = Column(String(64), primary_key=True, default=lambda: f"u-{secrets.token_hex(8)}")
    account = Column(String(200), nullable=False, unique=True, index=True)
    name = Column(String(200), nullable=False)
    password_hash = Column(String(256), nullable=False)
    salt = Column(String(64), nullable=False, default="")
    company = Column(String(200), nullable=True)
    role = Column(String(20), nullable=False, default="user")  # user | admin
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class KbSession(Base):
    __tablename__ = "kb_sessions"

    token = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    name = Column(String(200), nullable=True)
    role = Column(String(20), nullable=False, default="user")  # user | admin
    account = Column(String(200), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


# ── Demo / admin demo token 配置 ────────────────────────────────────────────
# 源码不提供默认值: 未配置环境变量时为 None, demo/admin demo 通道关闭。
KB_ADMIN_TOKEN = os.getenv("KB_ADMIN_TOKEN")  # admin demo token (仅本地演示)
KB_DEMO_TOKEN = os.getenv("KB_DEMO_TOKEN")    # demo 用户 token (仅本地演示)


def is_production() -> bool:
    """生产环境标记: APP_ENV in {production, prod}。"""
    return os.getenv("APP_ENV", "development").lower() in ("production", "prod")


def demo_tokens_enabled() -> bool:
    """demo/admin demo 静态 token 是否生效。

    仅当显式开启 demo 模式 (KB_DEMO_MODE=true) 且非生产环境时生效。
    复用 kb.config.KB_DEMO_MODE 语义 (生产环境应关闭)。
    """
    if is_production():
        return False
    return os.getenv("KB_DEMO_MODE", "false").lower() == "true"


# ── 密码工具 (bcrypt, 兼容旧 sha256) ────────────────────────────────────────
_BCRYPT_PREFIX = "$2"  # bcrypt 哈希前缀 ($2a$ / $2b$ / $2y$)


def _hash_password(password: str) -> str:
    """bcrypt 密码哈希, salt 内嵌于返回值。"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str, salt: str = "") -> bool:
    """校验密码。

    - bcrypt 哈希 (以 $2 开头): 直接 bcrypt.checkpw。
    - 历史 sha256 哈希 (salt:password): 用 salt 校验 (仅用于登录期渐进迁移)。
    """
    if password_hash.startswith(_BCRYPT_PREFIX):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except (ValueError, TypeError):
            return False
    # 历史 sha256 (salt:password)
    if not salt:
        return False
    legacy = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
    return legacy == password_hash


def seed_demo_users(
    demo_password: str | None = None,
    admin_password: str | None = None,
) -> None:
    """显式种子: 创建 demo / admin 账号 (bcrypt)。

    仅供本地演示 seed 脚本调用; 不在模块 import 时执行。
    密码优先取参数, 其次环境变量 DEMO_USER_PASSWORD / DEMO_ADMIN_PASSWORD,
    均缺失时跳过该账号 (不创建空密码账号)。
    """
    demo_password = demo_password or os.getenv("DEMO_USER_PASSWORD")
    admin_password = admin_password or os.getenv("DEMO_ADMIN_PASSWORD")
    with session_scope() as s:
        if demo_password and not s.query(KbUser).filter_by(account="demo@matchforge.ai").first():
            s.add(KbUser(
                id="demo-user", account="demo@matchforge.ai", name="Demo Buyer",
                password_hash=_hash_password(demo_password), salt="",
                company="MatchForge Demo", role="user",
            ))
        if admin_password and not s.query(KbUser).filter_by(account="admin@matchforge.ai").first():
            s.add(KbUser(
                id="kb-admin", account="admin@matchforge.ai", name="KB Admin",
                password_hash=_hash_password(admin_password), salt="",
                company="MatchForge", role="admin",
            ))


# ── 认证函数 ──────────────────────────────────────────────────────────────
def register(name: str, account: str, password: str, company: str, role: str = "user") -> str | None:
    """注册新用户 (bcrypt), 返回 token。已存在返回 None。"""
    account = account.strip().lower()
    with session_scope() as s:
        existing = s.query(KbUser).filter_by(account=account).first()
        if existing:
            return None
        user = KbUser(
            account=account,
            name=name.strip(),
            password_hash=_hash_password(password),
            salt="",
            company=company.strip(),
            role=role,
        )
        s.add(user)
        s.flush()
        token = secrets.token_hex(24)
        s.add(KbSession(token=token, user_id=user.id, name=user.name,
                        role=user.role, account=user.account))
        return token


def login(account: str, password: str) -> str | None:
    """登录：校验密码, 返回 token。失败返回 None。

    历史 sha256 用户验证成功后自动升级为 bcrypt (渐进迁移)。
    """
    account = account.strip().lower()
    with session_scope() as s:
        user = s.query(KbUser).filter_by(account=account).first()
        if not user:
            return None
        if not _verify_password(password, user.password_hash, user.salt):
            return None
        # 渐进迁移: 旧 sha256 -> bcrypt
        if not user.password_hash.startswith(_BCRYPT_PREFIX):
            user.password_hash = _hash_password(password)
            user.salt = ""
            s.flush()
        token = secrets.token_hex(24)
        s.add(KbSession(token=token, user_id=user.id, name=user.name,
                        role=user.role, account=user.account))
        return token


def resolve_token(token: str | None) -> dict | None:
    """解析 Bearer token -> {user_id, name, role, account}。

    未知 token 一律返回 None (不兜底放行)。
    demo/admin demo token 仅在 demo_tokens_enabled() 时生效。
    """
    if not token:
        return None
    token = token.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not token:
        return None

    # demo / admin demo 静态 token: 仅 demo 模式 + 非生产环境生效
    if demo_tokens_enabled():
        if KB_DEMO_TOKEN and token == KB_DEMO_TOKEN:
            return {"user_id": "demo-user", "name": "Demo Buyer",
                    "role": "user", "account": "demo@matchforge.ai", "token": token}
        if KB_ADMIN_TOKEN and token == KB_ADMIN_TOKEN:
            return {"user_id": "kb-admin", "name": "KB Admin",
                    "role": "admin", "account": "admin@matchforge.ai", "token": token}

    # 真实会话 token (kb_sessions)
    with session_scope() as s:
        sess = s.get(KbSession, token)
        if sess:
            return {"user_id": sess.user_id, "name": sess.name,
                    "role": sess.role, "account": sess.account, "token": token}
    return None


def issue_token(name: str, role: str, account: str | None = None) -> str:
    """签发新会话 token (admin / demo-login 操作)。不创建 KbUser, 仅写 kb_sessions。"""
    token = secrets.token_hex(24)
    with session_scope() as s:
        s.add(KbSession(token=token, user_id=f"u-{token[:8]}", name=name,
                        role=role, account=account))
    return token


def can_access_company(user_id: str, company_id: int) -> bool:
    """
    公司访问校验。
    - 默认策略 (无白名单记录): 允许 (B2B 公开供应商知识)
    - 若该 user_id 在 kb_company_access 有任意记录 -> 强制白名单校验
    """
    from kb.models import CompanyAccess

    with session_scope() as s:
        cnt = s.query(CompanyAccess).filter_by(user_id=user_id).count()
        if cnt == 0:
            return True  # 无白名单 -> 公开访问
        return s.query(CompanyAccess).filter_by(
            user_id=user_id, company_id=company_id
        ).first() is not None


def grant_company_access(user_id: str, company_id: int):
    from kb.models import CompanyAccess

    with session_scope() as s:
        if not s.query(CompanyAccess).filter_by(user_id=user_id, company_id=company_id).first():
            s.add(CompanyAccess(user_id=user_id, company_id=company_id))
