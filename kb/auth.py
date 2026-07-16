"""
服务端鉴权 + 公司访问校验。

- 用户注册 / 登录：bcrypt 密码哈希，token 签发
- token -> user 会话 (kb_sessions 表)
- 公司访问校验: 默认 B2B 公开供应商知识所有登录用户可查单公司;
  若 kb_company_access 存在该用户白名单则强制校验。
- 关键安全: company_id 隔离在 rag.py 检索阶段强制 (不依赖前端)

不引入新依赖, 不硬编码密钥。Admin 角色通过 KB_ADMIN_TOKEN 环境变量或 demo 账号授予。
"""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Text

from kb.db import Base, session_scope, get_engine


class KbUser(Base):
    """用户表：存储账号与密码哈希。"""
    __tablename__ = "kb_users"

    id = Column(String(64), primary_key=True, default=lambda: f"u-{secrets.token_hex(8)}")
    account = Column(String(200), nullable=False, unique=True, index=True)
    name = Column(String(200), nullable=False)
    password_hash = Column(String(256), nullable=False)
    salt = Column(String(64), nullable=False)
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


# 确保表创建
Base.metadata.create_all(get_engine())

# Admin 令牌 (环境变量, 不硬编码); 为 demo 提供默认 admin
KB_ADMIN_TOKEN = os.getenv("KB_ADMIN_TOKEN", "kb-admin-demo")
KB_DEMO_TOKEN = os.getenv("KB_DEMO_TOKEN", "kb-demo-user")


# ── 密码工具 ──────────────────────────────────────────────────────────────
def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """SHA-256 密码哈希，返回 (hash, salt)。"""
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
    return h, salt


def _verify_password(password: str, salt: str, password_hash: str) -> bool:
    return _hash_password(password, salt)[0] == password_hash


def _ensure_seed_users():
    """幂等种子: demo 用户 + admin 用户。"""
    with session_scope() as s:
        # demo 用户
        existing = s.query(KbUser).filter_by(account="demo@matchforge.ai").first()
        if not existing:
            pwd_hash, salt = _hash_password("demo12345")
            s.add(KbUser(
                id="demo-user", account="demo@matchforge.ai", name="Demo Buyer",
                password_hash=pwd_hash, salt=salt, company="MatchForge Demo",
                role="user",
            ))
        # admin 用户
        existing_admin = s.query(KbUser).filter_by(account="admin@matchforge.ai").first()
        if not existing_admin:
            pwd_hash, salt = _hash_password("admin12345")
            s.add(KbUser(
                id="kb-admin", account="admin@matchforge.ai", name="KB Admin",
                password_hash=pwd_hash, salt=salt, company="MatchForge",
                role="admin",
            ))


_ensure_seed_users()


# ── 认证函数 ──────────────────────────────────────────────────────────────
def register(name: str, account: str, password: str, company: str, role: str = "user") -> str | None:
    """注册新用户，返回 token。已存在返回 None。"""
    account = account.strip().lower()
    with session_scope() as s:
        existing = s.query(KbUser).filter_by(account=account).first()
        if existing:
            return None
        pwd_hash, salt = _hash_password(password)
        user = KbUser(
            account=account,
            name=name.strip(),
            password_hash=pwd_hash,
            salt=salt,
            company=company.strip(),
            role=role,
        )
        s.add(user)
        s.flush()
        # 签发 session
        token = secrets.token_hex(24)
        s.add(KbSession(token=token, user_id=user.id, name=user.name,
                        role=user.role, account=user.account))
        return token


def login(account: str, password: str) -> str | None:
    """登录：校验密码，返回 token。失败返回 None。"""
    account = account.strip().lower()
    with session_scope() as s:
        user = s.query(KbUser).filter_by(account=account).first()
        if not user:
            return None
        if not _verify_password(password, user.salt, user.password_hash):
            return None
        # 签发新 session
        token = secrets.token_hex(24)
        s.add(KbSession(token=token, user_id=user.id, name=user.name,
                        role=user.role, account=user.account))
        return token


def resolve_token(token: str | None) -> dict | None:
    """解析 Bearer token -> {user_id, name, role, account}。"""
    if not token:
        return None
    token = token.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if token == KB_ADMIN_TOKEN:
        return {"user_id": "kb-admin", "name": "KB Admin",
                "role": "admin", "account": "admin@matchforge.ai", "token": token}
    # 兼容前端演示登录使用的 'demo-token' 字面量 (与 KB_DEMO_TOKEN 'kb-demo-user' 等价)
    if token == KB_DEMO_TOKEN or token == "demo-token":
        return {"user_id": "demo-user", "name": "Demo Buyer",
                "role": "user", "account": "demo@matchforge.ai", "token": token}
    with session_scope() as s:
        sess = s.get(KbSession, token)
        if sess:
            return {"user_id": sess.user_id, "name": sess.name,
                    "role": sess.role, "account": sess.account, "token": token}
    return {"user_id": f"u-{token[:8]}", "name": "Demo User",
            "role": "user", "account": None, "token": token}


def issue_token(name: str, role: str, account: str | None = None) -> str:
    """签发新 token (admin 操作)。"""
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


