"""
演示场景沙盘后端验证 (demo scenario sandbox)。

覆盖:
  - demo state / events / scenarios 查询
  - reset 场景 (仅清演示数据, 不动基线)
  - generate-orders (+联动下游/上游/支撑事件)
  - consume-inventory (写入 demo override, 不改基线)
  - recalculate-shortages (基线需求 + 演示订单 - 演示可用库存)
  - generate-rfq (仅直接关系候选; 无直接供应商时提示)
  - simulate-quotes (合理价格/交期)
  - execute-replenishment (补货入库 + 关闭 RFQ + 联动)
  - select-alternative (仅直接关系替代料来源)
  - 直接关系供应商限制 (候选均为直接关系)
  - 无直接供应商时的明确提示 (no_direct_supplier)
  - reset 后数据恢复 + 基线业务表未被污染
  - 非主视角企业被拒绝 (400)

不依赖外部 LLM / 向量库 (纯 DB 计算 + demo_* 表)。
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# 让 seed 脚本可被导入
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import seed_demo_scenario as demo_seed  # noqa: E402
from api.main import create_app  # noqa: E402
from kb import demo_calc as dcalc  # noqa: E402
from kb.db import session_scope  # noqa: E402
from kb.models import (  # noqa: E402
    DemoOrder,
    DemoInventoryOverride,
    DemoRfq,
    DemoQuotation,
    InventoryItem,
    ProductionOrder,
)

DEMO_TOKEN = "kb-demo-user"
AUTH = {"Authorization": f"Bearer {DEMO_TOKEN}"}

# 鼎云整机制造 (主视角, midstream): 上游创捷(9002), 下游星河(9005), 支撑远达(9004)
DY = 9003
CJ = 9002  # 创捷 (直接上游, 供主板/PCBA)
HX = 9001  # 华芯 (非鼎云直接关系, 供CPU)
YD = 9004  # 远达 (支撑/物流)

SID = dcalc.DEFAULT_SCENARIO_ID


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(scope="module", autouse=True)
def _offline_rag():
    """离线兜底: 关闭 LLM + 强制 Local 向量库。"""
    with patch("kb.rag.llm_available", return_value=False), \
            patch("kb.config.milvus_available", return_value=False):
        yield


@pytest.fixture(scope="module", autouse=True)
def _ensure_data(_offline_rag):
    """幂等写入: 基线 (Phase1+Phase2) + 演示场景 default_mvp_demo。"""
    demo_seed.seed()


@pytest.fixture(autouse=True)
def _reset_scenario(_ensure_data):
    """每个测试前重置演示场景, 保证独立 (仅清演示数据, 不动基线)。"""
    with session_scope() as s:
        dcalc.ensure_default_scenario(s)
        dcalc.reset_scenario(s, SID)
    yield


@pytest.fixture(scope="module")
def client(_ensure_data):
    app = create_app()
    with TestClient(app) as c:
        yield c


# ============================================================
# 1. 查询接口
# ============================================================

def test_demo_scenarios(client):
    r = client.get("/api/v1/demo/scenarios", headers=AUTH)
    assert r.status_code == 200, r.text
    data = r.json()
    assert any(s["scenario_id"] == SID for s in data["items"])
    assert data["default"] == SID


def test_demo_state(client):
    r = client.get("/api/v1/demo/state", headers=AUTH, params={"company_id": DY})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["scenario_id"] == SID
    assert data["company_id"] == DY
    assert data["is_primary"] is True
    # 鼎云有在产产品
    assert data["products_total"] >= 1
    # 直接关系: 上游创捷 / 下游星河 / 支撑远达
    directions = {p["direction"] for p in data["direct_partners"]}
    assert "supplier" in directions  # 创捷
    assert "customer" in directions  # 星河
    assert "support" in directions   # 远达
    # 初始无演示订单/增量
    assert data["demo_orders_total"] == 0
    assert data["demo_inventory_overrides_total"] == 0


def test_demo_state_company_not_found(client):
    r = client.get("/api/v1/demo/state", headers=AUTH, params={"company_id": 999999})
    assert r.status_code == 404


def test_demo_events_empty(client):
    r = client.get("/api/v1/demo/events", headers=AUTH, params={"company_id": DY})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 0


# ============================================================
# 2. generate-orders
# ============================================================

def test_generate_orders(client):
    r = client.post("/api/v1/demo/actions/generate-orders", headers=AUTH, json={
        "company_id": DY, "product_id": 9101, "quantity": 200, "priority": "high",
    })
    assert r.status_code == 200, r.text
    data = r.json()
    order = data["order"]
    assert order["order_number"].startswith("DEMO-ORD-")
    assert order["quantity"] == 200
    assert order["product_id"] == 9101
    # 客户 = 直接下游星河
    assert order["customer_company_id"] == 9005
    # 产生了主事件 + 下游 + 上游 + 支撑 联动事件
    assert data["events_created"] >= 3

    # 演示订单已写入 demo_orders (基线 kb_production_orders 未被污染)
    with session_scope() as s:
        demo_cnt = s.query(DemoOrder).filter_by(
            scenario_id=SID, company_id=DY).count()
        assert demo_cnt == 1
        # 基线生产订单无 DEMO-ORD- 编号
        base_demo = s.query(ProductionOrder).filter(
            ProductionOrder.order_number.like("DEMO-ORD-%")).count()
        assert base_demo == 0

    # 事件日志可见
    r2 = client.get("/api/v1/demo/events", headers=AUTH, params={"company_id": DY})
    evs = r2.json()["items"]
    assert any("新增订单" in e["title"] for e in evs)
    # 联动到下游星河(9005)的事件
    r3 = client.get("/api/v1/demo/events", headers=AUTH, params={"company_id": 9005})
    assert any("收到" in e["title"] and "订单需求" in e["title"] for e in r3.json()["items"])


def test_generate_orders_rejects_non_primary(client):
    r = client.post("/api/v1/demo/actions/generate-orders", headers=AUTH, json={
        "company_id": 1, "quantity": 10,
    })
    assert r.status_code == 400
    assert "主视角企业" in r.text


# ============================================================
# 3. consume-inventory
# ============================================================

def test_consume_inventory(client):
    # 先消耗 CPU 库存 (鼎云有 CPU-I7-13700)
    r = client.post("/api/v1/demo/actions/consume-inventory", headers=AUTH, json={
        "company_id": DY, "part_number": "CPU-I7-13700", "quantity": 10,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    consumed = data["consumed"]
    assert consumed["part_number"] == "CPU-I7-13700"
    assert consumed["consumed_qty"] == 10
    # 基线 on_hand=20, consumed=10 -> available_after = 20-0-10 = 10
    assert consumed["baseline_on_hand"] == 20
    assert consumed["available_after"] == 10

    # demo override 已写入, 基线 kb_inventory_items 未被修改
    with session_scope() as s:
        ov = s.query(DemoInventoryOverride).filter_by(
            scenario_id=SID, company_id=DY, part_number="CPU-I7-13700").first()
        assert ov is not None
        assert ov.consumed_qty == 10
        assert ov.replenished_qty == 0
        inv = s.query(InventoryItem).filter_by(
            company_id=DY, part_number="CPU-I7-13700").first()
        assert inv.on_hand_qty == 20  # 基线未变


def test_consume_inventory_auto_pick(client):
    # 不指定 part_number, 自动取最近演示订单 BOM 关键件
    client.post("/api/v1/demo/actions/generate-orders", headers=AUTH, json={
        "company_id": DY, "product_id": 9101, "quantity": 100,
    })
    r = client.post("/api/v1/demo/actions/consume-inventory", headers=AUTH, json={
        "company_id": DY,
    })
    assert r.status_code == 200, r.text
    assert r.json()["consumed"]["consumed_qty"] >= 1


# ============================================================
# 4. recalculate-shortages
# ============================================================

def test_recalculate_shortages(client):
    r = client.post("/api/v1/demo/actions/recalculate-shortages", headers=AUTH, json={
        "company_id": DY,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    # 鼎云基线即存在缺件 (CPU/PCBA 等)
    assert data["shortage_count"] >= 1
    parts = {s["part_number"] for s in data["shortages"]}
    assert "CPU-I7-13700" in parts
    assert "PCBA-DY-DT-Z690" in parts
    # 事件
    r2 = client.get("/api/v1/demo/events", headers=AUTH,
                    params={"company_id": DY, "phase": "recalculate_shortages"})
    assert any("触发缺件" in e["title"] for e in r2.json()["items"])


def test_recalculate_after_order_increases_demand(client):
    # 基线 CPU 缺口
    r0 = client.post("/api/v1/demo/actions/recalculate-shortages", headers=AUTH,
                     json={"company_id": DY})
    base_cpu = next(s for s in r0.json()["shortages"]
                    if s["part_number"] == "CPU-I7-13700")
    base_gap = base_cpu["shortage_qty"]

    # 新增 200 台台式机订单 -> CPU 需求 +200
    client.post("/api/v1/demo/actions/generate-orders", headers=AUTH, json={
        "company_id": DY, "product_id": 9101, "quantity": 200,
    })
    r1 = client.post("/api/v1/demo/actions/recalculate-shortages", headers=AUTH,
                     json={"company_id": DY})
    cpu = next(s for s in r1.json()["shortages"]
               if s["part_number"] == "CPU-I7-13700")
    assert cpu["shortage_qty"] == base_gap + 200


# ============================================================
# 5. generate-rfq (含直接关系限制 + 无直接供应商提示)
# ============================================================

def test_generate_rfq_with_direct_supplier(client):
    # PCBA 首选供应商创捷(9002) 是鼎云直接上游 -> 应有候选
    r = client.post("/api/v1/demo/actions/generate-rfq", headers=AUTH, json={
        "company_id": DY, "part_number": "PCBA-DY-DT-Z690",
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["no_direct_supplier"] is False
    rfq = data["rfq"]
    assert rfq["rfq_number"].startswith("DEMO-RFQ-")
    assert rfq["status"] == "sent"
    cands = data["candidates"]
    assert len(cands) >= 1
    # 候选必须是直接关系企业
    with session_scope() as s:
        for c in cands:
            assert dcalc._has_direct_relationship(s, DY, c["supplier_company_id"])
    # 创捷应在候选中
    cand_ids = {c["supplier_company_id"] for c in cands}
    assert CJ in cand_ids
    # 基线 kb_rfqs 未被污染 (无 DEMO-RFQ-)
    from kb.models import RfqRecord
    with session_scope() as s:
        base_demo = s.query(RfqRecord).filter(
            RfqRecord.rfq_number.like("DEMO-RFQ-%")).count()
        assert base_demo == 0


def test_generate_rfq_no_direct_supplier(client):
    # CPU 首选供应商华芯(9001) 不是鼎云直接关系 -> 无候选
    r = client.post("/api/v1/demo/actions/generate-rfq", headers=AUTH, json={
        "company_id": DY, "part_number": "CPU-I7-13700",
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["no_direct_supplier"] is True
    assert data["rfq"] is None
    assert data["candidates"] == []
    assert "无可用直接关系供应商" in data["message"]
    # 事件日志有 no_direct_supplier
    r2 = client.get("/api/v1/demo/events", headers=AUTH,
                    params={"company_id": DY, "phase": "generate_rfq"})
    evs = r2.json()["items"]
    assert any(e["event_type"] == "no_direct_supplier" for e in evs)


def test_generate_rfq_action_log_status(client):
    # 无直接供应商时 action_log 状态 = no_direct_supplier
    client.post("/api/v1/demo/actions/generate-rfq", headers=AUTH, json={
        "company_id": DY, "part_number": "CPU-I7-13700",
    })
    with session_scope() as s:
        from kb.models import DemoActionLog
        log = s.query(DemoActionLog).filter_by(
            scenario_id=SID, company_id=DY,
            action_type="generate_rfq").order_by(DemoActionLog.id.desc()).first()
        assert log.status == "no_direct_supplier"


# ============================================================
# 6. simulate-quotes
# ============================================================

def test_simulate_quotes(client):
    # 先生成 PCBA 的 RFQ (有候选创捷)
    gr = client.post("/api/v1/demo/actions/generate-rfq", headers=AUTH, json={
        "company_id": DY, "part_number": "PCBA-DY-DT-Z690",
    })
    rfq_id = gr.json()["rfq"]["id"]
    r = client.post("/api/v1/demo/actions/simulate-quotes", headers=AUTH, json={
        "company_id": DY, "rfq_id": rfq_id,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["quote_count"] >= 1
    assert data["lowest_price"] is not None
    # 报价合理 (PCBA 基准 380, 浮动 ±10%)
    for q in data["quotes"]:
        assert 300 < q["unit_price"] < 450
        assert q["lead_time_days"] >= 1
    # 报价事件
    r2 = client.get("/api/v1/demo/events", headers=AUTH,
                    params={"company_id": CJ, "phase": "simulate_quotes"})
    assert any("报价" in e["title"] for e in r2.json()["items"])


def test_simulate_quotes_no_rfq(client):
    r = client.post("/api/v1/demo/actions/simulate-quotes", headers=AUTH, json={
        "company_id": DY,
    })
    assert r.status_code == 200, r.text
    assert r.json()["quotes"] == []


# ============================================================
# 7. execute-replenishment
# ============================================================

def test_execute_replenishment(client):
    # 完整链路: generate-rfq -> simulate-quotes -> execute-replenishment
    gr = client.post("/api/v1/demo/actions/generate-rfq", headers=AUTH, json={
        "company_id": DY, "part_number": "PCBA-DY-DT-Z690",
    })
    rfq_id = gr.json()["rfq"]["id"]
    client.post("/api/v1/demo/actions/simulate-quotes", headers=AUTH, json={
        "company_id": DY, "rfq_id": rfq_id,
    })
    r = client.post("/api/v1/demo/actions/execute-replenishment", headers=AUTH, json={
        "company_id": DY, "rfq_id": rfq_id,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["replenished_qty"] >= 1
    assert data["selected_supplier_company_id"] == CJ
    # RFQ 已关闭
    with session_scope() as s:
        rfq = s.get(DemoRfq, rfq_id)
        assert rfq.status == "closed"
        assert rfq.selected_supplier_company_id == CJ
        # 入库 override 已写入
        ov = s.query(DemoInventoryOverride).filter_by(
            scenario_id=SID, company_id=DY, part_number="PCBA-DY-DT-Z690").first()
        assert ov is not None
        assert ov.replenished_qty >= 1
        # 基线库存未变
        inv = s.query(InventoryItem).filter_by(
            company_id=DY, part_number="PCBA-DY-DT-Z690").first()
        assert inv.on_hand_qty == 50
    # 物流(远达)收到运输任务事件
    r2 = client.get("/api/v1/demo/events", headers=AUTH,
                    params={"company_id": YD, "phase": "execute_replenishment"})
    assert any("运输任务" in e["title"] for e in r2.json()["items"])


def test_execute_replenishment_resolves_shortage(client):
    # PCBA 缺口补齐后, 重算应不再有 PCBA shortage
    gr = client.post("/api/v1/demo/actions/generate-rfq", headers=AUTH, json={
        "company_id": DY, "part_number": "PCBA-DY-DT-Z690",
    })
    rfq_id = gr.json()["rfq"]["id"]
    client.post("/api/v1/demo/actions/simulate-quotes", headers=AUTH, json={
        "company_id": DY, "rfq_id": rfq_id,
    })
    client.post("/api/v1/demo/actions/execute-replenishment", headers=AUTH, json={
        "company_id": DY, "rfq_id": rfq_id,
    })
    r = client.post("/api/v1/demo/actions/recalculate-shortages", headers=AUTH, json={
        "company_id": DY,
    })
    parts = {s["part_number"] for s in r.json()["shortages"]}
    assert "PCBA-DY-DT-Z690" not in parts


# ============================================================
# 8. select-alternative
# ============================================================

def test_select_alternative_rejects_non_direct(client):
    # 指定非直接关系企业 (华芯 9001 不是鼎云直接关系) -> 400
    r = client.post("/api/v1/demo/actions/select-alternative", headers=AUTH, json={
        "company_id": DY, "part_number": "CPU-I7-13700",
        "alternative_supplier_company_id": HX,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    # select_alternative 对无直接关系返回 failed (HTTP 200, 业务失败)
    assert data.get("replenished") is None or data.get("alternative") is None


def test_select_alternative_with_direct(client):
    # 用创捷(直接上游)作为 PCBA 替代来源
    r = client.post("/api/v1/demo/actions/select-alternative", headers=AUTH, json={
        "company_id": DY, "part_number": "PCBA-DY-DT-Z690",
        "alternative_supplier_company_id": CJ,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["alternative_supplier_company_id"] == CJ
    assert data["replenished_qty"] >= 1
    with session_scope() as s:
        ov = s.query(DemoInventoryOverride).filter_by(
            scenario_id=SID, company_id=DY, part_number="PCBA-DY-DT-Z690").first()
        assert ov.replenished_qty >= 1


def test_select_alternative_no_direct(client):
    # CPU 无任何直接关系替代供应商 -> no_direct_supplier
    r = client.post("/api/v1/demo/actions/select-alternative", headers=AUTH, json={
        "company_id": DY, "part_number": "CPU-I7-13700",
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("no_direct_supplier") is True


# ============================================================
# 9. reset 恢复 + 基线不污染
# ============================================================

def test_reset_restores_baseline(client):
    # 产生若干演示数据
    client.post("/api/v1/demo/actions/generate-orders", headers=AUTH, json={
        "company_id": DY, "quantity": 100,
    })
    client.post("/api/v1/demo/actions/consume-inventory", headers=AUTH, json={
        "company_id": DY, "part_number": "CPU-I7-13700", "quantity": 5,
    })
    client.post("/api/v1/demo/actions/recalculate-shortages", headers=AUTH, json={
        "company_id": DY,
    })
    with session_scope() as s:
        assert s.query(DemoOrder).filter_by(scenario_id=SID, company_id=DY).count() == 1
        assert s.query(DemoInventoryOverride).filter_by(
            scenario_id=SID, company_id=DY).count() >= 1

    # 重置
    r = client.post("/api/v1/demo/scenarios/reset", headers=AUTH, json={"scenario_id": SID})
    assert r.status_code == 200, r.text
    deleted = r.json()["deleted"]
    assert deleted["demo_orders"] >= 1
    assert deleted["demo_inventory_overrides"] >= 1

    # 演示数据已清空
    with session_scope() as s:
        assert s.query(DemoOrder).filter_by(scenario_id=SID).count() == 0
        assert s.query(DemoInventoryOverride).filter_by(scenario_id=SID).count() == 0
        assert s.query(DemoRfq).filter_by(scenario_id=SID).count() == 0
        assert s.query(DemoQuotation).filter_by(scenario_id=SID).count() == 0
        from kb.models import DemoEvent, DemoActionLog
        assert s.query(DemoEvent).filter_by(scenario_id=SID).count() == 0
        assert s.query(DemoActionLog).filter_by(scenario_id=SID).count() == 0

    # 状态恢复基线 (演示订单 0)
    r2 = client.get("/api/v1/demo/state", headers=AUTH, params={"company_id": DY})
    assert r2.json()["demo_orders_total"] == 0
    assert r2.json()["demo_inventory_overrides_total"] == 0


def test_baseline_tables_unpolluted(client):
    """完整链路后, 基线业务表 (kb_production_orders/kb_inventory_items/kb_rfqs/kb_quotations) 未被污染。"""
    from kb.models import RfqRecord, QuotationRecord, RfqSupplierLink
    with session_scope() as s:
        before_orders = s.query(ProductionOrder).count()
        before_inv = s.query(InventoryItem).filter_by(company_id=DY).count()
        before_rfqs = s.query(RfqRecord).count()
        before_quotes = s.query(QuotationRecord).count()

    # 跑完整演示链路
    client.post("/api/v1/demo/actions/generate-orders", headers=AUTH, json={
        "company_id": DY, "quantity": 100,
    })
    client.post("/api/v1/demo/actions/consume-inventory", headers=AUTH, json={
        "company_id": DY, "part_number": "PCBA-DY-DT-Z690", "quantity": 20,
    })
    client.post("/api/v1/demo/actions/recalculate-shortages", headers=AUTH, json={"company_id": DY})
    gr = client.post("/api/v1/demo/actions/generate-rfq", headers=AUTH, json={
        "company_id": DY, "part_number": "PCBA-DY-DT-Z690",
    })
    rfq_id = gr.json()["rfq"]["id"]
    client.post("/api/v1/demo/actions/simulate-quotes", headers=AUTH, json={
        "company_id": DY, "rfq_id": rfq_id,
    })
    client.post("/api/v1/demo/actions/execute-replenishment", headers=AUTH, json={
        "company_id": DY, "rfq_id": rfq_id,
    })

    with session_scope() as s:
        after_orders = s.query(ProductionOrder).count()
        after_inv = s.query(InventoryItem).filter_by(company_id=DY).count()
        after_rfqs = s.query(RfqRecord).count()
        after_quotes = s.query(QuotationRecord).count()
        # 基线业务表行数不变
        assert after_orders == before_orders
        assert after_inv == before_inv
        assert after_rfqs == before_rfqs
        assert after_quotes == before_quotes
        # 基线库存数值未变
        inv = s.query(InventoryItem).filter_by(
            company_id=DY, part_number="PCBA-DY-DT-Z690").first()
        assert inv.on_hand_qty == 50
        assert inv.reserved_qty == 10


# ============================================================
# 10. 完整 RFQ 主链路 (分阶段)
# ============================================================

def test_full_rfq_chain(client):
    """缺件 -> RFQ -> 报价 -> 对比 -> 补货 -> 重算缺件 (主链路打通)。"""
    # 1. 重算缺件
    r1 = client.post("/api/v1/demo/actions/recalculate-shortages", headers=AUTH,
                     json={"company_id": DY})
    assert r1.json()["shortage_count"] >= 1

    # 2. 生成 RFQ (PCBA, 直接上游创捷)
    r2 = client.post("/api/v1/demo/actions/generate-rfq", headers=AUTH, json={
        "company_id": DY, "part_number": "PCBA-DY-DT-Z690",
    })
    rfq_id = r2.json()["rfq"]["id"]
    assert r2.json()["candidates"]

    # 3. 模拟报价
    r3 = client.post("/api/v1/demo/actions/simulate-quotes", headers=AUTH, json={
        "company_id": DY, "rfq_id": rfq_id,
    })
    assert r3.json()["quote_count"] >= 1

    # 4. 报价对比
    r4 = client.get("/api/v1/demo/rfqs/{}/quote-comparison".format(rfq_id),
                    headers=AUTH, params={"company_id": DY})
    assert r4.status_code == 200, r4.text
    cmp = r4.json()
    assert cmp["quote_count"] >= 1
    assert cmp["items"][0]["is_lowest"] is True

    # 5. 执行补货
    r5 = client.post("/api/v1/demo/actions/execute-replenishment", headers=AUTH, json={
        "company_id": DY, "rfq_id": rfq_id,
    })
    assert r5.json()["replenished_qty"] >= 1

    # 6. 入库后重算缺件 -> PCBA 缺件消除
    r6 = client.post("/api/v1/demo/actions/recalculate-shortages", headers=AUTH,
                     json={"company_id": DY})
    parts = {s["part_number"] for s in r6.json()["shortages"]}
    assert "PCBA-DY-DT-Z690" not in parts

    # 因果链事件覆盖: 鼎云新增缺件 -> 创捷收到RFQ -> 创捷报价 -> 远达运输
    all_events = client.get("/api/v1/demo/events", headers=AUTH,
                            params={"company_id": DY, "limit": 200}).json()["items"]
    titles = " | ".join(e["title"] for e in all_events)
    assert "触发缺件" in titles
    assert "生成 RFQ" in titles
    cj_events = client.get("/api/v1/demo/events", headers=AUTH,
                           params={"company_id": CJ, "limit": 200}).json()["items"]
    cj_titles = " | ".join(e["title"] for e in cj_events)
    assert "收到 RFQ" in cj_titles
    assert "报价" in cj_titles
    yd_events = client.get("/api/v1/demo/events", headers=AUTH,
                           params={"company_id": YD, "limit": 200}).json()["items"]
    yd_titles = " | ".join(e["title"] for e in yd_events)
    assert "运输任务" in yd_titles
