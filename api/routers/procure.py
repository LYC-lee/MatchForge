"""
寻源 Agent API — SSE 流式多 Agent 编排 + 会话历史

POST /api/v1/procure/stream     — SSE 流式寻源 (parse → normalize → alternatives → match → gen_rfq → grade)
POST /api/v1/procure/spec        — 仅解析 + 标准化 (非流式，返回结构化 JSON)
POST /api/v1/procure/match       — 仅替代料 + 供应商匹配 (非流式，返回结构化 JSON)
GET  /api/v1/procure/sessions    — 获取用户会话历史列表
GET  /api/v1/procure/sessions/{thread_id} — 获取单个会话详情
DELETE /api/v1/procure/sessions/{thread_id} — 删除会话
"""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ai.graph import init_state, run_procure_stream, get_graph
from ai.supervisor import ROUTING_ORDER

# pg_store 为可选依赖（需要 psycopg2）
try:
    from ai.pg_store import list_sessions, get_session, delete_session
    _pg_available = True
except ImportError:
    _pg_available = False
    list_sessions = None  # type: ignore
    get_session = None  # type: ignore
    delete_session = None  # type: ignore

logger = logging.getLogger("api.procure")

router = APIRouter(prefix="/procure", tags=["procure"])


# ── 请求模型 ──────────────────────────────────────────────────────────────

class ProcureRequest(BaseModel):
    raw_query: str = Field(..., min_length=1, description="用户自然语言需求，如 'TMK212BJ105KG-T 缺货找替代'")
    phase: str = Field(default="spec", description="spec=解析+标准化+替代 | match=替代+匹配+询价+分级")
    thread_id: str | None = Field(default=None, description="会话 ID，None 则自动生成")
    confirmed_spec: dict | None = Field(default=None, description="已确认的规格（phase=match 时使用）")
    user_id: str = Field(default="anonymous", description="用户标识（登录用户为账号，匿名用户为设备 ID）")


class SpecOnlyRequest(BaseModel):
    raw_query: str = Field(..., min_length=1, description="用户自然语言需求")
    thread_id: str | None = None


class MatchOnlyRequest(BaseModel):
    normalized_spec: dict = Field(..., description="已确认的标准化规格")
    thread_id: str | None = None


# ── SSE 辅助 ───────────────────────────────────────────────────────────────

def _sse(event_type: str, data: dict) -> str:
    return f"data: {json.dumps({'type': event_type, **data}, ensure_ascii=False)}\n\n"


# ── 流式寻源 ───────────────────────────────────────────────────────────────

@router.post("/stream")
async def procure_stream(
    req: ProcureRequest,
):
    """
    SSE 流式多 Agent 寻源。

    事件类型:
      - start:     初始化完成
      - progress:  Agent 执行进度 (agent + status + result)
      - result:    最终结果 (完整 state)
      - error:     错误信息
      - end:       流结束
    """
    user_id = req.user_id or "anonymous"

    async def event_generator():
        thread_id = req.thread_id or uuid.uuid4().hex[:12]

        try:
            yield _sse("start", {"thread_id": thread_id, "phase": req.phase})

            async for event in run_procure_stream(
                raw_query=req.raw_query,
                thread_id=thread_id,
                confirmed_spec=req.confirmed_spec,
                phase=req.phase,
                user_id=user_id,
            ):
                yield event

            yield _sse("end", {"thread_id": thread_id})

        except Exception as e:
            logger.exception("Procure stream error")
            yield _sse("error", {"message": str(e)[:500], "thread_id": thread_id})
            yield _sse("end", {"thread_id": thread_id})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── 仅解析 + 标准化 (非流式，直接调用 Agent) ───────────────────────────────

@router.post("/spec")
async def procure_spec(
    req: SpecOnlyRequest,
):
    """
    仅执行 parse → normalize，直接调用 Agent（不走 Supervisor 全图）。

    适用场景: 前端先解析规格，展示给用户确认后再进入 match 阶段。
    """
    from ai.agents.parse import parse_agent
    from ai.agents.normalize import normalize_agent

    thread_id = req.thread_id or uuid.uuid4().hex[:12]
    state = init_state(req.raw_query, "anonymous", thread_id)

    try:
        # 直接调用 parse + normalize，不经过 Supervisor
        state = await parse_agent(state)
        state = await normalize_agent(state)

        return {
            "thread_id": thread_id,
            "parsed_spec": state.get("parsed_spec"),
            "normalized_spec": state.get("normalized_spec"),
            "errors": state.get("errors", []),
        }

    except Exception as e:
        logger.exception("Procure spec error")
        raise HTTPException(status_code=500, detail=str(e)[:500])


# ── 仅替代料 + 供应商匹配 (非流式，直接调用 Agent) ──────────────────────────

@router.post("/match")
async def procure_match(
    req: MatchOnlyRequest,
):
    """
    仅执行 alternatives → match，直接调用 Agent（不走 Supervisor 全图）。

    适用场景: 前端已确认规格后，直接进入匹配阶段。
    """
    from ai.agents.alternatives import alternatives_agent
    from ai.agents.match import match_agent

    thread_id = req.thread_id or uuid.uuid4().hex[:12]
    state = init_state("", "anonymous", thread_id)
    state["normalized_spec"] = req.normalized_spec

    try:
        state = await alternatives_agent(state)
        state = await match_agent(state)

        return {
            "thread_id": thread_id,
            "alternatives": state.get("alternatives", []),
            "matched_suppliers": state.get("matched_suppliers", []),
            "errors": state.get("errors", []),
        }

    except Exception as e:
        logger.exception("Procure match error")
        raise HTTPException(status_code=500, detail=str(e)[:500])


# ── 健康检查 ───────────────────────────────────────────────────────────────

@router.get("/health")
async def procure_health():
    """检查 Agent 模块是否可用。"""
    return {
        "status": "ok",
        "agents": ROUTING_ORDER,
        "llm_configured": bool(
            __import__("ai.config").DASHSCOPE_API_KEY
        ),
    }


# ── 会话历史 CRUD ──────────────────────────────────────────────────────────

@router.get("/sessions")
async def list_user_sessions(
    user_id: str = Query(..., description="用户标识"),
    limit: int = Query(50, ge=1, le=200),
):
    """获取用户的会话历史列表（按时间倒序）。"""
    if not _pg_available:
        return {"sessions": [], "total": 0, "notice": "PostgreSQL 未连接，会话历史不可用"}
    sessions = list_sessions(user_id, limit)
    return {"sessions": sessions, "total": len(sessions)}


@router.get("/sessions/{thread_id}")
async def get_session_detail(thread_id: str):
    """获取单个会话的完整详情（含状态快照）。"""
    if not _pg_available:
        raise HTTPException(status_code=503, detail="PostgreSQL 未连接，会话历史不可用")
    session = get_session(thread_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


@router.delete("/sessions/{thread_id}")
async def delete_user_session(thread_id: str):
    """删除指定会话。"""
    if not _pg_available:
        raise HTTPException(status_code=503, detail="PostgreSQL 未连接")
    ok = delete_session(thread_id)
    if not ok:
        raise HTTPException(status_code=500, detail="删除失败")
    return {"ok": True}