"""
测试 Agent ③ - 替代料推荐 (LLM 自主调用版) + #16 输出校验层

校验层 (#16, P0) 测试重点:
  - 幻觉型号 (不在工具返回集合) 被拦截
  - LLM 自报 verified/source 被代码改写
  - 红线违规 (电压降级/封装不同/EOL) 被移除
  - diff_items type 由代码复核
"""

import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from ai.agents.alternatives import (
    alternatives_agent,
    _validate_alternatives,
    _ToolFactCollector,
    _check_safety,
    _parse_voltage,
)


def _mock_run_tool_agent_with_facts(llm_output: dict | list, tool_parts: dict[str, str] | None = None,
                                     rag_parts: set[str] | None = None):
    """构造 run_tool_agent 的 mock: 返回 LLM 输出的同时, 通过 sink 填充工具事实。

    tool_parts: {型号: neo4j_source标签}  模拟 Neo4j 工具返回
    rag_parts:  {型号}                    模拟 search_knowledge_base 返回文本中出现的型号
    """
    tool_parts = tool_parts or {}
    rag_parts = rag_parts or set()

    async def _side_effect(*args, **kwargs):
        sink = kwargs.get("tool_call_sink")
        if sink is not None:
            # 模拟 Neo4j 工具返回
            if tool_parts:
                sink("query_all_alternatives", {"part_number": "X"},
                     [{"part": p} for p in tool_parts])
            # 模拟 search_knowledge_base 返回文本
            if rag_parts:
                sink("search_knowledge_base", {"company_name": "C", "query": "q"},
                     " ".join(rag_parts))
        mock_msg = MagicMock()
        mock_msg.content = json.dumps(llm_output, ensure_ascii=False)
        return {"messages": [mock_msg], "next_agent": None}

    return AsyncMock(side_effect=_side_effect)


# ============================================================
# 基础流程测试
# ============================================================
@pytest.mark.asyncio
async def test_alternatives_agent_empty_spec(sample_state):
    """没有 normalized_spec：返回空列表"""
    sample_state["normalized_spec"] = None
    result = await alternatives_agent(sample_state)
    assert result["alternatives"] == []


@pytest.mark.asyncio
async def test_alternatives_agent_neograph_hit(sample_state, sample_normalized_spec):
    """LLM 返回 Neo4j 来源的替代料: verified/source 由代码赋值"""
    sample_state["normalized_spec"] = sample_normalized_spec

    llm_output = {
        "alternatives": [{
            "part": "GRM188R61A106KE69D",
            "brand": "Murata",
            "package": "0805",
            "capacitance": "10uF",
            "rated_voltage": "10V",
            "temp_coeff": "X5R",
            "confidence": 0.95,
            "level": "L1",
            "source": "llm_inferred",       # LLM 自报, 应被代码改写
            "verified": False,               # LLM 自报, 应被代码改写
            "specs": {},
            "diff_items": [],
        }]
    }

    with patch("ai.agents.alternatives.agent_engine.run_tool_agent",
               _mock_run_tool_agent_with_facts(
                   llm_output,
                   tool_parts={"GRM188R61A106KE69D": "Neo4j:direct"})):
        result = await alternatives_agent(sample_state)

    alts = result["alternatives"]
    assert len(alts) == 1
    # verified/source 由代码赋值, 不信任 LLM 自报
    assert alts[0]["verified"] is True
    assert alts[0]["source"].startswith("Neo4j:")  # 代码赋值, 不信任 LLM 自报 llm_inferred


