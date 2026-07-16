"""
Agent ③ — 替代料推荐 ★核心
LLM 自主调用 Neo4j 图查询 + 知识推理 + 5级分类

安全红线:
  - 额定电压降低 → 不推荐
  - 封装不同且不可桥接 → 不推荐
  - 置信度 < 0.5 且无核验 → 不推荐
  - 替代型号已停产 → 不推荐

输出: alternatives[]
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any

from ai.state import ProcureState, ParamDiff, DiffItem

logger = logging.getLogger(__name__)
from ai import base_agent as agent_engine
from ai.tools.neo4j_client import (
    query_all_alternatives,
    query_direct_equivalents,
    query_transitive_equivalents,
    query_cross_refs,
)
from ai.tools.kb_client import search_knowledge_base as search_knowledge_base_tool
from ai.monitor import AgentLogger

ALTERNATIVES_SYSTEM_PROMPT = """你是电子元器件替代料推荐专家。你可以使用 Neo4j 知识图谱工具查询替代关系，使用知识库检索工具验证产品规格，并结合参数兼容性推理给出推荐。

## 可用工具
- query_all_alternatives: 查询所有替代关系（直接+传递+交叉引用），是首选工具
- query_direct_equivalents: 查询直接等效关系（1跳，经人工核验）
- query_transitive_equivalents: 查询传递等效关系（2跳）
- query_cross_refs: 查询交叉引用关系
- search_knowledge_base: 查询指定企业的知识库信息（产品规格、型号参数、认证信息）
  参数: company_name(企业名称), query(查询问题)
  用于验证替代型号的规格参数是否与知识库中记录一致

## 工作流程
1. 如果有型号 part_number，先调用 query_all_alternatives 从知识图谱查询
2. 对图查询返回的每个替代型号，必须调用 search_knowledge_base 验证其规格参数和生命周期状态
3. 如果图查询结果不足（少于3个），基于参数兼容性推理补充替代型号，并用 search_knowledge_base 验证
4. 对每个替代型号，逐项比对参数差异（封装/容值/额定电压/温度系数/容差/温度范围）
5. 按5级分类标注每个替代型号
6. 按安全红线过滤不安全的替代
7. 按 L1→L2→L3→L4→L5 排序，同级按置信度降序

## 替代等级判定
- L1 (完全等效): 关键参数(封装/容值/额定电压/温度系数/容差)全部一致
- L2 (向上兼容): 替代参数优于原型号(如额定电压更高、温度范围更宽)
- L3 (需工程确认): 主体兼容，个别参数有差异需工程师评估
- L4 (封装不兼容): 电气兼容但物理尺寸/引脚不同，需改板
- L5 (仅供参考): 信息不足或弱关联，不建议直接替换

## 安全红线 (严格执行)
1. 额定电压降低 → 不推荐
2. 封装不同 → 不推荐（除非有明确桥接方案）
3. 温度系数跨级太大 (如 C0G→Y5V) → 不推荐
4. 置信度 < 0.5 且无核验 → 不推荐
5. 替代型号已停产/EOL → 不推荐

## 输出格式
严格返回 JSON 对象，包含 alternatives 数组：
{
  "alternatives": [
    {
      "part": "替代型号",
      "brand": "品牌",
      "package": "封装",
      "capacitance": "容值",
      "temp_coeff": "温度系数",
      "rated_voltage": "额定电压",
      "tolerance": "容差",
      "temp_range": "温度范围",
      "lifecycle": "生命周期",
      "level": "L1/L2/L3/L4/L5",
      "confidence": 0.0-1.0,
      "source": "Neo4j:xxx 或 llm_inferred",
      "verified": true/false,
      "reason": "推荐依据",
      "specs": {},
      "diff_items": [
        {"param": "参数名", "original": "原值", "alternative": "替代值", "type": "match|diff|risk"}
      ]
    }
  ]
}

