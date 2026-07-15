"""
测试 Agent ③ — 替代料推荐 (核心)
"""

import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from ai.agents.alternatives import (
    alternatives_agent,
    _compare_params,
    _classify_level,
    _safety_filter,
)
from datetime import datetime


@pytest.mark.asyncio
async def test_alternatives_agent_empty_spec(sample_state):
    """没有 normalized_spec：返回空列表"""
    sample_state["normalized_spec"] = None
    result = await alternatives_agent(sample_state)
    assert result["alternatives"] == []


@pytest.mark.asyncio
async def test_compare_params_match():
    """参数完全一致：全部 match"""
    orig = {"package": "0805", "capacitance": "10uF",
            "rated_voltage": "50V", "temp_coeff": "X7R",
            "tolerance": "±10%", "temp_range": "-55~125℃"}
    alt = {"package": "0805", "capacitance": "10uF",
           "rated_voltage": "50V", "temp_coeff": "X7R",
           "tolerance": "±10%", "temp_range": "-55~125℃"}
    diffs = _compare_params(orig, alt)
    non_match = [d for d in diffs if d["status"] != "match"]
    assert len(non_match) == 0, f"Expected all match, got: {non_match}"


def test_compare_params_risk():
    """额定电压降低：标记 risk"""
    orig = {"package": "0805", "capacitance": "10uF",
            "rated_voltage": "50V", "temp_coeff": "X7R", "tolerance": "±10%"}
    alt = {"package": "0805", "capacitance": "10uF",
           "rated_voltage": "25V", "temp_coeff": "X7R", "tolerance": "±5%"}
    diffs = _compare_params(orig, alt)
    voltage_diff = [d for d in diffs if d["field"] == "额定电压"]
    assert len(voltage_diff) > 0
    assert voltage_diff[0]["status"] == "risk"


def test_classify_level_l1():
    """无风险无差异 = L1"""
    diffs = []
    assert _classify_level(diffs, 0.95, True) == "L1"


def test_classify_level_l3():
    """有风险项 = L3"""
    diffs = [{"field": "容差", "original": "±5%", "alternative": "±10%", "status": "diff", "note": ""},
             {"field": "额定电压", "original": "50V", "alternative": "25V", "status": "risk", "note": ""}]
    assert _classify_level(diffs, 0.8, False) == "L3"


def test_classify_level_l4():
    """封装不兼容 = L4"""
    diffs = [{"field": "封装", "original": "0805", "alternative": "0603", "status": "risk", "note": ""}]
    assert _classify_level(diffs, 0.7, False) == "L4"


def test_classify_level_l5():
    """置信度低 + 无核验 = L5"""
    diffs = [{"field": "容差", "original": "±5%", "alternative": "±10%", "status": "diff", "note": ""}]
    assert _classify_level(diffs, 0.4, False) == "L5"


def test_safety_filter_low_confidence():
    """置信度 < 0.5 且无核验 → 过滤"""
    alts = [{"confidence": 0.3, "verified": False, "diffs": [], "lifecycle": "量产"}]
    result = _safety_filter(alts)
    assert len(result) == 0


def test_safety_filter_eol():
    """已停产 → 过滤"""
    alts = [{"confidence": 0.9, "verified": True, "diffs": [], "lifecycle": "停产"}]
    result = _safety_filter(alts)
    assert len(result) == 0


def test_safety_filter_voltage_risk():
    """电压降压风险 + 无核验 → 过滤"""
    alts = [{
        "confidence": 0.8, "verified": False, "lifecycle": "量产",
        "diffs": [{"field": "额定电压", "status": "risk"}],
    }]
    result = _safety_filter(alts)
    assert len(result) == 0


def test_safety_filter_pass():
    """合格的替代 → 通过"""
    alts = [{
        "confidence": 0.95, "verified": True, "lifecycle": "量产",
        "diffs": [],
    }]
    result = _safety_filter(alts)
    assert len(result) == 1


# ============================================================
# 异步 Agent 工作流测试
# ============================================================

@pytest.mark.asyncio
async def test_alternatives_agent_neograph_hit(sample_state, sample_normalized_spec):
    """Neo4j 图查询命中 → 返回 Neo4j 来源的替代料"""
    sample_state["normalized_spec"] = sample_normalized_spec
    neo4j_mock_data = [
        {"part": "GRM188R61A106KE69D", "brand": "Murata", "confidence": 0.95, "verified": True,
         "source": "direct", "specs": {"package": "0805", "capacitance": "10uF", "rated_voltage": "25V"}},
    ]

    with patch("ai.agents.alternatives.query_all_alternatives", return_value=neo4j_mock_data):
        result = await alternatives_agent(sample_state)

    alts = result["alternatives"]
    assert len(alts) >= 1
    neo4j_alts = [a for a in alts if "Neo4j" in a.get("source", "")]
    assert len(neo4j_alts) >= 1
    assert neo4j_alts[0]["verified"] is True