@pytest.mark.asyncio
async def test_alternatives_agent_llm_fallback(sample_state, sample_normalized_spec):
    """LLM 推理兜底 (型号在 RAG 命中但无 Neo4j 关系): verified=False"""
    sample_state["normalized_spec"] = sample_normalized_spec

    llm_output = {
        "alternatives": [{
            "part": "GRM188R61A106KE69D",
            "brand": "Murata",
            "package": "0805",
            "capacitance": "10uF",
            "rated_voltage": "10V",
            "temp_coeff": "X5R",
            "confidence": 0.7,
            "level": "L3",
            "source": "Neo4j:direct",   # LLM 自报, 应被改写 (实际无 Neo4j 关系)
            "verified": True,
            "specs": {},
            "diff_items": [],
        }]
    }

    with patch("ai.agents.alternatives.agent_engine.run_tool_agent",
               _mock_run_tool_agent_with_facts(
                   llm_output,
                   rag_parts={"GRM188R61A106KE69D"})):  # 仅 RAG 命中, 无 Neo4j
        result = await alternatives_agent(sample_state)

    alts = result["alternatives"]
    assert len(alts) == 1
    # 无 Neo4j 关系 -> verified=False (不信任 LLM 自报 True)
    assert alts[0]["verified"] is False
    # 未核验 confidence 上限 0.5
    assert alts[0]["confidence"] <= 0.5


@pytest.mark.asyncio
async def test_alternatives_agent_safety_filter(sample_state, sample_normalized_spec):
    """LLM 返回空且无规则兜底命中 -> 结果为空"""
    # 用一个不命中 _KNOWN_ALTERNATIVES 的型号, 使 rule_fallback 也返回空
    spec = dict(sample_normalized_spec)
    spec["part_number"] = "UNKNOWN9999"
    spec["package"] = "1206"  # 不命中 0805/0603 的兜底分支
    sample_state["normalized_spec"] = spec
    llm_output = {"alternatives": []}

    with patch("ai.agents.alternatives.agent_engine.run_tool_agent",
               _mock_run_tool_agent_with_facts(llm_output)):
        result = await alternatives_agent(sample_state)

    assert len(result["alternatives"]) == 0


@pytest.mark.asyncio
async def test_alternatives_agent_sorted_by_level(sample_state, sample_normalized_spec):
    """LLM 返回按 L1->L5 排序的结果"""
    sample_state["normalized_spec"] = sample_normalized_spec

    llm_output = {
        "alternatives": [
            {
                "part": "ALTA0001", "brand": "A", "package": "0805", "capacitance": "1uF",
                "rated_voltage": "10V", "temp_coeff": "X5R", "confidence": 0.95,
                "level": "L1", "source": "Neo4j:direct", "verified": True,
                "specs": {}, "diff_items": [],
            },
            {
                "part": "ALTB0002", "brand": "B", "package": "0805", "capacitance": "1uF",
                "rated_voltage": "25V", "temp_coeff": "X5R", "confidence": 0.85,
                "level": "L2", "source": "Neo4j:transitive", "verified": True,
                "specs": {}, "diff_items": [
                    {"param": "rated_voltage", "original": "10V", "alternative": "25V", "type": "diff"},
                ],
            },
        ]
    }

    with patch("ai.agents.alternatives.agent_engine.run_tool_agent",
               _mock_run_tool_agent_with_facts(
                   llm_output,
                   tool_parts={"ALTA0001": "Neo4j:direct", "ALTB0002": "Neo4j:transitive"})):
        result = await alternatives_agent(sample_state)

    alts = result["alternatives"]
    assert len(alts) == 2
    level_order = {"L1": 0, "L2": 1, "L3": 2, "L4": 3, "L5": 4}
    levels = [level_order.get(a.get("level", "L5"), 5) for a in alts]
    assert levels == sorted(levels), f"排序异常: {[a.get('level') for a in alts]}"


@pytest.mark.asyncio
async def test_alternatives_agent_neocom_error_fallback(sample_state, sample_normalized_spec):
    """run_tool_agent 抛异常 -> 不中断流程"""
    sample_state["normalized_spec"] = sample_normalized_spec

    with patch("ai.agents.alternatives.agent_engine.run_tool_agent",
               side_effect=Exception("LLM timeout")):
        result = await alternatives_agent(sample_state)

    assert result["alternatives"] is not None
    has_error = any("alternatives" in e for e in result.get("errors", []))
    assert has_error


