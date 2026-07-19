"""
供应商接口 (旧 routes 目录，当前未注册到 main.py，保留兼容)。

注意: 品类/品牌/MOQ 等信息在 supplier_capabilities 表中，不在 suppliers 表。
本路由仅返回 suppliers 主体表字段。如需品类信息，应通过 mysql_client.filter_suppliers_raw 查询。
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
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """供应商列表/搜索 (仅主体表字段)"""
    query = select(Supplier).where(Supplier.status == "approved")

    if keyword:
        query = query.where(Supplier.name.contains(keyword))

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    suppliers = result.scalars().all()

    return ApiResponse(data=[{
        "id": s.id,
        "name": s.name,
        "location": s.location,
        "rating": s.rating,
        "status": s.status,
        "contact_phone": s.contact_phone,
        "contact_email": s.contact_email,
        "updated_at": s.updated_at.isoformat() if s.updated_at else "",
    } for s in suppliers])


@router.get("/{supplier_id}")
async def get_supplier(supplier_id: int, db: AsyncSession = Depends(get_db)):
    """供应商详情 (仅主体表字段)"""
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="供应商不存在")

    return ApiResponse(data={
        "id": s.id,
        "name": s.name,
        "location": s.location,
        "rating": s.rating,
        "status": s.status,
        "contact_phone": s.contact_phone,
        "contact_email": s.contact_email,
        "created_at": s.created_at.isoformat() if s.created_at else "",
        "updated_at": s.updated_at.isoformat() if s.updated_at else "",
    })
