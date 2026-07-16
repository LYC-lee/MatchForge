"""认证 API: 登录 / 注册 / 当前用户。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from kb.auth import login, register
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


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user