@pytest.mark.asyncio
async def test_alternatives_agent_parse_failure(sample_state, sample_normalized_spec):
    """LLM 返回非 JSON -> 不崩溃 (走规则兜底或空)"""
    sample_state["normalized_spec"] = sample_normalized_spec

    mock_msg = MagicMock()
    mock_msg.content = "无法解析的文本回复"
    mock_run = AsyncMock(return_value={"messages": [mock_msg], "next_agent": None})

    with patch("ai.agents.alternatives.agent_engine.run_tool_agent", mock_run):
        result = await alternatives_agent(sample_state)

    assert result["alternatives"] == [] or result["alternatives"]  # 兜底或空均可, 不崩溃


# ============================================================
# #16 校验层 - 3 个幻觉拦截单测 (issue 验收要求)
# ============================================================
@pytest.mark.asyncio
async def test_hallucinated_part_intercepted(sample_state, sample_normalized_spec):
    """幻觉 1: LLM 编造型号 (不在工具返回集合) -> 被代码层拦截。"""
    sample_state["normalized_spec"] = sample_normalized_spec

    llm_output = {
        "alternatives": [
            {
                "part": "FABRC999",  # 编造型号, 工具从未返回
                "brand": "Fake", "package": "0805", "capacitance": "1uF",
                "rated_voltage": "10V", "temp_coeff": "X5R",
                "confidence": 0.9, "level": "L1",
                "source": "Neo4j:direct", "verified": True,
                "specs": {}, "diff_items": [],
            },
            {
                "part": "REALPRT123",  # 合法型号, 工具返回过
                "brand": "Murata", "package": "0805", "capacitance": "1uF",
                "rated_voltage": "10V", "temp_coeff": "X5R",
                "confidence": 0.9, "level": "L1",
                "source": "Neo4j:direct", "verified": True,
                "specs": {}, "diff_items": [],
            },
        ]
    }

    with patch("ai.agents.alternatives.agent_engine.run_tool_agent",
               _mock_run_tool_agent_with_facts(
                   llm_output,
                   tool_parts={"REALPRT123": "Neo4j:direct"})):  # 仅真实型号在集合
        result = await alternatives_agent(sample_state)

    alts = result["alternatives"]
    parts = [a["part"] for a in alts]
    assert "FABRC999" not in parts, "幻觉型号未被拦截"
    assert "REALPRT123" in parts, "合法型号不应被误杀"
    # 拦截事件记录到 errors
    assert any("拦截" in e for e in result.get("errors", []))


@pytest.mark.asyncio
async def test_self_reported_verified_overridden(sample_state, sample_normalized_spec):
    """幻觉 2: LLM 自报 verified=true/source=Neo4j:direct, 但型号不在 Neo4j 返回 -> 代码改写。"""
    sample_state["normalized_spec"] = sample_normalized_spec

    llm_output = {
        "alternatives": [{
            "part": "SELFRPT456",
            "brand": "Murata", "package": "0805", "capacitance": "1uF",
            "rated_voltage": "10V", "temp_coeff": "X5R",
            "confidence": 0.95, "level": "L1",
            "source": "Neo4j:direct",   # LLM 自报 Neo4j 来源
            "verified": True,            # LLM 自报已核验
            "specs": {}, "diff_items": [],
        }]
    }

    # 型号在工具集合 (避免被幻觉拦截), 但仅来自 RAG, 无 Neo4j 关系
    with patch("ai.agents.alternatives.agent_engine.run_tool_agent",
               _mock_run_tool_agent_with_facts(
                   llm_output,
                   rag_parts={"SELFRPT456"})):  # 仅 RAG, 无 Neo4j
        result = await alternatives_agent(sample_state)

    alts = result["alternatives"]
    assert len(alts) == 1
    # 代码改写: 无 Neo4j 关系 -> verified=False, source 不含 Neo4j:direct
    assert alts[0]["verified"] is False, "LLM 自报 verified 未被代码改写"
    assert "Neo4j:direct" not in alts[0]["source"], "LLM 自报 source 未被代码改写"


