"""
Auth 认证接口
POST /api/v1/auth/register, /login, /refresh, /me
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.database import get_db
from api.auth import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from api.dependencies import get_current_user
from api.models import User
from api.schemas import LoginRequest, RegisterRequest, TokenResponse, UserInfo, ApiResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


@router.post("/register")
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """用户注册"""
    result = await db.execute(
        select(User).where((User.username == req.account) | (User.email == req.account))
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该账号已注册")

    user = User(
        username=req.account,
        email=req.account,
        password_hash=hash_password(req.password),
        name=req.name,
        company=req.company,
        role=req.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return TokenResponse(
        token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        user={"id": user.id, "name": user.name, "account": user.username, "company": user.company, "role": user.role},
    )


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """用户登录"""
    result = await db.execute(
        select(User).where((User.username == req.account) | (User.email == req.account))
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="账号或密码不正确")

    return TokenResponse(
        token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        user={"id": user.id, "name": user.name, "account": user.username, "company": user.company, "role": user.role},
    )


@router.post("/refresh")
async def refresh(
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(None),
):
    """刷新 Access Token（Header 传入 Bearer Refresh Token）"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少 Refresh Token")

    refresh_token = authorization[7:]
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Refresh Token 无效")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")

    return TokenResponse(
        token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        user={"id": user.id, "name": user.name, "account": user.username, "company": user.company, "role": user.role},
    )


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    """当前用户信息"""
    return UserInfo(
        id=user.id,
        name=user.name,
        account=user.username,
        company=user.company,
        role=user.role,
    )
