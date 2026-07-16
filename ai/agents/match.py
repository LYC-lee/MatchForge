"""
Agent ④ — 供应商匹配
确定性流程: MySQL 查询 → RAG 知识库检索 → LLM 评分排序

流程:
  1. 从 normalized_spec 提取品类/品牌/地区参数
  2. 确定性调用 filter_suppliers_raw 查询供应商 (MySQL)
  3. 对每个匹配到的供应商，确定性调用 search_knowledge_base 检索知识库 (RAG)
  4. 将 MySQL 数据 + RAG 结果一并交给 LLM 评分排序

红线: 供应商必须来自 DB，首期库存/交期/价格一律标"未确认"

输出: matched_suppliers[]
"""

from __future__ import annotations

import json

from ai.state import ProcureState
from ai import base_agent as agent_engine
from ai.tools.mysql_client import filter_suppliers_raw
from ai.tools.kb_client import search_knowledge_base as search_knowledge_base_tool
from ai.monitor import AgentLogger

MATCH_SYSTEM_PROMPT = """你是电子元器件供应商匹配专家。根据提供的供应商数据库查询结果和知识库检索结果，进行评分排序。

## 输入数据说明
- 每个供应商包含两部分信息：
  1. 数据库字段: id, name, category, brands, location, moq, lead_time_weeks, data_source, updated_at
  2. 知识库检索: 从该企业知识库中检索到的产品线、认证资质、业务能力等文本信息

## 评分标准 (必须严格按此权重)
- 品牌覆盖度: 匹配的品牌数 / 需求品牌数 × 0.4
- 资质等级: IATF16949=3分, ISO14001=2分, ISO9001=2分, 原厂授权=3分 → 归一化 /3 × 0.3
- 响应速度: 24h/12h内响应 +0.2, 48h内 +0.1
- 数据新鲜度: 30天内更新 +0.1, 90天内 +0.05
- 知识库匹配度: RAG 检索结果与需求的匹配程度 × 0.1

## 关键规则
- 知识库检索结果为空或"未找到"时，该供应商仍可评分，但知识库匹配度计为 0
- 知识库中明确提到认证资质、原厂授权、产品线匹配的，相应加分
- 知识库中明确提到负面信息（如停产、质量问题）的，降低评分

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
      "confirmed_price": false,
      "rag_insights": "从知识库中提取的关键信息摘要"
    }
  ]
}

## 红线规则
- 供应商必须来自提供的数据库查询结果，不得编造
- 库存、交期、价格一律标 "未确认" (confirmed_stock/confirmed_lead/confirmed_price = false)
- 数据超过 90 天未更新，标注 "信息可能过期"
- 按 match_score 降序排列
- 返回纯 JSON，不要包含 markdown 代码块标记"""