@pytest.mark.asyncio
async def test_redline_violation_intercepted(sample_state, sample_normalized_spec):
    """幻觉 3: 红线违规 (电压降级/封装不同/EOL) -> 代码层移除。

    sample_normalized_spec: rated_voltage=10V, package=0805, temp_coeff=X5R
    """
    sample_state["normalized_spec"] = sample_normalized_spec

    llm_output = {
        "alternatives": [
            {  # 电压降级 10V -> 6.3V
                "part": "VLTDRP001", "brand": "A", "package": "0805",
                "capacitance": "1uF", "rated_voltage": "6.3V", "temp_coeff": "X5R",
                "confidence": 0.9, "level": "L1", "source": "Neo4j:direct",
                "verified": True, "specs": {}, "diff_items": [],
            },
            {  # 封装不同 0805 -> 0603 (无桥接方案)
                "part": "PKGDF002", "brand": "B", "package": "0603",
                "capacitance": "1uF", "rated_voltage": "10V", "temp_coeff": "X5R",
                "confidence": 0.9, "level": "L1", "source": "Neo4j:direct",
                "verified": True, "specs": {}, "diff_items": [],
            },
            {  # EOL 停产
                "part": "EOLPRT003", "brand": "C", "package": "0805",
                "capacitance": "1uF", "rated_voltage": "10V", "temp_coeff": "X5R",
                "lifecycle": "停产",
                "confidence": 0.9, "level": "L1", "source": "Neo4j:direct",
                "verified": True, "specs": {}, "diff_items": [],
            },
            {  # 合法: 同规格
                "part": "SAFEPRT004", "brand": "D", "package": "0805",
                "capacitance": "1uF", "rated_voltage": "10V", "temp_coeff": "X5R",
                "confidence": 0.9, "level": "L1", "source": "Neo4j:direct",
                "verified": True, "specs": {}, "diff_items": [],
            },
        ]
    }

    # 4 个型号都在工具集合 (避免幻觉拦截), 仅校验红线
    tool_parts = {f"VLTDRP001": "Neo4j:direct", f"PKGDF002": "Neo4j:direct",
                  f"EOLPRT003": "Neo4j:direct", f"SAFEPRT004": "Neo4j:direct"}
    with patch("ai.agents.alternatives.agent_engine.run_tool_agent",
               _mock_run_tool_agent_with_facts(llm_output, tool_parts=tool_parts)):
        result = await alternatives_agent(sample_state)

    alts = result["alternatives"]
    parts = [a["part"] for a in alts]
    assert "VLTDRP001" not in parts, "电压降级未被拦截"
    assert "PKGDF002" not in parts, "封装不同未被拦截"
    assert "EOLPRT003" not in parts, "EOL 未被拦截"
    assert "SAFEPRT004" in parts, "合法型号不应被误杀"


