"""
测试 Agent ③ — 替代料推荐 (核心)
"""

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