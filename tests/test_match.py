"""
测试 Agent ④ — 供应商匹配
"""

import pytest
from unittest.mock import patch, MagicMock
from ai.agents.match import match_agent
from datetime import datetime


@pytest.mark.asyncio
async def test_match_agent_empty_spec(sample_state):
    """没有 normalized_spec：返回空列表"""
    sample_state["normalized_spec"] = None
    result = await match_agent(sample_state)
    assert result["matched_suppliers"] == []


@pytest.mark.asyncio
async def test_match_agent_no_suppliers(sample_state, sample_normalized_spec):
    """数据库无匹配：返回空列表"""
    sample_state["normalized_spec"] = sample_normalized_spec

    with patch("ai.tools.mysql_client.filter_suppliers_raw", return_value=[]):
        result = await match_agent(sample_state)

    assert result["matched_suppliers"] == []


@pytest.mark.asyncio
async def test_match_agent_formatted_output(sample_state, sample_normalized_spec):
    """匹配成功：输出格式与前端 Supplier 对齐"""
    sample_state["normalized_spec"] = sample_normalized_spec

    mock_suppliers = [{
        "id": 1,
        "name": "深圳芯联电子",
        "category": "MLCC",
        "brands": ["YAGEO", "Murata"],
        "qualifications": ["ISO9001"],
        "location": "深圳",
        "moq": 10000,
        "lead_time_weeks": 2,
        "data_source": "平台数据",
        "updated_at": "2026-07-10",
        "response_speed": "",
    }]

    with patch("ai.agents.match.filter_suppliers_raw", return_value=mock_suppliers):
        result = await match_agent(sample_state)

    suppliers = result["matched_suppliers"]
    assert len(suppliers) == 1
    assert suppliers[0]["name"] == "深圳芯联电子"
    assert suppliers[0]["confirmed_stock"] is False
    assert suppliers[0]["confirmed_lead"] is False
    assert suppliers[0]["confirmed_price"] is False
    assert isinstance(suppliers[0]["match_score"], float)