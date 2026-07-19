"""
Agent ④ - 供应商匹配
确定性流程: MySQL 查询 -> RAG 知识库检索 -> 程序化评分排序

流程:
  1. 从 normalized_spec 提取品类/品牌/地区参数
  2. 确定性调用 filter_suppliers_raw 查询供应商 (MySQL)
  3. 对每个匹配到的供应商，确定性调用 search_knowledge_base 检索知识库 (RAG)
  4. 程序化计算评分 (品牌覆盖度 + 地区匹配 + RAG 命中) 并排序

红线: 供应商必须来自 DB，首期库存/交期/价格一律标"未确认"

输出: matched_suppliers[]

注: 本 Agent 已确定性化, 不再调用 LLM 评分 (原 MATCH_SYSTEM_PROMPT 死代码已移除)。
"""

from __future__ import annotations

import json

from ai.state import ProcureState
from ai import base_agent as agent_engine
from ai.tools.mysql_client import filter_suppliers_raw
from ai.tools.kb_client import search_knowledge_base as search_knowledge_base_tool
from ai.monitor import AgentLogger


# kb_client 在"无结果"时实际返回的文案片段。用于判定 RAG 是否真的命中内容,
# 避免把"未找到/暂未收录/不可用/检索异常"等空结果误判为有效命中而加分。
# (历史 bug: 旧实现仅判 `"未找到" not in rag`, 而 kb_client 实际返回"未在知识库中找到",
#  导致未命中也加 0.05 分。)
_RAG_EMPTY_MARKERS = (
    "未在知识库中找到",
    "暂未收录",
    "暂无相关信息",
    "知识库系统当前不可用",
    "查询「",
    "知识库检索异常",
    "遇到错误",
)


def _rag_is_empty(text: str) -> bool:
    """判断 RAG 返回文本是否实质为空/无命中。"""
    if not text:
        return True
    return any(marker in text for marker in _RAG_EMPTY_MARKERS)


async def match_agent(state: ProcureState) -> ProcureState:
    """供应商匹配 Agent - 确定性: MySQL 查询 -> RAG 检索 -> 程序化评分。"""
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
            # 真实 schema: supplier_capabilities.brand_names (逗号分隔字符串)
            # 兼容旧格式: brands / brand_coverage (JSON 数组或字符串)
            sup_brands_raw = sup.get("brand_names") or sup.get("brands") or sup.get("brand_coverage") or ""
            if isinstance(sup_brands_raw, str):
                # brand_names 在 supplier_capabilities 表中是逗号分隔字符串
                if sup_brands_raw.startswith("["):
                    try:
                        sup_brands = json.loads(sup_brands_raw)
                    except (json.JSONDecodeError, TypeError):
                        sup_brands = [b.strip() for b in sup_brands_raw.split(",") if b.strip()]
                else:
                    sup_brands = [b.strip() for b in sup_brands_raw.split(",") if b.strip()]
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

            # RAG 洞察加分: 仅在 RAG 真正命中内容时给分 (修复: 旧实现匹配文案失效)
            rag = sup.get("rag_insight", "") or ""
            rag_score = 0.0 if _rag_is_empty(rag) else 0.05

            # 综合评分（满分 1.0）
            match_score = min(1.0, brand_score * 0.7 + location_score + rag_score + 0.1)

            sup_brand_str = json.dumps(sup_brands, ensure_ascii=False) if sup_brands else ""

            # 真实 schema: category_name (supplier_capabilities 表)
            category_val = sup.get("category_name") or sup.get("category") or ""
            categories_list = [c.strip() for c in str(category_val).split(",") if c.strip()] or ["MLCC"]

            # 真实 schema: lead_time_days (supplier_capabilities 表), 转换为周
            lead_time_days = sup.get("lead_time_days") or sup.get("lead_time_weeks")
            lead_time_weeks = None
            if lead_time_days is not None:
                try:
                    ltd = int(lead_time_days)
                    lead_time_weeks = round(ltd / 7, 1) if ltd > 7 else 1
                except (ValueError, TypeError):
                    lead_time_weeks = lead_time_days

            matched.append({
                "id": str(sup.get("id", "")),
                "name": sup.get("name", ""),
                "match_score": round(match_score, 2),
                "category": category_val,
                "categories": categories_list,
                "region": sup.get("region") or sup.get("location", ""),
                "location": sup.get("location", ""),
                "brands": sup_brands,
                "brand_coverage": sup_brand_str,
                "qualifications": [],
                "moq": sup.get("moq"),
                "lead_time_weeks": lead_time_weeks,
                "in_stock": False,
                "response_speed": "暂无数据",
                "data_source": sup.get("source_name") or sup.get("data_source") or "平台数据",
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