@pytest.mark.asyncio
async def test_alternatives_agent_llm_fallback(sample_state, sample_normalized_spec):
    """Neo4j 无结果 → LLM 推理兜底"""
    sample_state["normalized_spec"] = sample_normalized_spec

    mock_response = MagicMock()
    mock_response.content = (
        '[{"part": "GRM188R61A106KE69D", "brand": "Murata", '
        '"package": "0805", "capacitance": "10uF", "rated_voltage": "25V", '
        '"temp_coeff": "X7R", "confidence": 0.7}]'
    )
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with (
        patch("ai.agents.alternatives.query_all_alternatives", return_value=[]),
        patch("ai.base_agent.get_agent_llm", return_value=mock_llm),
    ):
        result = await alternatives_agent(sample_state)

    alts = result["alternatives"]
    assert len(alts) >= 1
    llm_alts = [a for a in alts if "llm_inferred" in a.get("source", "")]
    assert len(llm_alts) >= 1
    assert llm_alts[0]["verified"] is False


@pytest.mark.asyncio
async def test_alternatives_agent_safety_filter(sample_state, sample_normalized_spec):
    """安全红线过滤：低置信度 + 无核验 → 被过滤"""
    sample_state["normalized_spec"] = sample_normalized_spec

    mock_response = MagicMock()
    mock_response.content = (
        '[{"part": "UNSAFE_ALT", "brand": "NoName", '
        '"package": "0603", "capacitance": "1uF", "rated_voltage": "10V", '
        '"confidence": 0.3}]'
    )
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with (
        patch("ai.agents.alternatives.query_all_alternatives", return_value=[]),
        patch("ai.base_agent.get_agent_llm", return_value=mock_llm),
    ):
        result = await alternatives_agent(sample_state)

    # 置信度 < 0.5 且无核验 → 被安全红线过滤
    alts = result["alternatives"]
    unsafe = [a for a in alts if a.get("part") == "UNSAFE_ALT"]
    assert len(unsafe) == 0


@pytest.mark.asyncio
async def test_alternatives_agent_sorted_by_level(sample_state, sample_normalized_spec):
    """结果按 L1→L5 排序，同级按置信度降序"""
    sample_state["normalized_spec"] = sample_normalized_spec

    mock_response = MagicMock()
    mock_response.content = json.dumps([
        {"part": "ALT_A", "brand": "A", "package": "0805", "capacitance": "10uF",
         "rated_voltage": "50V", "temp_coeff": "X7R", "confidence": 0.9},
        {"part": "ALT_B", "brand": "B", "package": "0805", "capacitance": "10uF",
         "rated_voltage": "50V", "temp_coeff": "X7R", "confidence": 0.8},
    ])

    with (
        patch("ai.agents.alternatives.query_all_alternatives", return_value=[]),
        patch("ai.base_agent.get_agent_llm") as mock_get_llm,
    ):
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_get_llm.return_value = mock_llm

        result = await alternatives_agent(sample_state)

    alts = result["alternatives"]
    assert len(alts) >= 1
    # ALT_A 的参数与原始规格有差异 → 应分类为 L2/L3
    level_order = {"L1": 0, "L2": 1, "L3": 2, "L4": 3, "L5": 4}
    levels = [level_order.get(a.get("level", "L5"), 5) for a in alts]
    # level 序号应单调递增（排序正确）
    assert levels == sorted(levels), f"排序异常: {[a.get('level') for a in alts]}"


@pytest.mark.asyncio
async def test_alternatives_agent_neocom_error_fallback(sample_state, sample_normalized_spec):
    """Neo4j 查询抛异常 → 不中断流程"""
    sample_state["normalized_spec"] = sample_normalized_spec

    with patch("ai.agents.alternatives.query_all_alternatives",
               side_effect=Exception("Neo4j connection refused")):
        result = await alternatives_agent(sample_state)

    # 不崩溃，errors 里有记录
    assert result["alternatives"] is not None
    has_neo4j_error = any("Neo4j" in e for e in result.get("errors", []))
    assert has_neo4j_error