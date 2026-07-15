"""
RAG 管线 -- 严格 company_id 隔离。

核心:
  - Language Detection: 中文问题优先检索 zh chunk, 英文优先 en chunk (Unicode 规则)
  - Intent Classification: factual / advisory / comparison (规则 + 关键词)
  - Company Scoped Retrieval: 服务端强制 company_id == current_company_id 过滤,
    不得全库 Top-K 再让 LLM 筛选。公司隔离发生在 Retrieval 阶段。
  - Factual RAG: 严格依据召回知识回答; 无证据则拒绝, 不编造价格/参数/型号
  - Advisory RAG: 知识 + LLM 推理, 但不超出企业业务范围
  - Comparison RAG: 多公司分别检索再汇总, 不全库搜索
  - Retrieval Trace: 完整记录到 RagTrace
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any

from kb.config import KB_RAG_TOP_K, llm_available
from kb.db import session_scope
from kb.embedder import embed_text
from kb.llm_client import chat_text
from kb.models import CompanyCache, KnowledgeChunk, RagTrace
from kb.vectorstore import get_vector_store

logger = logging.getLogger("kb.rag")

_CN_RE = re.compile(r"[一-鿿]")
_EN_RE = re.compile(r"[A-Za-z]")

# 意图关键词
_FACTUAL_KEYWORDS_ZH = ["多少钱", "价格", "价格是多少", "规格", "参数", "功率", "容值", "阻值",
                        "型号", "有哪些型号", "MOQ", "起订", "交期", "交付周期", "怎么组装",
                        "安装", "封装", "容量", "频率", "电压", "尺寸", "材料", "库存", "有货"]
_FACTUAL_KEYWORDS_EN = ["price", "how much", "spec", "specification", "parameter", "model",
                        "models available", "moq", "lead time", "install", "package", "voltage",
                        "capacitance", "resistance", "frequency", "dimension", "in stock"]
_COMPARE_KEYWORDS_ZH = ["对比", "比较", "和", "与", "区别", "差异", "哪个好", "vs"]
_COMPARE_KEYWORDS_EN = ["compare", "comparison", "vs", "difference between", "versus"]


# ============================================================
# 语言检测
# ============================================================
def detect_language(text: str) -> str:
    if not text:
        return "zh"
    cn = len(_CN_RE.findall(text))
    en = len(_EN_RE.findall(text))
    return "zh" if cn >= en else "en"


# ============================================================
# 意图分类
# ============================================================
def classify_intent(query: str, company_ids: list[int] | None = None) -> str:
    q = query.lower()
    if company_ids and len(company_ids) > 1:
        # 多公司默认比较意图 (除非明确单点事实)
        for kw in _COMPARE_KEYWORDS_ZH + _COMPARE_KEYWORDS_EN:
            if kw in q:
                return "comparison"
        # 多公司 + 事实关键词仍可能比较, 但若只问单型号参数可事实
        return "comparison"
    for kw in _COMPARE_KEYWORDS_ZH + _COMPARE_KEYWORDS_EN:
        if kw in q:
            return "comparison"
    for kw in _FACTUAL_KEYWORDS_ZH:
        if kw in query:
            return "factual"
    for kw in _FACTUAL_KEYWORDS_EN:
        if kw in q:
            return "factual"
    return "advisory"


# ============================================================
# 检索 (严格公司隔离)
# ============================================================
def retrieve(
    query: str,
    company_id: int,
    language: str | None = None,
    manual_type: str | None = None,
    top_k: int = KB_RAG_TOP_K,
    extra_filter: dict | None = None,
) -> list[dict]:
    """单公司检索。服务端强制 company_id 过滤。"""
    lang = language or detect_language(query)
    emb = embed_text(query)
    store = get_vector_store()
    # 1. 优先同语言检索
    hits = store.search(
        emb,
        company_id=company_id,
        language=lang,
        manual_type=manual_type,
        top_k=top_k,
        extra_filter=extra_filter,
    )
    # 2. 若同语言不足, 补检索另一语言 (仍限同公司)
    if len(hits) < top_k // 2:
        other = "en" if lang == "zh" else "zh"
        more = store.search(
            emb,
            company_id=company_id,
            language=other,
            manual_type=manual_type,
            top_k=top_k - len(hits),
            extra_filter=extra_filter,
        )
        hits.extend(more)

    # 3. 从 Source of Truth (DB) 取完整 chunk 文本 (向量库可能不存全量文本)
    out: list[dict] = []
    with session_scope() as s:
        for h in hits:
            uid = h.get("chunk_uid")
            meta = h.get("meta", {})
            chunk = s.query(KnowledgeChunk).filter_by(chunk_uid=uid, active=True).first()
            if not chunk:
                continue
            out.append({
                "chunk_id": chunk.id,
                "chunk_uid": uid,
                "company_id": chunk.company_id,
                "manual_type": chunk.manual_type,
                "language": chunk.language,
                "chunk_type": chunk.chunk_type,
                "product_model": chunk.product_model,
                "business_type": chunk.business_type,
                "text": chunk.text,
                "source_type": chunk.source_type,
                "confidence": chunk.confidence,
                "score": h.get("score", 0.0),
            })
    return out


def retrieve_multi(
    query: str,
    company_ids: list[int],
    language: str | None = None,
    manual_type: str = "product",
    top_k: int = KB_RAG_TOP_K,
) -> dict[int, list[dict]]:
    """多公司分别检索 (比较模式)。禁止 company_id IN ALL。"""
    result: dict[int, list[dict]] = {}
    for cid in company_ids:
        result[cid] = retrieve(query, cid, language=language, manual_type=manual_type, top_k=top_k)
    return result


# ============================================================
# 回答生成
# ============================================================
def _company_name(company_id: int, lang: str = "zh") -> str:
    with session_scope() as s:
        c = s.get(CompanyCache, company_id)
        if not c:
            return f"Company#{company_id}"
        if lang == "en" and c.name_en:
            return c.name_en
        return c.name


def _build_context(hits: list[dict], lang: str) -> str:
    if not hits:
        return ""
    parts = []
    for i, h in enumerate(hits, 1):
        parts.append(f"[{i}] ({h['chunk_type']}/{h.get('product_model') or h.get('business_type') or '-'}) {h['text']}")
    return "\n\n".join(parts)


def _factual_answer(query: str, hits: list[dict], company_name: str, lang: str) -> str:
    """事实型: 严格依据召回。无证据拒绝。"""
    if not hits:
        if lang == "en":
            return f"The current enterprise knowledge base for {company_name} does not contain sufficient information to answer this question. No price, spec, or model will be fabricated."
        return f"当前企业（{company_name}）知识库中暂无足够信息支持该问题。不会编造价格、参数或型号。"

    context = _build_context(hits, lang)
    if llm_available():
        sys = (
            f"You are a strict enterprise knowledge assistant for {company_name}. "
            "Answer ONLY using the provided context. If the context does not contain the answer, "
            "say the knowledge base lacks the information. NEVER fabricate prices, specs, models, or steps."
        ) if lang == "en" else (
            f"你是 {company_name} 的企业知识助手。严格依据下方知识回答。"
            "若知识中没有答案, 明确说知识库暂无该信息。禁止编造价格、参数、型号、安装步骤。"
        )
        ans = chat_text_sync(sys, f"知识:\n{context}\n\n问题: {query}")
        if ans:
            return ans
    # 降级: 直接从召回提取最相关片段
    top = hits[0]
    if lang == "en":
        return f"According to {company_name}'s knowledge base:\n{top['text']}"
    return f"根据 {company_name} 知识库：\n{top['text']}"


def chat_text_sync(system: str, user: str) -> str | None:
    """同步包装 (RAG 回答用)。"""
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 在运行中的 loop 内 (如 FastAPI), 用线程跑
            import threading

            box: dict = {}
            def _run():
                box["r"] = asyncio.run(chat_text(system, user, heavy=False, max_tokens=800))
            t = threading.Thread(target=_run)
            t.start()
            t.join()
            return box.get("r")
    except RuntimeError:
        pass
    return asyncio.run(chat_text(system, user, heavy=False, max_tokens=800))


def _advisory_answer(query: str, hits: list[dict], company_name: str, lang: str, boundary) -> str:
    """建议型: 知识 + LLM 推理, 不超出业务范围。"""
    context = _build_context(hits, lang)
    scope = ", ".join(boundary.allowed_business_scope) if boundary else ""
    if llm_available():
        sys = (
            f"You are an enterprise business advisor for {company_name}. "
            f"Use the provided knowledge plus general reasoning. "
            f"Only recommend services within the business scope: {scope}. "
            "Do not recommend out-of-scope business."
        ) if lang == "en" else (
            f"你是 {company_name} 的企业业务顾问。结合下方知识与推理回答。"
            f"只推荐业务范围内（{scope}）的服务, 不得推荐范围外业务。"
        )
        ans = chat_text_sync(sys, f"知识:\n{context}\n\n问题: {query}")
        if ans:
            return ans
    # 降级: 基于召回知识 + 业务流程给出建议
    if hits:
        proc = next((h for h in hits if h["chunk_type"] in ("business_sop", "business_process")), None)
        if proc:
            return (f"根据 {company_name} 的业务流程建议：\n{proc['text']}\n\n"
                    f"（业务范围：{scope}）") if lang == "zh" else (
                f"Based on {company_name}'s business process:\n{proc['text']}\n\n(Business scope: {scope})")
    if lang == "en":
        return f"{company_name} can support: {scope}. Please provide your requirement details for a tailored recommendation."
    return f"{company_name} 可支持：{scope}。请提供具体需求以便给出针对性建议。"


def _comparison_answer(query: str, multi_hits: dict[int, list[dict]], company_ids: list[int], lang: str) -> str:
    """比较型: 各公司独立召回, 汇总成对比。不串公司信息。"""
    from kb.boundary import get_boundary

    sections = []
    for cid in company_ids:
        name = _company_name(cid, lang)
        hits = multi_hits.get(cid, [])
        if not hits:
            if lang == "en":
                sections.append(f"## {name}\nNo relevant product knowledge found in this company's knowledge base.")
            else:
                sections.append(f"## {name}\n该公司知识库中未检索到相关产品知识。")
            continue
        # 优先规格/价格 chunk
        pri = [h for h in hits if h["chunk_type"] in ("product_specification", "product_price", "product_overview", "product_model")]
        items = pri[:4] if pri else hits[:4]
        lines = [f"## {name}"]
        for h in items:
            tag = h.get("product_model") or h.get("chunk_type") or ""
            lines.append(f"- [{tag}] {h['text']}")
        sections.append("\n".join(lines))

    header = "Product Comparison" if lang == "en" else "产品对比"
    summary = (
        "Comparison is based solely on each company's own knowledge base. "
        "Information is not cross-attributed between companies."
    ) if lang == "en" else (
        "对比仅基于各公司自有知识库, 不相互串联归属。"
    )
    return f"# {header}\n\n{summary}\n\n" + "\n\n".join(sections)


# ============================================================
# 统一入口
# ============================================================
def answer(
    query: str,
    company_id: int | None = None,
    company_ids: list[int] | None = None,
    user_id: str | None = None,
    language: str | None = None,
) -> dict:
    """
    单公司问答 (company_id) 或多公司比较 (company_ids)。
    返回: {request_id, answer, intent, language, retrieved, trace}
    """
    request_id = str(uuid.uuid4())
    lang = language or detect_language(query)

    # 比较模式
    if company_ids and len(company_ids) >= 2:
        intent = "comparison"
        multi = retrieve_multi(query, company_ids, language=lang, manual_type="product")
        all_hits = [h for hs in multi.values() for h in hs]
        ans = _comparison_answer(query, multi, company_ids, lang)
        _save_trace(request_id, user_id, None, company_ids, query, lang, intent, all_hits, ans, "comparison-rag")
        return {
            "request_id": request_id,
            "answer": ans,
            "intent": intent,
            "language": lang,
            "retrieved": [{"company_id": cid, "count": len(hs), "chunks": [_trace_chunk(h) for h in hs[:3]]} for cid, hs in multi.items()],
            "mode": "comparison",
        }

    # 单公司
    if company_id is None:
        raise ValueError("单公司问答需提供 company_id")
    intent = classify_intent(query)
    hits = retrieve(query, company_id, language=lang, top_k=KB_RAG_TOP_K)
    company_name = _company_name(company_id, lang)

    from kb.boundary import get_boundary
    with session_scope() as s:
        c = s.get(CompanyCache, company_id)
        boundary = get_boundary(c) if c else None

    if intent == "factual":
        ans = _factual_answer(query, hits, company_name, lang)
    else:
        ans = _advisory_answer(query, hits, company_name, lang, boundary)

    model = "dashscope-qwen" if llm_available() else "local-extract"
    _save_trace(request_id, user_id, company_id, None, query, lang, intent, hits, ans, model)
    return {
        "request_id": request_id,
        "answer": ans,
        "intent": intent,
        "language": lang,
        "retrieved": [_trace_chunk(h) for h in hits[:5]],
        "mode": "single",
    }


def _trace_chunk(h: dict) -> dict:
    return {
        "chunk_id": h["chunk_id"],
        "chunk_uid": h["chunk_uid"],
        "chunk_type": h["chunk_type"],
        "product_model": h.get("product_model"),
        "business_type": h.get("business_type"),
        "score": round(h.get("score", 0.0), 4),
        "language": h["language"],
        "source_type": h["source_type"],
    }


def _save_trace(request_id, user_id, company_id, company_ids, query, lang, intent, hits, ans, model):
    try:
        with session_scope() as s:
            s.add(RagTrace(
                request_id=request_id,
                user_id=user_id,
                company_id=company_id,
                company_ids=",".join(str(c) for c in company_ids) if company_ids else None,
                query=query,
                detected_language=lang,
                query_intent=intent,
                retrieved_chunk_ids=json.dumps([h.get("chunk_id") or h.get("chunk_uid") for h in hits]),
                retrieval_scores=json.dumps([round(h.get("score", 0.0), 4) for h in hits]),
                source_types=json.dumps(list({h.get("source_type", "") for h in hits})),
                model=model,
                answer=ans,
            ))
    except Exception as e:
        logger.warning("Trace 保存失败: %s", str(e)[:120])


def get_trace(request_id: str) -> dict | None:
    with session_scope() as s:
        t = s.query(RagTrace).filter_by(request_id=request_id).first()
        if not t:
            return None
        return {
            "request_id": t.request_id,
            "user_id": t.user_id,
            "company_id": t.company_id,
            "company_ids": t.company_ids,
            "query": t.query,
            "detected_language": t.detected_language,
            "query_intent": t.query_intent,
            "retrieved_chunk_ids": json.loads(t.retrieved_chunk_ids or "[]"),
            "retrieval_scores": json.loads(t.retrieval_scores or "[]"),
            "source_types": json.loads(t.source_types or "[]"),
            "model": t.model,
            "answer": t.answer,
            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
        }
