"""
Agent ② — 标准化
LLM 自主调用 MySQL material_dictionary 映射到标准编码
输出: normalized_spec
"""

from __future__ import annotations

import json
import re

from ai.state import ProcureState
from ai import base_agent as agent_engine
from ai.tools.mysql_client import lookup_std_code as lookup_std_code_tool
from ai.tools.kb_client import search_knowledge_base as search_knowledge_base_tool
from ai.monitor import AgentLogger

NORMALIZE_SYSTEM_PROMPT = """你是电子元器件标准化专家。你的任务是将用户输入的元器件规格参数映射到标准字典编码，并利用知识库补充缺失信息。

## 可用工具
- lookup_std_code: 在标准字典 material_dictionary 中查询匹配的标准编码
  参数: category(品类), package(封装), capacitance(容值), temp_coeff(温度系数), rated_voltage(额定电压)
- search_knowledge_base: 查询指定企业的知识库信息（产品规格、型号参数、标准编码）
  参数: company_name(企业名称), query(查询问题)
  用于在字典查询未命中时，从知识库中查找标准编码和规格补充信息

## 工作流程
1. 根据用户提供的规格参数，调用 lookup_std_code 工具查询标准编码
2. 如果字典查询未命中或返回信息不完整，必须调用 search_knowledge_base 从知识库中查找补充信息
3. 根据查询结果，输出标准化后的规格 JSON

## 输出格式
严格返回 JSON 对象，包含以下字段：
{
  "std_code": "标准编码 或 null",
  "standard": "标准名称 或 null",
  "_mapped": true/false,
  "category": "品类",
  "package": "封装",
  "capacitance": "容值",
  "temp_coeff": "温度系数",
  "rated_voltage": "额定电压",
  "part_number": "型号",
  "brand": "品牌",
  "tolerance": "容差",
  "temp_range": "温度范围",
  "lifecycle": "生命周期",
  "monthly_qty": 月用量数字,
  "lead_time_weeks": 交期周数
}

## 规则
- 所有字段为可选，未提取到则不返回该 key
- 如果字典查询命中，std_code 和 standard 填充查询结果，_mapped 设为 true
- 如果字典查询未命中，std_code 设为 null，_mapped 设为 false，但保留原始规格参数
- 中文字段名自动映射为英文（如 "容值" → "capacitance"、"封装" → "package"）
- 返回纯 JSON，不要包含 markdown 代码块标记"""


async def normalize_agent(state: ProcureState) -> ProcureState:
    """标准化 Agent — LLM 自主调用 MySQL 字典查询。"""
    log = AgentLogger("normalize", thread_id=state.get("thread_id", ""))
    parsed_spec = state.get("parsed_spec")

    if not parsed_spec:
        state["normalized_spec"] = None
        return state

    log.start(state)

    try:
        # 用 parsed_spec 构造一条用户消息，让 LLM 自主决定查什么
        user_msg = f"请将以下元器件规格标准化：\n{json.dumps(parsed_spec, ensure_ascii=False)}"

        # 临时 state 只包含当前用户消息
        tool_state = {"messages": [{"role": "user", "content": user_msg}]}

        result = await agent_engine.run_tool_agent(
            state=tool_state,
            system_prompt=NORMALIZE_SYSTEM_PROMPT,
            tools=[lookup_std_code_tool, search_knowledge_base_tool],
            max_tool_rounds=3,
            heavy=False,
        )

        # 解析 LLM 最终回复中的 JSON
        content = result["messages"][0].content
        normalized = agent_engine.parse_json_from_llm(content)

        if normalized and isinstance(normalized, dict):
            state["normalized_spec"] = normalized
        else:
            # 解析失败，保留原始规格
            state["normalized_spec"] = dict(parsed_spec)
            state["normalized_spec"]["std_code"] = None
            state["normalized_spec"]["_mapped"] = False

        log.end(state)

    except Exception as e:
        state.setdefault("errors", []).append(f"[normalize] {str(e)[:200]}")
        state["normalized_spec"] = dict(parsed_spec) if parsed_spec else None
        log.fail(str(e)[:200])

    return state


# ecs_assistant 风格别名
process = normalize_agent