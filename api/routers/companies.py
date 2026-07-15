"""
公司相关 API: 列表 / 详情 / 知识状态。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from kb.db import session_scope
from kb.models import CompanyCache, Product
from kb.pipeline import company_knowledge_status
from api.deps import check_company_access, get_current_user

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("")
def list_companies(
    search: str | None = Query(default=None),
    segment: str | None = Query(default=None),
    knowledge_ready: bool | None = Query(default=None),
    user: dict = Depends(get_current_user),
):
    """公司列表 (带搜索/过滤)。"""
    with session_scope() as s:
        q = s.query(CompanyCache)
        if search:
            like = f"%{search}%"
            q = q.filter(
                (CompanyCache.name.like(like))
                | (CompanyCache.name_en.like(like))
                | (CompanyCache.name_alias.like(like))
            )
        if segment:
            q = q.filter(CompanyCache.segment_code == segment)
        if knowledge_ready is True:
            q = q.filter(CompanyCache.knowledge_status == "ready")
        rows = q.order_by(CompanyCache.id).all()
        return {
            "items": [
                {
                    "id": c.id,
                    "name": c.name,
                    "name_en": c.name_en,
                    "country": c.country,
                    "region": c.region,
                    "segment_code": c.segment_code,
                    "segment_name": c.segment_name_cn,
                    "role": c.role,
                    "knowledge_status": c.knowledge_status,
                    "last_generated_at": c.last_generated_at.isoformat() if c.last_generated_at else None,
                }
                for c in rows
            ],
            "total": len(rows),
        }


@router.get("/segments")
def list_segments(user: dict = Depends(get_current_user)):
    """产业环节列表 (用于筛选)。"""
    with session_scope() as s:
        rows = (
            s.query(CompanyCache.segment_code, CompanyCache.segment_name_cn)
            .filter(CompanyCache.segment_code.isnot(None))
            .distinct()
            .all()
        )
        return {"items": [{"code": r[0], "name": r[1]} for r in rows]}


@router.get("/{company_id}")
def get_company_detail(company_id: int, user: dict = Depends(get_current_user)):
    """公司详情。"""
    check_company_access(user, company_id)
    with session_scope() as s:
        c = s.get(CompanyCache, company_id)
        if not c:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="公司不存在")
        return {
            "id": c.id,
            "name": c.name,
            "name_en": c.name_en,
            "name_alias": c.name_alias,
            "country": c.country,
            "region": c.region,
            "website": c.website,
            "description": c.description,
            "segment_code": c.segment_code,
            "segment_name": c.segment_name_cn,
            "segment_name_en": c.segment_name_en,
            "chain_position": c.chain_position,
            "role": c.role,
            "confidence_level": c.confidence_level,
            "knowledge_status": c.knowledge_status,
            "last_generated_at": c.last_generated_at.isoformat() if c.last_generated_at else None,
        }


@router.get("/{company_id}/knowledge")
def get_company_knowledge(company_id: int, user: dict = Depends(get_current_user)):
    """公司知识库状态 (管理员/用户可见概览)。"""
    check_company_access(user, company_id)
    return company_knowledge_status(company_id)


@router.get("/{company_id}/products")
def get_company_products(company_id: int, user: dict = Depends(get_current_user)):
    """公司结构化产品列表 (用于产品比较)。"""
    check_company_access(user, company_id)
    with session_scope() as s:
        rows = s.query(Product).filter_by(company_id=company_id).all()
        import json

        return {
            "items": [
                {
                    "id": p.id,
                    "product_name": p.product_name,
                    "product_series": p.product_series,
                    "product_model": p.product_model,
                    "category": p.category,
                    "positioning": p.positioning,
                    "price": p.price,
                    "price_min": p.price_min,
                    "price_max": p.price_max,
                    "currency": p.currency,
                    "price_type": p.price_type,
                    "specification": json.loads(p.specification) if p.specification else {},
                    "language": p.language,
                    "source_type": p.source_type,
                    "confidence": p.confidence,
                }
                for p in rows
            ]
        }
