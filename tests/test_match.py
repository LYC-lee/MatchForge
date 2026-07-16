"""
测试 Agent ④ — 供应商匹配 (确定性 MySQL → RAG → LLM 评分)

重构后的 match_agent 流程:
  1. filter_suppliers_raw() 程序化查询 MySQL
  2. search_knowledge_base.invoke() 对每个供应商确定性 RAG 检索
  3. run_direct_agent() LLM 评分排序
"""

import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock, call
from ai.agents.match import match_agent


def _mock_run_direct_agent(return_content: dict | list):
    """构造 run_direct_agent 的 mock 返回值。"""
    mock_msg = MagicMock()
    mock_msg.content = json.dumps(return_content, ensure_ascii=False)
    return AsyncMock(return_value={"messages": [mock_msg], "next_agent": None})


MOCK_SUPPLIERS = [
    {
        "id": "1", "name": "深圳芯联电子有限公司",
        "category": "MLCC", "brands": ["YAGEO", "Murata"],
        "location": "深圳", "moq": 10000, "lead_time_weeks": 2,
        "data_source": "平台数据", "updated_at": "2026-07-10",
    },
    {
        "id": "2", "name": "远达供应链管理有限公司",
        "category": "MLCC", "brands": ["Samsung"],
        "location": "上海", "moq": 5000, "lead_time_weeks": 4,
        "data_source": "平台数据", "updated_at": "2026-07-15",
    },
]

MOCK_RAG_RESULT = "主营MLCC产品线，拥有IATF16949认证，原厂授权代理YAGEO和Murata品牌，月产能500万颗"


@pytest.mark.asyncio
async def test_match_agent_empty_spec(sample_state):
    """没有 normalized_spec：返回空列表"""
    sample_state["normalized_spec"] = None
    result = await match_agent(sample_state)
    assert result["matched_suppliers"] == []


@pytest.mark.asyncio
async def test_match_agent_no_suppliers_from_db(sample_state, sample_normalized_spec):
    """MySQL 查询无结果：返回空列表"""
    sample_state["normalized_spec"] = sample_normalized_spec

    with patch("ai.agents.match.filter_suppliers_raw", return_value=[]):
        result = await match_agent(sample_state)

    assert result["matched_suppliers"] == []


@pytest.mark.asyncio
async def test_match_agent_rag_called_for_each_supplier(sample_state, sample_normalized_spec):
    """验证对每个供应商都确定性调用了 RAG"""
    sample_state["normalized_spec"] = sample_normalized_spec

    mock_rag = MagicMock()
    mock_rag.invoke = MagicMock(return_value=MOCK_RAG_RESULT)

    with patch("ai.agents.match.filter_suppliers_raw", return_value=MOCK_SUPPLIERS), \
         patch("ai.agents.match.search_knowledge_base_tool", mock_rag), \
         patch("ai.agents.match.agent_engine.run_direct_agent",
               _mock_run_direct_agent({"matched_suppliers": []})):
        await match_agent(sample_state)

    # 验证每个供应商都被调用了 RAG
    assert mock_rag.invoke.call_count == len(MOCK_SUPPLIERS)
    for supplier in MOCK_SUPPLIERS:
        mock_rag.invoke.assert_any_call({
            "company_name": supplier["name"],
            "query": "主营产品、认证资质、MLCC产品线、业务能力",
        })


@pytest.mark.asyncio
async def test_match_agent_rag_failure_graceful(sample_state, sample_normalized_spec):
    """单个供应商 RAG 失败不影响整体流程"""
    sample_state["normalized_spec"] = sample_normalized_spec

    mock_rag = MagicMock()
    # 第一个供应商 RAG 正常，第二个抛异常
    mock_rag.invoke = MagicMock(side_effect=[
        MOCK_RAG_RESULT,
        Exception("Milvus 连接超时"),
    ])

    llm_output = {
        "matched_suppliers": [{
            "id": "1", "name": "深圳芯联电子有限公司",
            "match_score": 0.85, "category": "MLCC",
            "region": "深圳", "location": "深圳",
            "categories": ["MLCC"], "brands": ["YAGEO", "Murata"],
            "qualifications": ["IATF16949"], "moq": 10000, "lead_time_weeks": 2,
            "in_stock": False, "response_speed": "48h 内首次响应",
            "data_source": "平台数据", "updated_at": "2026-07-10",
            "confirmed_stock": False, "confirmed_lead": False, "confirmed_price": False,
            "rag_insights": "IATF16949认证",
        }]
    }

    with patch("ai.agents.match.filter_suppliers_raw", return_value=MOCK_SUPPLIERS), \
         patch("ai.agents.match.search_knowledge_base_tool", mock_rag), \
         patch("ai.agents.match.agent_engine.run_direct_agent",
               _mock_run_direct_agent(llm_output)):
        result = await match_agent(sample_state)

    # 流程不中断，仍有结果
    assert len(result["matched_suppliers"]) == 1


