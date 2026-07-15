"""
测试 Agent ① — 需求解析
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from ai.agents.parse import parse_agent


@pytest.mark.asyncio
async def test_parse_agent_success(sample_state):
    """正常解析：LLM 返回合法 JSON"""
    mock_response = MagicMock()
    mock_response.content = (
        '{"category": "MLCC", "package": "0805", "capacitance": "10uF", '
        '"temp_coeff": "X7R", "rated_voltage": "50V", "tolerance": "±10%", '
        '"monthly_qty": 500000}'
    )
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("ai.base_agent.get_agent_llm", return_value=mock_llm):
        result = await parse_agent(sample_state)

    assert result["parsed_spec"] is not None
    assert result["parsed_spec"]["category"] == "MLCC"
    assert result["parsed_spec"]["package"] == "0805"
    assert result["parsed_spec"]["monthly_qty"] == 500000
    assert len(result["errors"]) == 0


@pytest.mark.asyncio
async def test_parse_agent_empty_query(sample_state):
    """空输入：返回 None + error"""
    sample_state["raw_query"] = ""
    result = await parse_agent(sample_state)
    assert result["parsed_spec"] is None
    assert len(result["errors"]) > 0


@pytest.mark.asyncio
async def test_parse_agent_json_decode_error(sample_state):
    """LLM 返回非法 JSON：捕获异常"""
    mock_response = MagicMock()
    mock_response.content = "这不是 JSON"
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("ai.base_agent.get_agent_llm", return_value=mock_llm):
        result = await parse_agent(sample_state)

    assert result["parsed_spec"] is None
    assert len(result["errors"]) > 0


@pytest.mark.asyncio
async def test_parse_agent_validate_package(sample_state):
    """校验非法封装值：过滤掉"""
    mock_response = MagicMock()
    mock_response.content = '{"package": "INVALID", "capacitance": "10uF"}'
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("ai.base_agent.get_agent_llm", return_value=mock_llm):
        result = await parse_agent(sample_state)

    assert result["parsed_spec"] is not None
    assert "package" not in result["parsed_spec"]
    assert result["parsed_spec"]["capacitance"] == "10uF"


@pytest.mark.asyncio
async def test_parse_agent_missing_critical_fields(sample_state):
    """关键字段大量缺失：标记为低质量"""
    mock_response = MagicMock()
    mock_response.content = '{"category": "MLCC"}'
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("ai.base_agent.get_agent_llm", return_value=mock_llm):
        result = await parse_agent(sample_state)

    assert result["parsed_spec"] is not None
    assert result["parsed_spec"]["category"] == "MLCC"