# ============================================================
# 校验层单元测试 (纯逻辑, 不跑 agent)
# ============================================================
class TestValidationUnit:
    """直接测试校验函数, 覆盖边界"""

    def test_parse_voltage(self):
        assert _parse_voltage("10V") == 10.0
        assert _parse_voltage("6.3v") == 6.3
        assert _parse_voltage("10") == 10.0
        assert _parse_voltage(None) is None
        assert _parse_voltage("abc") is None

    def test_check_safety_voltage_drop(self):
        spec = {"rated_voltage": "10V", "package": "0805", "temp_coeff": "X5R"}
        alt = {"rated_voltage": "6.3V", "package": "0805", "temp_coeff": "X5R"}
        safe, reason = _check_safety(alt, spec)
        assert not safe
        assert "电压" in reason

    def test_check_safety_package_diff(self):
        spec = {"rated_voltage": "10V", "package": "0805", "temp_coeff": "X5R"}
        alt = {"rated_voltage": "10V", "package": "0603", "temp_coeff": "X5R"}
        safe, reason = _check_safety(alt, spec)
        assert not safe
        assert "封装" in reason

    def test_check_safety_eol(self):
        spec = {"rated_voltage": "10V", "package": "0805", "temp_coeff": "X5R"}
        alt = {"rated_voltage": "10V", "package": "0805", "temp_coeff": "X5R",
               "lifecycle": "已停产 EOL"}
        safe, reason = _check_safety(alt, spec)
        assert not safe

    def test_check_safety_safe(self):
        spec = {"rated_voltage": "10V", "package": "0805", "temp_coeff": "X5R"}
        alt = {"rated_voltage": "10V", "package": "0805", "temp_coeff": "X5R"}
        safe, reason = _check_safety(alt, spec)
        assert safe

    def test_check_safety_voltage_upgrade_safe(self):
        """电压向上兼容 (10V -> 16V) 是安全的"""
        spec = {"rated_voltage": "10V", "package": "0805", "temp_coeff": "X5R"}
        alt = {"rated_voltage": "16V", "package": "0805", "temp_coeff": "X5R"}
        safe, _ = _check_safety(alt, spec)
        assert safe

    def test_validate_hallucinated_part_rejected(self):
        """型号不在工具集合 -> 拦截"""
        collector = _ToolFactCollector()
        collector.all_seen_parts.add("REAL")
        collector.neo4j_parts["REAL"] = "Neo4j:direct"
        alts = [{"part": "FAKE", "package": "0805", "rated_voltage": "10V", "temp_coeff": "X5R"}]
        validated, rejected = _validate_alternatives(alts, collector, {})
        assert len(validated) == 0
        assert len(rejected) == 1

    def test_validate_confidence_capped_for_unverified(self):
        """未核验型号 confidence 上限 0.5"""
        collector = _ToolFactCollector()
        collector.all_seen_parts.add("P1")
        collector.rag_verified_parts.add("P1")  # 仅 RAG, 未核验
        alts = [{"part": "P1", "package": "0805", "rated_voltage": "10V",
                 "temp_coeff": "X5R", "confidence": 0.95}]
        validated, _ = _validate_alternatives(
            alts, collector, {"package": "0805", "rated_voltage": "10V", "temp_coeff": "X5R"})
        assert validated[0]["confidence"] <= 0.5


# ============================================================
# #17: rule_fallback 降级标注
# ============================================================
@pytest.mark.asyncio
async def test_rule_fallback_marked_as_query_failed(sample_state, sample_normalized_spec):
    """#17: LLM/Neo4j 双挂走 rule_fallback 时, source 标 query_failed, confidence<=0.3, verified=False"""
    sample_state["normalized_spec"] = sample_normalized_spec  # part_number=TMK212BJ105KG-T 命中 known

    mock_msg = MagicMock()
    mock_msg.content = json.dumps({"alternatives": []})  # LLM 返回空
    mock_run = AsyncMock(return_value={"messages": [mock_msg], "next_agent": None})

    with patch("ai.agents.alternatives.agent_engine.run_tool_agent", mock_run):
        result = await alternatives_agent(sample_state)

    alts = result["alternatives"]
    assert len(alts) > 0  # rule_fallback 补料
    for a in alts:
        assert a["source"].startswith("rule_fallback:query_failed"), f"source 未标查询失败: {a['source']}"
        assert a["verified"] is False
        assert a["confidence"] <= 0.3
        # note 含"需人工核验"提示
        assert "人工核验" in a["note"] or "未核验" in a["reason"]


def test_rule_fallback_no_contradictory_reason():
    """#17: 修复矛盾 reason (容值不同不应说"参数兼容")"""
    from ai.agents.alternatives import _rule_based_fallback, _KNOWN_ALTERNATIVES
    alts = _rule_based_fallback({"part_number": "TMK212BJ105KG-T", "package": "0805",
                                  "capacitance": "1uF", "temp_coeff": "X5R", "rated_voltage": "10V"})
    # 容值不同的那条 (1uF->10uF), reason 不应说"参数兼容"
    cap_diff_alt = next(a for a in alts if "10uF" in str(a.get("capacitance", "")))
    assert "参数兼容" not in cap_diff_alt["reason"], f"矛盾 reason 未修复: {cap_diff_alt['reason']}"
    assert "容值不同" in cap_diff_alt["reason"] or "工程确认" in cap_diff_alt["reason"]
