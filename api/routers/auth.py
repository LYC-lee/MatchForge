"""认证 API: 登录 / 注册 / 当前用户 / demo 登录。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from kb.auth import login, register, issue_token, demo_tokens_enabled
from kb.companies import get_company
from kb.db import session_scope
from api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    account: str
    password: str


class RegisterRequest(BaseModel):
    name: str
    account: str
    password: str
    company: str
    role: str = "buyer"


class DemoLoginRequest(BaseModel):
    company_id: int


@router.post("/login")
def kb_login(req: LoginRequest):
    """登录：校验密码，返回 token。"""
    token = login(req.account, req.password)
    if not token:
        raise HTTPException(status_code=401, detail="账号或密码不正确")
    return {"token": token, "name": "user", "role": "user", "account": req.account}


@router.post("/register")
def kb_register(req: RegisterRequest):
    """注册：创建用户并返回 token。"""
    token = register(req.name, req.account, req.password, req.company, req.role)
    if not token:
        raise HTTPException(status_code=400, detail="该账号已注册")
    return {"token": token, "name": req.name, "role": req.role, "account": req.account}


@router.post("/demo-login")
def demo_login(req: DemoLoginRequest):
    """演示登录: 签发 demo 用户会话 token (绑定指定公司)。

    仅在 demo 模式 (KB_DEMO_MODE=true) 且非生产环境时可用; 否则 404。
    不需要密码, 不创建管理员; 仅签发 role=user 的临时会话。
    """
    if not demo_tokens_enabled():
        raise HTTPException(status_code=404, detail="Demo login is not enabled")
    with session_scope() as s:
        company = get_company(s, req.company_id)
        if not company:
            raise HTTPException(status_code=404, detail=f"公司 {req.company_id} 不存在")
        company_name = company.name
    token = issue_token(name="Demo Buyer", role="user", account="demo@matchforge.ai")
    return {
        "token": token,
        "name": "Demo Buyer",
        "role": "user",
        "account": "demo@matchforge.ai",
        "company_id": req.company_id,
        "company_name": company_name,
        "is_demo": True,
    }


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user
