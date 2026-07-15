"""
Agent ⑥ — 线索分级

流程:
  1. 规则评分 (主) — 月用量/交期/品牌偏好/替代灵活性
  2. LLM 润色理由 (辅) — 可选

LLM 不参与评分决策，只润色文本

输出: lead_grade { grade, score, reasons }
"""

from ai.state import ProcureState, LeadGrade
from ai.monitor import AgentLogger


def score_lead(spec: dict) -> LeadGrade:
    """
    规则评分 — 纯代码逻辑
    维度: 月用量(0-35) + 交期(0-25) + 品牌偏好(0-20) + 替代灵活性(0-20)
    """
    score = 0
    reasons = []

    # 月用量
    qty = spec.get("monthly_qty", 0) or 0
    if qty >= 1_000_000:
        score += 35
        reasons.append("月用量超百万，大客户线索")
    elif qty >= 100_000:
        score += 25
        reasons.append(f"月用量 {qty//10000} 万，优质线索")
    elif qty >= 10_000:
        score += 15
        reasons.append(f"月用量 {qty//10000} 万+")
    else:
        score += 5

    # 交期紧迫度
    lead_time = spec.get("lead_time_weeks", 999) or 999
    if lead_time <= 1:
        score += 25
        reasons.append("交期 1 周内，急单")
    elif lead_time <= 4:
        score += 15
        reasons.append("交期明确")
    else:
        score += 5

    # 品牌偏好
    brands = spec.get("brand_pref", []) or []
    if len(brands) >= 2:
        score += 20
        reasons.append("品牌偏好明确，精准匹配")
    elif len(brands) == 1:
        score += 15
        reasons.append("有品牌偏好")
    else:
        score += 5

    # 替代灵活性
    if spec.get("has_alternatives", False):
        score += 20
        reasons.append("接受替代料，成交概率高")
    else:
        score += 5

    # 分级
    if score >= 80:
        grade = "A"
    elif score >= 60:
        grade = "B"
    elif score >= 40:
        grade = "C"
    else:
        grade = "D"

    return LeadGrade(grade=grade, score=score, reasons=reasons)


async def grade_agent(state: ProcureState) -> ProcureState:
    log = AgentLogger("grade", thread_id=state.get("thread_id", ""))
    parsed_spec = state.get("parsed_spec") or state.get("normalized_spec") or {}
    errors = list(state.get("errors", []))

    log.start(state)

    try:
        lead_grade = score_lead(parsed_spec)
        state["lead_grade"] = lead_grade
        log.end(state)

    except Exception as e:
        errors.append(f"[grade] {str(e)[:200]}")
        state["lead_grade"] = LeadGrade(grade="D", score=0, reasons=["评分失败"])
        state["errors"] = errors
        log.fail(str(e)[:200])

    return state