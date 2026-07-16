"""
供应商接口
GET /api/v1/suppliers, /suppliers/{id}
POST /api/v1/suppliers/onboard
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.database import get_db
from api.models import Supplier
from api.schemas import ApiResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/suppliers", tags=["供应商"])


@router.get("")
async def list_suppliers(
    category: str = "",
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """供应商列表/搜索"""
    query = select(Supplier).where(Supplier.status == "approved")

    if category:
        # JSON 字段模糊搜索 (SQLite 兼容)
        query = query.where(Supplier.categories.contains(category))
    if keyword:
        query = query.where(Supplier.name.contains(keyword))

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    suppliers = result.scalars().all()

    return ApiResponse(data=[{
        "id": s.id,
        "name": s.name,
        "location": s.location,
        "region": s.region,
        "categories": s.categories or [],
        "brands": s.brands or [],
        "qualifications": s.qualifications or [],
        "moq": s.moq,
        "lead_time_weeks": s.lead_time_weeks,
        "match_score": s.match_score,
        "updated_at": s.updated_at.isoformat() if s.updated_at else "",
    } for s in suppliers])


@router.get("/{supplier_id}")
async def get_supplier(supplier_id: str, db: AsyncSession = Depends(get_db)):
    """供应商详情"""
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="供应商不存在")

    return ApiResponse(data={
        "id": s.id,
        "name": s.name,
        "location": s.location,
        "region": s.region,
        "categories": s.categories or [],
        "brands": s.brands or [],
        "qualifications": s.qualifications or [],
        "moq": s.moq,
        "lead_time_weeks": s.lead_time_weeks,
        "response_speed": s.response_speed,
        "data_source": s.data_source,
        "match_score": s.match_score,
        "rating": s.rating,
        "updated_at": s.updated_at.isoformat() if s.updated_at else "",
    })
