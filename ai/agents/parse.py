"""
Agent ① — 需求解析
流程: 正则前置识别 → LLM 槽位提取 → 规则校验 → 合并

输出: parsed_spec (dict, 与前端 SpecField 格式对齐)
"""

from __future__ import annotations

import json
import logging
import re

from ai.state import ProcureState
from ai import base_agent as agent_engine
from ai.tools.regex_utils import extract_part_number_with_brand
from ai.prompts.parse import PARSE_SYSTEM_PROMPT, PARSE_USER_TEMPLATE
from ai.monitor import AgentLogger

logger = logging.getLogger(__name__)


# ============================================================
# 字段校验
# ============================================================
VALID_PACKAGES = {"01005", "0201", "0402", "0603", "0805", "1206", "1210", "1808", "1812", "2010", "2220", "2512"}
VALID_TEMP_COEFFS = {"X5R", "X7R", "X8R", "X8L", "C0G", "NP0", "Y5V", "Z5U", "X6S", "X7S"}
VALID_CATEGORIES = {"MLCC", "钽电容", "电阻", "贴片电阻", "电感", "连接器", "IC", "二极管", "晶振", "MOSFET"}


def _validate_spec(spec: dict) -> dict:
    """校验并清洗 LLM 输出的规格字段。"""
    cleaned = {}
    for key, val in spec.items():
        if val is None or val == "" or val == "null":
            continue
        if key == "package":
            pkg = str(val).strip()
            if pkg in VALID_PACKAGES:
                cleaned[key] = pkg
        elif key == "temp_coeff":
            tc = str(val).strip().upper()
            if tc in VALID_TEMP_COEFFS:
                cleaned[key] = tc
            else:
                cleaned[key] = str(val).strip()
        elif key == "category":
            cat = str(val).strip()
            cleaned[key] = cat if cat in VALID_CATEGORIES else cat
        elif key == "monthly_qty":
            try:
                cleaned[key] = int(float(str(val).replace(",", "").replace("万", "0000")))
            except (ValueError, TypeError):
                pass
        elif key == "lead_time_weeks":
            try:
                cleaned[key] = int(float(str(val).replace("周", "").strip()))
            except (ValueError, TypeError):
                pass
        elif key == "brand_pref":
            if isinstance(val, list):
                cleaned[key] = val
            elif isinstance(val, str):
                cleaned[key] = [b.strip() for b in val.split(",") if b.strip()]
        else:
            cleaned[key] = str(val).strip() if not isinstance(val, (int, float)) else val
    return cleaned


# ============================================================
# 核心 Agent
# ============================================================
async def parse_agent(state: ProcureState) -> ProcureState:
    """需求解析 Agent — 正则前置 + LLM 槽位提取 + 规则校验。"""
    log = AgentLogger("parse", thread_id=state.get("thread_id", ""))
    raw_query = state.get("raw_query", "")

    if not raw_query.strip():
        state.setdefault("errors", []).append("[parse] 输入为空")
        state["parsed_spec"] = None
        return state

    log.start(state)

    try:
        part_number, brand_hint = extract_part_number_with_brand(raw_query)

        # 尝试用重模型解析，失败则降级到轻量模型
        llm_spec = None
        for heavy_try in (True, False):
            try:
                llm = agent_engine.get_agent_llm(heavy=heavy_try)
                prompt = PARSE_USER_TEMPLATE.format(raw_query=raw_query)
                messages = [("system", PARSE_SYSTEM_PROMPT), ("human", prompt)]
                response = await llm.ainvoke(messages)
                content = response.content.strip()

                if content.startswith("```"):
                    content = re.sub(r"^```(?:json)?\s*", "", content)
                    content = re.sub(r"\s*```$", "", content)

                llm_spec = json.loads(content) if isinstance(content, str) else content
                llm_spec = _validate_spec(llm_spec)
                if llm_spec:
                    break  # 解析成功，跳出循环
            except (json.JSONDecodeError, Exception) as e:
                if not heavy_try:
                    raise  # 轻量模型也失败则抛出
                logger.warning("parse 重模型 JSON 解析失败 (%s)，降级到轻量模型", str(e)[:60])

        if part_number and "part_number" not in llm_spec:
            llm_spec["part_number"] = part_number
        if brand_hint and brand_hint != "Unknown" and "brand" not in llm_spec:
            llm_spec["brand"] = brand_hint

        critical_fields = ["part_number", "category", "package", "capacitance", "rated_voltage"]
        missing = [f for f in critical_fields if f not in llm_spec]

        if len(missing) >= 3 and not part_number:
            state["parsed_spec"] = llm_spec if llm_spec else None
            if not llm_spec:
                state.setdefault("errors", []).append("[parse] 未识别到有效型号或规格参数")
        else:
            state["parsed_spec"] = llm_spec

        log.end(state)

    except json.JSONDecodeError as e:
        state.setdefault("errors", []).append(f"[parse] LLM 返回格式异常: {str(e)[:100]}")
        state["parsed_spec"] = None
        log.fail(f"LLM JSON 解析失败: {str(e)[:100]}")
    except Exception as e:
        state.setdefault("errors", []).append(f"[parse] {str(e)[:200]}")
        state["parsed_spec"] = None
        log.fail(str(e)[:200])

    return state


# ecs_assistant 风格别名
process = parse_agent