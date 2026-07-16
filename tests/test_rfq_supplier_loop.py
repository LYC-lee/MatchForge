"""
缺件采购闭环 (RFQ / 供应商线索 / 报价 / 审核) 后端验证。

覆盖:
  - 创建 RFQ (含候选供应商)
  - RFQ send 后生成供应商线索 + 审核项
  - 供应商线索按供应商企业查询 + 状态过滤
  - 供应商提交报价 + 报价对比
  - admin 审核队列: 查询 / approve / reject
  - company_id 不存在 -> 404
  - 无关企业不能查看不属于自己的线索 -> 403
  - seeded 数据存在性

复用 conftest 的 mock_external_deps (autouse); 额外关闭 LLM/Milvus 保证离线。
Phase 1 的 15 个测试在 test_enterprise_phase1.py, 不受本文件影响。
"""

from __future__ import annotations

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
from kb.auth import grant_company_access  # noqa: E402

DEMO_TOKEN = "kb-demo-user"          # role=user, 无白名单 -> 公开访问
ADMIN_TOKEN = "kb-admin-demo"        # role=admin
AUTH = {"Authorization": f"Bearer {DEMO_TOKEN}"}
ADMIN_AUTH = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

# 仅授权 9002 的供应商账号 (用于 "无关企业" 隔离测试)
RESTRICTED_TOKEN = "test-supplier-9002-only-token"


@pytest.fixture(scope="module", autouse=True)
def _offline_rag():
    with patch("kb.rag.llm_available", return_value=False), \
            patch("kb.config.milvus_available", return_value=False):
        yield


@pytest.fixture(scope="module", autouse=True)
def _ensure_data(_offline_rag):
    """幂等写入: 6 家企业 + RFQ 闭环种子。"""
    # 企业 + 关系 (Phase 1 种子, 不触发知识生成)
    import seed_enterprise_chain as chain
    chain.init_db()
    chain.upsert_companies()
    chain.upsert_relationships()
    # RFQ 闭环种子
    rfq_seed.seed()
    # 授权受限账号仅可访问 9002
    restricted_user = f"u-{RESTRICTED_TOKEN[:8]}"
    grant_company_access(restricted_user, 9002)


@pytest.fixture(scope="module")
def client(_offline_rag):
    app = create_app()
    with TestClient(app) as c:
        yield c


# ── 1. 创建 RFQ ────────────────────────────────────────────────

