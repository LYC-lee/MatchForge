"""
线索接口 (供应商端)
GET /api/v1/leads
"""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from api.database import get_db
from api.dependencies import get_current_user
from api.models import User, Lead, RFQ
from api.schemas import ApiResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["线索"])


@router.get("/leads")
async def list_leads(
    grade: str = "",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """线索列表（供应商端）"""
    query = select(Lead).order_by(desc(Lead.score))
    if grade:
        query = query.where(Lead.grade == grade)

    result = await db.execute(query)
    leads = result.scalars().all()

    # 关联询价信息
    data = []
    for lead in leads:
        rfq = None
        if lead.rfq_id:
            r = await db.execute(select(RFQ).where(RFQ.id == lead.rfq_id))
            rfq = r.scalar_one_or_none()

        data.append({
            "id": lead.id,
            "rfq_id": lead.rfq_id,
            "supplier_id": lead.supplier_id,
            "grade": lead.grade,
            "score": lead.score,
            "reasons": lead.reasons or [],
            "status": lead.status,
            "raw_query": rfq.raw_query if rfq else "",
            "created_at": lead.created_at.isoformat() if lead.created_at else "",
        })

    return ApiResponse(data=data)
