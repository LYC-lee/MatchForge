"""
Agent ① — 需求解析
流程: 正则前置识别 → LLM 槽位提取 → 规则校验 → 合并

输出: parsed_spec (dict, 与前端 SpecField 格式对齐)
"""

import json
import re
from langchain_openai import ChatOpenAI
from ai.state import ProcureState
from ai.config import LLM_BASE_URL, DASHSCOPE_API_KEY, LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS, LLM_TIMEOUT
from ai.tools.regex_utils import extract_part_number_with_brand, validate_package, validate_temp_coeff
from ai.prompts.parse import PARSE_SYSTEM_PROMPT, PARSE_USER_TEMPLATE


# ============================================================
# LLM 客户端
# ============================================================
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
# 字段校验
# ============================================================
VALID_PACKAGES = {"01005", "0201", "0402", "0603", "0805", "1206", "1210", "1808", "1812", "2010", "2220", "2512"}
VALID_TEMP_COEFFS = {"X5R", "X7R", "X8R", "X8L", "C0G", "NP0", "Y5V", "Z5U", "X6S", "X7S"}
VALID_CATEGORIES = {"MLCC", "钽电容", "电阻", "贴片电阻", "电感", "连接器", "IC", "二极管", "晶振", "MOSFET"}


def _validate_spec(spec: dict) -> dict:
    """校验并清洗 LLM 输出的规格字段"""
    cleaned = {}
    for key, val in spec.items():
        if val is None or val == "" or val == "null":
            continue
        if key == "package":
            pkg = str(val).strip()
            if pkg in VALID_PACKAGES:
                cleaned[key] = pkg
            # 非法封装不写入，避免误导
        elif key == "temp_coeff":
            tc = str(val).strip().upper()
            if tc in VALID_TEMP_COEFFS:
                cleaned[key] = tc
            else:
                cleaned[key] = str(val).strip()  # 保留但标注低置信
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
    raw_query = state.get("raw_query", "")
    errors = list(state.get("errors", []))

    if not raw_query.strip():
        errors.append("[parse] 输入为空")
        state["parsed_spec"] = None
        state["errors"] = errors
        return state

    try:
        # ---- Step 1: 正则前置识别 ----
        part_number, brand_hint = extract_part_number_with_brand(raw_query)

        # ---- Step 2: LLM 槽位提取 ----
        llm = _get_llm()
        prompt = PARSE_USER_TEMPLATE.format(raw_query=raw_query)
        messages = [
            ("system", PARSE_SYSTEM_PROMPT),
            ("human", prompt),
        ]
        response = await llm.ainvoke(messages)
        content = response.content.strip()

        # 清理 markdown 代码块
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)

        llm_spec = json.loads(content) if isinstance(content, str) else content

        # ---- Step 3: 规则校验 ----
        llm_spec = _validate_spec(llm_spec)

        # ---- Step 4: 合并正则 + LLM 结果 ----
        # 正则命中的型号优先
        if part_number and "part_number" not in llm_spec:
            llm_spec["part_number"] = part_number
        if brand_hint and brand_hint != "Unknown" and "brand" not in llm_spec:
            llm_spec["brand"] = brand_hint

        # 判断关键字段缺失
        critical_fields = ["part_number", "category", "package", "capacitance", "rated_voltage"]
        missing = [f for f in critical_fields if f not in llm_spec]

        if len(missing) >= 3 and not part_number:
            # 型号识别失败 + 关键字段大量缺失 → 标记为低质量
            state["parsed_spec"] = llm_spec if llm_spec else None
            if not llm_spec:
                errors.append("[parse] 未识别到有效型号或规格参数")
        else:
            state["parsed_spec"] = llm_spec

        state["errors"] = errors

    except json.JSONDecodeError as e:
        errors.append(f"[parse] LLM 返回格式异常: {str(e)[:100]}")
        state["parsed_spec"] = None
        state["errors"] = errors
    except Exception as e:
        errors.append(f"[parse] {str(e)[:200]}")
        state["parsed_spec"] = None
        state["errors"] = errors

    return state