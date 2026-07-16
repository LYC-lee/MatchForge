"""
演示场景沙盘数据服务 (纯函数, 接收 SQLAlchemy session)。

设计原则:
  - 所有演示变化 (订单/库存/RFQ/报价/事件/动作日志) 都带 scenario_id。
  - 原始基线数据 (kb_production_orders/kb_inventory_items/kb_rfqs/...) 只读, 不被污染。
  - 演示可用库存 = baseline_on_hand - baseline_reserved - consumed_qty + replenished_qty
    (consumed/replenished 记录在 demo_inventory_overrides, 不改 kb_inventory_items)。
  - 演示缺件 = (基线需求 + 演示订单需求) × BOM - 演示可用库存 (不写入 kb_shortages)。
  - RFQ 候选供应商仅限当前企业的直接上下游/支撑关系企业; 无则明确提示, 不自动建立关系。
  - 每个动作写事件日志 (demo_events), 含因果链 (parent_event_id) 与联动企业。

router 与 seed 共用本模块, 保证口径一致。不依赖 LLM / 向量库, 纯 DB 计算。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException

from kb import dashboard_calc as dc
from kb.models import (
    CompanyCache,
    CompanyProduct,
    CompanyRelationship,
    DemoActionLog,
    DemoCompanyState,
    DemoEvent,
    DemoInventoryOverride,
    DemoOrder,
    DemoQuotation,
    DemoRfq,
    DemoScenario,
    InventoryItem,
    ProductBomItem,
)

# ============================================================
# 常量
# ============================================================

DEFAULT_SCENARIO_ID = "default_mvp_demo"

# 6 家可登录主视角企业 (与 seed_enterprise_chain 一致)
DEMO_COMPANY_IDS = [9001, 9002, 9003, 9004, 9005, 9006]

# 订单状态: 仅这些计入需求 (与 dashboard_calc 同口径)
ACTIVE_ORDER_STATUSES = ("open", "confirmed", "in_progress")

# 严重度排序
_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# 零件品类 -> (基准单价, 单位) 用于合理报价生成
_CATEGORY_PRICE_BASELINE: dict[str, tuple[float, str]] = {
    "半导体芯片": (1200.0, "颗"),
    "CPU": (1500.0, "颗"),
    "PCBA": (380.0, "片"),
    "PCB": (45.0, "片"),
    "内存": (120.0, "条"),
    "存储": (120.0, "块"),
    "电源": (110.0, "个"),
    "电池": (150.0, "块"),
    "显示": (300.0, "片"),
    "输入": (60.0, "个"),
    "被动元件": (0.12, "颗"),
    "连接器": (3.5, "个"),
    "结构件": (70.0, "个"),
    "散热": (35.0, "个"),
}

# segment_code -> 可供货品类关键词 (用于候选供应商匹配)
_SEGMENT_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "semiconductor_chips": ["半导体芯片", "CPU", "SoC", "芯片组", "GPU"],
    "pcb_pcba": ["PCB", "PCBA", "主板", "模组"],
    "passive_components": ["被动元件", "MLCC", "电阻", "电感", "磁珠"],
    "odm_ems_manufacturing": ["整机", "台式机", "笔记本"],
    "sourcing_distribution": ["整机", "台式机", "笔记本", "现货", "分销"],
    "logistics_service": [],  # 物流不供货
}

# segment_code -> 典型交期(天)
_SEGMENT_LEAD_TIME: dict[str, tuple[int, int]] = {
    "semiconductor_chips": (21, 35),
    "pcb_pcba": (10, 21),
    "passive_components": (7, 14),
    "odm_ems_manufacturing": (14, 28),
    "sourcing_distribution": (3, 7),
    "logistics_service": (2, 5),
}


# ============================================================
# 通用 helper
# ============================================================

def _parse_json(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _company(s, company_id: int) -> CompanyCache:
    c = s.get(CompanyCache, company_id)
    if not c:
        raise HTTPException(status_code=404, detail=f"公司 {company_id} 不存在")
    return c


def _company_name(s, company_id: int | None) -> str | None:
    if not company_id:
        return None
    c = s.get(CompanyCache, company_id)
    return c.name if c else None


def _now() -> datetime:
    return datetime.utcnow()


def _next_event_seq(s, scenario_id: str) -> int:
    """场景内事件全局递增序号。"""
    from sqlalchemy import func as sa_func
    max_seq = (
        s.query(sa_func.max(DemoEvent.seq))
        .filter(DemoEvent.scenario_id == scenario_id)
        .scalar()
    )
    return (max_seq or 0) + 1


def _log_event(
    s,
    *,
    scenario_id: str,
    company_id: int,
    phase: str | None,
    event_type: str,
    title: str,
    detail: str | None = None,
    payload: dict | None = None,
    parent_event_id: int | None = None,
    linked_company_id: int | None = None,
    action_log_id: int | None = None,
    seq: int | None = None,
) -> DemoEvent:
    """写一条演示事件, 返回对象 (调用方可取 id 作后续事件 parent)。"""
    if seq is None:
        seq = _next_event_seq(s, scenario_id)
    ev = DemoEvent(
        scenario_id=scenario_id,
        seq=seq,
        phase=phase,
        action_log_id=action_log_id,
        company_id=company_id,
        company_name=_company_name(s, company_id),
        linked_company_id=linked_company_id,
        linked_company_name=_company_name(s, linked_company_id),
        event_type=event_type,
        title=title,
        detail=detail,
        payload_json=_dump_json(payload) if payload else None,
        parent_event_id=parent_event_id,
    )
    s.add(ev)
    s.flush()
    return ev


def _is_primary(company_id: int) -> bool:
    return company_id in DEMO_COMPANY_IDS


def _has_direct_relationship(s, company_id: int, partner_company_id: int) -> bool:
    """两公司是否存在任意活跃直接关系 (复用 dashboard_calc 口径)。"""
    return dc._has_direct_relationship(s, company_id, partner_company_id)


def _direct_partners(s, company_id: int) -> list[dict]:
    """查询企业的全部直接关系伙伴 (source 或 target 任一, 去重),
    返回 [{company_id, company_name, segment_code, role, chain_position,
           direction, relationship_type, product_scope, business_scope}]。

    direction 为从 company_id 视角的语义:
      supplier  -> 该伙伴向本企业供货 (本企业的上游)
      customer  -> 本企业向该伙伴供货 (本企业的下游)
      support   -> 该伙伴向本企业提供支撑服务
    """
    rows = (
        s.query(CompanyRelationship)
        .filter(
            CompanyRelationship.status == "active",
            (CompanyRelationship.source_company_id == company_id)
            | (CompanyRelationship.target_company_id == company_id),
        )
        .all()
    )
    seen: dict[int, dict] = {}
    for r in rows:
        if r.source_company_id == company_id:
            partner_id = r.target_company_id
            # source=本企业: direction 字段直接表达本企业视角
            view = r.direction  # upstream=partner是我上游(supplier), downstream=partner是我下游(customer), support=partner支撑我
        else:
            partner_id = r.source_company_id
            # target=本企业: 反转视角
            view = {"upstream": "downstream", "downstream": "upstream",
                    "support": "support"}.get(r.direction, r.direction)
        if partner_id == company_id or partner_id in seen:
            continue
        p = s.get(CompanyCache, partner_id)
        direction_label = {
            "upstream": "supplier", "downstream": "customer", "support": "support",
        }.get(view, view)
        seen[partner_id] = {
            "company_id": partner_id,
            "company_name": p.name if p else None,
            "segment_code": p.segment_code if p else None,
            "segment_name": p.segment_name_cn if p else None,
            "role": p.role if p else None,
            "chain_position": p.chain_position if p else None,
            "direction": direction_label,
            "relationship_type": r.relationship_type,
            "product_scope": _parse_json(r.product_scope, []),
            "business_scope": _parse_json(r.business_scope, []),
        }
    return list(seen.values())


def _partner_supplies(partner: CompanyCache | None, rel_product_scope: list,
                      category_name: str | None,
                      part_number: str | None, part_name: str | None) -> bool:
    """判断直接关系伙伴是否能供应该零件。

    匹配依据 (仅限本企业 ↔ 该伙伴的直接关系 product_scope + 伙伴 segment/typical_products):
      - segment 品类关键词命中 part 品类/名称
      - 直接关系 product_scope 命中 part 品类/名称
      - segment + part_number 关键词兜底 (芯片/被动元件)
    不查询该伙伴与第三方的关系, 避免把"伙伴采购进来的料"误判为"可供货"。
    """
    if not partner:
        return False
    seg = partner.segment_code or ""
    keywords: list[str] = list(_SEGMENT_CATEGORY_KEYWORDS.get(seg, []))
    keywords += _parse_json(partner.typical_products, [])
    keywords += list(rel_product_scope or [])

    targets: list[str] = []
    if category_name:
        targets.append(category_name)
    if part_name:
        targets.append(part_name)
    if not targets:
        # 无品类信息时, 仅"供货型"上游伙伴视为可供应
        return seg in ("semiconductor_chips", "pcb_pcba", "passive_components",
                       "sourcing_distribution")
    # 任一目标 token 命中关键词即视为可供应
    for t in targets:
        for kw in keywords:
            if kw and (kw in t or t in kw):
                return True
    # 半导体芯片段按 part_number 关键词兜底
    if seg == "semiconductor_chips" and part_number and (
        "CPU" in part_number.upper() or "SOC" in part_number.upper()
        or "CHIPSET" in part_number.upper() or "PMIC" in part_number.upper()
    ):
        return True
    if seg == "passive_components" and part_number and (
        "MLCC" in part_number.upper() or "RES-" in part_number.upper()
        or "IND-" in part_number.upper()
    ):
        return True
    return False


def _direct_supplier_candidates(s, company_id: int, category_name: str | None,
                                part_number: str | None, part_name: str | None,
                                preferred_supplier_company_id: int | None) -> list[dict]:
    """从直接上下游/支撑关系中找出可供应该零件的候选供应商。

    仅返回与本企业有活跃直接关系且能供货的伙伴。
    首选供应商若为直接关系则置顶 (match_score 高)。
    """
    partners = _direct_partners(s, company_id)
    candidates: list[dict] = []
    for p in partners:
        partner_obj = s.get(CompanyCache, p["company_id"])
        rel_scope = p.get("product_scope") or []
        # 物流企业除非直接关系 product_scope 明确命中, 否则不作为零件供应商
        if not _partner_supplies(partner_obj, rel_scope, category_name,
                                 part_number, part_name):
            continue
        is_pref = (preferred_supplier_company_id == p["company_id"])
        score = 0.95 if is_pref else 0.7
        reason = (
            f"{p['company_name']} 为本企业直接{('上游' if p['direction']=='supplier' else '伙伴')}, "
            f"主营 {', '.join(rel_scope) or p.get('segment_name') or '相关品类'}"
        )
        candidates.append({
            "supplier_company_id": p["company_id"],
            "supplier_name": p["company_name"],
            "direction": p["direction"],
            "segment_code": p.get("segment_code"),
            "match_score": score,
            "match_reason": reason,
            "status": "pending",
        })
    candidates.sort(key=lambda c: -c["match_score"])
    return candidates


def _part_baseline_price(part_number: str | None, category_name: str | None) -> float:
    """根据零件号/品类给出合理基准单价 (用于目标价与报价)。"""
    pn = (part_number or "").upper()
    if "CPU-I7" in pn:
        return 1500.0
    if "CPU-I5" in pn:
        return 1200.0
    if "SOC-" in pn or "N5105" in pn:
        return 800.0
    if "CHIPSET" in pn:
        return 450.0
    if "PMIC" in pn:
        return 60.0
    if "PCBA" in pn:
        return 380.0
    if "PCB-" in pn:
        return 45.0
    if "DDR5-16" in pn:
        return 150.0
    if "DDR5-8" in pn:
        return 90.0
    if "SSD" in pn and "512" in pn:
        return 180.0
    if "SSD" in pn and "256" in pn:
        return 100.0
    if "MLCC" in pn:
        return 0.12
    if "RES-" in pn:
        return 0.08
    if "IND-" in pn:
        return 0.15
    if "PSU" in pn:
        return 110.0
    if "BAT-" in pn:
        return 150.0
    if "LCD" in pn:
        return 300.0
    if "KB-" in pn:
        return 60.0
    if "CASE" in pn:
        return 70.0
    if "COOLER" in pn:
        return 35.0
    if "CONN" in pn:
        return 3.5
    # 按品类兜底
    if category_name:
        base = _CATEGORY_PRICE_BASELINE.get(category_name)
        if base:
            return base[0]
    return 100.0


def _supplier_lead_time(s, supplier_company_id: int) -> int:
    p = s.get(CompanyCache, supplier_company_id)
    seg = p.segment_code if p else None
    lo_hi = _SEGMENT_LEAD_TIME.get(seg or "", (10, 21))
    # 确定性取中值
    return (lo_hi[0] + lo_hi[1]) // 2


def _supplier_price_factor(s, supplier_company_id: int) -> float:
    """不同供应商的报价浮动因子 (确定性, 基于企业ID)。"""
    p = s.get(CompanyCache, supplier_company_id)
    seg = p.segment_code if p else ""
    # 分销商略贵 (现货), 被动元件厂略低 (直供), 芯片厂中位
    factor = {
        "semiconductor_chips": 1.02,
        "pcb_pcba": 0.98,
        "passive_components": 0.95,
        "sourcing_distribution": 1.08,
    }.get(seg, 1.0)
    # 企业ID尾数微调 (确定性, 不随机)
    factor += (supplier_company_id % 3) * 0.01
    return round(factor, 3)


# ============================================================
# 场景管理
# ============================================================

def ensure_default_scenario(s) -> str:
    """确保默认演示场景存在, 并初始化 6 家主视角企业状态。返回 scenario_id。"""
    scn = s.query(DemoScenario).filter_by(scenario_id=DEFAULT_SCENARIO_ID).first()
    if not scn:
        scn = DemoScenario(
            scenario_id=DEFAULT_SCENARIO_ID,
            name="MVP 演示场景 (6 家电脑制造产业链)",
            description="鼎云整机/创捷主板/华芯芯片/毅诚被动元件/星河渠道/远达物流 的演示沙盘",
            status="active",
            primary_company_ids=_dump_json(DEMO_COMPANY_IDS),
            config_json=_dump_json({"version": 1}),
        )
        s.add(scn)
        s.flush()
    _init_company_states(s, DEFAULT_SCENARIO_ID)
    return DEFAULT_SCENARIO_ID


def _init_company_states(s, scenario_id: str) -> None:
    """为 6 家主视角企业 + 其直接关系伙伴初始化状态快照 (幂等)。"""
    existing = {
        st.company_id for st in
        s.query(DemoCompanyState).filter_by(scenario_id=scenario_id).all()
    }
    to_init: list[int] = list(DEMO_COMPANY_IDS)
    # 把直接关系伙伴也纳入 (支撑/上下游环境企业)
    for cid in list(DEMO_COMPANY_IDS):
        for p in _direct_partners(s, cid):
            if p["company_id"] not in to_init:
                to_init.append(p["company_id"])
    for cid in to_init:
        if cid in existing:
            continue
        c = s.get(CompanyCache, cid)
        st = DemoCompanyState(
            scenario_id=scenario_id,
            company_id=cid,
            company_name=c.name if c else None,
            is_primary=_is_primary(cid),
            role=c.role if c else None,
            chain_position=c.chain_position if c else None,
            state_json=_dump_json(_compute_company_state(s, scenario_id, cid)),
        )
        s.add(st)
    s.flush()


def _compute_company_state(s, scenario_id: str, company_id: int) -> dict:
    """聚合企业当前演示状态 (基线只读 + 演示增量)。"""
    c = s.get(CompanyCache, company_id)
    # 基线摘要 (只读)
    products = dc.get_products(s, company_id) if c else []
    baseline_inv = dc.get_inventory(s, company_id) if c else []
    # 演示订单
    demo_orders = (
        s.query(DemoOrder)
        .filter_by(scenario_id=scenario_id, company_id=company_id)
        .order_by(DemoOrder.id.desc())
        .all()
    )
    # 演示库存增量
    overrides = (
        s.query(DemoInventoryOverride)
        .filter_by(scenario_id=scenario_id, company_id=company_id)
        .all()
    )
    # 演示 RFQ
    demo_rfqs = (
        s.query(DemoRfq)
        .filter_by(scenario_id=scenario_id, company_id=company_id)
        .order_by(DemoRfq.id.desc())
        .all()
    )
    # 演示缺件 (从 state 缓存或重算)
    shortages = _demo_shortages(s, scenario_id, company_id)
    # 直接关系
    partners = _direct_partners(s, company_id)

    inv_view: list[dict] = []
    for ov in overrides:
        available = (ov.baseline_on_hand or 0) - (ov.baseline_reserved or 0) \
            - (ov.consumed_qty or 0) + (ov.replenished_qty or 0)
        inv_view.append({
            "part_number": ov.part_number,
            "part_name": ov.part_name,
            "category_name": ov.category_name,
            "baseline_on_hand": ov.baseline_on_hand,
            "consumed_qty": ov.consumed_qty,
            "replenished_qty": ov.replenished_qty,
            "available_qty": available,
            "safety_stock_qty": ov.safety_stock_qty,
            "unit": ov.unit,
        })

    return {
        "company_id": company_id,
        "company_name": c.name if c else None,
        "is_primary": _is_primary(company_id),
        "role": c.role if c else None,
        "chain_position": c.chain_position if c else None,
        "products_total": len(products),
        "baseline_inventory_total": len(baseline_inv),
        "demo_orders_total": len(demo_orders),
        "demo_orders": [
            {
                "order_number": o.order_number, "product_name": o.product_name,
                "quantity": o.quantity, "priority": o.priority, "status": o.status,
                "customer_company_name": o.customer_company_name,
            }
            for o in demo_orders
        ],
        "demo_inventory_overrides_total": len(overrides),
        "demo_inventory": inv_view,
        "demo_shortages_total": len(shortages),
        "demo_shortages": shortages,
        "demo_rfqs_total": len(demo_rfqs),
        "demo_rfqs": [
            {
                "rfq_number": r.rfq_number, "part_name": r.part_name,
                "quantity": r.quantity, "status": r.status,
                "candidate_count": len(_parse_json(r.candidates_json, [])),
            }
            for r in demo_rfqs
        ],
        "direct_partners": [
            {"company_id": p["company_id"], "company_name": p["company_name"],
             "direction": p["direction"], "role": p.get("role")}
            for p in partners
        ],
    }


def _refresh_company_state(s, scenario_id: str, company_id: int) -> None:
    """刷新单个企业状态缓存; 若无则插入。"""
    st = (
        s.query(DemoCompanyState)
        .filter_by(scenario_id=scenario_id, company_id=company_id)
        .first()
    )
    state = _compute_company_state(s, scenario_id, company_id)
    if st:
        st.state_json = _dump_json(state)
        st.updated_at = _now()
    else:
        c = s.get(CompanyCache, company_id)
        s.add(DemoCompanyState(
            scenario_id=scenario_id, company_id=company_id,
            company_name=c.name if c else None,
            is_primary=_is_primary(company_id),
            role=c.role if c else None,
            chain_position=c.chain_position if c else None,
            state_json=_dump_json(state),
        ))
    s.flush()


def get_demo_state(s, scenario_id: str, company_id: int) -> dict:
    """返回企业当前演示状态 (实时聚合)。"""
    _company(s, company_id)
    scn = s.query(DemoScenario).filter_by(scenario_id=scenario_id).first()
    if not scn:
        raise HTTPException(status_code=404, detail=f"演示场景 {scenario_id} 不存在")
    state = _compute_company_state(s, scenario_id, company_id)
    # 同步刷新缓存
    _refresh_company_state(s, scenario_id, company_id)
    state["scenario_id"] = scenario_id
    state["scenario_name"] = scn.name
    state["scenario_status"] = scn.status
    return state


def get_demo_events(s, scenario_id: str, company_id: int | None = None,
                    limit: int = 100, phase: str | None = None) -> dict:
    """返回事件日志 (可按企业/阶段过滤)。"""
    q = s.query(DemoEvent).filter(DemoEvent.scenario_id == scenario_id)
    if company_id is not None:
        # 包含本企业事件 + 联动到本企业的事件
        q = q.filter(
            (DemoEvent.company_id == company_id)
            | (DemoEvent.linked_company_id == company_id)
        )
    if phase:
        q = q.filter(DemoEvent.phase == phase)
    rows = q.order_by(DemoEvent.seq.desc()).limit(limit).all()
    return {
        "scenario_id": scenario_id,
        "company_id": company_id,
        "total": len(rows),
        "items": [_event_dict(e) for e in rows],
    }


def _event_dict(e: DemoEvent) -> dict:
    return {
        "id": e.id,
        "seq": e.seq,
        "scenario_id": e.scenario_id,
        "phase": e.phase,
        "action_log_id": e.action_log_id,
        "company_id": e.company_id,
        "company_name": e.company_name,
        "linked_company_id": e.linked_company_id,
        "linked_company_name": e.linked_company_name,
        "event_type": e.event_type,
        "title": e.title,
        "detail": e.detail,
        "payload": _parse_json(e.payload_json, {}),
        "parent_event_id": e.parent_event_id,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


def reset_scenario(s, scenario_id: str) -> dict:
    """重置场景: 仅删除该 scenario_id 下的演示数据, 不触碰基线业务表。"""
    scn = s.query(DemoScenario).filter_by(scenario_id=scenario_id).first()
    if not scn:
        raise HTTPException(status_code=404, detail=f"演示场景 {scenario_id} 不存在")
    counts = {
        "demo_quotations": s.query(DemoQuotation).filter_by(scenario_id=scenario_id).delete(
            synchronize_session=False),
        "demo_rfqs": s.query(DemoRfq).filter_by(scenario_id=scenario_id).delete(
            synchronize_session=False),
        "demo_orders": s.query(DemoOrder).filter_by(scenario_id=scenario_id).delete(
            synchronize_session=False),
        "demo_inventory_overrides": s.query(DemoInventoryOverride)
            .filter_by(scenario_id=scenario_id).delete(synchronize_session=False),
        "demo_events": s.query(DemoEvent).filter_by(scenario_id=scenario_id).delete(
            synchronize_session=False),
        "demo_action_logs": s.query(DemoActionLog).filter_by(scenario_id=scenario_id).delete(
            synchronize_session=False),
        "demo_company_states": s.query(DemoCompanyState).filter_by(scenario_id=scenario_id).delete(
            synchronize_session=False),
    }
    scn.status = "active"
    scn.updated_at = _now()
    s.flush()
    # 重新初始化状态快照
    _init_company_states(s, scenario_id)
    return {
        "scenario_id": scenario_id,
        "status": "reset",
        "deleted": counts,
        "message": "演示场景已重置: 仅清除演示数据, 基线业务表未受影响",
    }


# ============================================================
# 动作: 创建动作日志 + 事件辅助
# ============================================================

def _start_action(s, scenario_id: str, company_id: int, action_type: str,
                  request: dict | None) -> DemoActionLog:
    log = DemoActionLog(
        scenario_id=scenario_id,
        company_id=company_id,
        action_type=action_type,
        request_json=_dump_json(request) if request else None,
        status="success",
    )
    s.add(log)
    s.flush()
    return log


def _finish_action(s, log: DemoActionLog, result: dict, event_ids: list[int],
                   status: str = "success", message: str | None = None) -> dict:
    """结束动作: 写日志, 返回结果 dict (含动作元信息)。"""
    log.result_json = _dump_json(result)
    log.event_ids_json = _dump_json(event_ids)
    log.status = status
    log.message = message
    s.flush()
    if isinstance(result, dict):
        result.setdefault("action_log_id", log.id)
        result.setdefault("action_status", status)
        result.setdefault("event_ids", event_ids)
        if message and "message" not in result:
            result["message"] = message
    return result


def _gen_order_number(s, scenario_id: str, company_id: int) -> str:
    year = datetime.utcnow().year
    prefix = f"DEMO-ORD-{year}-"
    rows = s.query(DemoOrder).filter(
        DemoOrder.scenario_id == scenario_id,
        DemoOrder.order_number.like(f"{prefix}%"),
    ).all()
    max_seq = 0
    for r in rows:
        try:
            max_seq = max(max_seq, int(r.order_number[len(prefix):]))
        except (ValueError, TypeError):
            continue
    return f"{prefix}{max_seq + 1:04d}"


def _gen_rfq_number(s, scenario_id: str) -> str:
    year = datetime.utcnow().year
    prefix = f"DEMO-RFQ-{year}-"
    rows = s.query(DemoRfq).filter(
        DemoRfq.scenario_id == scenario_id,
        DemoRfq.rfq_number.like(f"{prefix}%"),
    ).all()
    max_seq = 0
    for r in rows:
        try:
            max_seq = max(max_seq, int(r.rfq_number[len(prefix):]))
        except (ValueError, TypeError):
            continue
    return f"{prefix}{max_seq + 1:04d}"


# ============================================================
# 演示缺件计算 (基线需求 + 演示订单 - 演示可用库存)
# ============================================================

def _demo_demand_by_product(s, scenario_id: str, company_id: int):
    """返回 (product_id -> 总需求量, product_id -> [订单号], product_id -> {优先级})。

    总需求 = 基线活跃订单 + 基线预测 + 演示订单。
    """
    # 基线需求 (复用 dashboard_calc, 只读)
    demand, order_numbers, priorities = dc._demand_by_product(s, company_id)
    demand = dict(demand)
    order_numbers = {k: list(v) for k, v in order_numbers.items()}
    priorities = {k: set(v) for k, v in priorities.items()}

    # 演示订单需求
    demo_orders = (
        s.query(DemoOrder)
        .filter(
            DemoOrder.scenario_id == scenario_id,
            DemoOrder.company_id == company_id,
            DemoOrder.status.in_(ACTIVE_ORDER_STATUSES),
        )
        .all()
    )
    for o in demo_orders:
        demand[o.product_id] = demand.get(o.product_id, 0) + (o.quantity or 0)
        order_numbers.setdefault(o.product_id, []).append(o.order_number)
        priorities.setdefault(o.product_id, set()).add(o.priority)
    return demand, order_numbers, priorities


def _demo_inventory_view(s, scenario_id: str, company_id: int) -> dict[str, dict]:
    """返回 part_number -> {on_hand, reserved, safety, consumed, replenished, available, unit, ...}。

    演示可用 = baseline_on_hand - baseline_reserved - consumed + replenished。
    基线库存无 override 时 consumed/replenished = 0。
    """
    inv_items = (
        s.query(InventoryItem).filter_by(company_id=company_id).all()
    )
    view: dict[str, dict] = {}
    for i in inv_items:
        view[i.part_number] = {
            "part_number": i.part_number,
            "part_name": i.part_name,
            "category_name": i.category_name,
            "baseline_on_hand": i.on_hand_qty or 0,
            "baseline_reserved": i.reserved_qty or 0,
            "safety_stock_qty": i.safety_stock_qty or 0,
            "consumed_qty": 0,
            "replenished_qty": 0,
            "unit": "个",  # InventoryItem 无 unit 列, 默认个; override 创建时以 BOM unit 覆盖
        }
    # 叠加演示 override
    overrides = (
        s.query(DemoInventoryOverride)
        .filter_by(scenario_id=scenario_id, company_id=company_id)
        .all()
    )
    for ov in overrides:
        v = view.get(ov.part_number)
        if v is None:
            view[ov.part_number] = {
                "part_number": ov.part_number,
                "part_name": ov.part_name,
                "category_name": ov.category_name,
                "baseline_on_hand": ov.baseline_on_hand,
                "baseline_reserved": ov.baseline_reserved,
                "safety_stock_qty": ov.safety_stock_qty,
                "consumed_qty": ov.consumed_qty or 0,
                "replenished_qty": ov.replenished_qty or 0,
                "unit": ov.unit or "个",
            }
        else:
            v["consumed_qty"] = ov.consumed_qty or 0
            v["replenished_qty"] = ov.replenished_qty or 0
    # 计算可用
    for v in view.values():
        v["available_qty"] = (
            v["baseline_on_hand"] - v["baseline_reserved"]
            - v["consumed_qty"] + v["replenished_qty"]
        )
    return view


def _demo_shortages(s, scenario_id: str, company_id: int) -> list[dict]:
    """计算演示缺件 (不写入 kb_shortages)。

    规则与 dashboard_calc.recalculate_shortages 一致, 但:
      - 需求含演示订单
      - 可用库存含演示消耗/补货 override
    """
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
        if product_ids else []
    )
    inv_view = _demo_inventory_view(s, scenario_id, company_id)
    demand, order_numbers, priorities = _demo_demand_by_product(s, scenario_id, company_id)

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

    shortages: list[dict] = []
    for part_number, agg in part_agg.items():
        inv = inv_view.get(part_number)
        available = inv["available_qty"] if inv else 0
        safety = inv["safety_stock_qty"] if inv else 0
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
            if agg["is_critical"] and ("urgent" in agg["priorities"] or "high" in agg["priorities"]):
                severity = "critical"
            elif agg["is_critical"]:
                severity = "high"
            else:
                severity = "medium"
            shortages.append({
                "part_number": part_number,
                "part_name": agg["part_name"],
                "category_name": agg["category_name"],
                "shortage_type": "shortage",
                "required_qty": round(required, 2),
                "available_qty": round(available, 2),
                "shortage_qty": round(gap, 2),
                "safety_stock_qty": safety,
                "unit": agg["unit"],
                "is_critical": agg["is_critical"],
                "severity": severity,
                "preferred_supplier_company_id": pref_sup,
                "preferred_supplier_name": _company_name(s, pref_sup),
                "relationship_missing": rel_missing,
                "product_id": product_id_repr,
                "product_name": product_name_repr,
                "affected_order_numbers": affected_orders,
                "affected_product_ids": affected_products,
            })
        elif available < safety:
            shortages.append({
                "part_number": part_number,
                "part_name": agg["part_name"],
                "category_name": agg["category_name"],
                "shortage_type": "warning",
                "required_qty": round(required, 2),
                "available_qty": round(available, 2),
                "shortage_qty": 0.0,
                "safety_stock_qty": safety,
                "unit": agg["unit"],
                "is_critical": agg["is_critical"],
                "severity": "low",
                "preferred_supplier_company_id": pref_sup,
                "preferred_supplier_name": _company_name(s, pref_sup),
                "relationship_missing": rel_missing,
                "product_id": product_id_repr,
                "product_name": product_name_repr,
                "affected_order_numbers": affected_orders,
                "affected_product_ids": affected_products,
            })

    shortages.sort(key=lambda x: (_SEVERITY_RANK.get(x["severity"], 9),
                                 -x["shortage_qty"], x["part_number"]))
    return shortages


# ============================================================
# 库存 override 写入
# ============================================================

def _get_or_create_override(s, scenario_id: str, company_id: int,
                            part_number: str, source: str) -> DemoInventoryOverride | None:
    """获取或创建库存 override。

    有基线库存时以基线值初始化; 无基线库存时查 BOM 取零件信息, baseline 置 0
    (仍可记录演示消耗/补货, 不阻断流程)。
    """
    ov = (
        s.query(DemoInventoryOverride)
        .filter_by(scenario_id=scenario_id, company_id=company_id, part_number=part_number)
        .first()
    )
    if ov:
        return ov
    inv = (
        s.query(InventoryItem)
        .filter_by(company_id=company_id, part_number=part_number)
        .first()
    )
    if inv:
        # InventoryItem 无 unit 列, 从 BOM 取单位 (兜底 "个")
        b = (
            s.query(ProductBomItem)
            .filter_by(part_number=part_number)
            .order_by(ProductBomItem.id)
            .first()
        )
        ov = DemoInventoryOverride(
            scenario_id=scenario_id,
            company_id=company_id,
            part_number=inv.part_number,
            part_name=inv.part_name,
            category_name=inv.category_name,
            baseline_on_hand=inv.on_hand_qty or 0,
            baseline_reserved=inv.reserved_qty or 0,
            safety_stock_qty=inv.safety_stock_qty or 0,
            consumed_qty=0,
            replenished_qty=0,
            unit=(b.unit if b else "个") or "个",
            source=source,
        )
    else:
        # 无基线库存: 从 BOM 取零件名/品类/单位, baseline 置 0
        b = (
            s.query(ProductBomItem)
            .filter_by(part_number=part_number)
            .order_by(ProductBomItem.id)
            .first()
        )
        ov = DemoInventoryOverride(
            scenario_id=scenario_id,
            company_id=company_id,
            part_number=part_number,
            part_name=b.part_name if b else part_number,
            category_name=b.category_name if b else None,
            baseline_on_hand=0,
            baseline_reserved=0,
            safety_stock_qty=0,
            consumed_qty=0,
            replenished_qty=0,
            unit=(b.unit if b else "个") or "个",
            source=source,
        )
    s.add(ov)
    s.flush()
    return ov


def _apply_consume(s, scenario_id: str, company_id: int, part_number: str,
                   qty: int, source: str = "consume_inventory") -> DemoInventoryOverride | None:
    ov = _get_or_create_override(s, scenario_id, company_id, part_number, source)
    if not ov:
        return None
    ov.consumed_qty = (ov.consumed_qty or 0) + int(qty)
    ov.source = source
    ov.updated_at = _now()
    s.flush()
    return ov


def _apply_replenish(s, scenario_id: str, company_id: int, part_number: str,
                     qty: int, source: str = "execute_replenishment") -> DemoInventoryOverride | None:
    ov = _get_or_create_override(s, scenario_id, company_id, part_number, source)
    if not ov:
        return None
    ov.replenished_qty = (ov.replenished_qty or 0) + int(qty)
    ov.source = source
    ov.updated_at = _now()
    s.flush()
    return ov


# ============================================================
# 动作 1: generate_orders
# ============================================================

def generate_orders(s, scenario_id: str, company_id: int,
                    product_id: int | None = None,
                    quantity: int | None = None,
                    priority: str = "normal") -> dict:
    """为主视角企业生成演示订单, 并联动上下游/支撑企业产生事件。

    - 选 1 个在产产品 (product_id 或取首个 active)。
    - 订单量参考月产能 (15-25%), 合理区间。
    - 客户 = 直接下游企业 (无则置空)。
    - 联动: 下游收到需求 / 上游预见采购需求 / 支撑方生成物流计划。
    """
    _company(s, company_id)
    log = _start_action(s, scenario_id, company_id, "generate_orders", {
        "product_id": product_id, "quantity": quantity, "priority": priority,
    })
    phase = "generate_orders"

    products = (
        s.query(CompanyProduct)
        .filter_by(company_id=company_id, status="active")
        .order_by(CompanyProduct.id)
        .all()
    )
    if not products:
        return _finish_action(s, log, {"created": []}, [], status="failed",
                              message=f"企业 {company_id} 无在产产品, 无法生成订单")
    prod = None
    if product_id:
        prod = next((p for p in products if p.id == product_id), None)
    if not prod:
        prod = products[0]

    # 订单量: 月产能 15-25%, 至少 50
    cap = prod.monthly_capacity or 1000
    if quantity and quantity > 0:
        qty = int(quantity)
    else:
        ratio = 0.15 + (prod.id % 10) * 0.01  # 确定性 0.15-0.24
        qty = max(50, int(cap * ratio))
    qty = max(qty, 1)

    # 客户 = 直接下游
    partners = _direct_partners(s, company_id)
    downstream = next((p for p in partners if p["direction"] == "customer"), None)
    customer_id = downstream["company_id"] if downstream else None
    customer_name = downstream["company_name"] if downstream else None

    order_number = _gen_order_number(s, scenario_id, company_id)
    due_date = _now() + timedelta(days=30)
    o = DemoOrder(
        scenario_id=scenario_id,
        company_id=company_id,
        product_id=prod.id,
        product_name=prod.product_name,
        order_number=order_number,
        customer_company_id=customer_id,
        customer_company_name=customer_name,
        quantity=qty,
        due_date=due_date,
        priority=priority,
        status="confirmed",
    )
    s.add(o)
    s.flush()

    company_name = _company_name(s, company_id)
    # 主事件
    ev = _log_event(s, scenario_id=scenario_id, company_id=company_id, phase=phase,
                    action_log_id=log.id, event_type="order_created",
                    title=f"{company_name} 新增订单 {order_number}",
                    detail=f"{company_name} 新增生产订单 {order_number}: {prod.product_name} "
                          f"{qty}{prod.unit}, 优先级 {priority}, 客户 {customer_name or '未指定'}。",
                    payload={"order_number": order_number, "product_id": prod.id,
                             "quantity": qty, "customer_company_id": customer_id},
                    parent_event_id=None)
    o.event_id = ev.id
    event_ids = [ev.id]

    # 联动: 下游客户收到需求
    if customer_id:
        ce = _log_event(s, scenario_id=scenario_id, company_id=customer_id, phase=phase,
                        action_log_id=log.id, event_type="order_demand_received",
                        title=f"{customer_name} 收到 {company_name} 订单需求",
                        detail=f"{customer_name} (下游) 收到 {company_name} 订单 {order_number} "
                              f"对应产品 {prod.product_name} {qty}{prod.unit} 的需求。",
                        payload={"order_number": order_number, "quantity": qty},
                        parent_event_id=ev.id, linked_company_id=company_id)
        event_ids.append(ce.id)

    # 联动: 直接上游预见采购需求 (取该产品 BOM 关键件的首选上游)
    bom_items = (
        s.query(ProductBomItem)
        .filter_by(product_id=prod.id)
        .filter(ProductBomItem.is_critical == True)  # noqa: E712
        .all()
    )
    upstream_seen: set[int] = set()
    for b in bom_items:
        sup_id = b.preferred_supplier_company_id
        if not sup_id or sup_id in upstream_seen:
            continue
        if not _has_direct_relationship(s, company_id, sup_id):
            continue
        upstream_seen.add(sup_id)
        sup_name = _company_name(s, sup_id)
        ue = _log_event(s, scenario_id=scenario_id, company_id=sup_id, phase=phase,
                        action_log_id=log.id, event_type="upstream_demand_forecast",
                        title=f"{sup_name} 预计收到 {company_name} 采购需求",
                        detail=f"{sup_name} (直接上游) 预计收到 {company_name} 对 "
                              f"{b.part_name}({b.part_number}) 的采购需求 (订单 {order_number})。",
                        payload={"order_number": order_number, "part_number": b.part_number},
                        parent_event_id=ev.id, linked_company_id=company_id)
        event_ids.append(ue.id)

    # 联动: 支撑方 (物流) 生成计划
    support = next((p for p in partners if p["direction"] == "support"), None)
    if support:
        se = _log_event(s, scenario_id=scenario_id, company_id=support["company_id"], phase=phase,
                        action_log_id=log.id, event_type="transport_planning",
                        title=f"{support['company_name']} 生成出/入库计划",
                        detail=f"{support['company_name']} (支撑) 为 {company_name} 订单 "
                              f"{order_number} 生成仓储与配送计划。",
                        payload={"order_number": order_number},
                        parent_event_id=ev.id, linked_company_id=company_id)
        event_ids.append(se.id)

    _refresh_company_state(s, scenario_id, company_id)
    result = {
        "order": {
            "order_number": order_number, "product_id": prod.id,
            "product_name": prod.product_name, "quantity": qty, "unit": prod.unit,
            "priority": priority, "customer_company_id": customer_id,
            "customer_company_name": customer_name,
        },
        "events_created": len(event_ids),
    }
    _finish_action(s, log, result, event_ids)
    return result


# ============================================================
# 动作 2: consume_inventory
# ============================================================

def consume_inventory(s, scenario_id: str, company_id: int,
                      part_number: str | None = None,
                      quantity: int | None = None) -> dict:
    """消耗当前企业某零件库存 (模拟生产领料), 写入 demo_inventory_overrides。

    - part_number 未指定时, 取最近演示订单产品 BOM 中一个关键件消耗。
    - 消耗量参考 BOM 用量 × 订单量, 或库存的 20-40%。
    - 联动: 上游供应商收到下游消耗信号 / 支撑方库内移动。
    """
    _company(s, company_id)
    log = _start_action(s, scenario_id, company_id, "consume_inventory", {
        "part_number": part_number, "quantity": quantity,
    })
    phase = "consume_inventory"
    company_name = _company_name(s, company_id)

    inv_items = (
        s.query(InventoryItem).filter_by(company_id=company_id).all()
    )
    if not inv_items:
        return _finish_action(s, log, {"consumed": None}, [], status="failed",
                              message=f"企业 {company_id} 无基线库存, 无法消耗")

    target_part = part_number
    target_qty = quantity
    target_bom_item: ProductBomItem | None = None

    if not target_part:
        # 取最近演示订单产品 BOM 的关键件
        last_order = (
            s.query(DemoOrder)
            .filter_by(scenario_id=scenario_id, company_id=company_id)
            .order_by(DemoOrder.id.desc())
            .first()
        )
        if last_order:
            b = (
                s.query(ProductBomItem)
                .filter_by(product_id=last_order.product_id)
                .filter(ProductBomItem.is_critical == True)  # noqa: E712
                .order_by(ProductBomItem.id)
                .first()
            )
            if b:
                target_bom_item = b
                target_part = b.part_number
                if not target_qty:
                    target_qty = max(1, int(b.qty_per_unit * last_order.quantity))
    if not target_part:
        # 兜底: 取第一个有库存的零件
        target_part = inv_items[0].part_number

    inv = next((i for i in inv_items if i.part_number == target_part), None)
    if not inv:
        return _finish_action(s, log, {"consumed": None}, [], status="failed",
                              message=f"零件 {target_part} 无基线库存记录")

    if not target_qty or target_qty <= 0:
        # 默认消耗库存的 20-40% (确定性), 至少 1
        ratio = 0.20 + (inv.id % 20) * 0.01
        target_qty = max(1, int((inv.on_hand_qty or 0) * ratio))
    target_qty = max(int(target_qty), 1)

    ov = _apply_consume(s, scenario_id, company_id, target_part, target_qty,
                        source="consume_inventory")
    if not ov:
        return _finish_action(s, log, {"consumed": None}, [], status="failed",
                              message=f"零件 {target_part} 无法创建库存 override")

    available_after = (ov.baseline_on_hand - ov.baseline_reserved
                       - ov.consumed_qty + ov.replenished_qty)
    ev = _log_event(s, scenario_id=scenario_id, company_id=company_id, phase=phase,
                    action_log_id=log.id, event_type="inventory_consumed",
                    title=f"{company_name} 消耗 {ov.part_name} 库存 {target_qty}{ov.unit}",
                    detail=f"{company_name} 生产领料消耗 {ov.part_name}({ov.part_number}) "
                          f"{target_qty}{ov.unit}, 演示可用库存剩余 {available_after}{ov.unit}。",
                    payload={"part_number": ov.part_number, "consumed_qty": target_qty,
                             "available_after": available_after})
    event_ids = [ev.id]

    # 联动: 直接上游供应商收到消耗信号
    pref_sup = (target_bom_item.preferred_supplier_company_id
                if target_bom_item else None)
    if not pref_sup:
        # 从 BOM 反查
        b_any = (
            s.query(ProductBomItem)
            .filter_by(part_number=target_part)
            .first()
        )
        if b_any:
            pref_sup = b_any.preferred_supplier_company_id
    if pref_sup and _has_direct_relationship(s, company_id, pref_sup):
        sup_name = _company_name(s, pref_sup)
        ue = _log_event(s, scenario_id=scenario_id, company_id=pref_sup, phase=phase,
                        action_log_id=log.id, event_type="inventory_consumed",
                        title=f"{sup_name} 下游 {company_name} 消耗 {ov.part_name}",
                        detail=f"{sup_name} (直接上游) 下游 {company_name} 消耗 "
                              f"{ov.part_name}({ov.part_number}) {target_qty}{ov.unit}。",
                        payload={"part_number": ov.part_number, "consumed_qty": target_qty},
                        parent_event_id=ev.id, linked_company_id=company_id)
        event_ids.append(ue.id)

    # 联动: 支撑方库内移动
    partners = _direct_partners(s, company_id)
    support = next((p for p in partners if p["direction"] == "support"), None)
    if support:
        se = _log_event(s, scenario_id=scenario_id, company_id=support["company_id"], phase=phase,
                        action_log_id=log.id, event_type="transport_task",
                        title=f"{support['company_name']} 库内移动 {ov.part_name}",
                        detail=f"{support['company_name']} (支撑) 为 {company_name} 办理 "
                              f"{ov.part_name}({ov.part_number}) {target_qty}{ov.unit} 库内移动。",
                        payload={"part_number": ov.part_number, "qty": target_qty},
                        parent_event_id=ev.id, linked_company_id=company_id)
        event_ids.append(se.id)

    _refresh_company_state(s, scenario_id, company_id)
    result = {
        "consumed": {
            "part_number": ov.part_number, "part_name": ov.part_name,
            "consumed_qty": target_qty, "unit": ov.unit,
            "baseline_on_hand": ov.baseline_on_hand,
            "available_after": available_after,
        },
        "events_created": len(event_ids),
    }
    _finish_action(s, log, result, event_ids)
    return result


# ============================================================
# 动作 3: recalculate_shortages
# ============================================================

def recalculate_demo_shortages(s, scenario_id: str, company_id: int) -> dict:
    """重算演示缺件 (基线需求 + 演示订单 - 演示可用库存), 写事件。

    - 不写入 kb_shortages, 结果缓存在 demo_company_states.state_json。
    - 每个缺件产生 shortage_triggered 事件, 联动直接上游/标记无直接供应商。
    """
    _company(s, company_id)
    log = _start_action(s, scenario_id, company_id, "recalculate_shortages", {})
    phase = "recalculate_shortages"
    company_name = _company_name(s, company_id)

    shortages = _demo_shortages(s, scenario_id, company_id)
    event_ids: list[int] = []
    no_direct_count = 0
    for rec in shortages:
        if rec["shortage_type"] != "shortage":
            continue
        gap = rec["shortage_qty"]
        ev = _log_event(s, scenario_id=scenario_id, company_id=company_id, phase=phase,
                        action_log_id=log.id, event_type="shortage_triggered",
                        title=f"{company_name} 触发缺件 {rec['part_name']} 缺口 {gap}{rec['unit']}",
                        detail=f"{company_name} 缺件 {rec['part_name']}({rec['part_number']}): "
                              f"需求 {rec['required_qty']}, 可用 {rec['available_qty']}, "
                              f"缺口 {gap}{rec['unit']}, 严重度 {rec['severity']}。",
                        payload={"part_number": rec["part_number"],
                                 "shortage_qty": gap, "severity": rec["severity"]})
        event_ids.append(ev.id)

        pref_sup = rec["preferred_supplier_company_id"]
        if pref_sup and _has_direct_relationship(s, company_id, pref_sup):
            sup_name = _company_name(s, pref_sup)
            ue = _log_event(s, scenario_id=scenario_id, company_id=pref_sup, phase=phase,
                            action_log_id=log.id, event_type="shortage_triggered",
                            title=f"{sup_name} 下游 {company_name} 缺件 {rec['part_name']}",
                            detail=f"{sup_name} (直接上游) 下游 {company_name} 缺件 "
                                  f"{rec['part_name']}({rec['part_number']}) 缺口 {gap}{rec['unit']}, 待询价。",
                            payload={"part_number": rec["part_number"], "shortage_qty": gap},
                            parent_event_id=ev.id, linked_company_id=company_id)
            event_ids.append(ue.id)
        else:
            # 无直接关系供应商
            no_direct_count += 1
            ne = _log_event(s, scenario_id=scenario_id, company_id=company_id, phase=phase,
                            action_log_id=log.id, event_type="no_direct_supplier",
                            title=f"{company_name} {rec['part_name']} 无可用直接关系供应商",
                            detail=f"{rec['part_name']}({rec['part_number']}) 缺口 {gap}{rec['unit']}, "
                                  f"首选供应商 {rec.get('preferred_supplier_name') or '未指定'} "
                                  f"与本企业无直接上下游关系, 需要先建立合作关系/人工审核。",
                            payload={"part_number": rec["part_number"],
                                     "shortage_qty": gap,
                                     "preferred_supplier_company_id": pref_sup},
                            parent_event_id=ev.id)
            event_ids.append(ne.id)

    _refresh_company_state(s, scenario_id, company_id)
    shortage_count = sum(1 for i in shortages if i["shortage_type"] == "shortage")
    warning_count = sum(1 for i in shortages if i["shortage_type"] == "warning")
    result = {
        "shortages": shortages,
        "total": len(shortages),
        "shortage_count": shortage_count,
        "warning_count": warning_count,
        "no_direct_supplier_count": no_direct_count,
        "events_created": len(event_ids),
    }
    status = "success" if shortages else "partial"
    msg = (f"重算完成: {shortage_count} 缺件 / {warning_count} 预警 / "
           f"{no_direct_count} 无直接供应商" if shortages else "无缺件")
    _finish_action(s, log, result, event_ids, status=status, message=msg)
    return result


# ============================================================
# 动作 4: generate_rfq
# ============================================================

def generate_rfq(s, scenario_id: str, company_id: int,
                 part_number: str | None = None,
                 shortage_index: int | None = None,
                 quantity: int | None = None,
                 target_price: float | None = None,
                 lead_time_days: int | None = None) -> dict:
    """从缺件生成 RFQ, 仅从直接上下游/支撑企业中找候选供应商。

    - 无直接关系供应商时返回 no_direct_supplier, 不自动建立关系, 不推荐非直接企业。
    """
    _company(s, company_id)
    log = _start_action(s, scenario_id, company_id, "generate_rfq", {
        "part_number": part_number, "shortage_index": shortage_index,
        "quantity": quantity, "target_price": target_price,
    })
    phase = "generate_rfq"
    company_name = _company_name(s, company_id)

    shortages = _demo_shortages(s, scenario_id, company_id)
    shortage_shortages = [x for x in shortages if x["shortage_type"] == "shortage"]

    target = None
    if part_number:
        target = next((x for x in shortages if x["part_number"] == part_number), None)
        if not target:
            # 允许针对非缺件零件发起 RFQ (sourcing)
            target = {"part_number": part_number, "part_name": part_number,
                      "category_name": None, "shortage_qty": quantity or 1,
                      "preferred_supplier_company_id": None,
                      "preferred_supplier_name": None,
                      "unit": "个", "product_id": None, "product_name": None,
                      "shortage_type": "sourcing"}
    elif shortage_index is not None and shortage_shortages:
        try:
            target = shortage_shortages[int(shortage_index)]
        except (IndexError, ValueError):
            target = None
    elif shortage_shortages:
        target = shortage_shortages[0]

    if not target:
        result = {"rfq": None, "candidates": [], "no_direct_supplier": False,
                  "message": "无缺件可生成 RFQ; 请先 generate-orders / consume-inventory / recalculate-shortages"}
        return _finish_action(s, log, result, [], status="failed",
                              message=result["message"])

    pn = target["part_number"]
    pcat = target.get("category_name")
    pname = target.get("part_name")
    pref_sup = target.get("preferred_supplier_company_id")
    gap = target.get("shortage_qty") or 1
    qty = int(quantity or max(1, int(gap)))
    base_price = target_price or _part_baseline_price(pn, pcat)
    lead = lead_time_days or 14

    # 关键: 仅从直接关系中找候选
    candidates = _direct_supplier_candidates(
        s, company_id, pcat, pn, pname, pref_sup
    )

    if not candidates:
        # 无可用直接关系供应商: 明确提示, 不自动建立关系
        ne = _log_event(s, scenario_id=scenario_id, company_id=company_id, phase=phase,
                        action_log_id=log.id, event_type="no_direct_supplier",
                        title=f"{company_name} {pname} 无可用直接关系供应商",
                        detail=f"{company_name} 缺件 {pname}({pn}) 缺口 {gap}, "
                              f"直接上下游/支撑关系中无合适供应商, "
                              f"需要先建立合作关系/人工审核 (不自动建立关系, 不推荐非直接企业)。",
                        payload={"part_number": pn, "shortage_qty": gap,
                                 "preferred_supplier_company_id": pref_sup})
        _refresh_company_state(s, scenario_id, company_id)
        result = {
            "rfq": None,
            "part_number": pn, "part_name": pname,
            "candidates": [],
            "no_direct_supplier": True,
            "message": "无可用直接关系供应商, 需要先建立合作关系/人工审核",
        }
        return _finish_action(s, log, result, [ne.id], status="no_direct_supplier",
                              message=result["message"])

    # 创建 demo RFQ (status=sent, 候选已收到)
    rfq_number = _gen_rfq_number(s, scenario_id)
    rfq = DemoRfq(
        scenario_id=scenario_id,
        company_id=company_id,
        rfq_number=rfq_number,
        title=f"{pname} 缺件采购 ({pn})",
        part_number=pn,
        part_name=pname,
        quantity=qty,
        unit=target.get("unit") or "个",
        target_price=base_price,
        lead_time_days=lead,
        accept_alternatives=True,
        scenario="shortage",
        status="sent",
        candidates_json=_dump_json(candidates),
        selected_supplier_company_id=None,
        shortage_event_id=None,
    )
    s.add(rfq)
    s.flush()

    ev = _log_event(s, scenario_id=scenario_id, company_id=company_id, phase=phase,
                    action_log_id=log.id, event_type="rfq_created",
                    title=f"{company_name} 生成 RFQ {rfq_number}",
                    detail=f"{company_name} 因缺件 {pname}({pn}) 缺口 {gap}, "
                          f"向 {len(candidates)} 家直接关系供应商发起询价 {rfq_number}, "
                          f"目标单价 {base_price}, 需求 {qty}{rfq.unit}。",
                    payload={"rfq_number": rfq_number, "part_number": pn,
                             "quantity": qty, "candidates": candidates})
    event_ids = [ev.id]
    rfq.event_id = ev.id

    # 联动: 每个候选供应商收到 RFQ
    for c in candidates:
        ce = _log_event(s, scenario_id=scenario_id, company_id=c["supplier_company_id"],
                        phase=phase, action_log_id=log.id, event_type="rfq_received",
                        title=f"{c['supplier_name']} 收到 RFQ {rfq_number}",
                        detail=f"{c['supplier_name']} (直接{('上游' if c['direction']=='supplier' else '关系')}) "
                              f"收到 {company_name} 询价 {rfq_number}: {pname}({pn}) {qty}{rfq.unit}, "
                              f"目标单价 {base_price}。",
                        payload={"rfq_number": rfq_number, "part_number": pn,
                                 "match_score": c["match_score"]},
                        parent_event_id=ev.id, linked_company_id=company_id)
        event_ids.append(ce.id)

    _refresh_company_state(s, scenario_id, company_id)
    result = {
        "rfq": _rfq_dict(rfq),
        "candidates": candidates,
        "no_direct_supplier": False,
        "events_created": len(event_ids),
    }
    _finish_action(s, log, result, event_ids)
    return result


def _rfq_dict(r: DemoRfq) -> dict:
    return {
        "id": r.id,
        "scenario_id": r.scenario_id,
        "rfq_number": r.rfq_number,
        "company_id": r.company_id,
        "title": r.title,
        "part_number": r.part_number,
        "part_name": r.part_name,
        "quantity": r.quantity,
        "unit": r.unit,
        "target_price": r.target_price,
        "lead_time_days": r.lead_time_days,
        "accept_alternatives": r.accept_alternatives,
        "scenario": r.scenario,
        "status": r.status,
        "candidates": _parse_json(r.candidates_json, []),
        "selected_supplier_company_id": r.selected_supplier_company_id,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# ============================================================
# 动作 5: simulate_quotes
# ============================================================

def simulate_quotes(s, scenario_id: str, company_id: int,
                    rfq_id: int | None = None) -> dict:
    """为 RFQ 的候选供应商模拟报价 (合理价格/交期, 基于企业角色与零件品类)。"""
    _company(s, company_id)
    log = _start_action(s, scenario_id, company_id, "simulate_quotes", {"rfq_id": rfq_id})
    phase = "simulate_quotes"
    company_name = _company_name(s, company_id)

    q = s.query(DemoRfq).filter(
        DemoRfq.scenario_id == scenario_id,
        DemoRfq.company_id == company_id,
    )
    if rfq_id:
        q = q.filter(DemoRfq.id == rfq_id)
    rfq = q.order_by(DemoRfq.id.desc()).first()
    if not rfq:
        return _finish_action(s, log, {"quotes": []}, [], status="failed",
                              message="无可用 RFQ, 请先 generate-rfq")

    candidates = _parse_json(rfq.candidates_json, [])
    if not candidates:
        return _finish_action(s, log, {"quotes": [], "rfq_number": rfq.rfq_number}, [],
                              status="no_direct_supplier",
                              message=f"RFQ {rfq.rfq_number} 无候选供应商 (无直接关系供应商)")

    base_price = rfq.target_price or _part_baseline_price(rfq.part_number, None)
    event_ids: list[int] = []
    quotes: list[dict] = []
    for c in candidates:
        sup_id = c["supplier_company_id"]
        factor = _supplier_price_factor(s, sup_id)
        unit_price = round(base_price * factor, 4)
        lead = _supplier_lead_time(s, sup_id)
        moq = max(1, int((rfq.quantity or 1) * 0.1)) if base_price < 1 else 1
        stock = max(0, (rfq.quantity or 1) + sup_id % 500) if c.get("direction") == "customer" else None
        in_stock = stock is not None and stock > 0
        # 更新候选状态
        c["status"] = "quoted"
        qrow = DemoQuotation(
            scenario_id=scenario_id,
            rfq_id=rfq.id,
            supplier_company_id=sup_id,
            supplier_name=c.get("supplier_name"),
            part_number=rfq.part_number,
            unit_price=unit_price,
            currency="CNY",
            moq=moq,
            lead_time_days=lead,
            stock_qty=stock,
            is_in_stock=in_stock,
            note=f"模拟报价 (匹配分 {c.get('match_score')})",
        )
        s.add(qrow)
        s.flush()
        qe = _log_event(s, scenario_id=scenario_id, company_id=sup_id, phase=phase,
                        action_log_id=log.id, event_type="quote_received",
                        title=f"{c.get('supplier_name')} 报价 {rfq.part_name} 单价 {unit_price}",
                        detail=f"{c.get('supplier_name')} 对 RFQ {rfq.rfq_number} 报价: "
                              f"{rfq.part_name}({rfq.part_number}) 单价 {unit_price} 元, "
                              f"交期 {lead} 天, MOQ {moq}。",
                        payload={"rfq_number": rfq.rfq_number, "unit_price": unit_price,
                                 "lead_time_days": lead, "moq": moq},
                        parent_event_id=rfq.event_id, linked_company_id=company_id)
        qrow.event_id = qe.id
        event_ids.append(qe.id)
        quotes.append(_quote_dict(qrow))

    rfq.candidates_json = _dump_json(candidates)
    rfq.status = "quoted"
    rfq.updated_at = _now()
    _refresh_company_state(s, scenario_id, company_id)
    result = {
        "rfq_number": rfq.rfq_number,
        "rfq_id": rfq.id,
        "quotes": quotes,
        "quote_count": len(quotes),
        "lowest_price": min((q["unit_price"] for q in quotes), default=None),
        "events_created": len(event_ids),
    }
    _finish_action(s, log, result, event_ids)
    return result


def _quote_dict(q: DemoQuotation) -> dict:
    return {
        "id": q.id,
        "rfq_id": q.rfq_id,
        "supplier_company_id": q.supplier_company_id,
        "supplier_name": q.supplier_name,
        "part_number": q.part_number,
        "unit_price": q.unit_price,
        "currency": q.currency,
        "moq": q.moq,
        "lead_time_days": q.lead_time_days,
        "stock_qty": q.stock_qty,
        "is_in_stock": q.is_in_stock,
        "note": q.note,
        "created_at": q.created_at.isoformat() if q.created_at else None,
    }


def quote_comparison(s, scenario_id: str, company_id: int, rfq_id: int) -> dict:
    """报价对比视图 (按单价排序 + 是否达标 + 最低价标记)。"""
    _company(s, company_id)
    rfq = s.get(DemoRfq, rfq_id)
    if not rfq or rfq.scenario_id != scenario_id or rfq.company_id != company_id:
        raise HTTPException(status_code=404, detail=f"RFQ {rfq_id} 不存在")
    rows = (
        s.query(DemoQuotation)
        .filter_by(rfq_id=rfq_id)
        .order_by(DemoQuotation.unit_price.asc())
        .all()
    )
    quotes = [_quote_dict(q) for q in rows]
    target = rfq.target_price
    for i, qd in enumerate(quotes):
        qd["rank"] = i + 1
        qd["is_lowest"] = (i == 0)
        if target is not None:
            qd["meets_target"] = qd["unit_price"] <= target
            qd["delta_vs_target"] = round(qd["unit_price"] - target, 4)
        else:
            qd["meets_target"] = None
            qd["delta_vs_target"] = None
    return {
        "rfq_id": rfq_id,
        "rfq_number": rfq.rfq_number,
        "target_price": target,
        "quantity": rfq.quantity,
        "quote_count": len(quotes),
        "lowest_price": quotes[0]["unit_price"] if quotes else None,
        "items": quotes,
    }


# ============================================================
# 动作 6: execute_replenishment
# ============================================================

def execute_replenishment(s, scenario_id: str, company_id: int,
                          rfq_id: int | None = None,
                          supplier_company_id: int | None = None) -> dict:
    """选择报价并执行补货: 入库 (demo_inventory_overrides replenished) + 关闭 RFQ + 联动事件。"""
    _company(s, company_id)
    log = _start_action(s, scenario_id, company_id, "execute_replenishment", {
        "rfq_id": rfq_id, "supplier_company_id": supplier_company_id,
    })
    phase = "execute_replenishment"
    company_name = _company_name(s, company_id)

    q = s.query(DemoRfq).filter(
        DemoRfq.scenario_id == scenario_id,
        DemoRfq.company_id == company_id,
        DemoRfq.status.in_(["sent", "quoted"]),
    )
    if rfq_id:
        q = q.filter(DemoRfq.id == rfq_id)
    rfq = q.order_by(DemoRfq.id.desc()).first()
    if not rfq:
        return _finish_action(s, log, {"replenished": None}, [], status="failed",
                              message="无待补货 RFQ (需先 generate-rfq / simulate-quotes)")

    quotes = (
        s.query(DemoQuotation)
        .filter_by(rfq_id=rfq.id)
        .order_by(DemoQuotation.unit_price.asc())
        .all()
    )
    if not quotes:
        return _finish_action(s, log, {"replenished": None, "rfq_number": rfq.rfq_number}, [],
                              status="failed",
                              message=f"RFQ {rfq.rfq_number} 暂无报价, 请先 simulate-quotes")

    # 选择报价: 指定供应商优先, 否则最低价 (达标优先)
    target = rfq.target_price
    chosen: DemoQuotation | None = None
    if supplier_company_id:
        chosen = next((qq for qq in quotes if qq.supplier_company_id == supplier_company_id), None)
        if not chosen:
            return _finish_action(s, log, {"replenished": None}, [], status="failed",
                                  message=f"供应商 {supplier_company_id} 未对该 RFQ 报价")
    else:
        meet = [qq for qq in quotes if target is None or qq.unit_price <= target]
        chosen = (meet[0] if meet else quotes[0])

    replenish_qty = max(int(rfq.quantity or 1), 1)
    ov = _apply_replenish(s, scenario_id, company_id, rfq.part_number, replenish_qty,
                          source="execute_replenishment")
    if not ov:
        return _finish_action(s, log, {"replenished": None}, [], status="failed",
                              message=f"零件 {rfq.part_number} 无基线库存记录, 无法入库")

    rfq.status = "closed"
    rfq.selected_supplier_company_id = chosen.supplier_company_id
    rfq.updated_at = _now()
    available_after = (ov.baseline_on_hand - ov.baseline_reserved
                       - ov.consumed_qty + ov.replenished_qty)
    sup_name = chosen.supplier_name or _company_name(s, chosen.supplier_company_id)

    ev = _log_event(s, scenario_id=scenario_id, company_id=company_id, phase=phase,
                    action_log_id=log.id, event_type="replenishment_executed",
                    title=f"{company_name} 选定 {sup_name} 报价, 执行补货 {replenish_qty}{ov.unit}",
                    detail=f"{company_name} 选定 {sup_name} 报价 (单价 {chosen.unit_price}), "
                          f"对 {rfq.part_name}({rfq.part_number}) 入库 {replenish_qty}{ov.unit}, "
                          f"演示可用库存恢复至 {available_after}{ov.unit}。",
                    payload={"rfq_number": rfq.rfq_number, "supplier_company_id": chosen.supplier_company_id,
                             "unit_price": chosen.unit_price, "replenished_qty": replenish_qty,
                             "available_after": available_after},
                    parent_event_id=rfq.event_id)
    event_ids = [ev.id]

    # 联动: 供应商确认订单
    ce = _log_event(s, scenario_id=scenario_id, company_id=chosen.supplier_company_id, phase=phase,
                    action_log_id=log.id, event_type="order_confirmed",
                    title=f"{sup_name} 确认订单 {rfq.part_name} {replenish_qty}{ov.unit}",
                    detail=f"{sup_name} (直接关系供应商) 确认 {company_name} 订单: "
                          f"{rfq.part_name}({rfq.part_number}) {replenish_qty}{ov.unit}, 单价 {chosen.unit_price}, "
                          f"交期 {chosen.lead_time_days} 天, 安排发货。",
                    payload={"rfq_number": rfq.rfq_number, "quantity": replenish_qty,
                             "unit_price": chosen.unit_price},
                    parent_event_id=ev.id, linked_company_id=company_id)
    event_ids.append(ce.id)

    # 联动: 支撑方 (物流) 生成运输任务
    partners = _direct_partners(s, company_id)
    support = next((p for p in partners if p["direction"] == "support"), None)
    if support:
        se = _log_event(s, scenario_id=scenario_id, company_id=support["company_id"], phase=phase,
                        action_log_id=log.id, event_type="transport_task",
                        title=f"{support['company_name']} 生成运输任务 {rfq.part_name}",
                        detail=f"{support['company_name']} (支撑) 生成运输任务: "
                              f"{rfq.part_name}({rfq.part_number}) {replenish_qty}{ov.unit}, "
                              f"{sup_name} -> {company_name}, 交期 {chosen.lead_time_days} 天。",
                        payload={"rfq_number": rfq.rfq_number, "quantity": replenish_qty,
                                 "from": sup_name, "to": company_name},
                        parent_event_id=ev.id, linked_company_id=company_id)
        event_ids.append(se.id)

    _refresh_company_state(s, scenario_id, company_id)
    result = {
        "rfq_number": rfq.rfq_number,
        "rfq_id": rfq.id,
        "selected_supplier_company_id": chosen.supplier_company_id,
        "selected_supplier_name": sup_name,
        "unit_price": chosen.unit_price,
        "replenished_qty": replenish_qty,
        "available_after": available_after,
        "events_created": len(event_ids),
    }
    _finish_action(s, log, result, event_ids)
    return result


# ============================================================
# 动作 7: select_alternative
# ============================================================

def select_alternative(s, scenario_id: str, company_id: int,
                       part_number: str | None = None,
                       alternative_supplier_company_id: int | None = None,
                       quantity: int | None = None) -> dict:
    """为缺件选用替代料来源 (仅允许直接关系企业)。

    - 若指定 alternative_supplier_company_id, 校验为直接关系, 否则 400。
    - 若未指定, 从直接关系中找一个能供应该品类的伙伴; 无则返回 no_direct_supplier。
    - 创建替代报价 + 入库 + 事件。
    """
    _company(s, company_id)
    log = _start_action(s, scenario_id, company_id, "select_alternative", {
        "part_number": part_number,
        "alternative_supplier_company_id": alternative_supplier_company_id,
        "quantity": quantity,
    })
    phase = "select_alternative"
    company_name = _company_name(s, company_id)

    # 确定目标零件
    shortages = _demo_shortages(s, scenario_id, company_id)
    target = None
    if part_number:
        target = next((x for x in shortages if x["part_number"] == part_number), None)
    if not target and shortages:
        # 取第一个无直接供应商的缺件, 否则取第一个缺件
        target = next((x for x in shortages if x["shortage_type"] == "shortage"), None)
    if not target:
        return _finish_action(s, log, {"alternative": None}, [], status="failed",
                              message="无缺件可选用替代料, 请先 recalculate-shortages")

    pn = target["part_number"]
    pcat = target.get("category_name")
    pname = target.get("part_name")
    gap = int(target.get("shortage_qty") or 1)
    qty = int(quantity or max(1, gap))

    # 校验指定替代供应商为直接关系
    if alternative_supplier_company_id:
        if not _has_direct_relationship(s, company_id, alternative_supplier_company_id):
            return _finish_action(s, log, {"alternative": None}, [], status="failed",
                                  message=f"供应商 {alternative_supplier_company_id} 与本企业无直接关系, "
                                          f"不允许作为替代料来源 (需先建立合作关系/人工审核)")
        alt_id = alternative_supplier_company_id
    else:
        cands = _direct_supplier_candidates(s, company_id, pcat, pn, pname,
                                            target.get("preferred_supplier_company_id"))
        if not cands:
            ne = _log_event(s, scenario_id=scenario_id, company_id=company_id, phase=phase,
                            action_log_id=log.id, event_type="no_direct_supplier",
                            title=f"{company_name} {pname} 无可用直接关系替代供应商",
                            detail=f"{company_name} 缺件 {pname}({pn}) 缺口 {gap}, "
                                  f"直接关系中无合适替代供应商, 需要先建立合作关系/人工审核。",
                            payload={"part_number": pn, "shortage_qty": gap})
            _refresh_company_state(s, scenario_id, company_id)
            return _finish_action(s, log, {
                "alternative": None, "no_direct_supplier": True,
                "message": "无可用直接关系供应商, 需要先建立合作关系/人工审核",
            }, [ne.id], status="no_direct_supplier",
                message="无可用直接关系供应商, 需要先建立合作关系/人工审核")
        alt_id = cands[0]["supplier_company_id"]

    alt_name = _company_name(s, alt_id)
    base_price = _part_baseline_price(pn, pcat)
    factor = _supplier_price_factor(s, alt_id)
    unit_price = round(base_price * factor * 1.03, 4)  # 替代料略贵 3%
    lead = _supplier_lead_time(s, alt_id)

    # 创建一条替代 RFQ + 报价 (闭环留痕)
    rfq_number = _gen_rfq_number(s, scenario_id)
    cand = [{
        "supplier_company_id": alt_id, "supplier_name": alt_name,
        "direction": "supplier", "match_score": 0.8,
        "match_reason": f"替代料来源: {alt_name} 为本企业直接关系", "status": "quoted",
    }]
    rfq = DemoRfq(
        scenario_id=scenario_id, company_id=company_id, rfq_number=rfq_number,
        title=f"{pname} 替代料采购 ({pn})", part_number=pn, part_name=pname,
        quantity=qty, unit=target.get("unit") or "个",
        target_price=base_price, lead_time_days=lead,
        accept_alternatives=True, scenario="shortage", status="closed",
        candidates_json=_dump_json(cand),
        selected_supplier_company_id=alt_id,
    )
    s.add(rfq)
    s.flush()
    quote = DemoQuotation(
        scenario_id=scenario_id, rfq_id=rfq.id, supplier_company_id=alt_id,
        supplier_name=alt_name, part_number=pn, unit_price=unit_price,
        currency="CNY", moq=1, lead_time_days=lead, stock_qty=None,
        is_in_stock=False, note="替代料模拟报价",
    )
    s.add(quote)
    s.flush()

    ov = _apply_replenish(s, scenario_id, company_id, pn, qty, source="select_alternative")
    available_after = (ov.baseline_on_hand - ov.baseline_reserved
                       - ov.consumed_qty + ov.replenished_qty) if ov else None

    ev = _log_event(s, scenario_id=scenario_id, company_id=company_id, phase=phase,
                    action_log_id=log.id, event_type="alternative_selected",
                    title=f"{company_name} 选用替代料 {pname} 来自 {alt_name}",
                    detail=f"{company_name} 为缺件 {pname}({pn}) 选用 {alt_name} (直接关系) 作为替代料来源, "
                          f"单价 {unit_price}, 入库 {qty}{rfq.unit}, 可用库存恢复至 {available_after}。",
                    payload={"rfq_number": rfq_number, "supplier_company_id": alt_id,
                             "unit_price": unit_price, "replenished_qty": qty})
    event_ids = [ev.id]
    rfq.event_id = ev.id
    quote.event_id = ev.id

    # 联动: 替代供应商提供替代料
    ce = _log_event(s, scenario_id=scenario_id, company_id=alt_id, phase=phase,
                    action_log_id=log.id, event_type="order_confirmed",
                    title=f"{alt_name} 提供替代料 {pname} {qty}{rfq.unit}",
                    detail=f"{alt_name} (直接关系) 为 {company_name} 提供替代料 "
                          f"{pname}({pn}) {qty}{rfq.unit}, 单价 {unit_price}, 交期 {lead} 天。",
                    payload={"rfq_number": rfq_number, "quantity": qty, "unit_price": unit_price},
                    parent_event_id=ev.id, linked_company_id=company_id)
    event_ids.append(ce.id)

    _refresh_company_state(s, scenario_id, company_id)
    result = {
        "rfq_number": rfq_number,
        "alternative_supplier_company_id": alt_id,
        "alternative_supplier_name": alt_name,
        "unit_price": unit_price,
        "replenished_qty": qty,
        "available_after": available_after,
        "events_created": len(event_ids),
    }
    _finish_action(s, log, result, event_ids)
    return result
