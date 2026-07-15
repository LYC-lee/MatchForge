"""
测试 Agent ③ — 替代料推荐 (LLM 自主调用版)
"""

import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from ai.agents.alternatives import alternatives_agent


def _mock_run_tool_agent(return_content: dict | list):
    """构造 run_tool_agent 的 mock 返回值。"""
    mock_msg = MagicMock()
    mock_msg.content = json.dumps(return_content, ensure_ascii=False)
    return AsyncMock(return_value={"messages": [mock_msg], "next_agent": None})


@pytest.mark.asyncio
async def test_alternatives_agent_empty_spec(sample_state):
    """没有 normalized_spec：返回空列表"""
    sample_state["normalized_spec"] = None
    result = await alternatives_agent(sample_state)
    assert result["alternatives"] == []


@pytest.mark.asyncio
async def test_alternatives_agent_neograph_hit(sample_state, sample_normalized_spec):
    """LLM 返回 Neo4j 来源的替代料"""
    sample_state["normalized_spec"] = sample_normalized_spec

    llm_output = {
        "alternatives": [{
            "part": "GRM188R61A106KE69D",
            "brand": "Murata",
            "package": "0603",
            "capacitance": "10uF",
            "rated_voltage": "25V",
            "temp_coeff": "X5R",
            "confidence": 0.95,
            "level": "L2",
            "source": "Neo4j:direct",
            "verified": True,
            "specs": {},
            "diff_items": [
                {"param": "封装", "original": "0805", "alternative": "0603", "type": "risk"},
                {"param": "额定电压", "original": "10V", "alternative": "25V", "type": "diff"},
            ],
        }]
    }

    with patch("ai.agents.alternatives.agent_engine.run_tool_agent",
               _mock_run_tool_agent(llm_output)):
        result = await alternatives_agent(sample_state)

    alts = result["alternatives"]
    assert len(alts) >= 1
    neo4j_alts = [a for a in alts if "Neo4j" in a.get("source", "")]
    assert len(neo4j_alts) >= 1
    assert neo4j_alts[0]["verified"] is True


@pytest.mark.asyncio
async def test_alternatives_agent_llm_fallback(sample_state, sample_normalized_spec):
    """LLM 推理兜底（无图查询结果）"""
    sample_state["normalized_spec"] = sample_normalized_spec

    llm_output = {
        "alternatives": [{
            "part": "GRM188R61A106KE69D",
            "brand": "Murata",
            "package": "0603",
            "capacitance": "10uF",
            "rated_voltage": "25V",
            "temp_coeff": "X5R",
            "confidence": 0.7,
            "level": "L3",
            "source": "llm_inferred",
            "verified": False,
            "specs": {},
            "diff_items": [
                {"param": "封装", "original": "0805", "alternative": "0603", "type": "risk"},
            ],
        }]
    }

    with patch("ai.agents.alternatives.agent_engine.run_tool_agent",
               _mock_run_tool_agent(llm_output)):
        result = await alternatives_agent(sample_state)

    alts = result["alternatives"]
    assert len(alts) >= 1
    llm_alts = [a for a in alts if "llm_inferred" in a.get("source", "")]
    assert len(llm_alts) >= 1
    assert llm_alts[0]["verified"] is False


@pytest.mark.asyncio
async def test_alternatives_agent_safety_filter(sample_state, sample_normalized_spec):
    """低置信度 + 无核验 → LLM 不输出（安全过滤由 LLM prompt 约束）"""
    sample_state["normalized_spec"] = sample_normalized_spec

    # LLM 遵循安全红线，不返回不安全的替代
    llm_output = {"alternatives": []}

    with patch("ai.agents.alternatives.agent_engine.run_tool_agent",
               _mock_run_tool_agent(llm_output)):
        result = await alternatives_agent(sample_state)

    alts = result["alternatives"]
    assert len(alts) == 0


@pytest.mark.asyncio
async def test_alternatives_agent_sorted_by_level(sample_state, sample_normalized_spec):
    """LLM 返回按 L1→L5 排序的结果"""
    sample_state["normalized_spec"] = sample_normalized_spec

    llm_output = {
        "alternatives": [
            {
                "part": "ALT_A", "brand": "A", "package": "0805", "capacitance": "1uF",
                "rated_voltage": "10V", "temp_coeff": "X5R", "confidence": 0.95,
                "level": "L1", "source": "Neo4j:direct", "verified": True,
                "specs": {}, "diff_items": [],
            },
            {
                "part": "ALT_B", "brand": "B", "package": "0805", "capacitance": "1uF",
                "rated_voltage": "25V", "temp_coeff": "X5R", "confidence": 0.85,
                "level": "L2", "source": "Neo4j:transitive", "verified": True,
                "specs": {}, "diff_items": [
                    {"param": "额定电压", "original": "10V", "alternative": "25V", "type": "diff"},
                ],
            },
        ]
    }

    with patch("ai.agents.alternatives.agent_engine.run_tool_agent",
               _mock_run_tool_agent(llm_output)):
        result = await alternatives_agent(sample_state)

    alts = result["alternatives"]
    assert len(alts) >= 2
    # 排序：L1 在 L2 前面
    level_order = {"L1": 0, "L2": 1, "L3": 2, "L4": 3, "L5": 4}
    levels = [level_order.get(a.get("level", "L5"), 5) for a in alts]
    assert levels == sorted(levels), f"排序异常: {[a.get('level') for a in alts]}"


@pytest.mark.asyncio
async def test_alternatives_agent_neocom_error_fallback(sample_state, sample_normalized_spec):
    """run_tool_agent 抛异常 → 不中断流程"""
    sample_state["normalized_spec"] = sample_normalized_spec

    with patch("ai.agents.alternatives.agent_engine.run_tool_agent",
               side_effect=Exception("LLM timeout")):
        result = await alternatives_agent(sample_state)

    assert result["alternatives"] is not None
    has_error = any("alternatives" in e for e in result.get("errors", []))
    assert has_error


@pytest.mark.asyncio
async def test_alternatives_agent_parse_failure(sample_state, sample_normalized_spec):
    """LLM 返回非 JSON → 空列表，不崩溃"""
    sample_state["normalized_spec"] = sample_normalized_spec

    mock_msg = MagicMock()
    mock_msg.content = "无法解析的文本回复"
    mock_run = AsyncMock(return_value={"messages": [mock_msg], "next_agent": None})

    with patch("ai.agents.alternatives.agent_engine.run_tool_agent", mock_run):
        result = await alternatives_agent(sample_state)

    assert result["alternatives"] == []