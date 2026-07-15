"""
Phase 1 后端验证: 路由注册 + 企业上下文 + 上下游关系 + 协同问答。

覆盖:
  - main.py 注册后的 /auth /companies /chat /procure 路由可访问
  - enterprise-context 企业列表与单企业上下文
  - relationships / upstream / downstream / chat-partners
  - partner-chat 有关系可问, 无关系被拒 (403)

RAG 走降级路径 (LLM 关闭, 向量库 Local), 测试不依赖外部 LLM。
embedding 走真实 API (与种子一致, 保证检索空间匹配)。
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# 让 seed_enterprise_chain 可被导入 (scripts/ 不是包)
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import seed_enterprise_chain as seed  # noqa: E402
from api.main import create_app  # noqa: E402
from kb.db import session_scope  # noqa: E402
from kb.models import KnowledgeChunk  # noqa: E402

DEMO_TOKEN = "kb-demo-user"
AUTH_HEADERS = {"Authorization": f"Bearer {DEMO_TOKEN}"}


@pytest.fixture(scope="module", autouse=True)
def _offline_rag():
    """关闭 LLM + 强制 Local 向量库, 保证测试离线且确定性。

    不关闭 embedding (走真实 API, 与种子向量同空间, 保证检索匹配)。
    """
    with patch("kb.rag.llm_available", return_value=False), \
            patch("kb.config.milvus_available", return_value=False):
        yield


@pytest.fixture(scope="module", autouse=True)
def ensure_seed(_offline_rag):
    """幂等写入种子数据 (公司 + 关系; 知识仅首次生成)。"""
    seed.init_db()
    seed.upsert_companies()
    seed.upsert_relationships()
    with session_scope() as s:
        has_knowledge = (
            s.query(KnowledgeChunk).filter_by(company_id=9001, active=True).first() is not None
        )
    if not has_knowledge:
        try:
            seed.seed_knowledge()
        except Exception as e:
            pytest.skip(f"知识种子失败 (允许): {e}")


@pytest.fixture(scope="module")
def client(_offline_rag):
    app = create_app()
    with TestClient(app) as c:
        yield c


# ── 1. 路由注册验证 ────────────────────────────────────────────

def test_auth_route_accessible(client):
    r = client.get("/api/v1/auth/me", headers=AUTH_HEADERS)
    assert r.status_code == 200
    assert r.json()["user_id"] == "demo-user"


def test_companies_route_accessible(client):
    r = client.get("/api/v1/companies", headers=AUTH_HEADERS)
    assert r.status_code == 200
    assert "items" in r.json()


def test_chat_route_registered(client):
    # trace 不存在 -> 404, 证明路由已注册
    r = client.get("/api/v1/chat/trace/nonexistent-request-id", headers=AUTH_HEADERS)
    assert r.status_code == 404


def test_procure_route_preserved(client):
    r = client.get("/api/v1/procure/health", headers=AUTH_HEADERS)
    assert r.status_code == 200


# ── 2. 企业驾驶舱上下文 ────────────────────────────────────────

def test_enterprise_context_list(client):
    r = client.get("/api/v1/enterprise-context/companies", headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 6
    item = data["items"][0]
    for f in ("company_id", "company", "segment_code", "chain_position", "role",
              "product_count", "order_count", "shortage_count",
              "upstream_count", "downstream_count", "knowledge_status"):
        assert f in item, f"缺字段 {f}"


def test_enterprise_context_single(client):
    r = client.get("/api/v1/enterprise-context/9003", headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["company_id"] == 9003
    assert data["upstream_count"] >= 1
    assert data["downstream_count"] >= 1
    assert data["knowledge_status"] == "ready"


def test_enterprise_context_not_found(client):
    r = client.get("/api/v1/enterprise-context/99999", headers=AUTH_HEADERS)
    assert r.status_code == 404


# ── 3. 上下游关系 ──────────────────────────────────────────────

def test_relationships(client):
    r = client.get("/api/v1/companies/9003/relationships", headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    # 鼎云(9003): 上游创捷 + 下游星河 + 支撑远达 = 3 条
    assert data["total"] >= 3


def test_upstream(client):
    r = client.get("/api/v1/companies/9003/upstream", headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    partner_ids = {p["company_id"] for p in data["items"]}
    assert 9002 in partner_ids  # 创捷是鼎云的上游


def test_downstream(client):
    r = client.get("/api/v1/companies/9003/downstream", headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    partner_ids = {p["company_id"] for p in data["items"]}
    assert 9005 in partner_ids  # 星河是鼎云的下游


def test_chat_partners(client):
    r = client.get("/api/v1/companies/9003/chat-partners", headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    partner_ids = {p["company_id"] for p in data["items"]}
    # 鼎云的直接关系方: 创捷(9002) + 星河(9005) + 远达(9004)
    assert {9002, 9005, 9004}.issubset(partner_ids)


# ── 4. 上下游协同问答 ──────────────────────────────────────────

def test_partner_chat_with_relationship(client):
    # 鼎云(9003) 问 创捷(9002) - 有直接关系
    r = client.post(
        "/api/v1/companies/9003/partner-chat",
        headers=AUTH_HEADERS,
        json={"partner_company_id": 9002, "query": "你们有哪些型号产品?", "scope": "product"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["partner_company_id"] == 9002
    assert "answer" in data
    assert data["answer"]  # 非空


def test_partner_chat_scope_business(client):
    # 鼎云(9003) 问 创捷(9002) business 范围
    r = client.post(
        "/api/v1/companies/9003/partner-chat",
        headers=AUTH_HEADERS,
        json={"partner_company_id": 9002, "query": "你们提供哪些业务?", "scope": "business"},
    )
    assert r.status_code == 200
    assert r.json()["answer"]


def test_partner_chat_without_relationship(client):
    # 毅诚(9006) 问 星河(9005) - 无直接关系
    r = client.post(
        "/api/v1/companies/9006/partner-chat",
        headers=AUTH_HEADERS,
        json={"partner_company_id": 9005, "query": "hello", "scope": "product"},
    )
    assert r.status_code == 403


def test_partner_chat_partner_not_found(client):
    r = client.post(
        "/api/v1/companies/9003/partner-chat",
        headers=AUTH_HEADERS,
        json={"partner_company_id": 99999, "query": "hello", "scope": "product"},
    )
    assert r.status_code == 404
