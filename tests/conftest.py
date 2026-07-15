"""
Agent 测试 — 所有的外部依赖 (LLM / MySQL / Neo4j / Milvus) 全部 mock
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime


# ============================================================
# Fixtures: mock 所有外部依赖
# ============================================================

@pytest.fixture(autouse=True)
def mock_external_deps():
    """全局 mock — 所有测试自动应用"""
    patches = [
        # 不实际连接任何外部服务
        patch("ai.tools.mysql_client.get_engine"),
        patch("ai.tools.neo4j_client.get_driver"),
        patch("ai.tools.milvus_client.connect_milvus"),
        # 不实际调 LLM
        patch("ai.agents.parse.ChatOpenAI"),
        patch("ai.agents.alternatives.ChatOpenAI"),
    ]
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()


@pytest.fixture
def mock_llm_response():
    """mock LLM 返回固定 JSON"""
    mock_llm = MagicMock()
    mock_llm.content = '{"category": "MLCC", "package": "0805", "capacitance": "10uF", "temp_coeff": "X7R", "rated_voltage": "50V", "tolerance": "±10%"}'
    return mock_llm


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
    from ai.state import ProcureState
    return ProcureState(
        thread_id="test-001",
        raw_query=sample_raw_query,
        parsed_spec=None,
        normalized_spec=None,
        alternatives=[],
        matched_suppliers=[],
        rfq_doc=None,
        rfq_id=None,
        lead_grade=None,
        errors=[],
        started_at=datetime.now().isoformat(),
        completed_at=None,
    )