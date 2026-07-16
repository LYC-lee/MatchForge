"""
驾驶舱 Phase2 数据服务 (纯函数, 接收 SQLAlchemy session)。

集中实现:
  - 产品 / BOM / 订单 / 预测 / 库存 查询
  - 缺件计算 (recalculate_shortages): 订单+预测需求 × BOM - 可用库存
  - 推荐动作 (build_recommended_actions): 基于缺件/预警 + 产能/销售启发
  - 聚合驾驶舱 (build_dashboard)

router 与 seed 共用本模块, 保证计算口径一致。
不依赖 LLM / 向量库, 纯 DB 计算。
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException

from kb.models import (
    CompanyCache,
    CompanyProduct,
    CompanyRelationship,
    DemandForecast,
    InventoryItem,
    ProductBomItem,
    ProductionOrder,
    Shortage,
)

# 订单状态: 仅这些计入需求 (completed/cancelled 不计)
ACTIVE_ORDER_STATUSES = ("open", "confirmed", "in_progress")

# 严重度排序 (用于推荐动作排序)
_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


# ============================================================
# 通用 helper
# ============================================================
def _require_company(s, company_id: int) -> CompanyCache:
    c = s.get(CompanyCache, company_id)
    if not c:
        raise HTTPException(status_code=404, detail=f"公司 {company_id} 不存在")
    return c


def _has_direct_relationship(s, company_id: int, partner_company_id: int) -> bool:
    """两公司是否存在任意活跃直接关系 (与 relationships router 同口径)。"""
    if company_id == partner_company_id or not partner_company_id:
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


def _parse_json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        v = json.loads(raw)
        return v if isinstance(v, list) else []
    except Exception:
        return []


def _company_name(s, company_id: int | None) -> str | None:
    if not company_id:
        return None
    c = s.get(CompanyCache, company_id)
    return c.name if c else None


# ============================================================
# 序列化
# ============================================================
def product_to_dict(p: CompanyProduct) -> dict:
    return {
        "id": p.id,
        "company_id": p.company_id,
        "product_name": p.product_name,
        "product_model": p.product_model,
        "product_type": p.product_type,
        "description": p.description,
        "monthly_capacity": p.monthly_capacity,
        "unit": p.unit,
        "status": p.status,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def bom_item_to_dict(b: ProductBomItem) -> dict:
    return {
        "id": b.id,
        "product_id": b.product_id,
        "part_number": b.part_number,
        "part_name": b.part_name,
        "category_name": b.category_name,
        "qty_per_unit": b.qty_per_unit,
        "unit": b.unit,
        "is_critical": bool(b.is_critical),
        "preferred_supplier_company_id": b.preferred_supplier_company_id,
        "created_at": b.created_at.isoformat() if b.created_at else None,
        "updated_at": b.updated_at.isoformat() if b.updated_at else None,
    }


def order_to_dict(o: ProductionOrder) -> dict:
    return {
        "id": o.id,
        "company_id": o.company_id,
        "product_id": o.product_id,
        "order_number": o.order_number,
        "customer_company_id": o.customer_company_id,
        "quantity": o.quantity,
        "due_date": o.due_date.isoformat() if o.due_date else None,
        "priority": o.priority,
        "status": o.status,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "updated_at": o.updated_at.isoformat() if o.updated_at else None,
    }


def forecast_to_dict(f: DemandForecast) -> dict:
    return {
        "id": f.id,
        "company_id": f.company_id,
        "product_id": f.product_id,
        "forecast_period": f.forecast_period,
        "forecast_quantity": f.forecast_quantity,
        "confidence": f.confidence,
        "source_type": f.source_type,
        "created_at": f.created_at.isoformat() if f.created_at else None,
        "updated_at": f.updated_at.isoformat() if f.updated_at else None,
    }


def inventory_to_dict(i: InventoryItem) -> dict:
    return {
        "id": i.id,
        "company_id": i.company_id,
        "part_number": i.part_number,
        "part_name": i.part_name,
        "category_name": i.category_name,
        "on_hand_qty": i.on_hand_qty,
        "reserved_qty": i.reserved_qty,
        "available_qty": (i.on_hand_qty or 0) - (i.reserved_qty or 0),
        "safety_stock_qty": i.safety_stock_qty,
        "updated_at": i.updated_at.isoformat() if i.updated_at else None,
    }


def shortage_to_dict(rec: Shortage, s=None) -> dict:
    return {
        "id": rec.id,
        "company_id": rec.company_id,
        "product_id": rec.product_id,
        "product_name": rec.product_name,
        "part_number": rec.part_number,
        "part_name": rec.part_name,
        "category_name": rec.category_name,
        "shortage_type": rec.shortage_type,
        "required_qty": rec.required_qty,
        "available_qty": rec.available_qty,
        "shortage_qty": rec.shortage_qty,
        "safety_stock_qty": rec.safety_stock_qty,
        "unit": rec.unit,
        "is_critical": bool(rec.is_critical),
        "severity": rec.severity,
        "status": rec.status,
        "preferred_supplier_company_id": rec.preferred_supplier_company_id,
        "preferred_supplier_name": _company_name(s, rec.preferred_supplier_company_id) if s else None,
        "relationship_missing": bool(rec.relationship_missing),
        "affected_order_numbers": _parse_json_list(rec.affected_order_numbers),
        "affected_product_ids": _parse_json_list(rec.affected_product_ids),
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
        "updated_at": rec.updated_at.isoformat() if rec.updated_at else None,
    }


# ============================================================
# 查询接口
# ============================================================
def get_products(s, company_id: int) -> list[dict]:
    _require_company(s, company_id)
    rows = (
        s.query(CompanyProduct)
        .filter_by(company_id=company_id)
        .order_by(CompanyProduct.id)
        .all()
    )
    return [product_to_dict(p) for p in rows]


def get_bom_for_product(s, product_id: int, scope_company_id: int | None = None) -> dict:
    """单产品 BOM。scope_company_id 提供时校验产品归属 (越权 403)。"""
    p = s.get(CompanyProduct, product_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"产品 {product_id} 不存在")
    if scope_company_id is not None and p.company_id != scope_company_id:
        raise HTTPException(
            status_code=403,
            detail=f"产品 {product_id} 不属于企业 {scope_company_id}, 拒绝访问",
        )
    items = (
        s.query(ProductBomItem)
        .filter_by(product_id=product_id)
        .order_by(ProductBomItem.id)
        .all()
    )
    return {
        "product_id": product_id,
        "company_id": p.company_id,
        "product_name": p.product_name,
        "product_model": p.product_model,
        "product_type": p.product_type,
        "unit": p.unit,
        "bom_count": len(items),
        "critical_count": sum(1 for b in items if b.is_critical),
        "items": [bom_item_to_dict(b) for b in items],
    }


def get_bom_summary(s, company_id: int) -> dict:
    """企业级 BOM 汇总: 各产品 BOM 概览 + 跨产品零件聚合。"""
    _require_company(s, company_id)
    products = (
        s.query(CompanyProduct)
        .filter_by(company_id=company_id)
        .order_by(CompanyProduct.id)
        .all()
    )
    product_ids = [p.id for p in products]
    bom_items = (
        s.query(ProductBomItem)
        .filter(ProductBomItem.product_id.in_(product_ids))
        .order_by(ProductBomItem.id)
        .all()
        if product_ids
        else []
    )

    product_summary = []
    by_product: dict[int, list] = {p.id: [] for p in products}
    for b in bom_items:
        by_product.setdefault(b.product_id, []).append(b)
    for p in products:
        items = by_product.get(p.id, [])
        product_summary.append({
            "product_id": p.id,
            "product_name": p.product_name,
            "product_model": p.product_model,
            "bom_count": len(items),
            "critical_count": sum(1 for b in items if b.is_critical),
        })

    # 跨产品零件聚合 (同一零件号可能被多产品共用)
    part_agg: dict[str, dict] = {}
    for b in bom_items:
        agg = part_agg.get(b.part_number)
        if agg is None:
            agg = {
                "part_number": b.part_number,
                "part_name": b.part_name,
                "category_name": b.category_name,
                "unit": b.unit,
                "is_critical": bool(b.is_critical),
                "preferred_supplier_company_id": b.preferred_supplier_company_id,
                "used_in_products": [],
                "total_qty_per_unit": 0.0,
            }
            part_agg[b.part_number] = agg
        agg["is_critical"] = agg["is_critical"] or bool(b.is_critical)
        if b.preferred_supplier_company_id and not agg["preferred_supplier_company_id"]:
            agg["preferred_supplier_company_id"] = b.preferred_supplier_company_id
        agg["total_qty_per_unit"] += float(b.qty_per_unit or 0)
        prod = next((p for p in products if p.id == b.product_id), None)
        agg["used_in_products"].append({
            "product_id": b.product_id,
            "product_name": prod.product_name if prod else None,
            "qty_per_unit": b.qty_per_unit,
        })

    parts = sorted(part_agg.values(), key=lambda x: (not x["is_critical"], x["part_number"]))
    for agg in parts:
        agg["preferred_supplier_name"] = _company_name(s, agg["preferred_supplier_company_id"])

    return {
        "company_id": company_id,
        "products": product_summary,
        "parts": parts,
        "totals": {
            "product_count": len(products),
            "part_count": len(parts),
            "critical_part_count": sum(1 for a in parts if a["is_critical"]),
        },
    }


def get_orders_summary(s, company_id: int) -> dict:
    _require_company(s, company_id)
    rows = (
        s.query(ProductionOrder)
        .filter_by(company_id=company_id)
        .order_by(ProductionOrder.id)
        .all()
    )
    by_status: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    active_qty = 0
    for o in rows:
        by_status[o.status] = by_status.get(o.status, 0) + 1
        by_priority[o.priority] = by_priority.get(o.priority, 0) + 1
        if o.status in ACTIVE_ORDER_STATUSES:
            active_qty += o.quantity or 0
    return {
        "company_id": company_id,
        "items": [order_to_dict(o) for o in rows],
        "total": len(rows),
        "active_count": sum(by_status.get(st, 0) for st in ACTIVE_ORDER_STATUSES),
        "active_total_quantity": active_qty,
        "by_status": by_status,
        "by_priority": by_priority,
    }


def get_forecasts_summary(s, company_id: int) -> dict:
    _require_company(s, company_id)
    rows = (
        s.query(DemandForecast)
        .filter_by(company_id=company_id)
        .order_by(DemandForecast.id)
        .all()
    )
    by_product: dict[int, int] = {}
    total_qty = 0
    for f in rows:
        by_product[f.product_id] = by_product.get(f.product_id, 0) + (f.forecast_quantity or 0)
        total_qty += f.forecast_quantity or 0
    return {
        "company_id": company_id,
        "items": [forecast_to_dict(f) for f in rows],
        "total": len(rows),
        "total_forecast_quantity": total_qty,
        "by_product": by_product,
    }


def get_inventory(s, company_id: int) -> list[dict]:
    _require_company(s, company_id)
    rows = (
        s.query(InventoryItem)
        .filter_by(company_id=company_id)
        .order_by(InventoryItem.part_number)
        .all()
    )
    return [inventory_to_dict(i) for i in rows]


# ============================================================
# 缺件计算 (核心)
# ============================================================
def _demand_by_product(s, company_id: int) -> tuple[dict[int, int], dict[int, list[str]], dict[int, set[str]]]:
    """返回 (product_id -> 需求量, product_id -> [订单号], product_id -> {优先级})。

    需求量 = 活跃订单 quantity 之和 + 全部预测 forecast_quantity 之和。
    """
    orders = (
        s.query(ProductionOrder)
        .filter(
            ProductionOrder.company_id == company_id,
            ProductionOrder.status.in_(ACTIVE_ORDER_STATUSES),
        )
        .all()
    )
    forecasts = (
        s.query(DemandForecast)
        .filter_by(company_id=company_id)
        .all()
    )
    demand: dict[int, int] = {}
    order_numbers: dict[int, list[str]] = {}
    priorities: dict[int, set[str]] = {}
    for o in orders:
        demand[o.product_id] = demand.get(o.product_id, 0) + (o.quantity or 0)
        order_numbers.setdefault(o.product_id, []).append(o.order_number)
        priorities.setdefault(o.product_id, set()).add(o.priority)
    for f in forecasts:
        demand[f.product_id] = demand.get(f.product_id, 0) + (f.forecast_quantity or 0)
    return demand, order_numbers, priorities


def recalculate_shortages(s, company_id: int) -> list[dict]:
    """重算并持久化企业的缺件/预警, 返回列表 (dict)。

    规则:
      - 产品需求 = 订单需求 + 预测需求
      - 零件 BOM 需求 = Σ(产品需求 × qty_per_unit)  (同零件号跨产品累加)
      - 可用库存 = on_hand_qty - reserved_qty
      - 缺口 = BOM 需求 - 可用库存; 缺口 > 0 -> shortage
      - 可用库存 < 安全库存 且 未缺货 -> warning
      - 关键件 + 高/紧急订单 -> severity=critical
    幂等: 先删除该企业 open 缺件, 再重算插入。
    """
    _require_company(s, company_id)
    products = (
        s.query(CompanyProduct)
        .filter_by(company_id=company_id)
        .order_by(CompanyProduct.id)
        .all()
    )
    product_by_id = {p.id: p for p in products}
    product_ids = list(product_by_id.keys())

    bom_items = (
        s.query(ProductBomItem)
        .filter(ProductBomItem.product_id.in_(product_ids))
        .order_by(ProductBomItem.id)
        .all()
        if product_ids
        else []
    )
    inv_items = (
        s.query(InventoryItem)
        .filter_by(company_id=company_id)
        .all()
    )
    inv_by_part = {i.part_number: i for i in inv_items}

    demand, order_numbers, priorities = _demand_by_product(s, company_id)

    # 零件级聚合 (按 part_number)
    part_agg: dict[str, dict] = {}
    for b in bom_items:
        prod = product_by_id.get(b.product_id)
        if not prod:
            continue
        d = demand.get(b.product_id, 0)
        if d <= 0:
            continue
        req = float(d) * float(b.qty_per_unit or 0)
        if req <= 0:
            continue
        agg = part_agg.get(b.part_number)
        if agg is None:
            agg = {
                "part_number": b.part_number,
                "part_name": b.part_name,
                "category_name": b.category_name,
                "unit": b.unit,
                "is_critical": bool(b.is_critical),
                "preferred_supplier_company_id": b.preferred_supplier_company_id,
                "required_qty": 0.0,
                "product_ids": [],
                "product_names": [],
                "order_numbers": set(),
                "priorities": set(),
            }
            part_agg[b.part_number] = agg
        agg["required_qty"] += req
        agg["is_critical"] = agg["is_critical"] or bool(b.is_critical)
        if b.preferred_supplier_company_id and not agg["preferred_supplier_company_id"]:
            agg["preferred_supplier_company_id"] = b.preferred_supplier_company_id
        if b.product_id not in agg["product_ids"]:
            agg["product_ids"].append(b.product_id)
            agg["product_names"].append(prod.product_name)
        for on in order_numbers.get(b.product_id, []):
            agg["order_numbers"].add(on)
        for pr in priorities.get(b.product_id, set()):
            agg["priorities"].add(pr)

    # 清空旧 open 记录 (幂等重算)
    s.query(Shortage).filter(
        Shortage.company_id == company_id,
        Shortage.status == "open",
    ).delete(synchronize_session=False)

    created: list[Shortage] = []
    for part_number, agg in part_agg.items():
        inv = inv_by_part.get(part_number)
        on_hand = inv.on_hand_qty if inv else 0
        reserved = inv.reserved_qty if inv else 0
        safety = inv.safety_stock_qty if inv else 0
        available = (on_hand or 0) - (reserved or 0)
        required = agg["required_qty"]
        gap = required - available
        pref_sup = agg["preferred_supplier_company_id"]
        rel_missing = False
        if pref_sup:
            rel_missing = not _has_direct_relationship(s, company_id, pref_sup)

        product_id_repr = agg["product_ids"][0] if agg["product_ids"] else None
        product_name_repr = " / ".join(agg["product_names"][:3])
        affected_orders = sorted(agg["order_numbers"])
        affected_products = sorted(agg["product_ids"])

        if gap > 0:
            # 缺件
            if agg["is_critical"] and ("urgent" in agg["priorities"] or "high" in agg["priorities"]):
                severity = "critical"
            elif agg["is_critical"]:
                severity = "high"
            elif "urgent" in agg["priorities"] or "high" in agg["priorities"]:
                severity = "medium"
            else:
                severity = "medium"
            rec = Shortage(
                company_id=company_id,
                product_id=product_id_repr,
                product_name=product_name_repr,
                part_number=part_number,
                part_name=agg["part_name"],
                category_name=agg["category_name"],
                shortage_type="shortage",
                required_qty=required,
                available_qty=available,
                shortage_qty=gap,
                safety_stock_qty=safety,
                unit=agg["unit"],
                is_critical=agg["is_critical"],
                severity=severity,
                status="open",
                preferred_supplier_company_id=pref_sup,
                relationship_missing=rel_missing,
                affected_order_numbers=json.dumps(affected_orders, ensure_ascii=False),
                affected_product_ids=json.dumps(affected_products, ensure_ascii=False),
            )
            s.add(rec)
            created.append(rec)
        elif available < safety:
            # 预警: 低于安全库存但未缺货
            rec = Shortage(
                company_id=company_id,
                product_id=product_id_repr,
                product_name=product_name_repr,
                part_number=part_number,
                part_name=agg["part_name"],
                category_name=agg["category_name"],
                shortage_type="warning",
                required_qty=required,
                available_qty=available,
                shortage_qty=0,
                safety_stock_qty=safety,
                unit=agg["unit"],
                is_critical=agg["is_critical"],
                severity="low",
                status="open",
                preferred_supplier_company_id=pref_sup,
                relationship_missing=rel_missing,
                affected_order_numbers=json.dumps(affected_orders, ensure_ascii=False),
                affected_product_ids=json.dumps(affected_products, ensure_ascii=False),
            )
            s.add(rec)
            created.append(rec)

    s.flush()
    # 按严重度 -> 缺口 排序返回
    created.sort(
        key=lambda r: (_SEVERITY_RANK.get(r.severity, 9), -r.shortage_qty, r.part_number)
    )
    return [shortage_to_dict(r, s) for r in created]


def get_shortages(s, company_id: int, auto_recalc: bool = True) -> dict:
    """读取持久化缺件; auto_recalc 时若为空则先重算 (懒初始化)。"""
    _require_company(s, company_id)
    existing = (
        s.query(Shortage)
        .filter_by(company_id=company_id, status="open")
        .all()
    )
    if not existing and auto_recalc:
        items = recalculate_shortages(s, company_id)
    else:
        items = [shortage_to_dict(r, s) for r in existing]
        items.sort(key=lambda r: (_SEVERITY_RANK.get(r["severity"], 9), -r["shortage_qty"], r["part_number"]))
    shortage_count = sum(1 for i in items if i["shortage_type"] == "shortage")
    warning_count = sum(1 for i in items if i["shortage_type"] == "warning")
    critical_count = sum(1 for i in items if i["shortage_type"] == "shortage" and i["severity"] == "critical")
    return {
        "company_id": company_id,
        "items": items,
        "total": len(items),
        "shortage_count": shortage_count,
        "warning_count": warning_count,
        "critical_count": critical_count,
    }


# ============================================================
# 推荐动作
# ============================================================
def build_recommended_actions(s, company_id: int) -> dict:
    """基于缺件/预警 + 产能/销售启发, 生成采购/生产/销售决策建议。"""
    _require_company(s, company_id)
    shortages = get_shortages(s, company_id, auto_recalc=True)["items"]

    actions: list[dict] = []
    for rec in shortages:
        part_name = rec["part_name"]
        part_number = rec["part_number"]
        gap = rec["shortage_qty"]
        pref_sup = rec["preferred_supplier_company_id"]
        sup_name = rec.get("preferred_supplier_name") or _company_name(s, pref_sup)
        rel_missing = rec["relationship_missing"]
        severity = rec["severity"]
        affected_orders = rec.get("affected_order_numbers") or []

        if rec["shortage_type"] == "warning":
            actions.append({
                "action_type": "replenish",
                "category": "inventory",
                "priority": "low",
                "severity": severity,
                "title": f"补货 {part_name}",
                "detail": (
                    f"{part_name}({part_number}) 可用库存 {rec['available_qty']} "
                    f"低于安全库存 {rec['safety_stock_qty']}, 尚未缺货, 建议尽快补货。"
                ),
                "part_number": part_number,
                "product_id": rec["product_id"],
                "suggested_supplier_company_id": pref_sup,
                "suggested_supplier_name": sup_name,
                "relationship_missing": rel_missing,
                "shortage_id": rec["id"],
            })
            continue

        # shortage
        if severity == "critical":
            prio = "urgent"
        elif severity == "high":
            prio = "high"
        else:
            prio = "medium"

        if pref_sup:
            if rel_missing:
                actions.append({
                    "action_type": "establish_relationship",
                    "category": "sourcing",
                    "priority": prio,
                    "severity": severity,
                    "title": f"与上游 {sup_name} 建立关系并补货 {part_name}",
                    "detail": (
                        f"{part_name}({part_number}) 缺口 {gap}, 首选供应商 {sup_name} "
                        f"与本企业无直接上下游关系, 建议先建立供应链关系再发起补货。"
                    ),
                    "part_number": part_number,
                    "product_id": rec["product_id"],
                    "suggested_supplier_company_id": pref_sup,
                    "suggested_supplier_name": sup_name,
                    "relationship_missing": True,
                    "shortage_id": rec["id"],
                })
            else:
                actions.append({
                    "action_type": "contact_supplier",
                    "category": "sourcing",
                    "priority": prio,
                    "severity": severity,
                    "title": f"联系上游 {sup_name} 紧急补货 {part_name}",
                    "detail": (
                        f"{part_name}({part_number}) 缺口 {gap}, 建议立即联系直接上游 "
                        f"{sup_name} 发起补货, 保障订单交付。"
                    ),
                    "part_number": part_number,
                    "product_id": rec["product_id"],
                    "suggested_supplier_company_id": pref_sup,
                    "suggested_supplier_name": sup_name,
                    "relationship_missing": False,
                    "shortage_id": rec["id"],
                })
        else:
            actions.append({
                "action_type": "find_supplier",
                "category": "sourcing",
                "priority": prio,
                "severity": severity,
                "title": f"为 {part_name} 寻找供应商",
                "detail": (
                    f"{part_name}({part_number}) 缺口 {gap}, 暂无首选供应商, "
                    f"建议尽快寻源并询价。"
                ),
                "part_number": part_number,
                "product_id": rec["product_id"],
                "suggested_supplier_company_id": None,
                "suggested_supplier_name": None,
                "relationship_missing": False,
                "shortage_id": rec["id"],
            })

        if severity == "critical" and affected_orders:
            actions.append({
                "action_type": "escalate",
                "category": "production",
                "priority": "urgent",
                "severity": severity,
                "title": f"升级处理关键件缺件 {part_name}",
                "detail": (
                    f"关键件 {part_name}({part_number}) 缺口 {gap}, 影响高优先级订单 "
                    f"{', '.join(affected_orders[:5])}, 建议升级至供应链负责人协调。"
                ),
                "part_number": part_number,
                "product_id": rec["product_id"],
                "suggested_supplier_company_id": pref_sup,
                "suggested_supplier_name": sup_name,
                "relationship_missing": rel_missing,
                "shortage_id": rec["id"],
            })

    # 产能/销售启发 (基于需求 vs 月产能, 粗略启发)
    demand, _, _ = _demand_by_product(s, company_id)
    products = (
        s.query(CompanyProduct)
        .filter_by(company_id=company_id, status="active")
        .all()
    )
    for p in products:
        d = demand.get(p.id, 0)
        cap = p.monthly_capacity or 0
        if cap <= 0:
            continue
        if d > cap:
            actions.append({
                "action_type": "expand_capacity",
                "category": "production",
                "priority": "high",
                "severity": "high",
                "title": f"评估 {p.product_name} 扩产",
                "detail": (
                    f"{p.product_name} 需求 {d} 超过月产能 {cap}, 建议评估扩产/外协或调整排产。"
                ),
                "part_number": None,
                "product_id": p.id,
                "suggested_supplier_company_id": None,
                "suggested_supplier_name": None,
                "relationship_missing": False,
                "shortage_id": None,
            })
        elif d < cap * 0.25:
            actions.append({
                "action_type": "promote_sales",
                "category": "sales",
                "priority": "low",
                "severity": "low",
                "title": f"推动 {p.product_name} 销售接单",
                "detail": (
                    f"{p.product_name} 需求 {d} 低于月产能 {cap} 的 25%, 产能利用率偏低, "
                    f"建议销售主动接单/拓展渠道。"
                ),
                "part_number": None,
                "product_id": p.id,
                "suggested_supplier_company_id": None,
                "suggested_supplier_name": None,
                "relationship_missing": False,
                "shortage_id": None,
            })

    _action_prio_rank = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
    actions.sort(key=lambda a: (_action_prio_rank.get(a["priority"], 9), a["action_type"]))
    by_type: dict[str, int] = {}
    for a in actions:
        by_type[a["action_type"]] = by_type.get(a["action_type"], 0) + 1
    return {
        "company_id": company_id,
        "items": actions,
        "total": len(actions),
        "by_type": by_type,
    }


# ============================================================
# 上下游 / 协同伙伴 (与 relationships router 同口径, 供 dashboard 聚合)
# ============================================================
def _partner_list(s, company_id: int, direction: str | None) -> list[dict]:
    q = s.query(CompanyRelationship).filter(
        CompanyRelationship.source_company_id == company_id,
        CompanyRelationship.status == "active",
    )
    if direction:
        q = q.filter(CompanyRelationship.direction == direction)
    items = []
    for r in q.all():
        p = s.get(CompanyCache, r.target_company_id)
        items.append({
            "company_id": r.target_company_id,
            "company_name": p.name if p else None,
            "segment_name": p.segment_name_cn if p else None,
            "role": p.role if p else None,
            "relationship_type": r.relationship_type,
            "direction": r.direction,
        })
    return items


def _chat_partner_list(s, company_id: int) -> list[dict]:
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
        p = s.get(CompanyCache, partner_id)
        seen[partner_id] = {
            "company_id": partner_id,
            "company_name": p.name if p else None,
            "segment_name": p.segment_name_cn if p else None,
            "role": p.role if p else None,
        }
    return list(seen.values())


# ============================================================
# 聚合驾驶舱
# ============================================================
def build_dashboard(s, company_id: int) -> dict:
    """当前企业经营驾驶舱聚合 (前端可直接消费)。"""
    c = _require_company(s, company_id)

    products = get_products(s, company_id)
    orders = get_orders_summary(s, company_id)
    forecasts = get_forecasts_summary(s, company_id)
    # dashboard 始终重算缺件, 保证聚合数据最新
    shortages = {
        "company_id": company_id,
        "items": recalculate_shortages(s, company_id),
    }
    shortages["shortage_count"] = sum(1 for i in shortages["items"] if i["shortage_type"] == "shortage")
    shortages["warning_count"] = sum(1 for i in shortages["items"] if i["shortage_type"] == "warning")
    shortages["critical_count"] = sum(
        1 for i in shortages["items"] if i["shortage_type"] == "shortage" and i["severity"] == "critical"
    )
    shortages["total"] = len(shortages["items"])

    actions = build_recommended_actions(s, company_id)

    upstream = _partner_list(s, company_id, "upstream")
    downstream = _partner_list(s, company_id, "downstream")
    support = _partner_list(s, company_id, "support")
    chat_partners = _chat_partner_list(s, company_id)

    active_products = [p for p in products if p["status"] == "active"]

    return {
        "company_id": company_id,
        "company": {
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
            "chain_position": c.chain_position,
            "role": c.role,
            "knowledge_status": c.knowledge_status,
        },
        "products_summary": {
            "total": len(products),
            "active_count": len(active_products),
            "items": products,
        },
        "orders_summary": {
            "total": orders["total"],
            "active_count": orders["active_count"],
            "active_total_quantity": orders["active_total_quantity"],
            "by_status": orders["by_status"],
            "by_priority": orders["by_priority"],
        },
        "forecast_summary": {
            "total": forecasts["total"],
            "total_forecast_quantity": forecasts["total_forecast_quantity"],
        },
        "shortages": shortages,
        "recommended_actions": {
            "total": actions["total"],
            "by_type": actions["by_type"],
            "items": actions["items"],
        },
        "upstream_summary": {"count": len(upstream), "items": upstream},
        "downstream_summary": {"count": len(downstream), "items": downstream},
        "support_summary": {"count": len(support), "items": support},
        "chat_partners_summary": {"count": len(chat_partners), "items": chat_partners},
    }
