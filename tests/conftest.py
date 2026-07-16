"""
Agent 测试 — 所有的外部依赖 (LLM / MySQL / Neo4j / Milvus) 全部 mock
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime


# ============================================================
# Fixtures: mock 所有外部依赖
# ============================================================

@pytest.fixture(autouse=True)
def mock_external_deps():
    """全局 mock — 所有测试自动应用"""
    mock_llm = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = '{"category": "MLCC", "package": "0805", "capacitance": "10uF", "temp_coeff": "X7R", "rated_voltage": "50V", "tolerance": "±10%"}'
    mock_response.tool_calls = []  # 无工具调用，直接返回文本回复
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    patches = []
    # resilient: skip patches whose target module is not importable (e.g. langgraph missing)
    for target, kwargs in [
        ("ai.tools.mysql_client.get_engine", {}),
        ("ai.tools.neo4j_client.get_driver", {}),
        ("ai.tools.milvus_client.connect_milvus", {}),
        ("ai.base_agent.get_agent_llm", {"return_value": mock_llm}),
        ("ai.supervisor.get_supervisor_llm", {"return_value": mock_llm}),
    ]:
        try:
            patches.append(patch(target, **kwargs))
        except (ModuleNotFoundError, AttributeError, ImportError):
            pass
    for p in patches:
        try:
            p.start()
        except Exception:
            pass
    yield
    for p in patches:
        try:
            p.stop()
        except Exception:
            pass


@pytest.fixture
def sample_raw_query() -> str:
    return "TMK212BJ105KG-T 缺货，找替代，月用量50万，交期2周"


@pytest.fixture
def sample_parsed_spec() -> dict:
    return {
        "part_number": "TMK212BJ105KG-T",
        "brand": "Taiyo Yuden",
        "category": "MLCC",
        "package": "0805",
        "capacitance": "1uF",
        "tolerance": "±10%",
        "temp_coeff": "X5R",
        "rated_voltage": "10V",
        "monthly_qty": 500000,
        "lead_time_weeks": 2,
    }


@pytest.fixture
def sample_normalized_spec(sample_parsed_spec) -> dict:
    spec = dict(sample_parsed_spec)
    spec["std_code"] = "MLCC-0805-X5R-10V-105"
    spec["_mapped"] = True
    return spec


@pytest.fixture
def sample_state(sample_raw_query) -> dict:
    return {
        "messages": [],
        "thread_id": "test-001",
        "raw_query": sample_raw_query,
        "parsed_spec": None,
        "normalized_spec": None,
        "alternatives": [],
        "matched_suppliers": [],
        "rfq_doc": None,
        "rfq_id": None,
        "lead_grade": None,
        "rag_enrichment": None,
        "chat_response": None,
        "errors": [],
        "_attempted_agents": [],
        "next_agent": "chat",
        "route_reason": None,
        "user_id": "test-user",
        "started_at": datetime.now().isoformat(),
        "completed_at": None,
    }