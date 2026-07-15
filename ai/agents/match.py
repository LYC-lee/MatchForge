"""
Agent ④ — 供应商匹配
LLM 自主调用 MySQL 供应商查询 + 评分排序

流程:
  1. LLM 自主调用 filter_suppliers 查询符合条件的供应商
  2. LLM 根据品牌覆盖度、资质等级、响应速度进行评分排序
  3. LLM 生成最终匹配结果

红线: 供应商必须来自 DB，首期库存/交期/价格一律标"未确认"

输出: matched_suppliers[]
"""

from __future__ import annotations

import json

from ai.state import ProcureState
from ai import base_agent as agent_engine
from ai.tools.mysql_client import filter_suppliers as filter_suppliers_tool
from ai.monitor import AgentLogger

MATCH_SYSTEM_PROMPT = """你是电子元器件供应商匹配专家。你可以查询数据库中的供应商信息，并根据用户需求进行评分排序。

## 可用工具
- filter_suppliers: 查询符合品类、品牌、地区条件的供应商列表
  参数: category(品类), brands(品牌名称，逗号分隔), location(地区)

## 工作流程
1. 从用户提供的元器件规格中提取品类、品牌偏好、地区等信息
2. 调用 filter_suppliers 工具查询符合条件的供应商
3. 对供应商进行评分排序：
   - 品牌覆盖度: 匹配的品牌数 / 需求品牌数 × 0.4
   - 资质等级: IATF16949=3分, ISO14001=2分, ISO9001=2分, 原厂授权=3分 → 归一化 /3 × 0.3
   - 响应速度: 24h/12h内响应 +0.2, 48h内 +0.1
   - 数据新鲜度: 30天内更新 +0.1, 90天内 +0.05
4. 输出排序后的匹配结果

## 输出格式
严格返回 JSON 对象，包含 matched_suppliers 数组：
{
  "matched_suppliers": [
    {
      "id": "供应商ID",
      "name": "供应商名称",
      "match_score": 0.0-1.0,
      "category": "品类",
      "region": "地区",
      "location": "地区",
      "categories": ["品类列表"],
      "brands": ["品牌列表"],
      "qualifications": ["资质列表"],
      "moq": 最小起订量,
      "lead_time_weeks": 交期周数,
      "in_stock": false,
      "response_speed": "24h/48h/72h/暂无数据",
      "data_source": "平台数据",
      "updated_at": "更新时间",
      "confirmed_stock": false,
      "confirmed_lead": false,
      "confirmed_price": false
    }
  ]
}

## 红线规则
- 供应商必须来自数据库查询结果，不得编造
- 库存、交期、价格一律标 "未确认" (confirmed_stock/confirmed_lead/confirmed_price = false)
- 数据超过 90 天未更新，标注 "信息可能过期"
- 按 match_score 降序排列
- 返回纯 JSON，不要包含 markdown 代码块标记"""


async def match_agent(state: ProcureState) -> ProcureState:
    """供应商匹配 Agent — LLM 自主调用 MySQL 查询 + 评分排序。"""
    log = AgentLogger("match", thread_id=state.get("thread_id", ""))
    normalized_spec = state.get("normalized_spec") or {}
    alternatives = state.get("alternatives", [])

    if not normalized_spec:
        state["matched_suppliers"] = []
        return state

    log.start(state)

    try:
        # 从 alternatives 中收集品牌信息
        brand_hints = []
        for alt in alternatives:
            b = alt.get("brand", "")
            if b and b not in brand_hints:
                brand_hints.append(b)
        brand_pref = normalized_spec.get("brand_pref", [])
        if isinstance(brand_pref, list):
            for b in brand_pref:
                if b not in brand_hints:
                    brand_hints.append(b)

        context = {
            "normalized_spec": normalized_spec,
            "brand_hints": brand_hints,
        }

        user_msg = (
            f"请为以下元器件需求匹配供应商：\n"
            f"{json.dumps(context, ensure_ascii=False, indent=2)}"
        )

        tool_state = {"messages": [{"role": "user", "content": user_msg}]}

        result = await agent_engine.run_tool_agent(
            state=tool_state,
            system_prompt=MATCH_SYSTEM_PROMPT,
            tools=[filter_suppliers_tool],
            max_tool_rounds=3,
            heavy=False,
        )

        content = result["messages"][0].content
        parsed = agent_engine.parse_json_from_llm(content)

        if parsed and isinstance(parsed, dict) and "matched_suppliers" in parsed:
            matched = parsed["matched_suppliers"]
        elif parsed and isinstance(parsed, list):
            matched = parsed
        else:
            matched = []

        # 后处理：确保字段完整性
        for m in matched:
            m.setdefault("confirmed_stock", False)
            m.setdefault("confirmed_lead", False)
            m.setdefault("confirmed_price", False)
            m.setdefault("in_stock", False)
            if m.get("updated_at"):
                try:
                    from datetime import datetime
                    days_ago = (datetime.now() - datetime.strptime(
                        str(m["updated_at"])[:10], "%Y-%m-%d"
                    )).days
                    if days_ago > 90:
                        m["data_source"] = m.get("data_source", "平台数据") + " (信息可能过期)"
                except Exception:
                    pass

        state["matched_suppliers"] = matched
        log.end(state)

    except Exception as e:
        state.setdefault("errors", []).append(f"[match] {str(e)[:200]}")
        state["matched_suppliers"] = []
        log.fail(str(e)[:200])

    return state


# ecs_assistant 风格别名
process = match_agent