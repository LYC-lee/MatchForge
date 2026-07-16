"""
缺件采购闭环种子数据 (RFQ / 供应商线索 / 报价 / 审核队列)。

围绕 Phase 1 的 6 家企业构造演示数据:
  - 9003 鼎云整机制造  -> 买方
  - 9002 创捷主板模组  -> 供应商 (主板/PCBA + 被动元件转售)
  - 9006 毅诚被动元件  -> 供应商 (MLCC/电阻)
  - 9004 远达物流      -> support 企业 (不报价)

数据量: 3 RFQ + 4 supplier lead + 3 quotation + 3 audit queue item。

幂等: RFQ 按 rfq_number, 线索按 (rfq_id, supplier), 报价按 (rfq_id, supplier),
      审核项按 (item_type, title) upsert, 重复执行只更新不重复插入。

运行: python scripts/seed_rfq_supplier_loop.py
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
# 复用 seed_enterprise_chain 的公司种子 (仅 upsert_companies, 不触发知识生成)
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

from kb.db import init_db, session_scope  # noqa: E402
from kb.models import (  # noqa: E402
    AuditQueueItem,
    QuotationRecord,
    RfqRecord,
    RfqSupplierLink,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("seed_rfq_supplier_loop")

NOW = datetime.utcnow()
SENT_AT = NOW - timedelta(hours=6)
VIEWED_AT = NOW - timedelta(hours=3)


# ============================================================
# RFQ 定义 (买方均为 9003 鼎云)
# ============================================================
RFQS = [
    {
        "rfq_number": "RFQ-2026-0001",
        "buyer_company_id": 9003,
        "title": "主板 PCBA 紧急采购 (缺件)",
        "raw_query": "鼎云整机缺件: 主板PCBA 月需求500套, 交期2周",
        "part_number": "MB-PCBA-X1",
        "part_name": "主板PCBA",
        "quantity": 500,
        "unit": "套",
        "target_price": 380.0,
        "lead_time_days": 14,
        "accept_alternatives": False,
        "scenario": "shortage",
        "status": "quoted",
        "suppliers": [
            {"id": 9002, "status": "quoted", "match_score": 0.92,
             "match_reason": "创捷主营PCB/PCBA, 直接上游"},
        ],
    },
    {
        "rfq_number": "RFQ-2026-0002",
        "buyer_company_id": 9003,
        "title": "MLCC 电容批量寻源",
        "raw_query": "鼎云整机: MLCC 0805 10uF 月用量10万, 目标单价0.12",
        "part_number": "MLCC-0805-10uF-X7R",
        "part_name": "MLCC电容",
        "quantity": 100000,
        "unit": "个",
        "target_price": 0.12,
        "lead_time_days": 10,
        "accept_alternatives": True,
        "scenario": "sourcing",
        "status": "quoted",
        "suppliers": [
            {"id": 9006, "status": "quoted", "match_score": 0.95,
             "match_reason": "毅诚被动元件原厂, MLCC 主营"},
            {"id": 9002, "status": "quoted", "match_score": 0.60,
             "match_reason": "创捷可转售被动元件, 非原厂"},
        ],
    },
    {
        "rfq_number": "RFQ-2026-0003",
        "buyer_company_id": 9003,
        "title": "芯片组 SoC 寻源 (接受替代)",
        "raw_query": "鼎云整机: SoC 芯片组 200片, 接受替代方案",
        "part_number": "SOC-COMPUTE-2",
        "part_name": "SoC芯片组",
        "quantity": 200,
        "unit": "片",
        "target_price": 220.0,
        "lead_time_days": 21,
        "accept_alternatives": True,
        "scenario": "sourcing",
        "status": "quoted",
        "suppliers": [
            {"id": 9002, "status": "quoted", "match_score": 0.70,
             "match_reason": "创捷可提供芯片组方案 (含替代)"},
        ],
    },
]


# ============================================================
# 报价定义 (rfq_number -> 供应商报价列表)
# ============================================================
QUOTATIONS = {
    "RFQ-2026-0001": [
        {"supplier_company_id": 9002, "unit_price": 375.0, "currency": "CNY",
         "moq": 100, "lead_time_days": 14, "stock_qty": 800, "is_in_stock": True,
         "valid_until": NOW + timedelta(days=30),
         "note": "现货可发, 支持鼎云交期"},
    ],
    "RFQ-2026-0002": [
        {"supplier_company_id": 9006, "unit_price": 0.115, "currency": "CNY",
         "moq": 5000, "lead_time_days": 7, "stock_qty": 200000, "is_in_stock": True,
         "valid_until": NOW + timedelta(days=30),
         "note": "原厂直供, 交期优势"},
        {"supplier_company_id": 9002, "unit_price": 0.130, "currency": "CNY",
         "moq": 10000, "lead_time_days": 10, "stock_qty": 50000, "is_in_stock": True,
         "valid_until": NOW + timedelta(days=20),
         "note": "转售报价, 含分拣"},
    ],
    "RFQ-2026-0003": [
        {"supplier_company_id": 9002, "unit_price": 360.0, "currency": "CNY",
         "moq": 50, "lead_time_days": 21, "stock_qty": 300, "is_in_stock": False,
         "valid_until": NOW + timedelta(days=15),
         "note": "含替代方案, 价格较高 (异常待审)"},
    ],
}


# ============================================================
# 审核队列定义 (供应商能力审核, 独立于 RFQ)
# ============================================================
AUDIT_ITEMS = [
    {
        "item_type": "supplier_capability",
        "entity_id": None,
        "company_id": 9006,
        "title": "毅诚被动元件(9006) 供应商能力审核",
        "payload": {"company_id": 9006, "capability": "MLCC/电阻原厂制造"},
        "status": "pending",
    },
    {
        "item_type": "supplier_capability",
        "entity_id": None,
        "company_id": 9002,
        "title": "创捷主板模组(9002) 供应商能力审核",
        "payload": {"company_id": 9002, "capability": "PCB/PCBA + 芯片方案"},
        "status": "approved",
    },
]


def _upsert_rfq(s, data: dict) -> RfqRecord:
    r = s.query(RfqRecord).filter_by(rfq_number=data["rfq_number"]).first()
    fields = {k: v for k, v in data.items() if k != "suppliers"}
    if r:
        for k, v in fields.items():
            setattr(r, k, v)
        r.updated_at = NOW
    else:
        r = RfqRecord(created_by="seed_rfq_supplier_loop", **fields)
        s.add(r)
        s.flush()
    return r


def _upsert_link(s, rfq_id: int, sup: dict) -> RfqSupplierLink:
    lk = (
        s.query(RfqSupplierLink)
        .filter_by(rfq_id=rfq_id, supplier_company_id=sup["id"])
        .first()
    )
    status = sup["status"]
    sent_at = SENT_AT if status in ("sent", "viewed", "quoted") else None
    viewed_at = VIEWED_AT if status in ("viewed", "quoted") else None
    if lk:
        lk.match_score = sup.get("match_score")
        lk.match_reason = sup.get("match_reason")
        lk.status = status
        lk.sent_at = sent_at
        lk.viewed_at = viewed_at
    else:
        lk = RfqSupplierLink(
            rfq_id=rfq_id, supplier_company_id=sup["id"],
            match_score=sup.get("match_score"), match_reason=sup.get("match_reason"),
            status=status, sent_at=sent_at, viewed_at=viewed_at,
        )
        s.add(lk)
        s.flush()
    return lk


def _upsert_quotation(s, rfq_id: int, qdata: dict) -> QuotationRecord:
    q = (
        s.query(QuotationRecord)
        .filter_by(rfq_id=rfq_id, supplier_company_id=qdata["supplier_company_id"])
        .first()
    )
    if q:
        for k, v in qdata.items():
            setattr(q, k, v)
    else:
        q = QuotationRecord(rfq_id=rfq_id, **qdata)
        s.add(q)
        s.flush()
    return q


def _upsert_audit(s, data: dict) -> AuditQueueItem:
    it = (
        s.query(AuditQueueItem)
        .filter_by(item_type=data["item_type"], title=data["title"])
        .first()
    )
    payload_json = json.dumps(data.get("payload", {}), ensure_ascii=False)
    if it:
        it.entity_id = data.get("entity_id")
        it.company_id = data.get("company_id")
        it.payload_json = payload_json
        # 已审核状态不回退为 pending (保留管理员操作结果)
        if data["status"] != "pending" or it.status == "pending":
            it.status = data["status"]
    else:
        it = AuditQueueItem(
            item_type=data["item_type"],
            entity_id=data.get("entity_id"),
            company_id=data.get("company_id"),
            title=data["title"],
            payload_json=payload_json,
            status=data["status"],
        )
        s.add(it)
        s.flush()
    return it


def seed() -> None:
    init_db()
    # 确保 6 家企业存在 (仅公司快照, 不触发知识生成)
    try:
        import seed_enterprise_chain as chain
        chain.init_db()
        chain.upsert_companies()
    except Exception as e:
        logger.warning("企业种子未运行 (假设公司已存在): %s", str(e)[:160])

    with session_scope() as s:
        link_by_key: dict[tuple[int, int], int] = {}
        quote_by_key: dict[tuple[str, int], int] = {}

        for rdata in RFQS:
            r = _upsert_rfq(s, rdata)
            for sup in rdata["suppliers"]:
                lk = _upsert_link(s, r.id, sup)
                link_by_key[(r.id, sup["id"])] = lk.id

            for qdata in QUOTATIONS.get(rdata["rfq_number"], []):
                q = _upsert_quotation(s, r.id, qdata)
                quote_by_key[(rdata["rfq_number"], qdata["supplier_company_id"])] = q.id

        # RFQ 供应商匹配审核 (每个 quoted/sent 线索一条)
        match_count = 0
        for rdata in RFQS:
            r = s.query(RfqRecord).filter_by(rfq_number=rdata["rfq_number"]).first()
            for sup in rdata["suppliers"]:
                lk_id = link_by_key.get((r.id, sup["id"]))
                _upsert_audit(s, {
                    "item_type": "rfq_supplier_match",
                    "entity_id": lk_id,
                    "company_id": sup["id"],
                    "title": f"{r.rfq_number} 供应商匹配审核 (供应商 {sup['id']})",
                    "payload": {"rfq_id": r.id, "rfq_number": r.rfq_number,
                                "supplier_company_id": sup["id"],
                                "match_score": sup.get("match_score")},
                    "status": "pending",
                })
                match_count += 1

        # 报价异常审核 (RFQ3: 360 >= 220*1.5=330)
        for rdata in RFQS:
            r = s.query(RfqRecord).filter_by(rfq_number=rdata["rfq_number"]).first()
            for qdata in QUOTATIONS.get(rdata["rfq_number"], []):
                if r.target_price and qdata["unit_price"] >= r.target_price * 1.5:
                    qid = quote_by_key.get((rdata["rfq_number"], qdata["supplier_company_id"]))
                    _upsert_audit(s, {
                        "item_type": "quotation_anomaly",
                        "entity_id": qid,
                        "company_id": qdata["supplier_company_id"],
                        "title": f"{r.rfq_number} 报价异常审核 (供应商 {qdata['supplier_company_id']})",
                        "payload": {"rfq_id": r.id, "rfq_number": r.rfq_number,
                                    "quotation_id": qid,
                                    "unit_price": qdata["unit_price"],
                                    "target_price": r.target_price},
                        "status": "pending",
                    })

        # 供应商能力审核 (独立项)
        for adata in AUDIT_ITEMS:
            _upsert_audit(s, adata)

    # 统计
    with session_scope() as s:
        logger.info(
            "RFQ=%d, 线索=%d, 报价=%d, 审核项=%d",
            s.query(RfqRecord).count(),
            s.query(RfqSupplierLink).count(),
            s.query(QuotationRecord).count(),
            s.query(AuditQueueItem).count(),
        )
    logger.info("缺件采购闭环种子完成 (幂等)")


if __name__ == "__main__":
    seed()
