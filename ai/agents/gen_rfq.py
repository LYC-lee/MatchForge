"""
Agent ⑤ — 询价单生成
流程: 模板填充 (首选) → LLM 润色 (可选)
兜底: LLM 失败 → 模板直接拼接
输出: rfq_doc, rfq_id
"""

from __future__ import annotations

import uuid
from datetime import datetime
from ai.state import ProcureState
from ai.monitor import AgentLogger


# 品类 -> 中文品名映射 (#17: 删除 MLCC 硬编码, 品名从 spec.category 取)
_CATEGORY_TO_NAME: dict[str, str] = {
    "MLCC": "多层陶瓷贴片电容(MLCC)",
    "钽电容": "钽电容",
    "电阻": "贴片电阻",
    "贴片电阻": "贴片电阻",
    "电感": "电感",
    "连接器": "连接器",
    "IC": "集成电路(IC)",
    "二极管": "二极管",
    "晶振": "晶振",
    "MOSFET": "MOSFET",
}


def _category_to_name(category: str) -> str:
    """根据品类返回中文品名, 未知品类用通用名。"""
    cat = str(category or "").strip()
    return _CATEGORY_TO_NAME.get(cat, "电子元器件")


def build_rfq_template(
    spec: dict, alternatives: list, suppliers: list,
    rfq_id: str, raw_query: str = "",
) -> str:
    f = lambda k: str(spec.get(k, "")) if spec.get(k) else "__(待补充)__"
    alt_lines = "\n".join(
        f"{i+1}. {a.get('part_name', a.get('part', ''))} ({a.get('brand', '')}) "
        f"— {a.get('level', '')} {'跨品牌兼容' if a.get('level') == 'L2' else '需工程评估' if a.get('level') in ('L3','L4') else '仅供参考'}"
        for i, a in enumerate(alternatives[:3]) if a.get("level") != "L5"
    ) or "__(待补充)__"
    sup_lines = " / ".join(s.get("name", "") for s in suppliers[:3]) or "__(待补充)__"
    # 品名从 spec.category 动态取, 不再硬编码 MLCC (#17)
    product_name = _category_to_name(spec.get("category", ""))
    return f"""【询价单 RFQ】
RFQ-ID: {rfq_id}
日期: {datetime.now().strftime('%Y-%m-%d')}
一、品名
{product_name}
二、原始需求
{raw_query}
三、规格要求
- 封装: {f('package')}
- 标称容值: {f('capacitance')}
- 容差: {f('tolerance')}
- 温度系数: {f('temp_coeff')}
- 额定电压: {f('rated_voltage')}
- 月用量: {f('monthly_qty')}
- 期望交期: {f('lead_time_weeks')}周
四、可接受替代料(仅供参考,需工程师确认)
{alt_lines}
五、目标供应商
{sup_lines}
六、说明
本询价单由 MatchForge AI 辅助生成,替代料仅供参考,最终可替代性须由工程师确认。
供应商回复的库存 / 交期 / 价格均以正式确认为准,本平台不承诺实时库存与报价。"""


async def gen_rfq_agent(state: ProcureState) -> ProcureState:
    log = AgentLogger("gen_rfq", thread_id=state.get("thread_id", ""))
    parsed_spec = state.get("parsed_spec") or state.get("normalized_spec") or {}
    alternatives = state.get("alternatives", [])
    matched_suppliers = state.get("matched_suppliers", [])
    raw_query = state.get("raw_query", "")
    rfq_id = f"MF-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
    log.start(state)
    try:
        rfq_doc = build_rfq_template(parsed_spec, alternatives, matched_suppliers, rfq_id, raw_query)
        state["rfq_doc"] = rfq_doc
        state["rfq_id"] = rfq_id
        log.end(state)
    except Exception as e:
        state.setdefault("errors", []).append(f"[gen_rfq] {str(e)[:200]}")
        state["rfq_doc"] = build_rfq_template({}, alternatives, matched_suppliers, rfq_id, raw_query)
        state["rfq_id"] = rfq_id
        log.fail(str(e)[:200])
    return state


# ecs_assistant 风格别名
process = gen_rfq_agent