def test_create_rfq(client):
    resp = client.post("/api/v1/rfqs", headers=AUTH, json={
        "buyer_company_id": 9003,
        "title": "测试-内存条采购",
        "part_number": "DDR5-16G",
        "part_name": "DDR5 内存条",
        "quantity": 1000,
        "unit": "条",
        "target_price": 120.0,
        "lead_time_days": 14,
        "scenario": "sourcing",
        "supplier_candidates": [9002],
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    rfq = data["rfq"]
    assert rfq["buyer_company_id"] == 9003
    assert rfq["status"] == "draft"
    assert rfq["rfq_number"].startswith("RFQ-")
    assert len(data["supplier_leads"]) == 1
    assert data["supplier_leads"][0]["status"] == "pending"


def test_create_rfq_with_phase2_compat_fields(client):
    # Phase 2 兼容字段存入 context, 不强依赖
    resp = client.post("/api/v1/rfqs", headers=AUTH, json={
        "buyer_company_id": 9003,
        "title": "测试-缺件触发RFQ",
        "quantity": 50,
        "shortage_id": "SH-001",
        "product_id": 12345,
        "recommended_action_id": "RA-9",
    })
    assert resp.status_code == 200, resp.text
    ctx = resp.json()["rfq"]["context"]
    assert ctx["shortage_id"] == "SH-001"
    assert ctx["product_id"] == 12345
    assert ctx["recommended_action_id"] == "RA-9"


# ── 2. RFQ send 后生成供应商线索 + 审核项 ───────────────────────

def test_send_rfq_generates_leads_and_audit(client):
    # 创建 RFQ with 2 candidates
    create = client.post("/api/v1/rfqs", headers=AUTH, json={
        "buyer_company_id": 9003,
        "title": "测试-发送RFQ",
        "part_name": "测试件",
        "quantity": 100,
        "supplier_candidates": [9002, 9006],
    })
    rfq_id = create.json()["rfq"]["id"]

    send = client.post(f"/api/v1/rfqs/{rfq_id}/send", headers=AUTH, json={})
    assert send.status_code == 200, send.text
    sdata = send.json()
    assert sdata["status"] == "sent"
    assert len(sdata["sent_leads"]) == 2
    for lk in sdata["sent_leads"]:
        assert lk["status"] == "sent"
        assert lk["sent_at"] is not None

    # 审核项已生成
    audit = client.get("/api/v1/admin/audit-queue?item_type=rfq_supplier_match",
                       headers=ADMIN_AUTH)
    assert audit.status_code == 200
    titles = [it["title"] for it in audit.json()["items"]
              if it["payload"].get("rfq_id") == rfq_id]
    assert len(titles) == 2  # 两个供应商各一条


# ── 3. 供应商线索按企业查询 + 状态过滤 ──────────────────────────

def test_supplier_leads_query(client):
    r = client.get("/api/v1/suppliers/9002/leads", headers=AUTH)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["company_id"] == 9002
    assert data["total"] >= 1
    assert "rfq_number" in data["items"][0]

    # 状态过滤
    r2 = client.get("/api/v1/suppliers/9006/leads?status=quoted", headers=AUTH)
    assert r2.status_code == 200
    for it in r2.json()["items"]:
        assert it["status"] == "quoted"


def test_supplier_lead_view_and_decline(client):
    # 新建 + 发送一条线索, 然后标记查看
    create = client.post("/api/v1/rfqs", headers=AUTH, json={
        "buyer_company_id": 9003,
        "title": "测试-线索动作",
        "quantity": 10,
        "supplier_candidates": [9006],
    })
    rfq_id = create.json()["rfq"]["id"]
    client.post(f"/api/v1/rfqs/{rfq_id}/send", headers=AUTH, json={})
    lead = client.get("/api/v1/suppliers/9006/leads?status=sent", headers=AUTH)
    lead_id = lead.json()["items"][0]["id"]

    viewed = client.post(f"/api/v1/supplier-leads/{lead_id}/view", headers=AUTH)
    assert viewed.status_code == 200, viewed.text
    assert viewed.json()["lead"]["status"] == "viewed"
    assert viewed.json()["lead"]["viewed_at"] is not None

    # 新建另一条用于 decline
    create2 = client.post("/api/v1/rfqs", headers=AUTH, json={
        "buyer_company_id": 9003,
        "title": "测试-拒绝线索",
        "quantity": 5,
        "supplier_candidates": [9006],
    })
    rfq_id2 = create2.json()["rfq"]["id"]
    client.post(f"/api/v1/rfqs/{rfq_id2}/send", headers=AUTH, json={})
    lead2 = client.get("/api/v1/suppliers/9006/leads?status=sent", headers=AUTH)
    lead_id2 = lead2.json()["items"][0]["id"]
    declined = client.post(f"/api/v1/supplier-leads/{lead_id2}/decline",
                           headers=AUTH, json={"note": "产能不足"})
    assert declined.status_code == 200, declined.text
    assert declined.json()["lead"]["status"] == "declined"


# ── 4. 供应商提交报价 + 报价对比 ────────────────────────────────

def test_quotation_and_comparison(client):
    # 创建 + 发送 RFQ, 两个供应商
    create = client.post("/api/v1/rfqs", headers=AUTH, json={
        "buyer_company_id": 9003,
        "title": "测试-报价对比",
        "part_number": "CMP-001",
        "quantity": 2000,
        "target_price": 10.0,
        "supplier_candidates": [9002, 9006],
    })
    rfq_id = create.json()["rfq"]["id"]
    client.post(f"/api/v1/rfqs/{rfq_id}/send", headers=AUTH, json={})

    # 9006 报低价
    q1 = client.post(f"/api/v1/rfqs/{rfq_id}/quotations", headers=AUTH, json={
        "supplier_company_id": 9006, "unit_price": 9.5, "is_in_stock": True,
        "lead_time_days": 7,
    })
    assert q1.status_code == 200, q1.text
    assert q1.json()["lead_status"] == "quoted"

    # 9002 报高价 (>= 目标价 1.5 倍 -> 异常审核项)
    q2 = client.post(f"/api/v1/rfqs/{rfq_id}/quotations", headers=AUTH, json={
        "supplier_company_id": 9002, "unit_price": 16.0, "is_in_stock": False,
    })
    assert q2.status_code == 200, q2.text

    # 报价列表
    qlist = client.get(f"/api/v1/rfqs/{rfq_id}/quotations", headers=AUTH)
    assert qlist.status_code == 200
    assert qlist.json()["total"] == 2

    # 报价对比
    cmp = client.get(f"/api/v1/rfqs/{rfq_id}/quote-comparison", headers=AUTH)
    assert cmp.status_code == 200, cmp.text
    cdata = cmp.json()
    assert cdata["quote_count"] == 2
    assert cdata["lowest_price"] == 9.5
    items = cdata["items"]
    assert items[0]["is_lowest"] is True
    assert items[0]["unit_price"] == 9.5
    assert items[0]["meets_target"] is True   # 9.5 <= 10
    assert items[1]["meets_target"] is False  # 16 > 10
    assert items[1]["rank"] == 2

    # 异常报价审核项已生成
    anomaly = client.get(
        "/api/v1/admin/audit-queue?item_type=quotation_anomaly", headers=ADMIN_AUTH)
    assert anomaly.status_code == 200
    assert any(it["payload"].get("rfq_id") == rfq_id
               for it in anomaly.json()["items"])


def test_quotation_without_link_rejected(client):
    # 供应商未收到 RFQ -> 403
    create = client.post("/api/v1/rfqs", headers=AUTH, json={
        "buyer_company_id": 9003,
        "title": "测试-无线索报价",
        "quantity": 10,
        "supplier_candidates": [9002],
    })
    rfq_id = create.json()["rfq"]["id"]
    # 9006 未被加入候选
    q = client.post(f"/api/v1/rfqs/{rfq_id}/quotations", headers=AUTH, json={
        "supplier_company_id": 9006, "unit_price": 1.0,
    })
    assert q.status_code == 403


# ── 5. admin 审核队列: 查询 / approve / reject ──────────────────

def test_audit_queue_approve_reject(client):
    # 取一个 pending 审核项
    pending = client.get("/api/v1/admin/audit-queue?status=pending", headers=ADMIN_AUTH)
    assert pending.status_code == 200
    assert pending.json()["total"] >= 1
    item_id = pending.json()["items"][0]["id"]

    # approve
    ap = client.post(f"/api/v1/admin/audit-queue/{item_id}/approve",
                     headers=ADMIN_AUTH, json={"note": "通过"})
    assert ap.status_code == 200, ap.text
    assert ap.json()["item"]["status"] == "approved"
    assert ap.json()["item"]["reviewed_at"] is not None

    # 再取一个 pending 用于 reject
    pending2 = client.get("/api/v1/admin/audit-queue?status=pending", headers=ADMIN_AUTH)
    assert pending2.json()["total"] >= 1
    item_id2 = pending2.json()["items"][0]["id"]
    rj = client.post(f"/api/v1/admin/audit-queue/{item_id2}/reject",
                     headers=ADMIN_AUTH, json={"note": "驳回"})
    assert rj.status_code == 200, rj.text
    assert rj.json()["item"]["status"] == "rejected"

    # 不存在的审核项 -> 404
    nf = client.post("/api/v1/admin/audit-queue/999999/approve", headers=ADMIN_AUTH)
    assert nf.status_code == 404


def test_audit_queue_requires_admin(client):
    # 普通用户不能访问审核队列 -> 403
    r = client.get("/api/v1/admin/audit-queue", headers=AUTH)
    assert r.status_code == 403


# ── 6. company_id 不存在 -> 404 ─────────────────────────────────

def test_company_not_found(client):
    # 供应商线索查询, 公司不存在
    r1 = client.get("/api/v1/suppliers/99999/leads", headers=AUTH)
    assert r1.status_code == 404

    # 买方 RFQ 列表, 公司不存在
    r2 = client.get("/api/v1/companies/99999/rfqs", headers=AUTH)
    assert r2.status_code == 404

    # 创建 RFQ, 买方不存在
    r3 = client.post("/api/v1/rfqs", headers=AUTH, json={
        "buyer_company_id": 99999, "title": "x", "quantity": 1,
    })
    assert r3.status_code == 404


# ── 7. 无关企业不能查看不属于自己的线索 ─────────────────────────

def test_unauthorized_company_cannot_view_leads(client):
    restricted = {"Authorization": f"Bearer {RESTRICTED_TOKEN}"}
    # 9002 允许 (已授权)
    ok = client.get("/api/v1/suppliers/9002/leads", headers=restricted)
    assert ok.status_code == 200
    # 9006 拒绝 (白名单中无 9006)
    denied = client.get("/api/v1/suppliers/9006/leads", headers=restricted)
    assert denied.status_code == 403


# ── 8. seeded 数据存在性 ────────────────────────────────────────

def test_seeded_data_present(client):
    r = client.get("/api/v1/rfqs", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["total"] >= 3  # 至少 3 条种子 RFQ

    # 找到种子 RFQ-2026-0002 (有 2 条报价: 9006 + 9002)
    cmp = client.get("/api/v1/rfqs", headers=AUTH).json()
    seed2 = next(rq for rq in cmp["items"] if rq["rfq_number"] == "RFQ-2026-0002")
    qc = client.get(f"/api/v1/rfqs/{seed2['id']}/quote-comparison", headers=AUTH)
    assert qc.status_code == 200
    assert qc.json()["quote_count"] >= 2


def test_company_rfqs_list(client):
    r = client.get("/api/v1/companies/9003/rfqs", headers=AUTH)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["company_id"] == 9003
    assert data["total"] >= 3  # 种子 3 条买方均为 9003
