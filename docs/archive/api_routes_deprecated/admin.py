"""
运营后台接口
GET  /api/v1/admin/audit
POST /api/v1/admin/audit/{id}
GET  /api/v1/admin/metrics
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from api.database import get_db
from api.dependencies import get_current_user
from api.models import User, AuditRecord, RFQ, Lead, Supplier
from api.schemas import AuditAction, ApiResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["运营管理"])


@router.get("/audit")
async def get_audit_queue(
    type: str = "alternatives",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """审核队列"""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可访问")

    result = await db.execute(
        select(AuditRecord).where(AuditRecord.target_type == type)
        .order_by(desc(AuditRecord.created_at)).limit(50)
    )
    records = result.scalars().all()

    return ApiResponse(data=[{
        "id": r.id,
        "target_type": r.target_type,
        "target_id": r.target_id,
        "action": r.action,
        "note": r.note,
        "created_at": r.created_at.isoformat() if r.created_at else "",
    } for r in records])


@router.post("/audit/{audit_id}")
async def perform_audit(
    audit_id: str,
    action: AuditAction,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """执行审核操作"""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")

    result = await db.execute(select(AuditRecord).where(AuditRecord.id == audit_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="审核记录不存在")

    record.action = action.action
    record.note = action.note
    await db.commit()

    return ApiResponse(data={"status": "updated", "action": action.action})


@router.get("/metrics")
async def get_metrics(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """运营指标"""
    # 总数统计
    rfq_count = (await db.execute(select(func.count(RFQ.id)))).scalar() or 0
    lead_count = (await db.execute(select(func.count(Lead.id)))).scalar() or 0
    supplier_count = (await db.execute(select(func.count(Supplier.id)))).scalar() or 0
    user_count = (await db.execute(select(func.count(User.id)))).scalar() or 0

    return ApiResponse(data={
        "total_rfqs": rfq_count,
        "total_leads": lead_count,
        "total_suppliers": supplier_count,
        "total_users": user_count,
    })
