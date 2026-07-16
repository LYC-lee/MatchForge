"""
Agent ④.5 — RAG 深度分析 (Agent ↔ RAG API 层编排)

流程:
  1. 从 state 中获取 matched_suppliers 和 alternatives
  2. 对每个匹配到的供应商，进行多维度 RAG 深度检索
  3. 汇总检索结果，生成供应商能力分析报告
  4. 将 RAG 分析结果写入 state，供前端消费

设计原则:
  - 确定性: 不依赖 LLM 工具调用决策，直接编程式遍历供应商
  - 多维度: 对每个供应商检索产品线、认证资质、业务能力、交期产能
  - 容错: 单个供应商 RAG 失败不影响整体流程
  - 缓存: 复用 kb_client 的 company_name → company_id 缓存

输出: state.rag_enrichment: {supplier_reports: [...], summary: "..."}
"""

from __future__ import annotations

import json
import logging

from ai.state import ProcureState
from ai.tools.kb_client import search_knowledge_base as search_knowledge_base_tool
from ai.monitor import AgentLogger

logger = logging.getLogger(__name__)

# 对每个供应商的检索维度
_ENRICH_QUERIES = [
    ("产品线", "主营产品系列、{category}相关产品线、核心型号"),
    ("认证资质", "质量体系认证、行业资质、原厂授权情况"),
    ("业务能力", "产能规模、交期、主要客户群体、业务覆盖区域"),
    ("技术能力", "技术研发能力、产品创新、专利情况"),
]


async def rag_enrich_agent(state: ProcureState) -> ProcureState:
    """RAG 深度分析 Agent — 确定性遍历供应商进行多维度知识库检索。"""
    log = AgentLogger("rag_enrich", thread_id=state.get("thread_id", ""))
    matched_suppliers = state.get("matched_suppliers", [])
    normalized_spec = state.get("normalized_spec") or {}
    category = normalized_spec.get("category", "")

    if not matched_suppliers:
        state["rag_enrichment"] = {"supplier_reports": [], "summary": "无匹配供应商，跳过 RAG 深度分析"}
        return state

    log.start(state)

    supplier_reports = []

    try:
        for supplier in matched_suppliers:
            supplier_name = supplier.get("name", "")
            if not supplier_name:
                continue

            supplier_report = {
                "supplier_name": supplier_name,
                "supplier_id": supplier.get("id", ""),
                "dimensions": {},
            }

            for dim_name, query_template in _ENRICH_QUERIES:
                query = query_template.format(category=category)
                try:
                    result = search_knowledge_base_tool.invoke({
                        "company_name": supplier_name,
                        "query": query,
                    })
                    supplier_report["dimensions"][dim_name] = {
                        "query": query,
                        "result": str(result)[:2000] if result else "知识库中暂无相关信息",
                    }
                except Exception as e:
                    logger.warning(
                        "RAG enrich failed for %s / %s: %s",
                        supplier_name, dim_name, str(e)[:150]
                    )
                    supplier_report["dimensions"][dim_name] = {
                        "query": query,
                        "result": f"检索异常: {str(e)[:100]}",
                    }

            supplier_reports.append(supplier_report)

        # 生成汇总摘要
        report_count = len(supplier_reports)
        total_dimensions = sum(len(r["dimensions"]) for r in supplier_reports)
        state["rag_enrichment"] = {
            "supplier_reports": supplier_reports,
            "summary": (
                f"RAG 深度分析完成: 对 {report_count} 个供应商进行了 "
                f"{total_dimensions} 个维度的知识库检索"
            ),
        }
        log.end(state)

    except Exception as e:
        state.setdefault("errors", []).append(f"[rag_enrich] {str(e)[:200]}")
        state["rag_enrichment"] = {"supplier_reports": [], "summary": f"RAG 分析异常: {str(e)[:200]}"}
        log.fail(str(e)[:200])

    return state


# ecs_assistant 风格别名
process = rag_enrich_agent