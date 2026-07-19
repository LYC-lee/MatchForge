"""
Agent ④.5 - RAG 深度分析 (Agent ↔ RAG API 层编排)

流程:
  1. 从 state 中获取 matched_suppliers 和 alternatives
  2. 对每个匹配到的供应商，进行多维度 RAG 深度检索 (直接调 kb.rag.retrieve, 保留 chunk 元数据)
  3. 汇总检索结果，生成供应商能力分析报告
  4. 收集 citations[] 透出真实来源 (契约 C2, #22)
  5. 将 RAG 分析结果写入 state，供前端消费

设计原则:
  - 确定性: 不依赖 LLM 工具调用决策，直接编程式遍历供应商
  - 多维度: 对每个供应商检索产品线、认证资质、业务能力、交期产能
  - 容错: 单个供应商 RAG 失败不影响整体流程
  - 引用透出 (#22): 直接用 retrieve 而非 search_knowledge_base 工具, 保留 chunk_id/score/excerpt

输出: state.rag_enrichment: {supplier_reports: [...], citations: [...], summary: "..."}
"""

from __future__ import annotations

import logging

from ai.state import ProcureState
from ai.tools.kb_client import _resolve_company_id, search_knowledge_base as search_knowledge_base_tool
from ai.monitor import AgentLogger

logger = logging.getLogger(__name__)

# 对每个供应商的检索维度
_ENRICH_QUERIES = [
    ("产品线", "主营产品系列、{category}相关产品线、核心型号"),
    ("认证资质", "质量体系认证、行业资质、原厂授权情况"),
    ("业务能力", "产能规模、交期、主要客户群体、业务覆盖区域"),
    ("技术能力", "技术研发能力、产品创新、专利情况"),
]

# 每个 supplier_report 最多保留的 citation 条数 (避免响应过大)
_MAX_CITATIONS_PER_SUPPLIER = 2
# excerpt 最大字符数
_EXCERPT_LEN = 120


def _build_citation(chunk: dict, supplier_name: str) -> dict | None:
    """将 retrieve 返回的 chunk 转为契约 C2 的 citation 结构。"""
    if not chunk or not chunk.get("chunk_uid"):
        return None
    text = str(chunk.get("text", "") or "")
    return {
        "doc": chunk.get("manual_type", ""),          # product | business
        "chunk_id": str(chunk.get("chunk_id", "")),
        "chunk_uid": chunk.get("chunk_uid", ""),
        "score": round(float(chunk.get("score", 0.0)), 4),
        "excerpt": text[:_EXCERPT_LEN],
        "company_id": chunk.get("company_id"),
        "language": chunk.get("language", ""),
        "supplier_name": supplier_name,                # 便于前端关联到供应商
    }


async def rag_enrich_agent(state: ProcureState) -> ProcureState:
    """RAG 深度分析 Agent - 确定性遍历供应商进行多维度知识库检索。"""
    log = AgentLogger("rag_enrich", thread_id=state.get("thread_id", ""))
    matched_suppliers = state.get("matched_suppliers", [])
    normalized_spec = state.get("normalized_spec") or {}
    category = normalized_spec.get("category", "")

    if not matched_suppliers:
        state["rag_enrichment"] = {
            "supplier_reports": [],
            "citations": [],
            "summary": "无匹配供应商，跳过 RAG 深度分析",
        }
        return state

    log.start(state)

    supplier_reports = []
    all_citations: list[dict] = []

    try:
        # 懒加载 retrieve (kb 模块可选)
        try:
            from kb.rag import retrieve as _retrieve
            _retrieve_available = True
        except ImportError:
            _retrieve_available = False
            _retrieve = None
            logger.warning("kb.rag.retrieve 不可用, citations 将为空, 降级到 search_knowledge_base 文本")

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
                    if _retrieve_available:
                        # 直接调 retrieve, 保留 chunk 元数据 (#22 citations)
                        cid = _resolve_company_id(supplier_name)
                        if cid is None:
                            result_text = f"未在知识库中找到企业「{supplier_name}」"
                            chunks = []
                        else:
                            hits = _retrieve(query, company_id=cid)
                            chunks = hits[:_MAX_CITATIONS_PER_SUPPLIER] if hits else []
                            result_text = " ".join(h.get("text", "") for h in hits[:3]) if hits else (
                                f"企业「{supplier_name}」的知识库中暂未收录相关信息"
                            )
                            # 收集 citations (契约 C2)
                            for ch in chunks:
                                cit = _build_citation(ch, supplier_name)
                                if cit:
                                    all_citations.append(cit)
                    else:
                        # 降级: 仅文本, 无 citations
                        result = search_knowledge_base_tool.invoke({
                            "company_name": supplier_name,
                            "query": query,
                        })
                        result_text = str(result)[:2000] if result else "知识库中暂无相关信息"
                        chunks = []

                    supplier_report["dimensions"][dim_name] = {
                        "query": query,
                        "result": result_text[:2000] if result_text else "知识库中暂无相关信息",
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
            "citations": all_citations,
            "summary": (
                f"RAG 深度分析完成: 对 {report_count} 个供应商进行了 "
                f"{total_dimensions} 个维度的知识库检索, 透出 {len(all_citations)} 条引用"
            ),
        }
        log.end(state)

    except Exception as e:
        state.setdefault("errors", []).append(f"[rag_enrich] {str(e)[:200]}")
        state["rag_enrichment"] = {
            "supplier_reports": [],
            "citations": [],
            "summary": f"RAG 分析异常: {str(e)[:200]}",
        }
        log.fail(str(e)[:200])

    return state


# ecs_assistant 风格别名
process = rag_enrich_agent
