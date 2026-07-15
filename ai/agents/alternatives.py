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

import json
import re
from datetime import datetime
from langchain_openai import ChatOpenAI
from ai.state import ProcureState, Alternative, ParamDiff, DiffItem
from ai.config import LLM_BASE_URL, DASHSCOPE_API_KEY, LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS, LLM_TIMEOUT
from ai.tools.neo4j_client import query_all_alternatives
from ai.prompts.alternatives import ALTERNATIVES_SYSTEM_PROMPT, ALTERNATIVES_USER_TEMPLATE
from ai.monitor import AgentLogger


_llm: ChatOpenAI | None = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            base_url=LLM_BASE_URL,
            api_key=DASHSCOPE_API_KEY,
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            timeout=LLM_TIMEOUT,
        )
    return _llm


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
    """逐项比对原型号 vs 替代型号，标注 match/diff/risk"""
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
    """判定差异是 diff 还是 risk"""
    if key == "package":
        return "risk"  # 封装不同 = 物理不兼容
    if key == "rated_voltage":
        try:
            o = float(re.sub(r"[^0-9.]", "", orig))
            a = float(re.sub(r"[^0-9.]", "", alt))
            return "risk" if a < o else "diff"  # 降压 = risk
        except ValueError:
            return "diff"
    if key == "temp_coeff":
        # 温度系数跨级 = risk (C0G→Y5V 之类)
        high_stability = {"C0G", "NP0", "X8R", "X8L"}
        low_stability = {"Y5V", "Z5U"}
        if orig.upper() in high_stability and alt.upper() in low_stability:
            return "risk"
        return "diff"
    if key == "capacitance":
        return "risk"  # 容值不同 = 电路行为改变
    return "diff"


# ============================================================
# 5级分类
# ============================================================
def _classify_level(diffs: list[ParamDiff], confidence: float, verified: bool) -> str:
    """根据差异列表 + 置信度 + 核验状态判定 L1-L5

    判定优先级:
      1. L1 — 无任何差异
      2. L5 — 置信度极低 (< 0.5) 且无核验
      3. L4 — 封装不兼容 (物理不可替换)
      4. L3 — 有风险项
      5. L2 — 仅有非风险差异
    """
    risk_count = sum(1 for d in diffs if d["status"] == "risk")
    diff_count = sum(1 for d in diffs if d["status"] == "diff")

    # L1: 完全等效
    if risk_count == 0 and diff_count == 0:
        return "L1"

    # L5: 信息不足
    if confidence < 0.5 and not verified:
        return "L5"

    # L4: 封装物理不兼容
    has_pkg_risk = any(d["field"] == "封装" and d["status"] == "risk" for d in diffs)
    if has_pkg_risk:
        return "L4"

    # L4: 低置信度 (< 0.7) 且无核验
    if confidence < 0.7 and not verified:
        return "L4"

    # L3: 有风险项
    if risk_count >= 1:
        return "L3"

    # L2: 仅有非风险差异
    if diff_count > 0:
        return "L2"

    return "L3"


# ============================================================
# 安全红线过滤
# ============================================================
def _safety_filter(alternatives: list[dict]) -> list[dict]:
    """过滤掉明显不安全的替代"""
    safe = []
    for alt in alternatives:
        # 置信度 < 0.5 且无核验 → 不输出
        if alt.get("confidence", 0) < 0.5 and not alt.get("verified", False):
            continue
        # 生命周期 = 停产 → 不输出
        if alt.get("lifecycle", "") in ("停产", "EOL", "Obsolete"):
            continue
        # 额定电压降低 + 无核验 → 不输出
        diffs = alt.get("diffs", [])
        has_voltage_risk = any(
            d["field"] == "额定电压" and d["status"] == "risk" for d in diffs
        )
        if has_voltage_risk and not alt.get("verified", False):
            continue
        safe.append(alt)
    return safe


# ============================================================
# 核心 Agent
# ============================================================
async def alternatives_agent(state: ProcureState) -> ProcureState:
    log = AgentLogger("alternatives", thread_id=state.get("thread_id", ""))
    normalized_spec = state.get("normalized_spec") or {}
    errors = list(state.get("errors", []))

    if not normalized_spec:
        state["alternatives"] = []
        return state

    log.start(state)

    try:
        all_results: list[dict] = []

        # ---- Step 1: Neo4j 图查询 ----
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
                    # 生成差异比对
                    alt["diffs"] = _compare_params(normalized_spec, alt)
                    alt["level"] = _classify_level(
                        alt["diffs"], alt.get("confidence", 0.9), alt.get("verified", True)
                    )
                    all_results.append(alt)
            except Exception as e:
                errors.append(f"[alternatives] Neo4j 查询失败: {str(e)[:100]}")

        # ---- Step 2: LLM 推理补充 ----
        if len(all_results) < 3:
            try:
                llm = _get_llm()
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
                errors.append(f"[alternatives] LLM 推理失败: {str(e)[:100]}")

        # ---- Step 3 & 4: 安全过滤 + 5级分类 ----
        all_results = _safety_filter(all_results)

        # ---- Step 5: 排序 (L1→L2→L3→L4→L5, 同等级置信度降序) ----
        level_order = {"L1": 0, "L2": 1, "L3": 2, "L4": 3, "L5": 4}
        all_results.sort(key=lambda x: (
            level_order.get(x.get("level", "L5"), 5),
            -x.get("confidence", 0),
        ))

        # 转换为前端期望的格式
        alternatives = _format_for_frontend(all_results, normalized_spec)
        state["alternatives"] = alternatives
        log.end(state)

    except Exception as e:
        errors.append(f"[alternatives] {str(e)[:200]}")
        state["alternatives"] = []
        state["errors"] = errors
        log.fail(str(e)[:200])

    return state


def _format_for_frontend(results: list[dict], spec: dict) -> list[dict]:
    """将内部格式转为前端 Alternative 接口"""
    formatted = []
    for r in results:
        key_params = {}
        for param_key in ("capacitance", "rated_voltage", "tolerance", "temp_coeff", "temp_range"):
            if r.get(param_key):
                key_params[param_key] = str(r[param_key])

        # 生成 diff_items（兼容旧版字段）
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