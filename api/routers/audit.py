"""
审核队列 API (管理员): 基础审核队列, 不做复杂工作流。

路由 (prefix="/admin", tags=["audit"]):
  GET  /admin/audit-queue                  审核队列 (可按 status / item_type 过滤)
  POST /admin/audit-queue/{item_id}/approve   审核通过
  POST /admin/audit-queue/{item_id}/reject    审核驳回

审核对象: supplier_capability / rfq_supplier_match / quotation_anomaly
访问控制: require_admin (会话 token role=admin)。管理员账号需通过真实登录或显式
seed 脚本创建; 源码不硬编码任何 admin token。
"""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from kb.db import session_scope
from kb.models import AuditQueueItem
from api.deps import require_admin

router = APIRouter(prefix="/admin", tags=["audit"])


class ReviewNote(BaseModel):
    note: str | None = None


def _item_dict(it: AuditQueueItem) -> dict:
    return {
        "id": it.id,
        "item_type": it.item_type,
        "entity_id": it.entity_id,
        "company_id": it.company_id,
        "title": it.title,
        "payload": json.loads(it.payload_json) if it.payload_json else {},
        "status": it.status,
        "review_note": it.review_note,
        "created_at": it.created_at.isoformat() if it.created_at else None,
        "reviewed_at": it.reviewed_at.isoformat() if it.reviewed_at else None,
    }


def _get_item(s, item_id: int) -> AuditQueueItem:
    it = s.get(AuditQueueItem, item_id)
    if not it:
        raise HTTPException(status_code=404, detail=f"审核项 {item_id} 不存在")
    return it


@router.get("/audit-queue")
def list_audit_queue(
    status: str | None = Query(default=None, description="pending|approved|rejected"),
    item_type: str | None = Query(default=None),
    admin: dict = Depends(require_admin),
):
    """管理员审核队列。"""
    with session_scope() as s:
        q = s.query(AuditQueueItem)
        if status:
            q = q.filter(AuditQueueItem.status == status)
        if item_type:
            q = q.filter(AuditQueueItem.item_type == item_type)
        rows = q.order_by(AuditQueueItem.id.desc()).all()
        return {"items": [_item_dict(it) for it in rows], "total": len(rows)}


@router.post("/audit-queue/{item_id}/approve")
def approve_item(
    item_id: int,
    body: ReviewNote | None = None,
    admin: dict = Depends(require_admin),
):
    """审核通过。"""
    with session_scope() as s:
        it = _get_item(s, item_id)
        it.status = "approved"
        it.reviewed_at = datetime.utcnow()
        if body and body.note:
            it.review_note = body.note
        s.flush()
        return {"item": _item_dict(it)}


@router.post("/audit-queue/{item_id}/reject")
def reject_item(
    item_id: int,
    body: ReviewNote | None = None,
    admin: dict = Depends(require_admin),
):
    """审核驳回。"""
    with session_scope() as s:
        it = _get_item(s, item_id)
        it.status = "rejected"
        it.reviewed_at = datetime.utcnow()
        if body and body.note:
            it.review_note = body.note
        s.flush()
        return {"item": _item_dict(it)}
