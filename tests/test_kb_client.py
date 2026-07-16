"""
测试 RAG 桥接工具 — ai/tools/kb_client.py

search_knowledge_base 是 Agent → RAG 的单向桥梁:
  - @tool 装饰，LLM 可自主调用
  - 内部调用 kb.rag.answer() 完成 RAG 检索
  - 公司名称 → company_id 解析（含缓存）
  - 容错：kb 不可用时返回清晰提示

注意: kb_client 使用懒加载（函数内 import），patch 需指向源模块路径。
"""

import pytest
from unittest.mock import patch, MagicMock


# ── 公司名称解析测试 ────────────────────────────────────────────────

def test_resolve_company_id_exact_match():
    """精确匹配公司中文名"""
    from ai.tools.kb_client import _resolve_company_id

    mock_company = MagicMock()
    mock_company.id = 9001
    mock_company.name = "深圳芯联电子有限公司"

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = mock_company

    # kb_client 内部是 from kb.db import session_scope
    with patch("kb.db.session_scope") as mock_scope:
        mock_scope.return_value.__enter__.return_value = mock_session
        result = _resolve_company_id("深圳芯联电子有限公司")

    assert result == 9001


def test_resolve_company_id_cache_hit():
    """缓存命中：不查数据库"""
    from ai.tools.kb_client import _resolve_company_id, _company_name_cache

    _company_name_cache["测试公司"] = 9999

    result = _resolve_company_id("测试公司")
    assert result == 9999

    # 清理
    _company_name_cache.pop("测试公司", None)


def test_resolve_company_id_not_found():
    """公司不存在：返回 None"""
    from ai.tools.kb_client import _resolve_company_id

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = None

    with patch("kb.db.session_scope") as mock_scope:
        mock_scope.return_value.__enter__.return_value = mock_session
        result = _resolve_company_id("不存在的公司")

    assert result is None


def test_resolve_company_id_fuzzy_match():
    """模糊匹配：公司名包含查询串"""
    from ai.tools.kb_client import _resolve_company_id
    from sqlalchemy.orm import Query

    mock_company = MagicMock()
    mock_company.id = 9002
    mock_company.name = "深圳华强电子世界"

    mock_session = MagicMock()
    # 精确中文名 → None, 精确英文名 → None, 模糊匹配 → 命中
    mock_session.query.return_value.filter.return_value.first.side_effect = [
        None, None, mock_company,
    ]

    with patch("kb.db.session_scope") as mock_scope:
        mock_scope.return_value.__enter__.return_value = mock_session
        result = _resolve_company_id("华强电子")

    assert result == 9002


# ── search_knowledge_base 工具测试 ──────────────────────────────────

def test_search_knowledge_base_company_not_found():
    """公司不存在：返回提示信息"""
    from ai.tools.kb_client import search_knowledge_base

    with patch("ai.tools.kb_client._resolve_company_id", return_value=None):
        result = search_knowledge_base.invoke({
            "company_name": "不存在的公司",
            "query": "主营产品",
        })

    assert "未在知识库中找到" in result


def test_search_knowledge_base_success():
    """正常 RAG 检索：返回答案"""
    from ai.tools.kb_client import search_knowledge_base

    mock_rag_result = {
        "answer": "该公司主营MLCC产品，拥有IATF16949认证",
        "trace_id": "trace-001",
    }

    # kb_client 内部是 from kb.rag import answer
    with patch("ai.tools.kb_client._resolve_company_id", return_value=9001), \
         patch("kb.rag.answer", return_value=mock_rag_result):
        result = search_knowledge_base.invoke({
            "company_name": "深圳芯联电子有限公司",
            "query": "主营产品",
        })

    assert "MLCC" in result
    assert "IATF16949" in result


def test_search_knowledge_base_long_answer_truncated():
    """答案过长：截断保护"""
    from ai.tools.kb_client import search_knowledge_base

    long_answer = "A" * 2500
    mock_rag_result = {"answer": long_answer}

    with patch("ai.tools.kb_client._resolve_company_id", return_value=9001), \
         patch("kb.rag.answer", return_value=mock_rag_result):
        result = search_knowledge_base.invoke({
            "company_name": "深圳芯联电子有限公司",
            "query": "详细产品信息",
        })

    assert len(result) <= 2100  # 2000 + 截断提示
    assert "已截断" in result


def test_search_knowledge_base_rag_not_available():
    """kb.rag 模块不可用（lazy import 失败）：返回提示"""
    from ai.tools.kb_client import search_knowledge_base
    import builtins

    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "kb.rag":
            raise ImportError("No module named 'kb.rag'")
        return real_import(name, *args, **kwargs)

    with patch("ai.tools.kb_client._resolve_company_id", return_value=9001), \
         patch("builtins.__import__", side_effect=mock_import):
        result = search_knowledge_base.invoke({
            "company_name": "深圳芯联电子有限公司",
            "query": "主营产品",
        })

    assert "知识库系统当前不可用" in result


def test_search_knowledge_base_exception():
    """RAG 检索异常：返回错误提示"""
    from ai.tools.kb_client import search_knowledge_base

    with patch("ai.tools.kb_client._resolve_company_id", return_value=9001), \
         patch("kb.rag.answer", side_effect=Exception("RAG pipeline error")):
        result = search_knowledge_base.invoke({
            "company_name": "深圳芯联电子有限公司",
            "query": "主营产品",
        })

    assert "错误" in result


def test_search_knowledge_base_empty_answer():
    """RAG 返回空答案：返回提示"""
    from ai.tools.kb_client import search_knowledge_base

    with patch("ai.tools.kb_client._resolve_company_id", return_value=9001), \
         patch("kb.rag.answer", return_value=None):
        result = search_knowledge_base.invoke({
            "company_name": "深圳芯联电子有限公司",
            "query": "主营产品",
        })

    assert "暂未收录" in result


# ── 工具 schema 测试 ──────────────────────────────────────────────────

def test_search_knowledge_base_is_langchain_tool():
    """验证 search_knowledge_base 是 LangChain @tool 装饰的函数"""
    from ai.tools.kb_client import search_knowledge_base

    assert hasattr(search_knowledge_base, "invoke"), "缺少 invoke 方法"
    assert hasattr(search_knowledge_base, "name"), "缺少 name 属性"
    assert search_knowledge_base.name == "search_knowledge_base"


def test_search_knowledge_base_args_schema():
    """验证工具参数 schema 包含 company_name 和 query"""
    from ai.tools.kb_client import search_knowledge_base

    assert hasattr(search_knowledge_base, "args_schema"), "缺少 args_schema"

    schema = search_knowledge_base.args_schema
    fields = schema.model_fields if hasattr(schema, 'model_fields') else {}
    assert "company_name" in fields
    assert "query" in fields


# ── 缓存测试 ──────────────────────────────────────────────────────────

def test_company_name_cache_cleared():
    """验证缓存机制：同一公司名第二次查询走缓存"""
    from ai.tools.kb_client import _resolve_company_id, _company_name_cache

    # 清理
    _company_name_cache.clear()

    mock_company = MagicMock()
    mock_company.id = 9001

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = mock_company

    with patch("kb.db.session_scope") as mock_scope:
        mock_scope.return_value.__enter__.return_value = mock_session

        # 第一次调用：查数据库
        result1 = _resolve_company_id("测试公司")
        assert result1 == 9001
        assert "测试公司" in _company_name_cache

        # 第二次调用：走缓存，不查数据库
        result2 = _resolve_company_id("测试公司")
        assert result2 == 9001

    # 清理
    _company_name_cache.clear()