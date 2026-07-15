"""认证 API: 登录 / 当前用户 (兼容前端 mock token)。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from kb.auth import login
from api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    name: str
    account: str
    role: str = "user"


@router.post("/login")
def kb_login(req: LoginRequest):
    """签发服务端 token (知识库 API 用)。"""
    token = login(req.name, req.account, req.role)
    return {"token": token, "name": req.name, "role": req.role, "account": req.account}


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user
