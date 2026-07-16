"""
RFQ 询价闭环 API: 创建 / 查询 / 发送 / 报价 / 报价对比。

路由 (prefix="", tags=["rfq"]):
  POST /rfqs                           创建 RFQ (可带候选供应商)
  GET  /rfqs                           RFQ 列表 (可按 buyer_company_id / status 过滤)
  GET  /rfqs/{rfq_id}                  RFQ 详情 (含供应商线索)
  POST /rfqs/{rfq_id}/send             发送 RFQ 给候选供应商 (生成线索 + 审核项)
  GET  /companies/{company_id}/rfqs    某买方企业的 RFQ 列表
  POST /rfqs/{rfq_id}/quotations       供应商提交报价
  GET  /rfqs/{rfq_id}/quotations       RFQ 下全部报价
  GET  /rfqs/{rfq_id}/quote-comparison 买方报价对比视图

访问控制: 本阶段不做复杂权限体系, 复用 Phase 1 的 check_company_access
(默认 demo 用户公开访问; 命中白名单则强制隔离)。供应商报价/线索按 supplier_company_id 校验。
"""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from kb.db import session_scope
from kb.models import (
    AuditQueueItem,
    CompanyCache,
    QuotationRecord,
    RfqRecord,
    RfqSupplierLink,
)
from api.deps import check_company_access, get_current_user

router = APIRouter(tags=["rfq"])


# ============================================================
# Pydantic 请求模型
# ============================================================
class RfqCreate(BaseModel):
    buyer_company_id: int
    title: str
    part_number: str | None = None
    part_name: str | None = None
    quantity: int = 1
    unit: str = "个"
    target_price: float | None = None
    lead_time_days: int | None = None
    accept_alternatives: bool = False
    scenario: str | None = None
    raw_query: str | None = None
    # 候选供应商 (仅 company_id 即可, 也可带匹配分/理由)
    supplier_candidates: list[int] | None = None
    # Phase 2 Dashboard 兼容字段 (不强依赖, 存入 context_json)
    shortage_id: str | None = None
    product_id: int | None = None
    recommended_action_id: str | None = None


class RfqSend(BaseModel):
    supplier_company_ids: list[int] | None = Field(
        default=None, description="指定发送的供应商; 为空则发送给全部 pending 候选"
    )


class QuotationCreate(BaseModel):
    supplier_company_id: int
    part_number: str | None = None
    unit_price: float
    currency: str = "CNY"
    moq: int | None = None
    lead_time_days: int | None = None
    stock_qty: int | None = None
    valid_until: datetime | None = None
    is_in_stock: bool = False
    note: str | None = None


# ============================================================
# 序列化 / 辅助
# ============================================================
def _parse_json(raw: str | None, default):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _require_company(s, company_id: int) -> CompanyCache:
    c = s.get(CompanyCache, company_id)
    if not c:
        raise HTTPException(status_code=404, detail=f"公司 {company_id} 不存在")
    return c


def _gen_rfq_number(s) -> str:
    """生成 RFQ-YYYY-NNNN 编号 (按当年序号, 冲突时自增)。"""
    year = datetime.utcnow().year
    prefix = f"RFQ-{year}-"
    rows = s.query(RfqRecord).filter(RfqRecord.rfq_number.like(f"{prefix}%")).all()
    max_seq = 0
    for r in rows:
        try:
            max_seq = max(max_seq, int(r.rfq_number[len(prefix):]))
        except (ValueError, TypeError):
            continue
    return f"{prefix}{max_seq + 1:04d}"


