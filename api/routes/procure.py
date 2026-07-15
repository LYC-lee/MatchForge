"""
POST /api/v1/procure — SSE 流式寻源 ★核心端点

对接 ai.graph.run_procure_stream()，逐事件推送给前端
"""

import json
import logging
import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from api.schemas import ProcureRequest
from api.dependencies import get_optional_user
from api.models import User
from api.config import MOCK_MODE

logger = logging.getLogger(__name__)
router = APIRouter(tags=["寻源"])

SSE = lambda d: f"data: {json.dumps(d, ensure_ascii=False)}\n\n"


async def _mock_procure_stream(query: str, phase: str, thread_id: str | None = None):
    """无 API Key 时的 mock 流式响应"""
    tid = thread_id or f"mock-{datetime.now().timestamp():.0f}"
    yield SSE({"type": "start", "thread_id": tid})
    await asyncio.sleep(0.1)

    if phase == "spec":
        yield SSE({"type": "progress", "agent": "parse", "status": "running"})
        await asyncio.sleep(0.5)
        yield SSE({
            "type": "progress", "agent": "parse", "status": "done",
            "result": {
                "part_number": "TMK212BJ105KG-T", "brand": "TAIYO YUDEN",
                "package": "0805", "capacitance": "1µF", "temp_coeff": "X5R",
                "rated_voltage": "25V",
            },
        })
        await asyncio.sleep(0.3)

        yield SSE({"type": "progress", "agent": "normalize", "status": "running"})
        await asyncio.sleep(0.5)
        yield SSE({
            "type": "progress", "agent": "normalize", "status": "done",
            "result": {
                "part_number": "TMK212BJ105KG-T", "brand": "TAIYO YUDEN",
                "package": "0805 (2012 Metric)", "capacitance": "1µF (1000nF)",
                "temp_coeff": "X5R (-55~85℃)", "rated_voltage": "25V DC",
            },
        })
    else:
        yield SSE({"type": "progress", "agent": "alternatives", "status": "running"})
        await asyncio.sleep(0.6)
        yield SSE({
            "type": "progress", "agent": "alternatives", "status": "done",
            "result": [
                {"part_name": "CL21B105KAFNNNE", "brand": "Samsung EM", "level": "L2", "confidence": 0.92},
                {"part_name": "CC0805KKX5R6BB105", "brand": "YAGEO", "level": "L2", "confidence": 0.90},
            ],
        })
        await asyncio.sleep(0.3)

        yield SSE({"type": "progress", "agent": "match", "status": "running"})
        await asyncio.sleep(0.5)
        yield SSE({
            "type": "progress", "agent": "match", "status": "done",
            "result": [
                {"id": "s1", "name": "深圳华强电子", "score": 0.86},
                {"id": "s2", "name": "上海赛格", "score": 0.82},
            ],
        })
        await asyncio.sleep(0.2)

        yield SSE({"type": "progress", "agent": "gen_rfq", "status": "running"})
        await asyncio.sleep(0.4)
        yield SSE({"type": "token", "text": "【询价单 RFQ】\n"})
        await asyncio.sleep(0.1)
        yield SSE({"type": "token", "text": "品名: MLCC 0805 10uF X5R 25V\n"})
        await asyncio.sleep(0.3)
        yield SSE({"type": "progress", "agent": "gen_rfq", "status": "done"})
        await asyncio.sleep(0.2)

        yield SSE({"type": "progress", "agent": "grade", "status": "running"})
        await asyncio.sleep(0.4)
        yield SSE({
            "type": "progress", "agent": "grade", "status": "done",
            "result": {"grade": "B", "score": 72, "reasons": ["月用量中高", "替代方案清晰"]},
        })

    yield SSE({
        "type": "result",
        "state": {
            "thread_id": tid, "raw_query": query,
            "parsed_spec": {"part_number": "TMK212BJ105KG-T"} if phase == "spec" else None,
            "normalized_spec": {"part_number": "TMK212BJ105KG-T"} if phase == "spec" else None,
            "alternatives": [{"part_name": "CL21B105KAFNNNE"}] if phase == "match" else [],
            "matched_suppliers": [{"id": "s1"}] if phase == "match" else [],
            "rfq_doc": "【询价单 RFQ】..." if phase == "match" else None,
            "lead_grade": {"grade": "B", "score": 72} if phase == "match" else None,
            "errors": [],
        },
    })
    yield SSE({"type": "end"})


@router.post("/api/v1/procure")
async def procure_stream(
    req: ProcureRequest,
    request: Request,
    user: User | None = Depends(get_optional_user),
):
    """
    一站式寻源 SSE 流式接口

    分两阶段:
    - phase=spec: parse + normalize → 门控
    - phase=match: alternatives + match + gen_rfq + grade
    """
    async def event_generator():
        if MOCK_MODE:
            async for event in _mock_procure_stream(req.query, req.phase, req.thread_id):
                if await request.is_disconnected():
                    break
                yield event
            return

        from ai.graph import run_procure_stream as real_stream
        user_id = user.id if user else ""
        async for event in real_stream(
            raw_query=req.query,
            thread_id=req.thread_id,
            confirmed_spec=req.confirmed_spec,
            phase=req.phase,
            user_id=user_id,
        ):
            if await request.is_disconnected():
                break
            yield event

    return EventSourceResponse(event_generator())
