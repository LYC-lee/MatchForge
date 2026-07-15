"""
Agent ② — 标准化
查 MySQL material_dictionary 表，映射到标准编码

输出: normalized_spec (基于 parsed_spec，补充 std_code + 标准化字段名)
"""

from ai.state import ProcureState
from ai.tools.mysql_client import lookup_std_code
from ai.monitor import AgentLogger


async def normalize_agent(state: ProcureState) -> ProcureState:
    log = AgentLogger("normalize", thread_id=state.get("thread_id", ""))
    parsed_spec = state.get("parsed_spec")
    errors = list(state.get("errors", []))

    if not parsed_spec:
        state["normalized_spec"] = None
        return state

    log.start(state)

    try:
        std_result = lookup_std_code(parsed_spec)
        normalized = dict(parsed_spec)

        if std_result:
            normalized["std_code"] = std_result.get("std_code", "")
            normalized["standard"] = std_result.get("standard", "")
            normalized["_mapped"] = True
        else:
            normalized["std_code"] = None
            normalized["_mapped"] = False

        field_aliases = {
            "容值": "capacitance",
            "阻值": "resistance",
            "封装": "package",
            "品牌": "brand",
            "型号": "part_number",
            "温度系数": "temp_coeff",
            "额定电压": "rated_voltage",
            "容差": "tolerance",
            "温度范围": "temp_range",
            "生命周期": "lifecycle",
            "月用量": "monthly_qty",
            "交期": "lead_time_weeks",
        }
        for cn, en in field_aliases.items():
            if cn in normalized and en not in normalized:
                normalized[en] = normalized[cn]

        state["normalized_spec"] = normalized
        log.end(state)

    except Exception as e:
        errors.append(f"[normalize] {str(e)[:200]}")
        state["normalized_spec"] = dict(parsed_spec) if parsed_spec else None
        state["errors"] = errors
        log.fail(str(e)[:200])

    return state