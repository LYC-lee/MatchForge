"""
P0-01 链路级测试: AI 寻源 -> 真实 RFQ / 供应商线索闭环。

验证断点已打通:
  - AI 链路产出 matched_suppliers (含 match_score) + lead_grade + rfq_doc + rfq_id
  - 前端用 AI 产物调 POST /rfqs (candidate_details + lead_grade) -> kb_rfqs 有真实记录
  - kb_rfq_suppliers 的 match_score / match_reason 非空 (不再是孤儿 NULL)
  - RfqRecord.context_json 含 lead_grade
  - POST /rfqs/{id}/send -> GET /suppliers/{cid}/leads 可查到 sent 线索
  - GET /rfqs/{id}/quote-comparison 可读 (空报价也不报错)
  - 兼容: 纯 supplier_candidates: list[int] 仍工作 (score/reason 为 null)
  - ID 统一: 后端返回 RfqRecord.id / rfq_number, 非内存 MF- ID

复用 conftest 的 mock_external_deps (autouse); 额外关闭 LLM/Milvus 保证离线。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# scripts/ 不是包, 加入 sys.path 以复用 seed 脚本
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import seed_rfq_supplier_loop as rfq_seed  # noqa: E402
from api.main import create_app  # noqa: E402
from ai.agents.gen_rfq import gen_rfq_agent  # noqa: E402
from ai.agents.grade import grade_agent  # noqa: E402

DEMO_TOKEN = "kb-demo-user"
AUTH = {"Authorization": f"Bearer {DEMO_TOKEN}"}

# 买方 9003, 候选供应商 9002 / 9006 (seed_rfq_supplier_loop 已 upsert)
BUYER = 9003
SUP_A = 9002
SUP_B = 9006


@pytest.fixture(scope="module", autouse=True)
def _offline_rag():
    with patch("kb.rag.llm_available", return_value=False), \
            patch("kb.config.milvus_available", return_value=False):
        yield


@pytest.fixture(scope="module", autouse=True)
def _ensure_data(_offline_rag):
    """幂等写入: 6 家企业 + RFQ 闭环种子。"""
    import seed_enterprise_chain as chain
    chain.init_db()
    chain.upsert_companies()
    chain.upsert_relationships()
    rfq_seed.seed()


@pytest.fixture(scope="module")
def client(_ensure_data):
    app = create_app()
    with TestClient(app) as c:
        yield c


# ── AI 产物构造 (跑 gen_rfq + grade, 模拟寻源链路末端 state) ──────────

def _build_ai_state() -> dict:
    """构造一个跑完 match 后的 ProcureState, 喂给 gen_rfq + grade。"""
    return {
        "messages": [],
        "thread_id": "ai-loop-test",
        "raw_query": "DDR5 16GB 内存条 缺货, 月用量1000, 交期2周",
        "parsed_spec": {
            "category": "DDR5",
            "part_number": "DDR5-16GB",
            "package": "UDIMM",
            "monthly_qty": 1000,
            "lead_time_weeks": 2,
        },
        "normalized_spec": {
            "category": "DDR5",
            "part_number": "DDR5-16GB",
            "package": "UDIMM",
            "monthly_qty": 1000,
            "lead_time_weeks": 2,
            "std_code": "DDR5-16GB-UDIMM",
            "_mapped": True,
        },
        "alternatives": [
            {"part_number": "DDR5-16GB-A", "part_name": "DDR5 16GB 替代A",
             "brand": "BrandA", "level": "L3"},
        ],
        # match_agent 产出的内存结构 (含 match_score)
        "matched_suppliers": [
            {"id": str(SUP_A), "name": "供应商A", "match_score": 0.85,
             "category": "内存", "region": "华南", "location": "深圳",
             "brands": ["BrandA"], "brand_coverage": "BrandA",
             "rag_insights": "有 DDR5 产线"},
            {"id": str(SUP_B), "name": "供应商B", "match_score": 0.62,
             "category": "内存", "region": "华东", "location": "上海",
             "brands": [], "brand_coverage": "",
             "rag_insights": ""},
        ],
        "rfq_doc": None,
        "rfq_id": None,
        "lead_grade": None,
        "rag_enrichment": None,
        "chat_response": None,
        "errors": [],
        "_attempted_agents": [],
        "next_agent": "gen_rfq",
        "route_reason": None,
        "user_id": "ai-loop-user",
    }


def _run_ai_agents() -> dict:
    """跑 gen_rfq + grade, 返回末端 state (含 rfq_doc/rfq_id/lead_grade/matched_suppliers)。"""
    state = _build_ai_state()
    state = asyncio.run(gen_rfq_agent(state))
    state = asyncio.run(grade_agent(state))
    return state


def test_ai_agents_produce_rfq_and_grade():
    """AI 链路末端: gen_rfq 产 rfq_doc/rfq_id (内存), grade 产 lead_grade。"""
    state = _run_ai_agents()
    assert state["rfq_doc"], "gen_rfq 应产出 rfq_doc"
    assert state["rfq_id"], "gen_rfq 应产出内存 rfq_id"
    assert state["rfq_id"].startswith("MF-"), "内存 rfq_id 应为 MF- 前缀"

    assert state["lead_grade"] is not None
    assert "grade" in state["lead_grade"]
    assert "score" in state["lead_grade"]
    # match_score 仍在内存 matched_suppliers 里 (尚未落库)
    assert state["matched_suppliers"][0]["match_score"] == 0.85


# ── AI 产物 -> 真实 POST /rfqs (candidate_details + lead_grade) ──────────

def test_ai_rfq_persists_with_match_score_and_grade(client):
    """AI 产物桥接到 POST /rfqs: match_score/match_reason 落 link, lead_grade 落 context。"""
    state = _run_ai_agents()

    # 模拟前端 sendRfqToBackend 的 payload 构造
    candidate_details = [
        {"supplier_company_id": int(s["id"]),
         "match_score": s["match_score"],
         "match_reason": f"品牌覆盖:{s.get('brand_coverage','')} | 知识匹配:{s.get('rag_insights','')[:80]}"}
        for s in state["matched_suppliers"]
    ]
    payload = {
        "buyer_company_id": BUYER,
        "title": "AI寻源-DDR5内存采购",
        "part_number": "DDR5-16GB",
        "part_name": "DDR5 16GB",
        "quantity": 1000,
        "unit": "条",
        "lead_time_days": 14,
        "accept_alternatives": True,
        "scenario": "sourcing",
        "raw_query": state["raw_query"],
        "candidate_details": candidate_details,
        "lead_grade": state["lead_grade"],
    }

    resp = client.post("/api/v1/rfqs", headers=AUTH, json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    rfq = data["rfq"]

    # 真实 DB 记录, 非内存 ID
    assert rfq["rfq_number"].startswith("RFQ-")
    assert isinstance(rfq["id"], int)
    assert rfq["status"] == "draft"

    # lead_grade 落 context_json
    assert "lead_grade" in rfq["context"]
    assert rfq["context"]["lead_grade"]["grade"] == state["lead_grade"]["grade"]

    # match_score / match_reason 落 supplier leads (不再是孤儿 NULL)
    leads = data["supplier_leads"]
    assert len(leads) == 2
    by_supplier = {lk["supplier_company_id"]: lk for lk in leads}
    assert by_supplier[SUP_A]["match_score"] == 0.85
    assert by_supplier[SUP_A]["match_reason"]  # 非空
    assert by_supplier[SUP_B]["match_score"] == 0.62
    assert all(lk["status"] == "pending" for lk in leads)

    # 返回 rfq_id 供后续测试用 (但 pytest 不消费返回值, 仅辅助阅读)
    _ = rfq["id"]


def test_full_loop_send_leads_and_comparison(client):
    """完整链路: AI 产物 -> 创建 -> send -> 供应商线索可见 -> 报价对比可读。"""
    # 1. AI 产物创建 RFQ
    state = _run_ai_agents()
    candidate_details = [
        {"supplier_company_id": int(s["id"]), "match_score": s["match_score"]}
        for s in state["matched_suppliers"]
    ]
    create = client.post("/api/v1/rfqs", headers=AUTH, json={
        "buyer_company_id": BUYER,
        "title": "AI寻源-闭环测试",
        "quantity": 500,
        "candidate_details": candidate_details,
        "lead_grade": state["lead_grade"],
    })
    assert create.status_code == 200, create.text
    rfq_id = create.json()["rfq"]["id"]

    # 2. 发送 -> 生成 supplier leads
    send = client.post(f"/api/v1/rfqs/{rfq_id}/send", headers=AUTH, json={})
    assert send.status_code == 200, send.text
    assert send.json()["status"] == "sent"
    assert len(send.json()["sent_leads"]) == 2

    # 3. 供应商能查到线索
    for sup_id in (SUP_A, SUP_B):
        r = client.get(f"/api/v1/suppliers/{sup_id}/leads", headers=AUTH)
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        own = [it for it in items if it["rfq_id"] == rfq_id]
        assert own, f"供应商 {sup_id} 应能查到 RFQ {rfq_id} 的线索"
        assert own[0]["status"] == "sent"
        # match_score 透出到供应商线索视图
        assert own[0]["match_score"] is not None

    # 4. 报价对比页可读 (无报价也返回结构, 不报错)
    cmp = client.get(f"/api/v1/rfqs/{rfq_id}/quote-comparison", headers=AUTH)
    assert cmp.status_code == 200, cmp.text
    cdata = cmp.json()
    assert cdata["rfq_id"] == rfq_id
    assert cdata["quote_count"] == 0

    # 5. RFQ 详情可读 (含 supplier_leads)
    detail = client.get(f"/api/v1/rfqs/{rfq_id}", headers=AUTH)
    assert detail.status_code == 200
    assert len(detail.json()["supplier_leads"]) == 2


# ── 兼容性: 纯 supplier_candidates: list[int] 仍工作 ───────────────

def test_legacy_supplier_candidates_still_works(client):
    """旧调用方 (ShortageProcurementView/测试) 用纯 id 列表, score/reason 为 null。"""
    resp = client.post("/api/v1/rfqs", headers=AUTH, json={
        "buyer_company_id": BUYER,
        "title": "兼容-纯id列表",
        "quantity": 10,
        "supplier_candidates": [SUP_A],
    })
    assert resp.status_code == 200, resp.text
    leads = resp.json()["supplier_leads"]
    assert len(leads) == 1
    assert leads[0]["supplier_company_id"] == SUP_A
    # 旧调用方不带 score/reason -> null (不破坏既有行为)
    assert leads[0]["match_score"] is None
    assert leads[0]["match_reason"] is None


def test_mixed_candidates_dedup(client):
    """candidate_details 与 supplier_candidates 同时存在时去重, details 优先。"""
    resp = client.post("/api/v1/rfqs", headers=AUTH, json={
        "buyer_company_id": BUYER,
        "title": "兼容-混合去重",
        "quantity": 10,
        "candidate_details": [
            {"supplier_company_id": SUP_A, "match_score": 0.9, "match_reason": "AI匹配"},
        ],
        "supplier_candidates": [SUP_A, SUP_B],  # SUP_A 重复, SUP_B 补充
    })
    assert resp.status_code == 200, resp.text
    leads = resp.json()["supplier_leads"]
    by = {lk["supplier_company_id"]: lk for lk in leads}
    assert set(by.keys()) == {SUP_A, SUP_B}  # 去重后两家
    assert by[SUP_A]["match_score"] == 0.9   # details 优先, 保留 score
    assert by[SUP_A]["match_reason"] == "AI匹配"
    assert by[SUP_B]["match_score"] is None  # 纯 id 补充, 无 score