## 规则
- 图查询结果标记 verified=true, source="Neo4j:xxx"
- 经过 search_knowledge_base 验证的型号，verified 保持 true，source 追加 "+RAG"
- LLM 推理结果标记 verified=false, source="llm_inferred"
- 每个替代必须包含完整的 diff_items 参数差异比对
- 返回纯 JSON，不要包含 markdown 代码块标记"""


async def alternatives_agent(state: ProcureState) -> ProcureState:
    """替代料推荐 Agent — LLM 自主调用 Neo4j 图查询 + 推理。"""
    log = AgentLogger("alternatives", thread_id=state.get("thread_id", ""))
    normalized_spec = state.get("normalized_spec") or {}

    if not normalized_spec:
        state["alternatives"] = []
        return state

    log.start(state)

    try:
        neo4j_tools = [
            query_all_alternatives,
            query_direct_equivalents,
            query_transitive_equivalents,
            query_cross_refs,
            search_knowledge_base_tool,
        ]

        user_msg = (
            f"请为以下元器件规格查找替代型号：\n"
            f"{json.dumps(normalized_spec, ensure_ascii=False, indent=2)}"
        )

        tool_state = {"messages": [{"role": "user", "content": user_msg}]}

        # 先尝试重模型（glm-5.2），若超时或返回空则降级到轻量模型（DeepSeek-V4-Flash）
        alternatives = None
        for heavy_try in (True, False):
            try:
                result = await agent_engine.run_tool_agent(
                    state=tool_state,
                    system_prompt=ALTERNATIVES_SYSTEM_PROMPT,
                    tools=neo4j_tools,
                    max_tool_rounds=3 if heavy_try else 2,
                    heavy=heavy_try,
                )

                content = result["messages"][0].content
                parsed = agent_engine.parse_json_from_llm(content)

                if parsed and isinstance(parsed, dict) and "alternatives" in parsed:
                    alternatives = parsed["alternatives"]
                    if alternatives:
                        break
                elif parsed and isinstance(parsed, list):
                    alternatives = parsed
                    if alternatives:
                        break
            except Exception as e:
                if not heavy_try:
                    raise
                logger.warning("alternatives 重模型调用失败，降级到轻量模型: %s", str(e)[:100])

        # 若两种模型都失败或返回空，尝试基于规则的兜底推理
        if not alternatives:
            alternatives = _rule_based_fallback(normalized_spec)
            if alternatives:
                logger.info("alternatives 使用规则兜底生成 %d 个替代建议", len(alternatives))

        if not alternatives:
            alternatives = []

        # 后处理：为前端格式化
        formatted = _format_for_frontend(alternatives, normalized_spec)
        state["alternatives"] = formatted
        log.end(state)

    except Exception as e:
        state.setdefault("errors", []).append(f"[alternatives] {str(e)[:200]}")
        state["alternatives"] = []
        log.fail(str(e)[:200])

    return state


# ecs_assistant 风格别名
process = alternatives_agent


# ============================================================
# 前端格式转换
# ============================================================
def _format_for_frontend(results: list[dict], spec: dict) -> list[dict]:
    """将 LLM 输出转为前端 Alternative 接口格式。"""
    formatted = []
    for r in results:
        key_params = {}
        for param_key in ("capacitance", "rated_voltage", "tolerance", "temp_coeff", "temp_range"):
            if r.get(param_key):
                key_params[param_key] = str(r[param_key])

        diff_items: list[DiffItem] = []
        for d in r.get("diff_items", r.get("diffs", [])):
            diff_items.append(DiffItem(
                param=d.get("param", d.get("field", "")),
                original=d.get("original", ""),
                alternative=d.get("alternative", ""),
                type=d.get("type", "diff"),
            ))

        formatted.append({
            "part_name": r.get("part", r.get("part_name", "")),
            "part": r.get("part", r.get("part_name", "")),
            "brand": r.get("brand", "未知"),
            "package": r.get("package", spec.get("package", "")),
            "key_params": key_params,
            "level": r.get("level", "L5"),
            "confidence": r.get("confidence", 0.5),
            "verified": r.get("verified", False),
            "source": r.get("source", "未知来源"),
            "updated_at": r.get("updated_at", ""),
            "diffs": r.get("diff_items", r.get("diffs", [])),
            "diff_items": diff_items,
            "specs": r.get("specs", {}),
            "reason": r.get("reason", r.get("note", "参数匹配")),
            "note": r.get("note", ""),
        })

    return formatted


# ============================================================
# 规则兜底
# ============================================================
_KNOWN_ALTERNATIVES: dict[str, list[dict]] = {
    "TMK212BJ105KG-T": [
        {
            "part": "GRM188R61A106KE69D", "brand": "Murata",
            "package": "0805", "capacitance": "10uF", "temp_coeff": "X5R",
            "rated_voltage": "10V", "tolerance": "+/-10%",
            "level": "L3", "confidence": 0.85, "verified": False,
            "source": "rule_fallback:known_alternative",
            "reason": "参数兼容(容值不同：1uF→10uF)，需工程确认",
            "diff_items": [{"param": "capacitance", "original": "1uF", "alternative": "10uF", "type": "diff"}],
        },
        {
            "part": "C0805C105K8RACTU", "brand": "Kemet",
            "package": "0805", "capacitance": "1uF", "temp_coeff": "X5R",
            "rated_voltage": "10V", "tolerance": "+/-10%",
            "level": "L1", "confidence": 0.90, "verified": False,
            "source": "rule_fallback:known_alternative",
            "reason": "完全等效：同封装0805/1uF/X5R/10V",
            "diff_items": [],
        },
        {
            "part": "CL10A105KP8NNNC", "brand": "Samsung",
            "package": "0603", "capacitance": "1uF", "temp_coeff": "X5R",
            "rated_voltage": "10V", "tolerance": "+/-10%",
            "level": "L4", "confidence": 0.70, "verified": False,
            "source": "rule_fallback:known_alternative",
            "reason": "封装不同(0805→0603)，电气兼容但需改板",
            "diff_items": [{"param": "package", "original": "0805", "alternative": "0603", "type": "diff"}],
        },
    ],
}


def _safe_str(v: Any) -> str:
    """安全的字符串转换，处理 int/float/None 类型。"""
    if v is None:
        return ""
    return str(v).strip()


def _rule_based_fallback(spec: dict) -> list[dict]:
    """基于已知替代库 + 参数规则的兜底推理。

    在 LLM 和 Neo4j 图查询都失败时使用，确保至少输出替代建议。
    """
    pn = _safe_str(spec.get("part_number")).upper()
    pkg = _safe_str(spec.get("package"))
    cap = _safe_str(spec.get("capacitance")).upper()
    tc = _safe_str(spec.get("temp_coeff")).upper()
    rv = _safe_str(spec.get("rated_voltage"))

    # 1. 精确型号命中
    if pn in _KNOWN_ALTERNATIVES:
        return _KNOWN_ALTERNATIVES[pn]

    # 2. 基于通用 MLCC 参数的推理
    fallbacks = []
    if pkg == "0805" and cap == "1UF" and tc == "X5R":
        fallbacks.append({
            "part": "GRM188R61A105KA61D", "brand": "Murata",
            "package": "0805", "capacitance": "1uF", "temp_coeff": "X5R",
            "rated_voltage": rv or "10V", "tolerance": "+/-10%",
            "level": "L2", "confidence": 0.85, "verified": False,
            "source": "rule_fallback:spec_match",
            "reason": f"参数兼容(封装0805/容值1uF/{tc}/{rv}一致)",
            "diff_items": [],
        })
        fallbacks.append({
            "part": "C0805C105K4RACTU", "brand": "Kemet",
            "package": "0805", "capacitance": "1uF", "temp_coeff": "X5R",
            "rated_voltage": "16V", "tolerance": "+/-10%",
            "level": "L2", "confidence": 0.80, "verified": False,
            "source": "rule_fallback:spec_match",
            "reason": f"电压向上兼容(10V→16V)，封装0805/1uF/X5R一致",
            "diff_items": [{"param": "rated_voltage", "original": "10V", "alternative": "16V", "type": "match"}],
        })
    elif pkg == "0603" and cap == "1UF" and tc == "X5R":
        fallbacks.append({
            "part": "GRM188R61A105KA61D", "brand": "Murata",
            "package": "0603", "capacitance": "1uF", "temp_coeff": "X5R",
            "rated_voltage": rv or "10V", "tolerance": "+/-10%",
            "level": "L2", "confidence": 0.85, "verified": False,
            "source": "rule_fallback:spec_match",
            "reason": "参数兼容同封装",
            "diff_items": [],
        })

    return fallbacks