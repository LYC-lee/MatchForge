"""
Agent ③ - 替代料推荐 ★核心
LLM 自主调用 Neo4j 图查询 + 知识推理 + 5级分类

安全红线:
  - 额定电压降低 -> 不推荐
  - 封装不同且不可桥接 -> 不推荐
  - 置信度 < 0.5 且无核验 -> 不推荐
  - 替代型号已停产 -> 不推荐

输出校验层 (#16, P0):
  LLM 输出的型号/verified/source/confidence 等事实性字段不再被信任,
  由代码层基于工具返回的事实集合重新校验与赋值:
    1. 型号必须 ∈ 工具(Neo4j / search_knowledge_base)返回集合, 否则拦截
    2. verified / source 由代码赋值, 不接受 LLM 填报
    3. 红线(电压降级 / 封装不同 / EOL / 温度系数跨级)代码复核, 违规移除
    4. diff_items 的 type 由代码重新判定, LLM 只负责解释文案

输出: alternatives[]
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Callable

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

# Neo4j 工具名 -> source 标签
_NEO4J_TOOL_SOURCE = {
    "query_direct_equivalents": "Neo4j:direct",
    "query_transitive_equivalents": "Neo4j:transitive",
    "query_cross_refs": "Neo4j:cross_ref",
    "query_all_alternatives": "Neo4j:all",
}

# 工具返回 dict 里可能承载型号的字段名 (容错)
_PART_KEYS = ("part", "part_number", "alt_part", "alternative", "equivalent",
              "equivalent_part", "target_part", "substitute", "mpn")

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
7. 按 L1->L2->L3->L4->L5 排序，同级按置信度降序

## 替代等级判定
- L1 (完全等效): 关键参数(封装/容值/额定电压/温度系数/容差)全部一致
- L2 (向上兼容): 替代参数优于原型号(如额定电压更高、温度范围更宽)
- L3 (需工程确认): 主体兼容，个别参数有差异需工程师评估
- L4 (封装不兼容): 电气兼容但物理尺寸/引脚不同，需改板
- L5 (仅供参考): 信息不足或弱关联，不建议直接替换

## 安全红线 (严格执行)
1. 额定电压降低 -> 不推荐
2. 封装不同 -> 不推荐（除非有明确桥接方案）
3. 温度系数跨级太大 (如 C0G->Y5V) -> 不推荐
4. 置信度 < 0.5 且无核验 -> 不推荐
5. 替代型号已停产/EOL -> 不推荐

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


# ============================================================
# 工具事实收集器 (#16 校验层基础设施)
# ============================================================
class _ToolFactCollector:
    """通过 run_tool_agent 的 tool_call_sink 收集工具返回的事实。

    收集两类事实:
      - neo4j_parts: {型号: source标签}  来自 Neo4j 图查询工具
      - rag_verified_parts: set[型号]    来自 search_knowledge_base 返回文本中提取的型号
      - rag_text_per_company: dict       保留 RAG 原文, 用于核对
    """

    def __init__(self):
        self.neo4j_parts: dict[str, str] = {}
        self.rag_verified_parts: set[str] = set()
        self.all_seen_parts: set[str] = set()

    def __call__(self, tool_name: str, tool_args: dict, output: Any) -> None:
        parts = _extract_parts_from_tool_output(output)
        if tool_name in _NEO4J_TOOL_SOURCE:
            label = _NEO4J_TOOL_SOURCE[tool_name]
            for p in parts:
                self.neo4j_parts[p] = label
                self.all_seen_parts.add(p)
        elif tool_name == "search_knowledge_base":
            # RAG 返回文本中出现的型号, 视为"知识库可核验"
            for p in parts:
                self.rag_verified_parts.add(p)
                self.all_seen_parts.add(p)


def _extract_parts_from_tool_output(output: Any) -> list[str]:
    """从工具返回值中尽可能提取型号字符串。

    Neo4j 工具返回 list[dict]; search_knowledge_base 返回 str。
    宽松提取, 避免漏型号导致误拦截。
    """
    parts: list[str] = []

    def _maybe_add(val: Any) -> None:
        if not val:
            return
        s = str(val).strip()
        # 型号通常含字母+数字, 长度 >=4; 过滤掉纯数字/纯中文描述
        if len(s) >= 4 and re.search(r"[A-Za-z]", s) and re.search(r"\d", s):
            # 取可能含 '-' 的型号串 (去除首尾引号/空白)
            s = s.strip("'\"")
            parts.append(s)

    if output is None:
        return parts
    if isinstance(output, list):
        for item in output:
            if isinstance(item, dict):
                for k in _PART_KEYS:
                    if k in item:
                        _maybe_add(item[k])
            elif isinstance(item, str):
                _maybe_add(item)
    elif isinstance(output, dict):
        for k in _PART_KEYS:
            if k in output:
                _maybe_add(output[k])
    elif isinstance(output, str):
        # 从文本中用正则提取类型号 token (大写字母+数字+连字符)
        for m in re.finditer(r"\b([A-Z]{2,}[A-Z0-9\-]{3,})\b", output):
            _maybe_add(m.group(1))
    return parts


# ============================================================
# 安全红线 / 参数复核 (#16)
# ============================================================
_VOLT_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*V?", re.IGNORECASE)


def _parse_voltage(val: Any) -> float | None:
    """从 '10V'/'10'/'10v' 等提取电压数值 (V)。失败返回 None。"""
    if val is None:
        return None
    m = _VOLT_NUM_RE.search(str(val))
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


# 温度系数等级 (越大越差): C0G/NP0 是 I 类稳定, X5R/X7R 是 II 类, Y5V/Z5U 是 III 类差
_TEMP_COEFF_TIER = {"C0G": 0, "NP0": 0, "X7R": 1, "X5R": 1, "X6S": 1, "X7S": 1, "X8R": 1, "X8L": 1, "Y5V": 2, "Z5U": 2}


def _temp_coeff_downgrade(orig_tc: str, alt_tc: str) -> bool:
    """温度系数是否跨级劣化 (如 C0G -> Y5V)。"""
    o = _TEMP_COEFF_TIER.get(str(orig_tc).strip().upper())
    a = _TEMP_COEFF_TIER.get(str(alt_tc).strip().upper())
    if o is None or a is None:
        return False
    return a > o


def _check_safety(alt: dict, spec: dict) -> tuple[bool, str]:
    """红线代码复核。返回 (是否安全, 不安全原因)。

    红线 (任一命中即不推荐):
      - 额定电压降低
      - 封装不同 (且无桥接方案)
      - 温度系数跨级劣化
      - 替代型号已停产/EOL
    """
    # 1. 电压降级
    orig_v = _parse_voltage(spec.get("rated_voltage"))
    alt_v = _parse_voltage(alt.get("rated_voltage"))
    if orig_v and alt_v and alt_v < orig_v:
        return False, f"额定电压降级 {orig_v}V->{alt_v}V"

    # 2. 封装不同
    orig_pkg = str(spec.get("package", "")).strip()
    alt_pkg = str(alt.get("package", "")).strip()
    if orig_pkg and alt_pkg and orig_pkg != alt_pkg:
        # 无桥接方案标记 (bridge/桥接) 则不推荐
        reason = str(alt.get("reason", "")) + str(alt.get("note", ""))
        if not re.search(r"桥接|bridge|转接", reason, re.IGNORECASE):
            return False, f"封装不同 {orig_pkg}->{alt_pkg}"

    # 3. 温度系数跨级劣化
    if _temp_coeff_downgrade(str(spec.get("temp_coeff", "")), str(alt.get("temp_coeff", ""))):
        return False, f"温度系数跨级劣化 {spec.get('temp_coeff')}->{alt.get('temp_coeff')}"

    # 4. EOL / 停产
    lifecycle = str(alt.get("lifecycle", "")) + str(alt.get("reason", ""))
    if re.search(r"停产|EOL|Obsolete|discontinued|not recommended|inactive", lifecycle, re.IGNORECASE):
        return False, f"替代型号已停产/EOL"

    return True, ""


def _recompute_diff_type(param: str, original: Any, alternative: Any, spec: dict) -> str:
    """代码复核单个 diff_item 的 type: match | diff | risk。

    电压/封装/温度系数差异若属红线 -> risk; 其余差异 -> diff; 相同 -> match。
    """
    param_l = str(param).lower()
    alt = str(alternative).strip()
    orig = str(original).strip()
    if not alt or not orig:
        return "diff"
    if alt == orig:
        return "match"
    if "电压" in param_l or "voltage" in param_l:
        ov = _parse_voltage(orig)
        av = _parse_voltage(alt)
        if ov and av and av < ov:
            return "risk"
        return "diff"
    if "封装" in param_l or "package" in param_l:
        return "risk"
    if "温度系数" in param_l or "temp_coeff" in param_l:
        if _temp_coeff_downgrade(orig, alt):
            return "risk"
        return "diff"
    return "diff"


def _recompute_diff_items(alt: dict, spec: dict) -> list[dict]:
    """复核 LLM 输出的 diff_items, 由代码重新判定 type。"""
    raw_items = alt.get("diff_items", alt.get("diffs", [])) or []
    recomputed = []
    for d in raw_items:
        if not isinstance(d, dict):
            continue
        param = d.get("param", d.get("field", ""))
        original = d.get("original", spec.get(str(param).lower(), ""))
        alternative = d.get("alternative", d.get("alt", ""))
        dtype = _recompute_diff_type(param, original, alternative, spec)
        recomputed.append({
            "param": param,
            "original": original,
            "alternative": alternative,
            "type": dtype,
        })
    return recomputed


# ============================================================
# 主校验 (#16 核心)
# ============================================================
def _validate_alternatives(
    alts: list[dict],
    collector: _ToolFactCollector,
    spec: dict,
) -> tuple[list[dict], list[str]]:
    """校验 LLM 输出的 alternatives, 返回 (合规列表, 拦截原因列表)。

    校验项:
      1. 型号必须 ∈ 工具返回集合 (neo4j_parts ∪ rag_verified_parts), 否则拦截
      2. verified / source 由代码赋值
      3. 红线代码复核, 违规移除
      4. diff_items type 代码复核
    """
    validated: list[dict] = []
    rejected: list[str] = []
    tool_parts = collector.all_seen_parts

    for alt in alts:
        part = str(alt.get("part", alt.get("part_name", ""))).strip()
        if not part:
            rejected.append("空型号, 已拦截")
            continue

        # 1. 型号幻觉拦截
        if part not in tool_parts:
            rejected.append(f"型号 {part} 不在工具返回集合 (幻觉), 已拦截")
            continue

        # 2. verified / source 代码赋值 (不信任 LLM)
        if part in collector.neo4j_parts:
            source = collector.neo4j_parts[part]
            verified = True
            if part in collector.rag_verified_parts:
                source = source + "+RAG"
        elif part in collector.rag_verified_parts:
            # 仅 RAG 命中 (无 Neo4j 图关系), 视为知识库可核验但非图谱直接关系
            source = "llm_inferred+RAG"
            verified = False
        else:
            source = "llm_inferred"
            verified = False
        alt["verified"] = verified
        alt["source"] = source

        # 3. 红线代码复核
        safe, reason = _check_safety(alt, spec)
        if not safe:
            rejected.append(f"型号 {part} 红线违规: {reason}, 已移除")
            continue

        # 4. diff_items type 代码复核
        alt["diff_items"] = _recompute_diff_items(alt, spec)

        # 5. confidence 复核: 未核验的不得超过 0.5 (宁缺毋假)
        try:
            conf = float(alt.get("confidence", 0.5))
        except (TypeError, ValueError):
            conf = 0.5
        if not verified and conf > 0.5:
            alt["confidence"] = 0.5
            alt.setdefault("note", "")
            if alt["note"]:
                alt["note"] += "; "
            alt["note"] += "未核验, 置信度上限 0.5"
        else:
            alt["confidence"] = conf

        validated.append(alt)

    return validated, rejected


async def alternatives_agent(state: ProcureState) -> ProcureState:
    """替代料推荐 Agent - LLM 自主调用 Neo4j 图查询 + 推理 + 代码层校验。"""
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

        # 工具事实收集器 (通过 sink 捕获工具返回, 供事后校验幻觉)
        collector = _ToolFactCollector()

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
                    tool_call_sink=collector,
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

        # ── #16 校验层: 对 LLM 输出做事实校验 (仅在 LLM 有输出时) ──
        rejected_reasons: list[str] = []
        if alternatives:
            alternatives, rejected_reasons = _validate_alternatives(
                alternatives, collector, normalized_spec
            )
            if rejected_reasons:
                logger.info(
                    "alternatives 校验层拦截 %d 项: %s",
                    len(rejected_reasons), "; ".join(rejected_reasons)[:300]
                )
                state.setdefault("errors", []).append(
                    f"[alternatives:validate] 拦截 {len(rejected_reasons)} 项幻觉/红线违规"
                )

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

        # rule_fallback 来源统一标注"查询失败"态 (#17)
        source = r.get("source", "未知来源")
        note = r.get("note", "")
        if str(source).startswith("rule_fallback"):
            note = (note + "; " if note else "") + "系统查询失败, 规则兜底建议, 仅供参考, 需人工核验"

        formatted.append({
            "part_name": r.get("part", r.get("part_name", "")),
            "part": r.get("part", r.get("part_name", "")),
            "brand": r.get("brand", "未知"),
            "package": r.get("package", spec.get("package", "")),
            "key_params": key_params,
            "level": r.get("level", "L5"),
            "confidence": r.get("confidence", 0.5),
            "verified": r.get("verified", False),
            "source": source,
            "updated_at": r.get("updated_at", ""),
            "diffs": r.get("diff_items", r.get("diffs", [])),
            "diff_items": diff_items,
            "specs": r.get("specs", {}),
            "reason": r.get("reason", r.get("note", "参数匹配")),
            "note": note,
        })

    return formatted


# ============================================================
# 规则兜底 (#17: 改为显式"查询失败"态, 降级标注, 宁缺毋假)
# ============================================================
_KNOWN_ALTERNATIVES: dict[str, list[dict]] = {
    "TMK212BJ105KG-T": [
        {
            "part": "GRM188R61A106KE69D", "brand": "Murata",
            "package": "0805", "capacitance": "10uF", "temp_coeff": "X5R",
            "rated_voltage": "10V", "tolerance": "+/-10%",
            "level": "L3", "confidence": 0.3, "verified": False,
            "source": "rule_fallback:query_failed",
            "reason": "容值不同(1uF->10uF), 需工程确认 (规则兜底, 未核验)",
            "diff_items": [{"param": "capacitance", "original": "1uF", "alternative": "10uF", "type": "diff"}],
        },
        {
            "part": "C0805C105K8RACTU", "brand": "Kemet",
            "package": "0805", "capacitance": "1uF", "temp_coeff": "X5R",
            "rated_voltage": "10V", "tolerance": "+/-10%",
            "level": "L1", "confidence": 0.3, "verified": False,
            "source": "rule_fallback:query_failed",
            "reason": "完全等效：同封装0805/1uF/X5R/10V (规则兜底, 未核验)",
            "diff_items": [],
        },
        {
            "part": "CL10A105KP8NNNC", "brand": "Samsung",
            "package": "0603", "capacitance": "1uF", "temp_coeff": "X5R",
            "rated_voltage": "10V", "tolerance": "+/-10%",
            "level": "L4", "confidence": 0.3, "verified": False,
            "source": "rule_fallback:query_failed",
            "reason": "封装不同(0805->0603)，电气兼容但需改板 (规则兜底, 未核验)",
            "diff_items": [{"param": "package", "original": "0805", "alternative": "0603", "type": "risk"}],
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

    在 LLM 和 Neo4j 图查询都失败时使用。返回的替代料统一标注:
      - source = "rule_fallback:query_failed"  (显式查询失败态)
      - verified = False
      - confidence <= 0.3  (降级, 未核验)
    不再作为"已核验替代料"进入正式输出流, 前端据 source 徽章提示用户需人工核验。
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
            "level": "L2", "confidence": 0.3, "verified": False,
            "source": "rule_fallback:query_failed",
            "reason": f"参数兼容(封装0805/容值1uF/{tc}/{rv}一致) (规则兜底, 未核验)",
            "diff_items": [],
        })
        fallbacks.append({
            "part": "C0805C105K4RACTU", "brand": "Kemet",
            "package": "0805", "capacitance": "1uF", "temp_coeff": "X5R",
            "rated_voltage": "16V", "tolerance": "+/-10%",
            "level": "L2", "confidence": 0.3, "verified": False,
            "source": "rule_fallback:query_failed",
            "reason": f"电压向上兼容(10V->16V)，封装0805/1uF/X5R一致 (规则兜底, 未核验)",
            "diff_items": [{"param": "rated_voltage", "original": "10V", "alternative": "16V", "type": "match"}],
        })
    elif pkg == "0603" and cap == "1UF" and tc == "X5R":
        fallbacks.append({
            "part": "GRM188R61A105KA61D", "brand": "Murata",
            "package": "0603", "capacitance": "1uF", "temp_coeff": "X5R",
            "rated_voltage": rv or "10V", "tolerance": "+/-10%",
            "level": "L2", "confidence": 0.3, "verified": False,
            "source": "rule_fallback:query_failed",
            "reason": "参数兼容同封装 (规则兜底, 未核验)",
            "diff_items": [],
        })

    return fallbacks
