"""
测试 Agent ④.5 - RAG 深度分析 (API 层编排) + #22 引用透出

rag_enrich_agent 流程:
  1. 从 state 获取 matched_suppliers
  2. 对每个供应商进行 4 维度确定性 RAG 检索 (直接调 kb.rag.retrieve, 保留 chunk 元数据)
  3. 汇总结果写入 state.rag_enrichment
  4. 收集 citations[] 透出真实来源 (契约 C2, #22)
"""

import pytest
from unittest.mock import patch, MagicMock
from ai.agents.rag_enrich import rag_enrich_agent, _build_citation


MOCK_MATCHED_SUPPLIERS = [
    {
        "id": "1", "name": "深圳芯联电子有限公司",
        "match_score": 0.85, "category": "MLCC",
        "region": "深圳", "location": "深圳",
        "categories": ["MLCC"], "brands": ["YAGEO", "Murata"],
        "qualifications": ["IATF16949"], "moq": 10000, "lead_time_weeks": 2,
    },
    {
        "id": "2", "name": "远达供应链管理有限公司",
        "match_score": 0.72, "category": "MLCC",
        "region": "上海", "location": "上海",
        "categories": ["MLCC"], "brands": ["Samsung"],
        "qualifications": ["ISO9001"], "moq": 5000, "lead_time_weeks": 4,
    },
]

MOCK_CHUNK = {
    "chunk_id": 101,
    "chunk_uid": "chunk-uid-001",
    "company_id": 1,
    "manual_type": "product",
    "language": "zh",
    "chunk_type": "product_overview",
    "text": "该企业主营MLCC产品，拥有IATF16949认证，月产能500万颗",
    "source_type": "llm_generated",
    "confidence": 0.9,
    "score": 0.87,
}


def _mock_resolve(cid: int = 1):
    """mock _resolve_company_id 返回固定 company_id。"""
    m = MagicMock(return_value=cid)
    return m


@pytest.mark.asyncio
async def test_rag_enrich_empty_suppliers(sample_state):
    """无匹配供应商：返回空报告 + 空 citations"""
    sample_state["matched_suppliers"] = []

    result = await rag_enrich_agent(sample_state)

    enrichment = result["rag_enrichment"]
    assert enrichment["supplier_reports"] == []
    assert enrichment["citations"] == []
    assert "无匹配供应商" in enrichment["summary"]


@pytest.mark.asyncio
async def test_rag_enrich_multi_dimension_search(sample_state):
    """验证对每个供应商进行 4 维度检索 (retrieve)"""
    sample_state["matched_suppliers"] = MOCK_MATCHED_SUPPLIERS

    mock_retrieve = MagicMock(return_value=[MOCK_CHUNK])
    mock_resolve = MagicMock(side_effect=lambda name: 1 if "芯联" in name else 2)

    with patch("ai.agents.rag_enrich._resolve_company_id", mock_resolve), \
         patch("kb.rag.retrieve", mock_retrieve):
        result = await rag_enrich_agent(sample_state)

    # 2 供应商 × 4 维度 = 8 次 retrieve 调用
    assert mock_retrieve.call_count == 8
    enrichment = result["rag_enrichment"]
    assert len(enrichment["supplier_reports"]) == 2
    for report in enrichment["supplier_reports"]:
        assert len(report["dimensions"]) == 4
        assert "产品线" in report["dimensions"]


@pytest.mark.asyncio
async def test_rag_enrich_citations_emitted(sample_state):
    """#22: retrieve 命中 -> citations 透出, 含契约 C2 必需字段"""
    sample_state["matched_suppliers"] = MOCK_MATCHED_SUPPLIERS[:1]

    mock_retrieve = MagicMock(return_value=[MOCK_CHUNK])

    with patch("ai.agents.rag_enrich._resolve_company_id", MagicMock(return_value=1)):
        # _retrieve 在函数内 from kb.rag import retrieve as _retrieve, patch kb.rag.retrieve
        with patch("kb.rag.retrieve", mock_retrieve):
            result = await rag_enrich_agent(sample_state)

    enrichment = result["rag_enrichment"]
    # 每维度最多 _MAX_CITATIONS_PER_SUPPLIER=2 条, 4 维度 -> 最多 8 条 (这里每维度 1 chunk -> 4 条)
    assert len(enrichment["citations"]) == 4
    cit = enrichment["citations"][0]
    # 契约 C2 必需字段
    assert cit["doc"] == "product"
    assert cit["chunk_id"] == "101"
    assert cit["chunk_uid"] == "chunk-uid-001"
    assert cit["score"] == 0.87
    assert "MLCC" in cit["excerpt"]
    assert cit["company_id"] == 1
    assert cit["language"] == "zh"
    assert cit["supplier_name"] == "深圳芯联电子有限公司"


