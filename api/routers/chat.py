"""知识库聊天 API: 单公司 RAG + 多公司比较 + Trace。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from kb.rag import answer, get_trace
from api.deps import check_company_access, get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])


class SingleChatRequest(BaseModel):
    company_id: int
    query: str
    language: str | None = None


class CompareChatRequest(BaseModel):
    company_ids: list[int] = Field(..., min_length=2, max_length=6)
    query: str
    language: str | None = None


@router.post("/ask")
def chat_single(req: SingleChatRequest, user: dict = Depends(get_current_user)):
    """单公司私域问答 (严格 company_id 隔离)。"""
    check_company_access(user, req.company_id)
    res = answer(req.query, company_id=req.company_id, user_id=user["user_id"],
                 language=req.language)
    return res


@router.post("/compare")
def chat_compare(req: CompareChatRequest, user: dict = Depends(get_current_user)):
    """多公司产品比较 (分别检索, 禁止全库)。"""
    for cid in req.company_ids:
        check_company_access(user, cid)
    res = answer(req.query, company_ids=req.company_ids, user_id=user["user_id"],
                 language=req.language)
    return res


@router.get("/trace/{request_id}")
def get_rag_trace(request_id: str, user: dict = Depends(get_current_user)):
    """RAG 检索追溯 (开发调试 / 管理员)。"""
    t = get_trace(request_id)
    if not t:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="trace not found")
    return t
