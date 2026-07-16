"""
供应商线索 API: 供应商企业查看收到的 RFQ 线索, 并标记查看/拒绝。

路由 (prefix="", tags=["supplier-leads"]):
  GET  /suppliers/{company_id}/leads          供应商收到的 RFQ 线索 (可按 status 过滤)
  POST /supplier-leads/{lead_id}/view         供应商标记线索已查看 (sent -> viewed)
  POST /supplier-leads/{lead_id}/decline      供应商拒绝线索 (-> declined)

访问控制: check_company_access(supplier_company_id) -- 命中白名单时强制企业隔离,
保证 "无关企业不能查看不属于自己的线索"。
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from kb.db import session_scope
from kb.models import CompanyCache, RfqRecord, RfqSupplierLink
from api.deps import check_company_access, get_current_user

router = APIRouter(tags=["supplier-leads"])


def _require_company(s, company_id: int) -> CompanyCache:
    c = s.get(CompanyCache, company_id)
    if not c:
        raise HTTPException(status_code=404, detail=f"公司 {company_id} 不存在")
    return c


def _lead_dict(s, lk: RfqSupplierLink) -> dict:
    r = s.get(RfqRecord, lk.rfq_id)
    buyer = s.get(CompanyCache, r.buyer_company_id) if r else None
    return {
        "id": lk.id,
        "rfq_id": lk.rfq_id,
        "rfq_number": r.rfq_number if r else None,
        "rfq_title": r.title if r else None,
        "rfq_status": r.status if r else None,
        "buyer_company_id": r.buyer_company_id if r else None,
        "buyer_name": buyer.name if buyer else None,
        "supplier_company_id": lk.supplier_company_id,
        "part_number": r.part_number if r else None,
        "part_name": r.part_name if r else None,
        "quantity": r.quantity if r else None,
        "unit": r.unit if r else None,
        "target_price": r.target_price if r else None,
        "lead_time_days": r.lead_time_days if r else None,
        "accept_alternatives": r.accept_alternatives if r else None,
        "match_score": lk.match_score,
        "match_reason": lk.match_reason,
        "status": lk.status,
        "sent_at": lk.sent_at.isoformat() if lk.sent_at else None,
        "viewed_at": lk.viewed_at.isoformat() if lk.viewed_at else None,
        "created_at": lk.created_at.isoformat() if lk.created_at else None,
    }


def _get_lead(s, lead_id: int) -> RfqSupplierLink:
    lk = s.get(RfqSupplierLink, lead_id)
    if not lk:
        raise HTTPException(status_code=404, detail=f"供应商线索 {lead_id} 不存在")
    return lk


@router.get("/suppliers/{company_id}/leads")
def list_supplier_leads(
    company_id: int,
    status: str | None = Query(default=None,
                               description="pending|sent|viewed|quoted|declined"),
    user: dict = Depends(get_current_user),
):
    """某供应商企业收到的 RFQ 线索。"""
    check_company_access(user, company_id)
    with session_scope() as s:
        _require_company(s, company_id)
        q = s.query(RfqSupplierLink).filter_by(supplier_company_id=company_id)
        if status:
            q = q.filter(RfqSupplierLink.status == status)
        rows = q.order_by(RfqSupplierLink.id.desc()).all()
        return {
            "company_id": company_id,
            "items": [_lead_dict(s, lk) for lk in rows],
            "total": len(rows),
        }


class DeclineNote(BaseModel):
    note: str | None = None


@router.post("/supplier-leads/{lead_id}/view")
def view_lead(lead_id: int, user: dict = Depends(get_current_user)):
    """供应商标记线索已查看 (sent -> viewed)。"""
    with session_scope() as s:
        lk = _get_lead(s, lead_id)
        check_company_access(user, lk.supplier_company_id)
        if lk.status == "declined":
            raise HTTPException(status_code=400, detail="已拒绝的线索不可标记查看")
        if lk.status in ("sent", "pending"):
            lk.status = "viewed"
            lk.viewed_at = datetime.utcnow()
        s.flush()
        return {"lead": _lead_dict(s, lk)}


@router.post("/supplier-leads/{lead_id}/decline")
def decline_lead(lead_id: int, body: DeclineNote | None = None,
                 user: dict = Depends(get_current_user)):
    """供应商拒绝线索 (-> declined)。可选附理由。"""
    with session_scope() as s:
        lk = _get_lead(s, lead_id)
        check_company_access(user, lk.supplier_company_id)
        if lk.status == "quoted":
            raise HTTPException(status_code=400, detail="已报价的线索不可拒绝")
        lk.status = "declined"
        if body and body.note:
            lk.match_reason = (lk.match_reason + " | 拒绝: " + body.note
                               if lk.match_reason else "拒绝: " + body.note)
        s.flush()
        return {"lead": _lead_dict(s, lk)}
