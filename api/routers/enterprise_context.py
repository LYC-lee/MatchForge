"""
企业驾驶舱上下文 API: 当前企业视角的基础信息聚合。

为前端"经营驾驶舱"提供:
  - 企业画像 (profile + segment + chain_position + role)
  - 知识库状态
  - 产品数 / 上下游伙伴数 (即时计算)
  - order_count / shortage_count 暂为占位 0 (需业务表 ORM, 见 TODO, 后续阶段)

路由:
  GET /api/v1/enterprise-context/companies     企业驾驶舱列表 (全公司 + 摘要)
  GET /api/v1/enterprise-context/{company_id}  单企业驾驶舱上下文
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from kb.db import session_scope
from kb.models import CompanyCache, CompanyRelationship, Product
from api.deps import get_current_user

router = APIRouter(prefix="/enterprise-context", tags=["enterprise-context"])


def _build_context(s, c: CompanyCache) -> dict:
    """构建单企业驾驶舱上下文。"""
    cid = c.id
    product_count = s.query(Product).filter_by(company_id=cid).count()
    upstream_count = (
        s.query(CompanyRelationship)
        .filter_by(source_company_id=cid, direction="upstream", status="active")
        .count()
    )
    downstream_count = (
        s.query(CompanyRelationship)
        .filter_by(source_company_id=cid, direction="downstream", status="active")
        .count()
    )
    return {
        "company_id": cid,
        "company": {
            "id": cid,
            "name": c.name,
            "name_en": c.name_en,
            "name_alias": c.name_alias,
            "country": c.country,
            "region": c.region,
            "website": c.website,
            "description": c.description,
        },
        "segment_code": c.segment_code,
        "segment_name": c.segment_name_cn,
        "segment_name_en": c.segment_name_en,
        "chain_position": c.chain_position,
        "role": c.role,
        "product_count": product_count,
        # TODO(驾驶舱 P1): order_count 需接入 rfqs/quotations 业务表 ORM (当前无 ORM, 占位 0)
        "order_count": 0,
        # TODO(驾驶舱 P1): shortage_count 需接入库存/风险监控 (kpi_snapshots/risk_alerts 后续阶段)
        "shortage_count": 0,
        "upstream_count": upstream_count,
        "downstream_count": downstream_count,
        "knowledge_status": c.knowledge_status,
    }


@router.get("/companies")
def list_enterprise_contexts(user: dict = Depends(get_current_user)):
    """企业驾驶舱列表 (所有公司 + 驾驶舱摘要)。"""
    with session_scope() as s:
        rows = s.query(CompanyCache).order_by(CompanyCache.id).all()
        return {
            "items": [_build_context(s, c) for c in rows],
            "total": len(rows),
        }


@router.get("/{company_id}")
def get_enterprise_context(company_id: int, user: dict = Depends(get_current_user)):
    """单个企业的驾驶舱上下文。"""
    with session_scope() as s:
        c = s.get(CompanyCache, company_id)
        if not c:
            raise HTTPException(status_code=404, detail=f"公司 {company_id} 不存在")
        return _build_context(s, c)
