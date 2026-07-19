"""
演示场景沙盘 API: 支持主视角企业通过悬浮控制台手动推进运营数据变化。

路由 (无统一前缀, 在 main.py 下挂 /api/v1):
  GET  /demo/state                                当前企业演示状态 (基线 + 演示增量)
  GET  /demo/events                               事件日志 (因果链, 可按企业/阶段过滤)
  GET  /demo/scenarios                            场景信息
  POST /demo/scenarios/reset                      重置场景 (仅清演示数据, 不动基线)
  POST /demo/actions/generate-orders              生成演示订单 (+联动上下游/支撑)
  POST /demo/actions/consume-inventory            消耗库存 (写入 demo override)
  POST /demo/actions/recalculate-shortages        重算演示缺件
  POST /demo/actions/generate-rfq                 从缺件生成 RFQ (仅直接关系候选)
  POST /demo/actions/simulate-quotes              模拟候选供应商报价 (幂等: 已报价则刷新不重复)
  POST /demo/actions/execute-replenishment        选择报价并补货入库
  POST /demo/actions/select-alternative           选用替代料来源 (仅直接关系)
  GET  /demo/rfqs                                 演示 RFQ 列表 (买方视角)
  GET  /demo/rfqs/{rfq_id}/quote-comparison       演示报价对比
  GET  /demo/supplier-view                        供应商视角: 收到的 demo RFQ + 报价 + 事件
  GET  /demo/audit-queue                          演示只读审核队列 (无直接供应商/报价异常/关系缺失)

行为约束:
  - 控制台只能操作 6 家主视角企业 (DEMO_COMPANY_IDS); 联动影响写入相关上下游/支撑企业事件。
  - RFQ 候选供应商仅限当前企业的直接上下游/支撑关系企业; 无则返回 no_direct_supplier 提示。
  - 所有演示变化带 scenario_id (默认 default_mvp_demo); 重置只清演示数据, 不触碰基线业务表。
  - 保留 demo token 兼容, 不破坏真实 JWT/MySQL 登录逻辑。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from kb.db import session_scope
from kb import demo_calc as dcalc
from api.deps import get_current_user

router = APIRouter(tags=["demo-scenario"])

DEFAULT_SCENARIO_ID = dcalc.DEFAULT_SCENARIO_ID


# ============================================================
# 请求模型
# ============================================================

class DemoCompanyReq(BaseModel):
    """演示动作通用请求: 指定当前登录的主视角企业。"""
    company_id: int = Field(..., description="当前登录主视角企业ID (9001-9006)")
    scenario_id: str | None = Field(default=None, description="场景ID, 默认 default_mvp_demo")


class GenerateOrdersReq(DemoCompanyReq):
    product_id: int | None = None
    quantity: int | None = None
    priority: str = "normal"


class ConsumeInventoryReq(DemoCompanyReq):
    part_number: str | None = None
    quantity: int | None = None


class RecalculateShortagesReq(DemoCompanyReq):
    pass


class GenerateRfqReq(DemoCompanyReq):
    part_number: str | None = None
    shortage_index: int | None = None
    quantity: int | None = None
    target_price: float | None = None
    lead_time_days: int | None = None


class SimulateQuotesReq(DemoCompanyReq):
    rfq_id: int | None = None


class ExecuteReplenishmentReq(DemoCompanyReq):
    rfq_id: int | None = None
    supplier_company_id: int | None = None


class SelectAlternativeReq(DemoCompanyReq):
    part_number: str | None = None
    alternative_supplier_company_id: int | None = None
    quantity: int | None = None


class ResetReq(BaseModel):
    scenario_id: str | None = None


# ============================================================
# 辅助
# ============================================================

def _resolve_scenario(scenario_id: str | None) -> str:
    return scenario_id or DEFAULT_SCENARIO_ID


def _require_primary(company_id: int) -> None:
    """演示控制台只能操作 6 家主视角企业。"""
    if company_id not in dcalc.DEMO_COMPANY_IDS:
        raise HTTPException(
            status_code=400,
            detail=f"企业 {company_id} 非演示主视角企业 (允许: {dcalc.DEMO_COMPANY_IDS}), "
                  f"控制台仅可操作 6 家可登录企业",
        )


def _ensure_scenario(s, scenario_id: str) -> str:
    """确保场景存在 (幂等), 返回 scenario_id。"""
    return dcalc.ensure_default_scenario(s) if scenario_id == DEFAULT_SCENARIO_ID else scenario_id


# ============================================================
# 查询接口
# ============================================================

@router.get("/demo/scenarios")
def list_scenarios(user: dict = Depends(get_current_user)):
    """列出演示场景。"""
    with session_scope() as s:
        dcalc.ensure_default_scenario(s)
        from kb.models import DemoScenario
        rows = s.query(DemoScenario).order_by(DemoScenario.id).all()
        return {"items": [
            {
                "scenario_id": r.scenario_id, "name": r.name,
                "description": r.description, "status": r.status,
                "primary_company_ids": dcalc._parse_json(r.primary_company_ids, []),
            }
            for r in rows
        ], "default": DEFAULT_SCENARIO_ID}


@router.get("/demo/state")
def get_demo_state(
    company_id: int = Query(..., description="当前登录企业ID"),
    scenario_id: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
):
    """当前企业演示状态 (基线只读 + 演示增量)。"""
    sid = _resolve_scenario(scenario_id)
    with session_scope() as s:
        _ensure_scenario(s, sid)
        return dcalc.get_demo_state(s, sid, company_id)


@router.get("/demo/events")
def get_demo_events(
    company_id: int | None = Query(default=None),
    scenario_id: str | None = Query(default=None),
    phase: str | None = Query(default=None,
                              description="generate_orders|consume_inventory|..."),
    limit: int = Query(default=100, ge=1, le=500),
    user: dict = Depends(get_current_user),
):
    """演示事件日志 (因果链)。"""
    sid = _resolve_scenario(scenario_id)
    with session_scope() as s:
        _ensure_scenario(s, sid)
        return dcalc.get_demo_events(s, sid, company_id=company_id, limit=limit, phase=phase)


@router.get("/demo/rfqs")
def list_demo_rfqs(
    company_id: int | None = Query(default=None),
    scenario_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
):
    """演示 RFQ 列表。"""
    sid = _resolve_scenario(scenario_id)
    with session_scope() as s:
        _ensure_scenario(s, sid)
        from kb.models import DemoRfq
        q = s.query(DemoRfq).filter_by(scenario_id=sid)
        if company_id is not None:
            q = q.filter(DemoRfq.company_id == company_id)
        if status:
            q = q.filter(DemoRfq.status == status)
        rows = q.order_by(DemoRfq.id.desc()).all()
        return {"items": [dcalc._rfq_dict(r) for r in rows], "total": len(rows)}


@router.get("/demo/rfqs/{rfq_id}/quote-comparison")
def demo_quote_comparison(
    rfq_id: int,
    company_id: int = Query(...),
    scenario_id: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
):
    """演示报价对比视图。"""
    sid = _resolve_scenario(scenario_id)
    with session_scope() as s:
        _ensure_scenario(s, sid)
        return dcalc.quote_comparison(s, sid, company_id, rfq_id)


@router.get("/demo/supplier-view")
def demo_supplier_view(
    company_id: int = Query(..., description="当前登录企业ID (作为供应商)"),
    scenario_id: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
):
    """供应商视角: 当前企业作为候选供应商收到的 demo RFQ + 自己的报价 + 相关事件。

    数据完全来自 demo_rfqs.candidates_json / demo_quotations / demo_events, 不写死。
    """
    sid = _resolve_scenario(scenario_id)
    with session_scope() as s:
        _ensure_scenario(s, sid)
        return dcalc.get_supplier_demo_view(s, sid, company_id)


@router.get("/demo/audit-queue")
def demo_audit_queue(
    company_id: int | None = Query(default=None, description="可选: 按企业过滤"),
    scenario_id: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
):
    """演示只读审核队列: 从 demo events/quotations/states 派生需人工处理的事项。

    来源: no_direct_supplier 事件 / 报价异常 (超目标价 1.5x) / relationship_missing 缺件。
    MVP 只读, 不写回审批状态。
    """
    sid = _resolve_scenario(scenario_id)
    with session_scope() as s:
        _ensure_scenario(s, sid)
        return dcalc.get_demo_audit_queue(s, sid, company_id=company_id)


# ============================================================
# 重置
# ============================================================

@router.post("/demo/scenarios/reset")
def reset_scenario(req: ResetReq, user: dict = Depends(get_current_user)):
    """重置演示场景: 仅删除该 scenario_id 下的演示数据, 不清空基线业务表。"""
    sid = _resolve_scenario(req.scenario_id)
    with session_scope() as s:
        _ensure_scenario(s, sid)
        return dcalc.reset_scenario(s, sid)


# ============================================================
# 动作接口 (仅主视角企业)
# ============================================================

@router.post("/demo/actions/generate-orders")
def action_generate_orders(req: GenerateOrdersReq, user: dict = Depends(get_current_user)):
    """生成演示订单 (联动下游客户/上游供应商/支撑物流)。"""
    _require_primary(req.company_id)
    sid = _resolve_scenario(req.scenario_id)
    with session_scope() as s:
        _ensure_scenario(s, sid)
        return dcalc.generate_orders(
            s, sid, req.company_id, product_id=req.product_id,
            quantity=req.quantity, priority=req.priority,
        )


@router.post("/demo/actions/consume-inventory")
def action_consume_inventory(req: ConsumeInventoryReq, user: dict = Depends(get_current_user)):
    """消耗库存 (写入 demo_inventory_overrides, 不改基线)。"""
    _require_primary(req.company_id)
    sid = _resolve_scenario(req.scenario_id)
    with session_scope() as s:
        _ensure_scenario(s, sid)
        return dcalc.consume_inventory(
            s, sid, req.company_id, part_number=req.part_number, quantity=req.quantity,
        )


@router.post("/demo/actions/recalculate-shortages")
def action_recalculate_shortages(req: RecalculateShortagesReq, user: dict = Depends(get_current_user)):
    """重算演示缺件 (基线需求 + 演示订单 - 演示可用库存)。"""
    _require_primary(req.company_id)
    sid = _resolve_scenario(req.scenario_id)
    with session_scope() as s:
        _ensure_scenario(s, sid)
        return dcalc.recalculate_demo_shortages(s, sid, req.company_id)


@router.post("/demo/actions/generate-rfq")
def action_generate_rfq(req: GenerateRfqReq, user: dict = Depends(get_current_user)):
    """从缺件生成 RFQ; 仅从直接上下游/支撑企业中找候选, 无则提示。"""
    _require_primary(req.company_id)
    sid = _resolve_scenario(req.scenario_id)
    with session_scope() as s:
        _ensure_scenario(s, sid)
        return dcalc.generate_rfq(
            s, sid, req.company_id, part_number=req.part_number,
            shortage_index=req.shortage_index, quantity=req.quantity,
            target_price=req.target_price, lead_time_days=req.lead_time_days,
        )


@router.post("/demo/actions/simulate-quotes")
def action_simulate_quotes(req: SimulateQuotesReq, user: dict = Depends(get_current_user)):
    """模拟候选供应商报价 (合理价格/交期)。"""
    _require_primary(req.company_id)
    sid = _resolve_scenario(req.scenario_id)
    with session_scope() as s:
        _ensure_scenario(s, sid)
        return dcalc.simulate_quotes(s, sid, req.company_id, rfq_id=req.rfq_id)


@router.post("/demo/actions/execute-replenishment")
def action_execute_replenishment(req: ExecuteReplenishmentReq, user: dict = Depends(get_current_user)):
    """选择报价并执行补货入库 (联动供应商确认/物流运输)。"""
    _require_primary(req.company_id)
    sid = _resolve_scenario(req.scenario_id)
    with session_scope() as s:
        _ensure_scenario(s, sid)
        return dcalc.execute_replenishment(
            s, sid, req.company_id, rfq_id=req.rfq_id,
            supplier_company_id=req.supplier_company_id,
        )


@router.post("/demo/actions/select-alternative")
def action_select_alternative(req: SelectAlternativeReq, user: dict = Depends(get_current_user)):
    """为缺件选用替代料来源 (仅允许直接关系企业)。"""
    _require_primary(req.company_id)
    sid = _resolve_scenario(req.scenario_id)
    with session_scope() as s:
        _ensure_scenario(s, sid)
        return dcalc.select_alternative(
            s, sid, req.company_id, part_number=req.part_number,
            alternative_supplier_company_id=req.alternative_supplier_company_id,
            quantity=req.quantity,
        )
