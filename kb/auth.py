"""
最小服务端鉴权 + 公司访问校验。

当前项目认证为前端 localStorage mock (无真实后端账号)。为知识库 API 提供:
  - token -> user 会话 (kb_sessions 表, 兼容前端已有 Bearer token)
  - 未知 token 自动注册为 demo 用户 (无缝兼容前端)
  - 公司访问校验: 默认 B2B 公开供应商知识所有登录用户可查单公司;
    若 kb_company_access 存在该用户白名单则强制校验。
  - 关键安全: company_id 隔离在 rag.py 检索阶段强制 (不依赖前端)

不引入新依赖, 不硬编码密钥。Admin 角色通过 KB_ADMIN_TOKEN 环境变量或 demo 账号授予。
"""

# ── 生产安全 TODO (Phase 1 暂不收紧, 保持 demo/mock 兼容) ──────────────
# 1. KB_ADMIN_TOKEN / KB_DEMO_TOKEN 有默认值 (kb-admin-demo / kb-demo-user),
#    生产部署必须用环境变量覆盖, 否则任何人可拿到 admin。
# 2. resolve_token 对未知 token 自动注册为 demo user (兼容前端 mock), 生产应拒识。
# 3. can_access_company 默认策略为"无白名单则全公开", 企业驾驶舱多租户场景需改为默认拒绝。
# 4. procure / partner-chat 等接口目前仅做 token 解析, 未校验企业归属, 生产需补 enterprise_id 隔离。
# ──────────────────────────────────────────────────────────────────────

from __future__ import annotations

import os
import secrets
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Text

from kb.db import Base, session_scope, get_engine


class KbSession(Base):
    __tablename__ = "kb_sessions"

    token = Column(String(64), primary_key=True)
    user_id = Column(String(100), nullable=False, index=True)
    name = Column(String(200), nullable=True)
    role = Column(String(20), nullable=False, default="user")  # user | admin
    account = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


# 确保 sessions 表创建
Base.metadata.create_all(get_engine())

# Admin 令牌 (环境变量, 不硬编码); 为 demo 提供默认 admin
KB_ADMIN_TOKEN = os.getenv("KB_ADMIN_TOKEN", "kb-admin-demo")
KB_DEMO_TOKEN = os.getenv("KB_DEMO_TOKEN", "kb-demo-user")


def _ensure_seed_sessions():
    """幂等种子: demo 用户 + admin 用户。"""
    with session_scope() as s:
        if not s.get(KbSession, KB_DEMO_TOKEN):
            s.add(KbSession(token=KB_DEMO_TOKEN, user_id="demo-user", name="Demo Buyer",
                            role="user", account="demo@matchforge.ai"))
        if not s.get(KbSession, KB_ADMIN_TOKEN):
            s.add(KbSession(token=KB_ADMIN_TOKEN, user_id="kb-admin", name="KB Admin",
                            role="admin", account="admin@matchforge.ai"))


_ensure_seed_sessions()


def resolve_token(token: str | None) -> dict | None:
    """解析 Bearer token -> {user_id, name, role, account}。未知 token 自动注册为 demo user。"""
    if not token:
        return None
    token = token.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    with session_scope() as s:
        sess = s.get(KbSession, token)
        if sess:
            return {"user_id": sess.user_id, "name": sess.name,
                    "role": sess.role, "account": sess.account, "token": token}
        # 未知 token: 自动注册为普通用户 (兼容前端 mock token)
        user_id = f"u-{token[:8]}"
        sess = KbSession(token=token, user_id=user_id, name="Frontend User",
                         role="user", account=None)
        s.add(sess)
        return {"user_id": user_id, "name": "Frontend User",
                "role": "user", "account": None, "token": token}


def issue_token(name: str, role: str, account: str | None = None) -> str:
    """签发新 token (登录/注册用)。"""
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


def login(name: str, account: str, role: str = "user") -> str:
    return issue_token(name, role, account)
