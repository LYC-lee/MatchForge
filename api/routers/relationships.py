"""
企业上下游关系 API: 产业链协同视图 + 上下游协同问答。

路由 (prefix=/companies, 与 companies.router 共用前缀):
  GET  /companies/{company_id}/relationships   全部直接关系 (作为 source 或 target)
  GET  /companies/{company_id}/upstream         上游伙伴
  GET  /companies/{company_id}/downstream       下游伙伴
  GET  /companies/{company_id}/chat-partners    可协同问答的伙伴 (全部直接关系方, 去重)
  POST /companies/{company_id}/partner-chat     与指定伙伴的协同问答 (校验直接关系)

关系语义见 kb.models.CompanyRelationship:
  direction=upstream   -> target 是 source 的上游 (source 向 target 采购)
  direction=downstream -> target 是 source 的下游 (source 向 target 供货)
  direction=support    -> target 向 source 提供支撑服务
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from kb.db import session_scope
from kb.models import CompanyCache, CompanyRelationship
from kb.rag import answer
from api.deps import check_company_access, get_current_user

router = APIRouter(prefix="/companies", tags=["company-relations"])


def _parse_json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        v = json.loads(raw)
        return v if isinstance(v, list) else []
    except Exception:
        return []


def _partner_payload(s, rel: CompanyRelationship, partner_id: int) -> dict:
    """构建伙伴公司 + 关系上下文。"""
    p = s.get(CompanyCache, partner_id)
    return {
        "company_id": partner_id,
        "company_name": p.name if p else None,
        "name_en": p.name_en if p else None,
        "segment_code": p.segment_code if p else None,
        "segment_name": p.segment_name_cn if p else None,
        "chain_position": p.chain_position if p else None,
        "role": p.role if p else None,
        "knowledge_status": p.knowledge_status if p else None,
        "relationship_type": rel.relationship_type,
        "direction": rel.direction,
        "product_scope": _parse_json_list(rel.product_scope),
        "business_scope": _parse_json_list(rel.business_scope),
        "confidence_level": rel.confidence_level,
        "status": rel.status,
    }


def _require_company(s, company_id: int) -> CompanyCache:
    c = s.get(CompanyCache, company_id)
    if not c:
        raise HTTPException(status_code=404, detail=f"公司 {company_id} 不存在")
    return c


def _query_partners(s, company_id: int, direction: str | None) -> list[dict]:
    """查询指定方向的伙伴 (source=company_id)。"""
    q = s.query(CompanyRelationship).filter(
        CompanyRelationship.source_company_id == company_id,
        CompanyRelationship.status == "active",
    )
    if direction:
        q = q.filter(CompanyRelationship.direction == direction)
    return [_partner_payload(s, r, r.target_company_id) for r in q.all()]


def _query_chat_partners(s, company_id: int) -> list[dict]:
    """查询全部直接关系方 (source 或 target 任一), 去重。"""
    seen: dict[int, dict] = {}
    rows = (
        s.query(CompanyRelationship)
        .filter(
            CompanyRelationship.status == "active",
            (CompanyRelationship.source_company_id == company_id)
            | (CompanyRelationship.target_company_id == company_id),
        )
        .all()
    )
    for r in rows:
        partner_id = (
            r.target_company_id if r.source_company_id == company_id else r.source_company_id
        )
        if partner_id == company_id or partner_id in seen:
            continue
        seen[partner_id] = _partner_payload(s, r, partner_id)
    return list(seen.values())


def _has_direct_relationship(s, company_id: int, partner_company_id: int) -> bool:
    """两公司是否存在任意活跃直接关系。"""
    if company_id == partner_company_id:
        return False
    cnt = (
        s.query(CompanyRelationship)
        .filter(
            CompanyRelationship.status == "active",
            (
                (CompanyRelationship.source_company_id == company_id)
                & (CompanyRelationship.target_company_id == partner_company_id)
            )
            | (
                (CompanyRelationship.source_company_id == partner_company_id)
                & (CompanyRelationship.target_company_id == company_id)
            ),
        )
        .count()
    )
    return cnt > 0


@router.get("/{company_id}/relationships")
def list_relationships(company_id: int, user: dict = Depends(get_current_user)):
    """公司的全部直接关系 (含作为 source 与 target)。"""
    check_company_access(user, company_id)
    with session_scope() as s:
        _require_company(s, company_id)
        rows = (
            s.query(CompanyRelationship)
            .filter(
                CompanyRelationship.status == "active",
                (CompanyRelationship.source_company_id == company_id)
                | (CompanyRelationship.target_company_id == company_id),
            )
            .order_by(CompanyRelationship.id)
            .all()
        )
        items = []
        for r in rows:
            src = s.get(CompanyCache, r.source_company_id)
            tgt = s.get(CompanyCache, r.target_company_id)
            items.append({
                "id": r.id,
                "source_company_id": r.source_company_id,
                "source_company_name": src.name if src else None,
                "target_company_id": r.target_company_id,
                "target_company_name": tgt.name if tgt else None,
                "relationship_type": r.relationship_type,
                "direction": r.direction,
                "product_scope": _parse_json_list(r.product_scope),
                "business_scope": _parse_json_list(r.business_scope),
                "confidence_level": r.confidence_level,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            })
        return {"company_id": company_id, "items": items, "total": len(items)}


@router.get("/{company_id}/upstream")
def list_upstream(company_id: int, user: dict = Depends(get_current_user)):
    """公司的上游伙伴 (source=company_id, direction=upstream)。"""
    check_company_access(user, company_id)
    with session_scope() as s:
        _require_company(s, company_id)
        items = _query_partners(s, company_id, "upstream")
        return {"company_id": company_id, "direction": "upstream", "items": items, "total": len(items)}


@router.get("/{company_id}/downstream")
def list_downstream(company_id: int, user: dict = Depends(get_current_user)):
    """公司的下游伙伴 (source=company_id, direction=downstream)。"""
    check_company_access(user, company_id)
    with session_scope() as s:
        _require_company(s, company_id)
        items = _query_partners(s, company_id, "downstream")
        return {"company_id": company_id, "direction": "downstream", "items": items, "total": len(items)}


@router.get("/{company_id}/chat-partners")
def list_chat_partners(company_id: int, user: dict = Depends(get_current_user)):
    """可协同问答的伙伴 (全部直接关系方, 去重)。"""
    check_company_access(user, company_id)
    with session_scope() as s:
        _require_company(s, company_id)
        items = _query_chat_partners(s, company_id)
        return {"company_id": company_id, "items": items, "total": len(items)}


class PartnerChatRequest(BaseModel):
    partner_company_id: int
    query: str
    scope: str = Field(default="product", description="product|business")


@router.post("/{company_id}/partner-chat")
def partner_chat(
    company_id: int,
    req: PartnerChatRequest,
    user: dict = Depends(get_current_user),
):
    """
    与指定伙伴的上下游协同问答。

    校验: company_id 与 partner_company_id 必须存在直接 company_relationships, 否则 403。
    检索: 仅检索 partner_company_id 的私域知识 (company_id 隔离), 禁止全库。
    scope=product|business 限定检索手册类型。
    """
    check_company_access(user, company_id)
    with session_scope() as s:
        _require_company(s, company_id)
        _require_company(s, req.partner_company_id)
        if not _has_direct_relationship(s, company_id, req.partner_company_id):
            raise HTTPException(
                status_code=403,
                detail=(
                    f"公司 {company_id} 与 {req.partner_company_id} 无直接关系, "
                    f"拒绝协同问答"
                ),
            )

    # scope -> manual_type (复用 RAG, 仅检索伙伴知识, 服务端强制 company_id 隔离)
    manual_type = None
    if req.scope == "product":
        manual_type = "product"
    elif req.scope == "business":
        manual_type = "business"

    res = answer(
        req.query,
        company_id=req.partner_company_id,
        user_id=user["user_id"],
        language=None,
        manual_type=manual_type,
    )
    return {
        "company_id": company_id,
        "partner_company_id": req.partner_company_id,
        "scope": req.scope,
        **res,
    }
