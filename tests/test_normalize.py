"""
测试 Agent ② — 标准化 (LLM 自主调用版)
"""

import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from ai.agents.normalize import normalize_agent


def _mock_run_tool_agent(return_content: dict):
    """构造 run_tool_agent 的 mock 返回值。"""
    mock_msg = MagicMock()
    mock_msg.content = json.dumps(return_content, ensure_ascii=False)
    return AsyncMock(return_value={"messages": [mock_msg], "next_agent": None})


@pytest.mark.asyncio
async def test_normalize_agent_success(sample_state, sample_parsed_spec):
    """正常标准化：LLM 返回标准编码"""
    sample_state["parsed_spec"] = sample_parsed_spec

    normalized = {
        **sample_parsed_spec,
        "std_code": "MLCC-0805-X5R-10V-105",
        "standard": "EIA",
        "_mapped": True,
    }

    with patch("ai.agents.normalize.agent_engine.run_tool_agent",
               _mock_run_tool_agent(normalized)):
        result = await normalize_agent(sample_state)

    assert result["normalized_spec"] is not None
    assert result["normalized_spec"]["std_code"] == "MLCC-0805-X5R-10V-105"
    assert result["normalized_spec"]["_mapped"] is True


@pytest.mark.asyncio
async def test_normalize_agent_no_spec(sample_state):
    """没有 parsed_spec：跳过"""
    sample_state["parsed_spec"] = None
    result = await normalize_agent(sample_state)
    assert result["normalized_spec"] is None


@pytest.mark.asyncio
async def test_normalize_agent_dict_not_found(sample_state, sample_parsed_spec):
    """字典未命中：LLM 返回 std_code=null"""
    sample_state["parsed_spec"] = sample_parsed_spec

    normalized = {
        **sample_parsed_spec,
        "std_code": None,
        "_mapped": False,
    }

    with patch("ai.agents.normalize.agent_engine.run_tool_agent",
               _mock_run_tool_agent(normalized)):
        result = await normalize_agent(sample_state)

    assert result["normalized_spec"] is not None
    assert result["normalized_spec"]["std_code"] is None
    assert result["normalized_spec"]["_mapped"] is False


@pytest.mark.asyncio
async def test_normalize_agent_field_aliases(sample_state):
    """LLM 自动处理中文字段映射"""
    sample_state["parsed_spec"] = {"封装": "0805", "容值": "10uF", "品牌": "YAGEO"}

    normalized = {
        "package": "0805",
        "capacitance": "10uF",
        "brand": "YAGEO",
        "std_code": None,
        "_mapped": False,
    }

    with patch("ai.agents.normalize.agent_engine.run_tool_agent",
               _mock_run_tool_agent(normalized)):
        result = await normalize_agent(sample_state)

    assert result["normalized_spec"]["package"] == "0805"
    assert result["normalized_spec"]["capacitance"] == "10uF"
    assert result["normalized_spec"]["brand"] == "YAGEO"


@pytest.mark.asyncio
async def test_normalize_agent_parse_failure(sample_state, sample_parsed_spec):
    """LLM 返回非 JSON 内容 → 回退到保留原始规格"""
    sample_state["parsed_spec"] = sample_parsed_spec

    mock_msg = MagicMock()
    mock_msg.content = "这是一段无法解析的文本回复"
    mock_run = AsyncMock(return_value={"messages": [mock_msg], "next_agent": None})

    with patch("ai.agents.normalize.agent_engine.run_tool_agent", mock_run):
        result = await normalize_agent(sample_state)

    assert result["normalized_spec"] is not None
    assert result["normalized_spec"]["std_code"] is None
    assert result["normalized_spec"]["_mapped"] is False
    # 原始字段保留
    assert result["normalized_spec"]["part_number"] == sample_parsed_spec["part_number"]