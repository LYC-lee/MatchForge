"""
测试 Agent ④.5 — RAG 深度分析 (API 层编排)

rag_enrich_agent 流程:
  1. 从 state 获取 matched_suppliers
  2. 对每个供应商进行 4 维度确定性 RAG 检索
  3. 汇总结果写入 state.rag_enrichment
"""

import pytest
from unittest.mock import patch, MagicMock
from ai.agents.rag_enrich import rag_enrich_agent


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

MOCK_RAG_RESULT = "该企业主营MLCC产品，拥有IATF16949认证，月产能500万颗，主要客户包括华为、小米等"


@pytest.mark.asyncio
async def test_rag_enrich_empty_suppliers(sample_state):
    """无匹配供应商：返回空报告"""
    sample_state["matched_suppliers"] = []

    result = await rag_enrich_agent(sample_state)

    enrichment = result["rag_enrichment"]
    assert enrichment["supplier_reports"] == []
    assert "无匹配供应商" in enrichment["summary"]


@pytest.mark.asyncio
async def test_rag_enrich_multi_dimension_search(sample_state):
    """验证对每个供应商进行 4 维度检索"""
    sample_state["matched_suppliers"] = MOCK_MATCHED_SUPPLIERS

    mock_rag = MagicMock()
    mock_rag.invoke = MagicMock(return_value=MOCK_RAG_RESULT)

    with patch("ai.agents.rag_enrich.search_knowledge_base_tool", mock_rag):
        result = await rag_enrich_agent(sample_state)

    # 2 个供应商 × 4 个维度 = 8 次 RAG 调用
    assert mock_rag.invoke.call_count == 8

    enrichment = result["rag_enrichment"]
    assert len(enrichment["supplier_reports"]) == 2

    # 验证每个供应商报告包含 4 个维度
    for report in enrichment["supplier_reports"]:
        assert "dimensions" in report
        assert len(report["dimensions"]) == 4
        assert "产品线" in report["dimensions"]
        assert "认证资质" in report["dimensions"]
        assert "业务能力" in report["dimensions"]
        assert "技术能力" in report["dimensions"]


@pytest.mark.asyncio
async def test_rag_enrich_single_supplier_failure(sample_state):
    """单个供应商 RAG 失败不影响其他供应商"""
    sample_state["matched_suppliers"] = MOCK_MATCHED_SUPPLIERS

    mock_rag = MagicMock()
    # 第一个供应商的 RAG 调用正常（4次），第二个供应商第一次调用就失败
    call_count = 0

    def side_effect(input_dict):
        nonlocal call_count
        call_count += 1
        if call_count > 4:  # 第二个供应商
            raise Exception("Milvus 连接超时")
        return MOCK_RAG_RESULT

    mock_rag.invoke = MagicMock(side_effect=side_effect)

    with patch("ai.agents.rag_enrich.search_knowledge_base_tool", mock_rag):
        result = await rag_enrich_agent(sample_state)

    enrichment = result["rag_enrichment"]
    # 两个供应商都有报告
    assert len(enrichment["supplier_reports"]) == 2


@pytest.mark.asyncio
async def test_rag_enrich_summary_format(sample_state):
    """验证汇总摘要格式正确"""
    sample_state["matched_suppliers"] = MOCK_MATCHED_SUPPLIERS[:1]

    mock_rag = MagicMock()
    mock_rag.invoke = MagicMock(return_value=MOCK_RAG_RESULT)

    with patch("ai.agents.rag_enrich.search_knowledge_base_tool", mock_rag):
        result = await rag_enrich_agent(sample_state)

    enrichment = result["rag_enrichment"]
    assert "1 个供应商" in enrichment["summary"]
    assert "4 个维度" in enrichment["summary"]


@pytest.mark.asyncio
async def test_rag_enrich_empty_rag_result(sample_state):
    """RAG 返回空结果：标注为无相关信息"""
    sample_state["matched_suppliers"] = MOCK_MATCHED_SUPPLIERS[:1]

    mock_rag = MagicMock()
    mock_rag.invoke = MagicMock(return_value="企业「某供应商」的知识库中暂未收录相关信息")

    with patch("ai.agents.rag_enrich.search_knowledge_base_tool", mock_rag):
        result = await rag_enrich_agent(sample_state)

    enrichment = result["rag_enrichment"]
    assert len(enrichment["supplier_reports"]) == 1
    # 空结果也应该在报告中
    dims = enrichment["supplier_reports"][0]["dimensions"]
    assert len(dims) == 4


@pytest.mark.asyncio
async def test_rag_enrich_exception_handling(sample_state):
    """整体异常不中断流程"""
    sample_state["matched_suppliers"] = MOCK_MATCHED_SUPPLIERS[:1]

    mock_rag = MagicMock()
    mock_rag.invoke = MagicMock(side_effect=Exception("RAG 系统不可用"))

    with patch("ai.agents.rag_enrich.search_knowledge_base_tool", mock_rag):
        result = await rag_enrich_agent(sample_state)

    # 应该标记为异常但不崩溃
    enrichment = result["rag_enrichment"]
    assert enrichment is not None
    assert "supplier_reports" in enrichment


@pytest.mark.asyncio
async def test_rag_enrich_no_supplier_name(sample_state):
    """供应商无名称：跳过"""
    sample_state["matched_suppliers"] = [
        {"id": "1", "name": "", "match_score": 0.5},
        {"id": "2", "name": "深圳芯联电子有限公司", "match_score": 0.8},
    ]

    mock_rag = MagicMock()
    mock_rag.invoke = MagicMock(return_value=MOCK_RAG_RESULT)

    with patch("ai.agents.rag_enrich.search_knowledge_base_tool", mock_rag):
        result = await rag_enrich_agent(sample_state)

    # 只有有名称的供应商被检索
    enrichment = result["rag_enrichment"]
    assert len(enrichment["supplier_reports"]) == 1
    assert enrichment["supplier_reports"][0]["supplier_name"] == "深圳芯联电子有限公司"