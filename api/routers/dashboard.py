"""
企业经营驾驶舱 Phase2 API: 产品/BOM/订单/预测/缺件/推荐动作/聚合 dashboard。

路由 (无统一前缀, 在 main.py 下挂 /api/v1):
  GET  /companies/{company_id}/bom-summary            企业级 BOM 汇总
  GET  /companies/{company_id}/orders                 生产订单列表 + 摘要
  GET  /companies/{company_id}/forecasts              预测需求列表 + 摘要
  GET  /companies/{company_id}/shortages              缺件/预警 (持久化, 空时懒重算)
  POST /companies/{company_id}/shortages/recalculate  强制重算缺件
  GET  /companies/{company_id}/recommended-actions    推荐动作 (采购/生产/销售)
  GET  /companies/{company_id}/dashboard              聚合驾驶舱 (前端直接消费)
  GET  /products/{product_id}/bom                     单产品 BOM (可选 ?company_id 越权校验)

注: GET /companies/{company_id}/products 由 companies.router 提供 (已追加 production_products)。
计算逻辑见 kb/dashboard_calc.py (router 与 seed 共用)。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from kb.db import session_scope
from kb import dashboard_calc as dc
from api.deps import check_company_access, get_current_user

router = APIRouter(tags=["enterprise-dashboard"])


# ── BOM ───────────────────────────────────────────────────────

@router.get("/companies/{company_id}/bom-summary")
def get_bom_summary(company_id: int, user: dict = Depends(get_current_user)):
    check_company_access(user, company_id)
    with session_scope() as s:
        return dc.get_bom_summary(s, company_id)


@router.get("/products/{product_id}/bom")
def get_product_bom(
    product_id: int,
    company_id: int | None = Query(default=None, description="提供则校验产品归属企业, 防越权"),
    user: dict = Depends(get_current_user),
):
    """单产品 BOM。company_id 可选, 提供时校验产品属于该企业 (否则 403)。"""
    with session_scope() as s:
        return dc.get_bom_for_product(s, product_id, scope_company_id=company_id)


# ── 订单 / 预测 ───────────────────────────────────────────────

@router.get("/companies/{company_id}/orders")
def get_orders(company_id: int, user: dict = Depends(get_current_user)):
    check_company_access(user, company_id)
    with session_scope() as s:
        return dc.get_orders_summary(s, company_id)


@router.get("/companies/{company_id}/forecasts")
def get_forecasts(company_id: int, user: dict = Depends(get_current_user)):
    check_company_access(user, company_id)
    with session_scope() as s:
        return dc.get_forecasts_summary(s, company_id)


# ── 缺件 ──────────────────────────────────────────────────────

@router.get("/companies/{company_id}/shortages")
def get_shortages(company_id: int, user: dict = Depends(get_current_user)):
    check_company_access(user, company_id)
    with session_scope() as s:
        return dc.get_shortages(s, company_id, auto_recalc=True)


@router.post("/companies/{company_id}/shortages/recalculate")
def recalculate_shortages(company_id: int, user: dict = Depends(get_current_user)):
    check_company_access(user, company_id)
    with session_scope() as s:
        items = dc.recalculate_shortages(s, company_id)
    return {
        "company_id": company_id,
        "items": items,
        "total": len(items),
        "shortage_count": sum(1 for i in items if i["shortage_type"] == "shortage"),
        "warning_count": sum(1 for i in items if i["shortage_type"] == "warning"),
        "critical_count": sum(
            1 for i in items if i["shortage_type"] == "shortage" and i["severity"] == "critical"
        ),
    }


# ── 推荐动作 / 聚合驾驶舱 ─────────────────────────────────────

@router.get("/companies/{company_id}/recommended-actions")
def get_recommended_actions(company_id: int, user: dict = Depends(get_current_user)):
    check_company_access(user, company_id)
    with session_scope() as s:
        return dc.build_recommended_actions(s, company_id)


@router.get("/companies/{company_id}/dashboard")
def get_dashboard(company_id: int, user: dict = Depends(get_current_user)):
    check_company_access(user, company_id)
    with session_scope() as s:
        return dc.build_dashboard(s, company_id)
