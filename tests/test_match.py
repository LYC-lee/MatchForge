"""
测试 Agent ④ — 供应商匹配 (LLM 自主调用版)
"""

import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from ai.agents.match import match_agent


def _mock_run_tool_agent(return_content: dict):
    """构造 run_tool_agent 的 mock 返回值。"""
    mock_msg = MagicMock()
    mock_msg.content = json.dumps(return_content, ensure_ascii=False)
    return AsyncMock(return_value={"messages": [mock_msg], "next_agent": None})


@pytest.mark.asyncio
async def test_match_agent_empty_spec(sample_state):
    """没有 normalized_spec：返回空列表"""
    sample_state["normalized_spec"] = None
    result = await match_agent(sample_state)
    assert result["matched_suppliers"] == []


@pytest.mark.asyncio
async def test_match_agent_no_suppliers(sample_state, sample_normalized_spec):
    """LLM 返回空结果"""
    sample_state["normalized_spec"] = sample_normalized_spec

    with patch("ai.agents.match.agent_engine.run_tool_agent",
               _mock_run_tool_agent({"matched_suppliers": []})):
        result = await match_agent(sample_state)

    assert result["matched_suppliers"] == []


@pytest.mark.asyncio
async def test_match_agent_formatted_output(sample_state, sample_normalized_spec):
    """匹配成功：输出格式与前端 Supplier 对齐"""
    sample_state["normalized_spec"] = sample_normalized_spec

    llm_output = {
        "matched_suppliers": [{
            "id": "1",
            "name": "深圳芯联电子",
            "match_score": 0.75,
            "category": "MLCC",
            "region": "深圳",
            "location": "深圳",
            "categories": ["MLCC"],
            "brands": ["YAGEO", "Murata"],
            "qualifications": ["ISO9001"],
            "moq": 10000,
            "lead_time_weeks": 2,
            "in_stock": False,
            "response_speed": "48h 内首次响应",
            "data_source": "平台数据",
            "updated_at": "2026-07-10",
            "confirmed_stock": False,
            "confirmed_lead": False,
            "confirmed_price": False,
        }]
    }

    with patch("ai.agents.match.agent_engine.run_tool_agent",
               _mock_run_tool_agent(llm_output)):
        result = await match_agent(sample_state)

    suppliers = result["matched_suppliers"]
    assert len(suppliers) == 1
    assert suppliers[0]["name"] == "深圳芯联电子"
    assert suppliers[0]["confirmed_stock"] is False
    assert suppliers[0]["confirmed_lead"] is False
    assert suppliers[0]["confirmed_price"] is False
    assert isinstance(suppliers[0]["match_score"], (int, float))


@pytest.mark.asyncio
async def test_match_agent_parse_failure(sample_state, sample_normalized_spec):
    """LLM 返回非 JSON → 空列表，不崩溃"""
    sample_state["normalized_spec"] = sample_normalized_spec

    mock_msg = MagicMock()
    mock_msg.content = "无法解析的文本"
    mock_run = AsyncMock(return_value={"messages": [mock_msg], "next_agent": None})

    with patch("ai.agents.match.agent_engine.run_tool_agent", mock_run):
        result = await match_agent(sample_state)

    assert result["matched_suppliers"] == []