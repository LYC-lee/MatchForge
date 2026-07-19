"""
单步 Agent 接口（独立调用各智能体）
POST /api/v1/parse, /alternatives, /match, /rfq/generate
"""

import logging
from fastapi import APIRouter
from api.schemas import ParseRequest, AlternativesRequest, MatchRequest, RfqGenerateRequest, ApiResponse
from api.config import MOCK_MODE

logger = logging.getLogger(__name__)
router = APIRouter(tags=["智能体"])


# ── Mock 数据 ────────────────────────────────────────────────

MOCK_PARSE = {
    "parsed_spec": {
        "part_number": "TMK212BJ105KG-T",
        "brand": "TAIYO YUDEN(太阳诱电)",
        "package": "0805",
        "capacitance": "1µF",
        "temp_coeff": "X5R",
        "rated_voltage": "25V",
    },
    "missing_fields": ["tolerance"],
}

MOCK_ALTERNATIVES = {
    "alternatives": [
        {"part_name": "CL21B105KAFNNNE", "brand": "Samsung EM", "level": "L2", "confidence": 0.92},
        {"part_name": "CC0805KKX5R6BB105", "brand": "YAGEO(国巨)", "level": "L2", "confidence": 0.90},
        {"part_name": "0805X105K250CT", "brand": "Walsin(华新科)", "level": "L3", "confidence": 0.78},
    ]
}


@router.post("/api/v1/parse")
async def parse_endpoint(req: ParseRequest):
    """需求解析 (F1)"""
    if MOCK_MODE:
        return ApiResponse(data=MOCK_PARSE)

    from ai.agents.parse import parse_agent
    from ai.graph import init_state
    state = init_state(req.query)
    result = await parse_agent(state)
    return ApiResponse(data={"parsed_spec": result.get("parsed_spec"), "errors": result.get("errors", [])})


@router.post("/api/v1/alternatives")
async def alternatives_endpoint(req: AlternativesRequest):
    """替代料推荐 (F3)"""
    if MOCK_MODE:
        return ApiResponse(data=MOCK_ALTERNATIVES)

    from ai.agents.alternatives import alternatives_agent
    from ai.graph import init_state
    state = init_state("")
    state["normalized_spec"] = req.spec
    result = await alternatives_agent(state)
    return ApiResponse(data={"alternatives": result.get("alternatives", [])})


@router.post("/api/v1/match")
async def match_endpoint(req: MatchRequest):
    """供应商匹配 (F4)"""
    if MOCK_MODE:
        return ApiResponse(data={"matched_suppliers": [
            {"id": "s1", "name": "深圳华强电子·恒达元器件", "score": 0.86, "region": "华南·深圳"},
            {"id": "s2", "name": "上海赛格集成电路", "score": 0.82, "region": "华东·上海"},
        ]})

    from ai.agents.match import match_agent
    from ai.graph import init_state
    state = init_state("")
    state["normalized_spec"] = req.spec
    state["alternatives"] = req.alternatives
    result = await match_agent(state)
    return ApiResponse(data={"matched_suppliers": result.get("matched_suppliers", [])})


@router.post("/api/v1/rfq/generate")
async def rfq_generate_endpoint(req: RfqGenerateRequest):
    """生成询价单 (F5)"""
    if MOCK_MODE:
        return ApiResponse(data={"rfq_doc": "【询价单 RFQ】\n品名: MLCC 0805 1µF X5R 25V\n..."})

    from ai.agents.gen_rfq import gen_rfq_agent
    from ai.graph import init_state
    state = init_state("")
    state["parsed_spec"] = state["normalized_spec"] = req.spec
    state["alternatives"] = req.alternatives
    state["matched_suppliers"] = req.suppliers
    result = await gen_rfq_agent(state)
    return ApiResponse(data={"rfq_doc": result.get("rfq_doc", "")})