async def match_agent(state: ProcureState) -> ProcureState:
    """供应商匹配 Agent — 确定性: MySQL 查询 → RAG 检索 → LLM 评分。"""
    log = AgentLogger("match", thread_id=state.get("thread_id", ""))
    normalized_spec = state.get("normalized_spec") or {}
    alternatives = state.get("alternatives", [])

    if not normalized_spec:
        state["matched_suppliers"] = []
        return state

    log.start(state)

    try:
        # ── 阶段 1: 从 normalized_spec 提取查询参数 ──
        category = normalized_spec.get("category", "")
        brand_pref = normalized_spec.get("brand_pref", [])
        if isinstance(brand_pref, str):
            brand_pref = [brand_pref] if brand_pref else []

        # 从 alternatives 中补充品牌信息
        for alt in alternatives:
            b = alt.get("brand", "")
            if b and b not in brand_pref:
                brand_pref.append(b)

        location = normalized_spec.get("location", "")

        # ── 阶段 2: 确定性调用 MySQL 查询供应商 ──
        raw_suppliers = filter_suppliers_raw(
            category=category,
            brands=brand_pref if brand_pref else None,
            location=location if location else None,
        )
        # 序列化 RowMapping 中的日期字段
        import datetime
        suppliers = []
        for row in raw_suppliers:
            ser = {}
            for k, v in dict(row).items():
                if isinstance(v, (datetime.date, datetime.datetime)):
                    ser[k] = v.isoformat()
                else:
                    ser[k] = v
            suppliers.append(ser)

        if not suppliers:
            state["matched_suppliers"] = []
            log.end(state)
            return state

        # ── 阶段 3: 对每个供应商确定性调用 RAG 知识库检索 ──
        enriched_suppliers = []
        for supplier in suppliers:
            supplier_name = supplier.get("name", "")
            rag_insight = ""
            if supplier_name:
                try:
                    rag_result = search_knowledge_base_tool.invoke({
                        "company_name": supplier_name,
                        "query": f"主营产品、认证资质、{category}产品线、业务能力",
                    })
                    rag_insight = str(rag_result) if rag_result else ""
                except Exception as e:
                    rag_insight = f"知识库检索异常: {str(e)[:100]}"
            enriched_suppliers.append({
                **supplier,
                "rag_insight": rag_insight[:1500],  # 截断保护
            })

        # ── 阶段 4: 确定性评分排序（绕过 LLM，直接基于品牌覆盖度 + 地区匹配 + RAG 结果计算评分）
        matched = []
        for sup in enriched_suppliers:
            # 品牌覆盖度计算
            sup_brands_raw = sup.get("brands") or sup.get("brand_coverage") or ""
            if isinstance(sup_brands_raw, str):
                try:
                    sup_brands = json.loads(sup_brands_raw) if sup_brands_raw.startswith("[") else [sup_brands_raw]
                except (json.JSONDecodeError, TypeError):
                    sup_brands = [sup_brands_raw] if sup_brands_raw else []
            elif isinstance(sup_brands_raw, (list, tuple)):
                sup_brands = list(sup_brands_raw)
            else:
                sup_brands = []
            sup_brands = [str(b).strip() for b in sup_brands if b]

            brand_score = 0.0
            if brand_pref and sup_brands:
                matched_brands = [b for b in brand_pref if b in sup_brands]
                brand_score = len(matched_brands) / len(brand_pref) if brand_pref else 0.0

            # 地区匹配
            location_score = 0.15 if location and sup.get("location") and location in str(sup.get("location", "")) else 0.0

            # RAG 洞察加分（只要有内容就给分）
            rag = sup.get("rag_insight", "") or ""
            rag_score = 0.05 if rag and rag != "知识库检索异常" and "未找到" not in rag else 0.0

            # 综合评分（满分 1.0）
            match_score = min(1.0, brand_score * 0.7 + location_score + rag_score + 0.1)

            sup_brand_str = json.dumps(sup_brands, ensure_ascii=False) if sup_brands else ""

            categories_list = [c.strip() for c in str(sup.get("category", "")).split(",") if c.strip()] or ["MLCC"]

            matched.append({
                "id": str(sup.get("id", "")),
                "name": sup.get("name", ""),
                "match_score": round(match_score, 2),
                "category": sup.get("category", ""),
                "categories": categories_list,
                "region": sup.get("location", ""),
                "location": sup.get("location", ""),
                "brands": sup_brands,
                "brand_coverage": sup_brand_str,
                "qualifications": [],
                "moq": sup.get("moq"),
                "lead_time_weeks": sup.get("lead_time_weeks"),
                "in_stock": False,
                "response_speed": "暂无数据",
                "data_source": sup.get("data_source", "平台数据"),
                "updated_at": sup.get("updated_at", ""),
                "confirmed_stock": False,
                "confirmed_lead": False,
                "confirmed_price": False,
                "rag_insights": rag[:500] if rag else "",
            })

        # 按评分降序排列
        matched.sort(key=lambda x: x["match_score"], reverse=True)
        state["matched_suppliers"] = matched
        log.end(state)

    except Exception as e:
        state.setdefault("errors", []).append(f"[match] {str(e)[:200]}")
        state["matched_suppliers"] = []
        log.fail(str(e)[:200])

    return state


# ecs_assistant 风格别名
process = match_agent