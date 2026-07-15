"""
测试 Agent ② — 标准化
"""

import pytest
from unittest.mock import patch
from ai.agents.normalize import normalize_agent


@pytest.mark.asyncio
async def test_normalize_agent_success(sample_state, sample_parsed_spec):
    """正常标准化：查字典成功"""
    sample_state["parsed_spec"] = sample_parsed_spec

    with patch("ai.agents.normalize.lookup_std_code_raw",
               return_value={"std_code": "MLCC-0805-X5R-10V-105", "standard": "EIA"}):
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
    """字典未命中：保留原值，标 unmapped"""
    sample_state["parsed_spec"] = sample_parsed_spec

    with patch("ai.agents.normalize.lookup_std_code_raw", return_value=None):
        result = await normalize_agent(sample_state)

    assert result["normalized_spec"] is not None
    assert result["normalized_spec"]["std_code"] is None
    assert result["normalized_spec"]["_mapped"] is False


@pytest.mark.asyncio
async def test_normalize_agent_field_aliases(sample_state):
    """中文字段名自动映射为英文"""
    sample_state["parsed_spec"] = {"封装": "0805", "容值": "10uF", "品牌": "YAGEO"}

    with patch("ai.agents.normalize.lookup_std_code_raw", return_value=None):
        result = await normalize_agent(sample_state)

    assert result["normalized_spec"]["package"] == "0805"
    assert result["normalized_spec"]["capacitance"] == "10uF"
    assert result["normalized_spec"]["brand"] == "YAGEO"