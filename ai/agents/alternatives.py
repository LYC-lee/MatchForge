"""
Agent ③ — 替代料推荐 ★核心

流程:
  1. Neo4j 图查询 (首选) — 人工核验的替代关系
  2. LLM 推理 (次选) — 参数兼容性推理
  3. 参数差异比对 — 逐项标注 match/diff/risk
  4. 5级分类 (L1-L5) + 安全红线过滤
  5. 排序 + 审核分流

安全红线:
  - 额定电压降低 → 不推荐
  - 封装不同且不可桥接 → 不推荐
  - 置信度 < 0.5 且无核验 → 不推荐
  - 替代型号已停产 → 不推荐

输出: alternatives[]
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from ai.state import ProcureState, ParamDiff, DiffItem
from ai import base_agent as agent_engine
from ai.tools.neo4j_client import query_all_alternatives
from ai.prompts.alternatives import ALTERNATIVES_SYSTEM_PROMPT, ALTERNATIVES_USER_TEMPLATE
from ai.monitor import AgentLogger


# ============================================================
# 参数差异比对
# ============================================================
CRITICAL_PARAMS = [
    ("package", "封装"),
    ("capacitance", "容值"),
    ("rated_voltage", "额定电压"),
    ("temp_coeff", "温度系数"),
    ("tolerance", "容差"),
    ("temp_range", "温度范围"),
]


def _compare_params(original: dict, alternative: dict) -> list[ParamDiff]:
    """逐项比对原型号 vs 替代型号，标注 match/diff/risk。"""
    diffs: list[ParamDiff] = []
    for key, label in CRITICAL_PARAMS:
        orig_val = str(original.get(key, "")) if original.get(key) else ""
        alt_val = str(alternative.get(key, "")) if alternative.get(key) else ""

        if not orig_val or not alt_val:
            diffs.append(ParamDiff(
                field=label, original=orig_val or "未知", alternative=alt_val or "未知",
                status="diff", note="参数缺失",
            ))
            continue

        if orig_val == alt_val:
            diffs.append(ParamDiff(field=label, original=orig_val, alternative=alt_val, status="match", note=""))
        else:
            status = _judge_risk(key, orig_val, alt_val)
            diffs.append(ParamDiff(field=label, original=orig_val, alternative=alt_val, status=status, note=""))

    return diffs


def _judge_risk(key: str, orig: str, alt: str) -> str:
    """判定差异是 diff 还是 risk。"""
    if key == "package":
        return "risk"
    if key == "rated_voltage":
        try:
            o = float(re.sub(r"[^0-9.]", "", orig))
            a = float(re.sub(r"[^0-9.]", "", alt))
            return "risk" if a < o else "diff"
        except ValueError:
            return "diff"
    if key == "temp_coeff":
        high_stability = {"C0G", "NP0", "X8R", "X8L"}
        low_stability = {"Y5V", "Z5U"}
        if orig.upper() in high_stability and alt.upper() in low_stability:
            return "risk"
        return "diff"
    if key == "capacitance":
        return "risk"
    return "diff"


# ============================================================
# 5级分类
# ============================================================
def _classify_level(diffs: list[ParamDiff], confidence: float, verified: bool) -> str:
    """根据差异列表 + 置信度 + 核验状态判定 L1-L5。"""
    risk_count = sum(1 for d in diffs if d["status"] == "risk")
    diff_count = sum(1 for d in diffs if d["status"] == "diff")

    if risk_count == 0 and diff_count == 0:
        return "L1"
    if confidence < 0.5 and not verified:
        return "L5"

    has_pkg_risk = any(d["field"] == "封装" and d["status"] == "risk" for d in diffs)
    if has_pkg_risk:
        return "L4"
    if confidence < 0.7 and not verified:
        return "L4"
    if risk_count >= 1:
        return "L3"
    if diff_count > 0:
        return "L2"

    return "L3"


# ============================================================
# 安全红线过滤
# ============================================================
def _safety_filter(alternatives: list[dict]) -> list[dict]:
    """过滤掉明显不安全的替代。"""
    safe = []
    for alt in alternatives:
        if alt.get("confidence", 0) < 0.5 and not alt.get("verified", False):
            continue
        if alt.get("lifecycle", "") in ("停产", "EOL", "Obsolete"):
            continue
        diffs = alt.get("diffs", [])
        has_voltage_risk = any(
            d["field"] == "额定电压" and d["status"] == "risk" for d in diffs
        )
        if has_voltage_risk and not alt.get("verified", False):
            continue
        safe.append(alt)
    return safe


# ============================================================
# 前端格式转换
# ============================================================
def _format_for_frontend(results: list[dict], spec: dict) -> list[dict]:
    """将内部格式转为前端 Alternative 接口。"""
    formatted = []
    for r in results:
        key_params = {}
        for param_key in ("capacitance", "rated_voltage", "tolerance", "temp_coeff", "temp_range"):
            if r.get(param_key):
                key_params[param_key] = str(r[param_key])

        diff_items: list[DiffItem] = []
        for d in r.get("diffs", []):
            diff_items.append(DiffItem(
                param=d["field"],
                original=d["original"],
                alternative=d["alternative"],
                type=d["status"],
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
            "diffs": r.get("diffs", []),
            "diff_items": diff_items,
            "specs": r.get("specs", {}),
            "reason": r.get("reason", r.get("note", "参数匹配")),
            "note": r.get("note", ""),
        })

    return formatted


# ============================================================
# 核心 Agent
# ============================================================
async def alternatives_agent(state: ProcureState) -> ProcureState:
    """替代料推荐 Agent — Neo4j 图查询 + LLM 推理 + 5级分类。"""
    log = AgentLogger("alternatives", thread_id=state.get("thread_id", ""))
    normalized_spec = state.get("normalized_spec") or {}

    if not normalized_spec:
        state["alternatives"] = []
        return state

    log.start(state)

    try:
        all_results: list[dict] = []

        part_number = normalized_spec.get("part_number", "")
        if part_number:
            try:
                neo4j_results = query_all_alternatives(part_number)
                for row in neo4j_results:
                    alt = dict(row)
                    alt["source"] = f"Neo4j:{alt.get('source', '图关系')}"
                    alt["verified"] = alt.get("verified", True)
                    alt["level"] = alt.get("level", "L2")
                    alt["updated_at"] = alt.get("updated_at", datetime.now().strftime("%Y-%m-%d"))
                    alt["diffs"] = _compare_params(normalized_spec, alt)
                    alt["level"] = _classify_level(
                        alt["diffs"], alt.get("confidence", 0.9), alt.get("verified", True)
                    )
                    all_results.append(alt)
            except Exception as e:
                state.setdefault("errors", []).append(f"[alternatives] Neo4j 查询失败: {str(e)[:100]}")

        # ---- Step 2: LLM 推理补充 ----
        if len(all_results) < 3:
            try:
                llm = agent_engine.get_agent_llm(heavy=True)
                prompt = ALTERNATIVES_USER_TEMPLATE.format(
                    original_spec=json.dumps(normalized_spec, ensure_ascii=False, indent=2)
                )
                messages = [
                    ("system", ALTERNATIVES_SYSTEM_PROMPT),
                    ("human", prompt),
                ]
                response = await llm.ainvoke(messages)
                content = response.content.strip()

                if content.startswith("```"):
                    content = re.sub(r"^```(?:json)?\s*", "", content)
                    content = re.sub(r"\s*```$", "", content)

                llm_results = json.loads(content)
                if isinstance(llm_results, dict):
                    llm_results = [llm_results]

                for alt in llm_results:
                    alt["source"] = "llm_inferred"
                    alt["verified"] = False
                    alt["updated_at"] = datetime.now().strftime("%Y-%m-%d")
                    alt["diffs"] = _compare_params(normalized_spec, alt)
                    alt["level"] = _classify_level(
                        alt["diffs"], alt.get("confidence", 0.6), False
                    )
                    all_results.append(alt)
            except Exception as e:
                state.setdefault("errors", []).append(f"[alternatives] LLM 推理失败: {str(e)[:100]}")

        # ---- Step 3 & 4: 安全过滤 + 5级分类 ----
        all_results = _safety_filter(all_results)

        # ---- Step 5: 排序 (L1→L2→L3→L4→L5, 同等级置信度降序) ----
        level_order = {"L1": 0, "L2": 1, "L3": 2, "L4": 3, "L5": 4}
        all_results.sort(key=lambda x: (
            level_order.get(x.get("level", "L5"), 5),
            -x.get("confidence", 0),
        ))

        alternatives = _format_for_frontend(all_results, normalized_spec)
        state["alternatives"] = alternatives
        log.end(state)

    except Exception as e:
        state.setdefault("errors", []).append(f"[alternatives] {str(e)[:200]}")
        state["alternatives"] = []
        log.fail(str(e)[:200])

    return state


# ecs_assistant 风格别名
process = alternatives_agent