def _rfq_dict(r: RfqRecord) -> dict:
    return {
        "id": r.id,
        "rfq_number": r.rfq_number,
        "buyer_company_id": r.buyer_company_id,
        "title": r.title,
        "raw_query": r.raw_query,
        "part_number": r.part_number,
        "part_name": r.part_name,
        "quantity": r.quantity,
        "unit": r.unit,
        "target_price": r.target_price,
        "lead_time_days": r.lead_time_days,
        "accept_alternatives": r.accept_alternatives,
        "scenario": r.scenario,
        "status": r.status,
        "created_by": r.created_by,
        "context": _parse_json(r.context_json, {}),
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _link_dict(s, lk: RfqSupplierLink) -> dict:
    sup = s.get(CompanyCache, lk.supplier_company_id)
    return {
        "id": lk.id,
        "rfq_id": lk.rfq_id,
        "supplier_company_id": lk.supplier_company_id,
        "supplier_name": sup.name if sup else None,
        "match_score": lk.match_score,
        "match_reason": lk.match_reason,
        "status": lk.status,
        "sent_at": lk.sent_at.isoformat() if lk.sent_at else None,
        "viewed_at": lk.viewed_at.isoformat() if lk.viewed_at else None,
        "created_at": lk.created_at.isoformat() if lk.created_at else None,
    }


def _quote_dict(s, q: QuotationRecord) -> dict:
    sup = s.get(CompanyCache, q.supplier_company_id)
    return {
        "id": q.id,
        "rfq_id": q.rfq_id,
        "supplier_company_id": q.supplier_company_id,
        "supplier_name": sup.name if sup else None,
        "part_number": q.part_number,
        "unit_price": q.unit_price,
        "currency": q.currency,
        "moq": q.moq,
        "lead_time_days": q.lead_time_days,
        "stock_qty": q.stock_qty,
        "valid_until": q.valid_until.isoformat() if q.valid_until else None,
        "is_in_stock": q.is_in_stock,
        "note": q.note,
        "created_at": q.created_at.isoformat() if q.created_at else None,
    }


def _get_rfq(s, rfq_id: int) -> RfqRecord:
    r = s.get(RfqRecord, rfq_id)
    if not r:
        raise HTTPException(status_code=404, detail=f"RFQ {rfq_id} 不存在")
    return r


# ============================================================
# RFQ 增删查
# ============================================================
@router.post("/rfqs")
def create_rfq(req: RfqCreate, user: dict = Depends(get_current_user)):
    """创建 RFQ。可选附候选供应商 (创建 pending 线索)。"""
    check_company_access(user, req.buyer_company_id)
    # 候选供应商必须存在
    candidates = req.supplier_candidates or []
    with session_scope() as s:
        _require_company(s, req.buyer_company_id)
        for sid in candidates:
            _require_company(s, sid)

        # Phase 2 兼容字段 -> context_json
        ctx = {}
        if req.shortage_id is not None:
            ctx["shortage_id"] = req.shortage_id
        if req.product_id is not None:
            ctx["product_id"] = req.product_id
        if req.recommended_action_id is not None:
            ctx["recommended_action_id"] = req.recommended_action_id

        r = RfqRecord(
            rfq_number=_gen_rfq_number(s),
            buyer_company_id=req.buyer_company_id,
            title=req.title,
            raw_query=req.raw_query,
            part_number=req.part_number,
            part_name=req.part_name,
            quantity=req.quantity,
            unit=req.unit,
            target_price=req.target_price,
            lead_time_days=req.lead_time_days,
            accept_alternatives=req.accept_alternatives,
            scenario=req.scenario,
            status="draft",
            created_by=user["user_id"],
            context_json=json.dumps(ctx, ensure_ascii=False) if ctx else None,
        )
        s.add(r)
        s.flush()

        links = []
        for sid in candidates:
            lk = RfqSupplierLink(
                rfq_id=r.id, supplier_company_id=sid, status="pending",
            )
            s.add(lk)
            s.flush()
            links.append(lk)

        return {
            "rfq": _rfq_dict(r),
            "supplier_leads": [_link_dict(s, lk) for lk in links],
        }


@router.get("/rfqs")
def list_rfqs(
    buyer_company_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
):
    """RFQ 列表 (可按买方/状态过滤)。"""
    with session_scope() as s:
        q = s.query(RfqRecord)
        if buyer_company_id is not None:
            q = q.filter(RfqRecord.buyer_company_id == buyer_company_id)
        if status:
            q = q.filter(RfqRecord.status == status)
        rows = q.order_by(RfqRecord.id.desc()).all()
        return {"items": [_rfq_dict(r) for r in rows], "total": len(rows)}


@router.get("/rfqs/{rfq_id}")
def get_rfq(rfq_id: int, user: dict = Depends(get_current_user)):
    """RFQ 详情 (含供应商线索)。"""
    with session_scope() as s:
        r = _get_rfq(s, rfq_id)
        links = (
            s.query(RfqSupplierLink)
            .filter_by(rfq_id=rfq_id)
            .order_by(RfqSupplierLink.id)
            .all()
        )
        return {**_rfq_dict(r), "supplier_leads": [_link_dict(s, lk) for lk in links]}


@router.post("/rfqs/{rfq_id}/send")
def send_rfq(rfq_id: int, req: RfqSend, user: dict = Depends(get_current_user)):
    """发送 RFQ 给候选供应商: pending -> sent, 生成审核项。"""
    with session_scope() as s:
        r = _get_rfq(s, rfq_id)
        check_company_access(user, r.buyer_company_id)

        q = s.query(RfqSupplierLink).filter_by(rfq_id=rfq_id)
        if req.supplier_company_ids:
            q = q.filter(RfqSupplierLink.supplier_company_id.in_(req.supplier_company_ids))
        links = q.all()
        if not links:
            raise HTTPException(status_code=400, detail="该 RFQ 无可发送的候选供应商")

        now = datetime.utcnow()
        sent_leads = []
        for lk in links:
            # 仅 pending 的才转 sent; 已 sent/viewed/quoted 的保持原状
            if lk.status == "pending":
                lk.status = "sent"
                lk.sent_at = now
            sent_leads.append(lk)

        # RFQ 状态推进
        if r.status == "draft":
            r.status = "sent"

        # 生成 "RFQ 供应商匹配" 审核项 (幂等: 同 link 不重复建 pending 项)
        for lk in sent_leads:
            exists = (
                s.query(AuditQueueItem)
                .filter_by(item_type="rfq_supplier_match", entity_id=lk.id)
                .first()
            )
            if not exists:
                s.add(AuditQueueItem(
                    item_type="rfq_supplier_match",
                    entity_id=lk.id,
                    company_id=lk.supplier_company_id,
                    title=f"{r.rfq_number} 供应商匹配审核 (供应商 {lk.supplier_company_id})",
                    payload_json=json.dumps({
                        "rfq_id": r.id, "rfq_number": r.rfq_number,
                        "supplier_company_id": lk.supplier_company_id,
                        "match_score": lk.match_score,
                    }, ensure_ascii=False),
                    status="pending",
                ))
        s.flush()
        return {
            "rfq_id": r.id,
            "rfq_number": r.rfq_number,
            "status": r.status,
            "sent_leads": [_link_dict(s, lk) for lk in sent_leads],
        }


@router.get("/companies/{company_id}/rfqs")
def list_company_rfqs(
    company_id: int,
    status: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
):
    """某买方企业的 RFQ 列表。"""
    check_company_access(user, company_id)
    with session_scope() as s:
        _require_company(s, company_id)
        q = s.query(RfqRecord).filter_by(buyer_company_id=company_id)
        if status:
            q = q.filter(RfqRecord.status == status)
        rows = q.order_by(RfqRecord.id.desc()).all()
        return {
            "company_id": company_id,
            "items": [_rfq_dict(r) for r in rows],
            "total": len(rows),
        }


# ============================================================
# 报价
# ============================================================
@router.post("/rfqs/{rfq_id}/quotations")
def create_quotation(
    rfq_id: int,
    req: QuotationCreate,
    user: dict = Depends(get_current_user),
):
    """供应商提交报价。需存在已发送的供应商线索, 否则 403。"""
    check_company_access(user, req.supplier_company_id)
    with session_scope() as s:
        r = _get_rfq(s, rfq_id)
        _require_company(s, req.supplier_company_id)

        lk = (
            s.query(RfqSupplierLink)
            .filter_by(rfq_id=rfq_id, supplier_company_id=req.supplier_company_id)
            .first()
        )
        if not lk:
            raise HTTPException(
                status_code=403,
                detail=f"供应商 {req.supplier_company_id} 未收到 RFQ {rfq_id}, 无法报价",
            )
        if lk.status == "declined":
            raise HTTPException(status_code=400, detail="该供应商已拒绝此 RFQ, 无法报价")

        q = QuotationRecord(
            rfq_id=rfq_id,
            supplier_company_id=req.supplier_company_id,
            part_number=req.part_number or r.part_number,
            unit_price=req.unit_price,
            currency=req.currency,
            moq=req.moq,
            lead_time_days=req.lead_time_days,
            stock_qty=req.stock_qty,
            valid_until=req.valid_until,
            is_in_stock=req.is_in_stock,
            note=req.note,
        )
        s.add(q)
        s.flush()

        # 线索 -> quoted
        if lk.status in ("sent", "viewed", "pending"):
            lk.status = "quoted"
        # RFQ 状态推进
        if r.status in ("sent", "draft"):
            r.status = "quoted"

        # 异常报价审核: 单价 >= 目标价 1.5 倍 (或目标价为空但单价 <= 0)
        anomaly = False
        if r.target_price and req.unit_price >= r.target_price * 1.5:
            anomaly = True
        elif req.unit_price <= 0:
            anomaly = True
        if anomaly:
            s.add(AuditQueueItem(
                item_type="quotation_anomaly",
                entity_id=q.id,
                company_id=req.supplier_company_id,
                title=f"{r.rfq_number} 报价异常审核 (供应商 {req.supplier_company_id})",
                payload_json=json.dumps({
                    "rfq_id": r.id, "rfq_number": r.rfq_number,
                    "quotation_id": q.id, "unit_price": req.unit_price,
                    "target_price": r.target_price,
                }, ensure_ascii=False),
                status="pending",
            ))

        s.flush()
        return {"quotation": _quote_dict(s, q), "lead_status": lk.status}


@router.get("/rfqs/{rfq_id}/quotations")
def list_quotations(rfq_id: int, user: dict = Depends(get_current_user)):
    """RFQ 下全部报价。"""
    with session_scope() as s:
        _get_rfq(s, rfq_id)
        rows = (
            s.query(QuotationRecord)
            .filter_by(rfq_id=rfq_id)
            .order_by(QuotationRecord.unit_price.asc())
            .all()
        )
        return {
            "rfq_id": rfq_id,
            "items": [_quote_dict(s, q) for q in rows],
            "total": len(rows),
        }


@router.get("/rfqs/{rfq_id}/quote-comparison")
def quote_comparison(rfq_id: int, user: dict = Depends(get_current_user)):
    """买方报价对比视图: 按单价排序 + 是否达标 + 最低价标记。"""
    with session_scope() as s:
        r = _get_rfq(s, rfq_id)
        rows = (
            s.query(QuotationRecord)
            .filter_by(rfq_id=rfq_id)
            .order_by(QuotationRecord.unit_price.asc())
            .all()
        )
        quotes = [_quote_dict(s, q) for q in rows]
        target = r.target_price
        cheapest = quotes[0]["unit_price"] if quotes else None
        for i, qd in enumerate(quotes):
            qd["rank"] = i + 1
            qd["is_lowest"] = (i == 0)
            if target is not None:
                qd["meets_target"] = qd["unit_price"] <= target
                qd["delta_vs_target"] = round(qd["unit_price"] - target, 4)
            else:
                qd["meets_target"] = None
                qd["delta_vs_target"] = None
        return {
            "rfq_id": rfq_id,
            "rfq_number": r.rfq_number,
            "target_price": target,
            "quantity": r.quantity,
            "quote_count": len(quotes),
            "lowest_price": cheapest,
            "items": quotes,
        }