@pytest.mark.asyncio
async def test_match_agent_formatted_output(sample_state, sample_normalized_spec):
    """匹配成功：输出格式与前端 Supplier 对齐"""
    sample_state["normalized_spec"] = sample_normalized_spec

    llm_output = {
        "matched_suppliers": [{
            "id": "1",
            "name": "深圳芯联电子有限公司",
            "match_score": 0.85,
            "category": "MLCC",
            "region": "深圳",
            "location": "深圳",
            "categories": ["MLCC"],
            "brands": ["YAGEO", "Murata"],
            "qualifications": ["IATF16949", "ISO9001"],
            "moq": 10000,
            "lead_time_weeks": 2,
            "in_stock": False,
            "response_speed": "48h 内首次响应",
            "data_source": "平台数据",
            "updated_at": "2026-07-10",
            "confirmed_stock": False,
            "confirmed_lead": False,
            "confirmed_price": False,
            "rag_insights": "IATF16949认证，原厂授权，月产能500万颗",
        }]
    }

    mock_rag = MagicMock()
    mock_rag.invoke = MagicMock(return_value=MOCK_RAG_RESULT)

    with patch("ai.agents.match.filter_suppliers_raw", return_value=MOCK_SUPPLIERS[:1]), \
         patch("ai.agents.match.search_knowledge_base_tool", mock_rag), \
         patch("ai.agents.match.agent_engine.run_direct_agent",
               _mock_run_direct_agent(llm_output)):
        result = await match_agent(sample_state)

    suppliers = result["matched_suppliers"]
    assert len(suppliers) == 1
    assert suppliers[0]["name"] == "深圳芯联电子有限公司"
    assert suppliers[0]["confirmed_stock"] is False
    assert suppliers[0]["confirmed_lead"] is False
    assert suppliers[0]["confirmed_price"] is False
    assert isinstance(suppliers[0]["match_score"], (int, float))
    # 验证 RAG 洞察被保留
    assert "rag_insights" in suppliers[0]


@pytest.mark.asyncio
async def test_match_agent_empty_rag_result(sample_state, sample_normalized_spec):
    """RAG 返回空结果（知识库中无该供应商）"""
    sample_state["normalized_spec"] = sample_normalized_spec

    mock_rag = MagicMock()
    mock_rag.invoke = MagicMock(return_value="企业「某供应商」的知识库中暂未收录相关信息")

    llm_output = {
        "matched_suppliers": [{
            "id": "1", "name": "深圳芯联电子有限公司",
            "match_score": 0.60, "category": "MLCC",
            "region": "深圳", "location": "深圳",
            "categories": ["MLCC"], "brands": ["YAGEO"],
            "qualifications": [], "moq": 10000, "lead_time_weeks": 2,
            "in_stock": False, "response_speed": "暂无数据",
            "data_source": "平台数据", "updated_at": "2026-07-10",
            "confirmed_stock": False, "confirmed_lead": False, "confirmed_price": False,
            "rag_insights": "",
        }]
    }

    with patch("ai.agents.match.filter_suppliers_raw", return_value=MOCK_SUPPLIERS[:1]), \
         patch("ai.agents.match.search_knowledge_base_tool", mock_rag), \
         patch("ai.agents.match.agent_engine.run_direct_agent",
               _mock_run_direct_agent(llm_output)):
        result = await match_agent(sample_state)

    # 即使 RAG 为空，也不影响流程
    assert len(result["matched_suppliers"]) == 1


@pytest.mark.asyncio
async def test_match_agent_parse_failure(sample_state, sample_normalized_spec):
    """LLM 返回非 JSON → 空列表，不崩溃"""
    sample_state["normalized_spec"] = sample_normalized_spec

    mock_rag = MagicMock()
    mock_rag.invoke = MagicMock(return_value="")

    mock_msg = MagicMock()
    mock_msg.content = "无法解析的文本"
    mock_run = AsyncMock(return_value={"messages": [mock_msg], "next_agent": None})

    with patch("ai.agents.match.filter_suppliers_raw", return_value=MOCK_SUPPLIERS[:1]), \
         patch("ai.agents.match.search_knowledge_base_tool", mock_rag), \
         patch("ai.agents.match.agent_engine.run_direct_agent", mock_run):
        result = await match_agent(sample_state)

    assert result["matched_suppliers"] == []


@pytest.mark.asyncio
async def test_match_agent_exception_handling(sample_state, sample_normalized_spec):
    """filter_suppliers_raw 抛异常 → 不中断流程，返回空列表"""
    sample_state["normalized_spec"] = sample_normalized_spec

    with patch("ai.agents.match.filter_suppliers_raw",
               side_effect=Exception("MySQL 连接失败")):
        result = await match_agent(sample_state)

    assert result["matched_suppliers"] == []
    has_error = any("match" in e for e in result.get("errors", []))
    assert has_error


@pytest.mark.asyncio
async def test_match_agent_enriched_data_passed_to_llm(sample_state, sample_normalized_spec):
    """验证 RAG 检索结果被注入到 LLM 评分上下文中"""
    sample_state["normalized_spec"] = sample_normalized_spec

    mock_rag = MagicMock()
    mock_rag.invoke = MagicMock(return_value="IATF16949认证，原厂授权Murata")

    captured_context = None

    async def capture_run_direct_agent(state, system_prompt, heavy):
        nonlocal captured_context
        captured_context = state["messages"][0]["content"]
        mock_msg = MagicMock()
        mock_msg.content = json.dumps({"matched_suppliers": []})
        return {"messages": [mock_msg], "next_agent": None}

    with patch("ai.agents.match.filter_suppliers_raw", return_value=MOCK_SUPPLIERS[:1]), \
         patch("ai.agents.match.search_knowledge_base_tool", mock_rag), \
         patch("ai.agents.match.agent_engine.run_direct_agent",
               side_effect=capture_run_direct_agent):
        await match_agent(sample_state)

    # 验证 LLM 上下文包含 RAG 检索结果
    assert "rag_insight" in captured_context
    assert "IATF16949" in captured_context