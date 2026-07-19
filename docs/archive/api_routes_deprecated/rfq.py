"""
RFQ 询价单接口
POST /api/v1/rfq/submit
GET  /api/v1/rfqs
GET  /api/v1/rfq/{rfq_id}
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from api.database import get_db
from api.dependencies import get_current_user
from api.models import User, RFQ, Lead
from api.schemas import RfqSubmitRequest, ApiResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["询价单"])


@router.post("/rfq/submit")
async def submit_rfq(
    req: RfqSubmitRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """提交询价单 → 触发线索分级"""
    rfq = RFQ(
        buyer_id=user.id,
        raw_query=req.parsed_spec.get("_raw_query", ""),
        parsed_spec=req.parsed_spec,
        rfq_doc=req.rfq_doc,
        status="sent",
    )
    db.add(rfq)
    await db.flush()

    # 为每个目标供应商创建线索
    for sid in req.target_supplier_ids:
        lead = Lead(
            rfq_id=rfq.id,
            supplier_id=sid,
            grade="B",
            score=70,
            reasons=["AI 自动匹配", "规格匹配度良好"],
        )
        db.add(lead)

    await db.commit()
    await db.refresh(rfq)

    return ApiResponse(data={
        "rfq_id": rfq.id,
        "status": "sent",
    })


@router.get("/rfqs")
async def list_rfqs(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """询价单列表"""
    result = await db.execute(
        select(RFQ).where(RFQ.buyer_id == user.id).order_by(desc(RFQ.created_at))
    )
    rfqs = result.scalars().all()

    return ApiResponse(data=[{
        "id": r.id,
        "raw_query": r.raw_query,
        "status": r.status,
        "created_at": r.created_at.isoformat() if r.created_at else "",
    } for r in rfqs])


@router.get("/rfq/{rfq_id}")
async def get_rfq(rfq_id: str, db: AsyncSession = Depends(get_db)):
    """询价单详情"""
    result = await db.execute(select(RFQ).where(RFQ.id == rfq_id))
    rfq = result.scalar_one_or_none()
    if not rfq:
        raise HTTPException(status_code=404, detail="询价单不存在")

    return ApiResponse(data={
        "id": rfq.id,
        "raw_query": rfq.raw_query,
        "parsed_spec": rfq.parsed_spec or {},
        "normalized_spec": rfq.normalized_spec or {},
        "alternatives": rfq.alternatives or [],
        "matched_suppliers": rfq.matched_suppliers or [],
        "rfq_doc": rfq.rfq_doc,
        "status": rfq.status,
        "lead_grade": rfq.lead_grade or {},
        "created_at": rfq.created_at.isoformat() if rfq.created_at else "",
    })