@pytest.mark.asyncio
async def test_rag_enrich_no_citations_when_company_unresolved(sample_state):
    """#22: company_id 解析失败 -> 无 citations, 不崩溃"""
    sample_state["matched_suppliers"] = MOCK_MATCHED_SUPPLIERS[:1]

    mock_retrieve = MagicMock(return_value=[MOCK_CHUNK])

    with patch("ai.agents.rag_enrich._resolve_company_id", MagicMock(return_value=None)), \
         patch("kb.rag.retrieve", mock_retrieve):
        result = await rag_enrich_agent(sample_state)

    enrichment = result["rag_enrichment"]
    assert enrichment["citations"] == []
    assert len(enrichment["supplier_reports"]) == 1


@pytest.mark.asyncio
async def test_rag_enrich_single_supplier_failure(sample_state):
    """单个供应商 RAG 失败不影响其他供应商"""
    sample_state["matched_suppliers"] = MOCK_MATCHED_SUPPLIERS

    call_count = 0

    def side_effect(query, company_id):
        nonlocal call_count
        call_count += 1
        if call_count > 4:  # 第二个供应商
            raise Exception("Milvus 连接超时")
        return [MOCK_CHUNK]

    mock_retrieve = MagicMock(side_effect=side_effect)

    with patch("ai.agents.rag_enrich._resolve_company_id",
               MagicMock(side_effect=lambda name: 1 if "芯联" in name else 2)), \
         patch("kb.rag.retrieve", mock_retrieve):
        result = await rag_enrich_agent(sample_state)

    enrichment = result["rag_enrichment"]
    assert len(enrichment["supplier_reports"]) == 2


@pytest.mark.asyncio
async def test_rag_enrich_summary_format(sample_state):
    """汇总摘要格式正确, 含引用数"""
    sample_state["matched_suppliers"] = MOCK_MATCHED_SUPPLIERS[:1]

    with patch("ai.agents.rag_enrich._resolve_company_id", MagicMock(return_value=1)), \
         patch("kb.rag.retrieve", MagicMock(return_value=[MOCK_CHUNK])):
        result = await rag_enrich_agent(sample_state)

    enrichment = result["rag_enrichment"]
    assert "1 个供应商" in enrichment["summary"]
    assert "4 个维度" in enrichment["summary"]
    assert "引用" in enrichment["summary"]


@pytest.mark.asyncio
async def test_rag_enrich_empty_rag_result(sample_state):
    """RAG 返回空: 无 citations, 报告仍含 4 维度"""
    sample_state["matched_suppliers"] = MOCK_MATCHED_SUPPLIERS[:1]

    with patch("ai.agents.rag_enrich._resolve_company_id", MagicMock(return_value=1)), \
         patch("kb.rag.retrieve", MagicMock(return_value=[])):
        result = await rag_enrich_agent(sample_state)

    enrichment = result["rag_enrichment"]
    assert len(enrichment["supplier_reports"]) == 1
    assert enrichment["citations"] == []
    dims = enrichment["supplier_reports"][0]["dimensions"]
    assert len(dims) == 4


@pytest.mark.asyncio
async def test_rag_enrich_no_supplier_name(sample_state):
    """供应商无名称：跳过"""
    sample_state["matched_suppliers"] = [
        {"id": "1", "name": "", "match_score": 0.5},
        {"id": "2", "name": "深圳芯联电子有限公司", "match_score": 0.8},
    ]

    with patch("ai.agents.rag_enrich._resolve_company_id", MagicMock(return_value=1)), \
         patch("kb.rag.retrieve", MagicMock(return_value=[MOCK_CHUNK])):
        result = await rag_enrich_agent(sample_state)

    enrichment = result["rag_enrichment"]
    assert len(enrichment["supplier_reports"]) == 1
    assert enrichment["supplier_reports"][0]["supplier_name"] == "深圳芯联电子有限公司"


# ============================================================
# _build_citation 单元测试
# ============================================================
class TestBuildCitation:
    def test_build_citation_full(self):
        cit = _build_citation(MOCK_CHUNK, "供应商A")
        assert cit["doc"] == "product"
        assert cit["chunk_uid"] == "chunk-uid-001"
        assert cit["score"] == 0.87
        assert cit["supplier_name"] == "供应商A"

    def test_build_citation_excerpt_truncated(self):
        long_chunk = dict(MOCK_CHUNK, text="A" * 500)
        cit = _build_citation(long_chunk, "S")
        assert len(cit["excerpt"]) <= 120

    def test_build_citation_none_for_empty(self):
        assert _build_citation({}, "S") is None
        assert _build_citation(None, "S") is None
