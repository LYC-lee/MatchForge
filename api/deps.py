"""
FastAPI 依赖: 鉴权 + 公司访问校验。
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from kb.auth import can_access_company, resolve_token


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    user = resolve_token(authorization)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供有效认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return user


def check_company_access(user: dict, company_id: int) -> None:
    """服务端公司访问校验 -- 不只信前端 company_id。

    1. 校验公司存在且知识可用 (404 否则)
    2. 校验用户访问权限 (403 若在白名单模式且无权)
    """
    from kb.companies import get_company
    from kb.db import session_scope

    with session_scope() as s:
        c = get_company(s, company_id)
        if not c:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"公司 {company_id} 不存在",
            )
    if not can_access_company(user["user_id"], company_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"用户无权访问公司 {company_id} 的私域知识",
        )
