"""
测试 Agent ④ - 供应商匹配 (确定性 MySQL -> RAG -> 程序化评分)

重构后的 match_agent 流程 (已确定性化, 不再调用 LLM):
  1. filter_suppliers_raw() 程序化查询 MySQL
  2. search_knowledge_base.invoke() 对每个供应商确定性 RAG 检索
  3. 阶段4: 程序化计算 match_score (brand_score*0.7 + location_score + rag_score + 0.1)
     按 match_score 降序排列

本测试针对确定性实现验证, 不再 mock run_direct_agent (实现里不存在该调用)。
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from ai.agents.match import match_agent


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


def _row(d: dict):
    """构造一个 behaves-like-RowMapping 的 dict (match_agent 用 dict(row) 序列化)。"""
    return dict(d)


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

    with patch("ai.agents.match.filter_suppliers_raw",
               return_value=[_row(s) for s in MOCK_SUPPLIERS]), \
         patch("ai.agents.match.search_knowledge_base_tool", mock_rag):
        await match_agent(sample_state)

    # 验证每个供应商都被调用了 RAG
    assert mock_rag.invoke.call_count == len(MOCK_SUPPLIERS)
    for supplier in MOCK_SUPPLIERS:
        mock_rag.invoke.assert_any_call({
            "company_name": supplier["name"],
            "query": "主营产品、认证资质、MLCC产品线、业务能力",
        })


@pytest.mark.asyncio
async def test_match_agent_score_calculation(sample_state, sample_normalized_spec):
    """确定性评分: 品牌全覆盖 > 品牌部分覆盖; RAG 命中加分; 按降序排列。

    sample_normalized_spec brand_pref 为空, 但 alternatives 为空 -> brand_pref 仍为空,
    brand_score=0。此处手动注入 brand_pref 验证品牌覆盖度逻辑。
    """
    sample_state["normalized_spec"] = {**sample_normalized_spec, "brand_pref": ["YAGEO", "Murata"]}

    mock_rag = MagicMock()
    mock_rag.invoke = MagicMock(return_value=MOCK_RAG_RESULT)

    with patch("ai.agents.match.filter_suppliers_raw",
               return_value=[_row(s) for s in MOCK_SUPPLIERS]), \
         patch("ai.agents.match.search_knowledge_base_tool", mock_rag):
        result = await match_agent(sample_state)

    suppliers = result["matched_suppliers"]
    assert len(suppliers) == 2
    # 供应商1 品牌全覆盖 (YAGEO+Murata), 供应商2 无覆盖 -> 供应商1 分更高
    s1 = next(s for s in suppliers if s["id"] == "1")
    s2 = next(s for s in suppliers if s["id"] == "2")
    assert s1["match_score"] > s2["match_score"]
    # 降序排列
    assert suppliers[0]["match_score"] >= suppliers[1]["match_score"]
    # 供应商1 品牌覆盖分 = 2/2 = 1.0, 贡献 0.7; +RAG 0.05 + 基础 0.1 = 0.85
    assert s1["match_score"] == 0.85


@pytest.mark.asyncio
async def test_match_agent_confirmed_flags(sample_state, sample_normalized_spec):
    """红线: 库存/交期/价格一律标未确认 (confirmed_* = False)"""
    sample_state["normalized_spec"] = sample_normalized_spec

    mock_rag = MagicMock()
    mock_rag.invoke = MagicMock(return_value=MOCK_RAG_RESULT)

    with patch("ai.agents.match.filter_suppliers_raw",
               return_value=[_row(s) for s in MOCK_SUPPLIERS]), \
         patch("ai.agents.match.search_knowledge_base_tool", mock_rag):
        result = await match_agent(sample_state)

    for sup in result["matched_suppliers"]:
        assert sup["confirmed_stock"] is False
        assert sup["confirmed_lead"] is False
        assert sup["confirmed_price"] is False
        assert sup["in_stock"] is False


@pytest.mark.asyncio
async def test_match_agent_rag_failure_graceful(sample_state, sample_normalized_spec):
    """单个供应商 RAG 失败不影响整体流程, 该供应商 rag_insights 含异常提示"""
    sample_state["normalized_spec"] = sample_normalized_spec

    mock_rag = MagicMock()
    mock_rag.invoke = MagicMock(side_effect=[
        MOCK_RAG_RESULT,
        Exception("Milvus 连接超时"),
    ])

    with patch("ai.agents.match.filter_suppliers_raw",
               return_value=[_row(s) for s in MOCK_SUPPLIERS]), \
         patch("ai.agents.match.search_knowledge_base_tool", mock_rag):
        result = await match_agent(sample_state)

    # 流程不中断, 仍有结果
    assert len(result["matched_suppliers"]) == 2
    # 第二个供应商 RAG 异常 -> rag_insights 含异常说明, 且 rag_score=0
    s2 = next(s for s in result["matched_suppliers"] if s["id"] == "2")
    assert "异常" in s2["rag_insights"]


@pytest.mark.asyncio
async def test_match_agent_empty_rag_no_score_boost(sample_state, sample_normalized_spec):
    """RAG 返回"未在知识库中找到"时不应加分 (对应 kb_client 实际文案)。

    回归: 旧实现判 `"未找到" not in rag`, 而 kb_client 实际返回"未在知识库中找到",
    导致未命中也加 0.05。修复后 rag_score 应为 0。
    """
    sample_state["normalized_spec"] = sample_normalized_spec

    mock_rag = MagicMock()
    # kb_client 实际返回的"无结果"文案
    mock_rag.invoke = MagicMock(
        return_value="未在知识库中找到企业「某供应商」的相关记录。")

    with patch("ai.agents.match.filter_suppliers_raw",
               return_value=[_row(MOCK_SUPPLIERS[0])]), \
         patch("ai.agents.match.search_knowledge_base_tool", mock_rag):
        result = await match_agent(sample_state)

    sup = result["matched_suppliers"][0]
    # brand_pref 为空 -> brand_score=0; location 空 -> 0; rag 未命中 -> 0; 仅基础 0.1
    assert sup["match_score"] == 0.1


@pytest.mark.asyncio
async def test_match_agent_exception_handling(sample_state, sample_normalized_spec):
    """filter_suppliers_raw 抛异常 -> 不中断流程，返回空列表"""
    sample_state["normalized_spec"] = sample_normalized_spec

    with patch("ai.agents.match.filter_suppliers_raw",
               side_effect=Exception("MySQL 连接失败")):
        result = await match_agent(sample_state)

    assert result["matched_suppliers"] == []
    has_error = any("match" in e for e in result.get("errors", []))
    assert has_error


@pytest.mark.asyncio
async def test_match_agent_output_format(sample_state, sample_normalized_spec):
    """匹配成功: 输出格式与前端 Supplier 对齐"""
    sample_state["normalized_spec"] = sample_normalized_spec

    mock_rag = MagicMock()
    mock_rag.invoke = MagicMock(return_value=MOCK_RAG_RESULT)

    with patch("ai.agents.match.filter_suppliers_raw",
               return_value=[_row(MOCK_SUPPLIERS[0])]), \
         patch("ai.agents.match.search_knowledge_base_tool", mock_rag):
        result = await match_agent(sample_state)

    sup = result["matched_suppliers"][0]
    assert sup["name"] == "深圳芯联电子有限公司"
    assert isinstance(sup["match_score"], (int, float))
    assert "rag_insights" in sup
    assert sup["brands"] == ["YAGEO", "Murata"]
