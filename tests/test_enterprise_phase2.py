"""
Phase 2 后端验证: 产品 / BOM / 订单 / 预测 / 缺件 / 推荐动作 / 聚合 dashboard。

覆盖:
  - products (含 production_products) / bom / bom-summary / orders / forecasts 接口可用
  - shortages 正确计算缺口 (3 个缺件场景: 严重缺件 / 可联系上游 / 安全库存预警)
  - recommended-actions 基于缺件生成采购/生产/销售建议
  - dashboard 返回当前企业完整聚合数据
  - company_id 不存在 -> 404
  - product 不属于当前企业 -> 403 (越权校验)
  - 无认证 -> 401

不依赖外部 LLM / 向量库 (纯 DB 计算)。
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# 让 seed_enterprise_phase2 / seed_enterprise_chain 可被导入
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import seed_enterprise_phase2 as seed2  # noqa: E402
from api.main import create_app  # noqa: E402

DEMO_TOKEN = "kb-demo-user"
AUTH_HEADERS = {"Authorization": f"Bearer {DEMO_TOKEN}"}


@pytest.fixture(scope="module", autouse=True)
def _offline_rag():
    """离线兜底: 关闭 LLM + 强制 Local 向量库 (Phase2 不依赖, 仅防 import 副作用)。"""
    with patch("kb.rag.llm_available", return_value=False), \
            patch("kb.config.milvus_available", return_value=False):
        yield


@pytest.fixture(scope="module", autouse=True)
def ensure_seed(_offline_rag):
    """幂等写入 Phase2 种子 (自包含: 含 Phase1 公司/关系 + 产品/BOM/订单/预测/库存/缺件)。"""
    seed2.upsert_all()


@pytest.fixture(scope="module")
def client(ensure_seed):
    app = create_app()
    with TestClient(app) as c:
        yield c


# ── 1. 产品 / BOM ──────────────────────────────────────────────

def test_company_products(client):
    r = client.get("/api/v1/companies/9003/products", headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["company_id"] == 9003
    # 向后兼容: kb 知识产品 items 仍在
    assert "items" in data
    # Phase2 追加: 在产产品
    assert data["production_total"] >= 2
    models = {p["product_model"] for p in data["production_products"]}
    assert "DY-DT-Pro" in models
    assert "DY-NB-Air" in models


def test_product_bom(client):
    r = client.get("/api/v1/products/9101/bom", headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["product_id"] == 9101
    assert data["company_id"] == 9003
    assert data["bom_count"] >= 5
    assert data["critical_count"] >= 1
    parts = {b["part_number"] for b in data["items"]}
    assert "CPU-I7-13700" in parts
    # 每条 BOM 含首选供应商字段
    cpu = next(b for b in data["items"] if b["part_number"] == "CPU-I7-13700")
    assert cpu["is_critical"] is True
    assert cpu["preferred_supplier_company_id"] == 9001


def test_bom_summary(client):
    r = client.get("/api/v1/companies/9003/bom-summary", headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["totals"]["product_count"] >= 2
    assert data["totals"]["part_count"] >= 10
    assert data["totals"]["critical_part_count"] >= 1
    # 跨产品零件聚合
    assert isinstance(data["parts"], list)
    assert "used_in_products" in data["parts"][0]


# ── 2. 订单 / 预测 ─────────────────────────────────────────────

def test_orders(client):
    r = client.get("/api/v1/companies/9003/orders", headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    # 9003 共 5 单 (含 1 完成)
    assert data["total"] == 5
    # 完成的不计入活跃需求: 4 单活跃, 500+300+300+200=1300
    assert data["active_count"] == 4
    assert data["active_total_quantity"] == 1300
    assert "by_status" in data and "by_priority" in data


def test_forecasts(client):
    r = client.get("/api/v1/companies/9003/forecasts", headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    # 9003 共 2 条预测 (400 + 300)
    assert data["total"] == 2
    assert data["total_forecast_quantity"] == 700


# ── 3. 缺件计算 (3 个场景) ─────────────────────────────────────

def test_shortages_recalculate(client):
    r = client.post("/api/v1/companies/9003/shortages/recalculate", headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    # 9003: 2 缺件 + 1 预警
    assert data["total"] == 3
    assert data["shortage_count"] == 2
    assert data["warning_count"] == 1
    assert data["critical_count"] >= 1

    by_part = {s["part_number"]: s for s in data["items"]}

    # 场景1: 严重缺件, 关键件, 影响高优先级订单, 首选供应商无直接关系
    cpu = by_part["CPU-I7-13700"]
    assert cpu["shortage_type"] == "shortage"
    assert cpu["shortage_qty"] == 780          # 需求 800 - 可用 20
    assert cpu["required_qty"] == 800
    assert cpu["available_qty"] == 20
    assert cpu["is_critical"] is True
    assert cpu["severity"] == "critical"
    assert cpu["preferred_supplier_company_id"] == 9001
    assert cpu["relationship_missing"] is True   # 9001 与 9003 无直接关系
    assert "DY-ORD-2026-001" in cpu["affected_order_numbers"]

    # 场景2: 有缺口但可联系直接上游
    pcba = by_part["PCBA-DY-DT-Z690"]
    assert pcba["shortage_type"] == "shortage"
    assert pcba["shortage_qty"] == 760          # 需求 800 - 可用 40
    assert pcba["preferred_supplier_company_id"] == 9002
    assert pcba["relationship_missing"] is False  # 9002 是 9003 直接上游

    # 场景3: 库存低于安全库存但尚未缺货
    ddr5 = by_part["DDR5-16GB-4800"]
    assert ddr5["shortage_type"] == "warning"
    assert ddr5["shortage_qty"] == 0            # 未缺货
    assert ddr5["available_qty"] == 1700
    assert ddr5["safety_stock_qty"] == 2000
    assert ddr5["available_qty"] < ddr5["safety_stock_qty"]


def test_shortages_get_persisted(client):
    r = client.get("/api/v1/companies/9003/shortages", headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 3
    assert data["shortage_count"] >= 2
    assert data["warning_count"] >= 1


def test_shortages_9002(client):
    r = client.post("/api/v1/companies/9002/shortages/recalculate", headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    by_part = {s["part_number"]: s for s in data["items"]}
    # 9002 关键件 Z690 芯片组缺件 (需求 2700 - 可用 200 = 2500)
    chip = by_part["CHIPSET-Z690"]
    assert chip["shortage_type"] == "shortage"
    assert chip["shortage_qty"] == 2500
    assert chip["is_critical"] is True
    assert chip["preferred_supplier_company_id"] == 9001
    assert chip["relationship_missing"] is False  # 9001 是 9002 直接上游


# ── 4. 推荐动作 ────────────────────────────────────────────────

def test_recommended_actions(client):
    r = client.get("/api/v1/companies/9003/recommended-actions", headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    types = {a["action_type"] for a in data["items"]}
    # 场景1 (rel_missing) -> establish_relationship
    assert "establish_relationship" in types
    # 场景2 (direct upstream) -> contact_supplier
    assert "contact_supplier" in types
    # 场景3 (warning) -> replenish
    assert "replenish" in types

    # contact_supplier 应指向直接上游 9002
    contacts = [a for a in data["items"] if a["action_type"] == "contact_supplier"]
    assert contacts, "应有 contact_supplier 动作"
    assert any(a["suggested_supplier_company_id"] == 9002 for a in contacts)
    assert all(a["relationship_missing"] is False for a in contacts)

    # establish_relationship 应标记 relationship_missing
    est = [a for a in data["items"] if a["action_type"] == "establish_relationship"]
    assert est and all(a["relationship_missing"] is True for a in est)

    # 严重缺件应触发升级
    assert "escalate" in types

    # by_type 统计
    assert sum(data["by_type"].values()) == data["total"]


# ── 5. 聚合 dashboard ──────────────────────────────────────────

def test_dashboard(client):
    r = client.get("/api/v1/companies/9003/dashboard", headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["company_id"] == 9003
    assert data["company"]["name"]
    for key in ("products_summary", "orders_summary", "forecast_summary",
                "shortages", "recommended_actions", "upstream_summary",
                "downstream_summary", "support_summary", "chat_partners_summary"):
        assert key in data, f"dashboard 缺字段 {key}"
    assert data["products_summary"]["total"] >= 2
    assert data["orders_summary"]["total"] >= 5
    assert data["shortages"]["total"] >= 3
    assert data["upstream_summary"]["count"] >= 1
    assert data["downstream_summary"]["count"] >= 1
    assert data["chat_partners_summary"]["count"] >= 1
    # 推荐动作已聚合
    assert data["recommended_actions"]["total"] >= 1


def test_dashboard_9002(client):
    r = client.get("/api/v1/companies/9002/dashboard", headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["products_summary"]["total"] >= 2
    parts = {s["part_number"] for s in data["shortages"]["items"]}
    assert "CHIPSET-Z690" in parts


# ── 6. 错误处理 / 越权 ─────────────────────────────────────────

def test_company_not_found(client):
    for path in ("/dashboard", "/shortages", "/orders", "/forecasts",
                 "/bom-summary", "/recommended-actions", "/products"):
        r = client.get(f"/api/v1/companies/99999{path}", headers=AUTH_HEADERS)
        assert r.status_code == 404, f"{path} 应 404"
    r = client.post("/api/v1/companies/99999/shortages/recalculate", headers=AUTH_HEADERS)
    assert r.status_code == 404


def test_product_not_found(client):
    r = client.get("/api/v1/products/99999/bom", headers=AUTH_HEADERS)
    assert r.status_code == 404


def test_product_bom_cross_company_forbidden(client):
    # 9103 属于 9002; 用 company_id=9003 越权校验 -> 403
    r = client.get("/api/v1/products/9103/bom?company_id=9003", headers=AUTH_HEADERS)
    assert r.status_code == 403
    # 不带 scope 仍可访问 (产品存在)
    r2 = client.get("/api/v1/products/9103/bom", headers=AUTH_HEADERS)
    assert r2.status_code == 200
    assert r2.json()["company_id"] == 9002
    # 正确归属校验通过
    r3 = client.get("/api/v1/products/9103/bom?company_id=9002", headers=AUTH_HEADERS)
    assert r3.status_code == 200


def test_unauthorized(client):
    r = client.get("/api/v1/companies/9003/dashboard")
    assert r.status_code == 401


# ── 7. Phase1 接口未受破坏 (回归) ──────────────────────────────

def test_phase1_enterprise_context_still_works(client):
    r = client.get("/api/v1/enterprise-context/9003", headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["company_id"] == 9003
    assert data["upstream_count"] >= 1


def test_phase1_relationships_still_works(client):
    r = client.get("/api/v1/companies/9003/upstream", headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert 9002 in {p["company_id"] for p in data["items"]}
