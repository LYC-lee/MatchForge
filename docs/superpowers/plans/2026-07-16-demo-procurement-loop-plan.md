# 演示沙盘闭环增强开发计划 (demo-procurement-loop)

**创建时间**: 2026-07-16 21:35
**分支**: main (working tree, 未提交)
**前置**: demo-state-merge-dashboard (驾驶舱合并 demo 订单/缺件/动作)

---

## 目标

让 demo 模式下的缺件采购、RFQ、报价、供应商工作台、审核管理具备接近正常业务的完整闭环。
demo 模式 = "沙盘运行模式" (非 mock): 所有数据基于当前企业 BOM/库存/订单/上下游关系/供应商能力/当前 scenario 状态动态计算, 落库到 demo_* 表, 可重置, 不污染基线。

## 问题清单 (本阶段解决)

1. ShortageProcurementView 在 demo 模式仍调真实业务接口 (createRfq/sendRfq/recalculateShortages), 未走 demo action。
2. SupplierDashboard/SupplierLeads 在 demo 模式调真实 /suppliers/{id}/leads, 看不到 demo RFQ。
3. P7AdminAudit 在 demo 模式调真实审核队列, 看不到 demo 派生审核项。
4. DemoConsole 执行动作后无结果反馈 (不显示 RFQ 编号 / no_direct_supplier 提示)。
5. demo API 客户端函数不接受参数 (part_number/rfq_id 等)。
6. simulate_quotes 非幂等: 重复执行产生重复报价行。
7. 无供应商视角接口 (供应商看不到自己作为候选收到的 demo RFQ)。
8. 无 demo 审核队列接口。

## 实施步骤

### A. 后端 (kb/demo_calc.py + api/routers/demo.py)
- [x] simulate_quotes 幂等: 已有报价时原地刷新 (uq_demo_quote_supplier 保证唯一), 不新增行, 不重复写事件。
- [x] 新增 `get_supplier_demo_view(s, scenario_id, supplier_company_id)`: 返回供应商作为候选收到的 demo RFQ + 自己的报价 + 相关事件。
- [x] 新增 `get_demo_audit_queue(s, scenario_id, company_id)`: 从 demo events (no_direct_supplier) + demo quotations (超目标价 1.5x) 派生只读审核队列。
- [x] 新增路由 GET /demo/supplier-view, GET /demo/audit-queue。

### B. 前端 API 客户端 (web/src/api/demo.ts)
- [x] 扩展 action 函数支持可选参数 (part_number, rfq_id, supplier_company_id, quantity, target_price, lead_time_days)。
- [x] 新增 getDemoRfqs / getDemoSupplierView / getDemoQuoteComparison / getDemoAuditQueue + 完整类型。

### C. 前端 composable (web/src/composables/useDemo.ts)
- [x] 新建 useDemo: 统一 isDemo 判定 + demoRfqs/supplierView/auditQueue/comparison 数据 + 动作执行 (generateRfq/simulateQuotes/executeReplenishment/recalculateShortages) + lastResult/actionError 反馈 + onDemoRefresh 联动。

### D. 前端视图 (demo 模式分支)
- [x] ShortageProcurementView: demo 模式调 demo action, 显示 demo RFQ 列表 + 报价对比 + 模拟报价/执行补货按钮 + no_direct_supplier 提示 + 演示沙盘标签。
- [x] SupplierDashboard: demo 模式取 supplierView, 统计/最近线索从 demo RFQ 派生。
- [x] SupplierLeads: demo 模式映射 demo RFQ 为线索, 显示我的报价/中标状态, 报价按钮提示"由采购方模拟报价统一生成"。
- [x] P7AdminAudit: demo 模式取 auditQueue, 只读 (不显示通过/驳回), 显示 no_direct_supplier/quotation_anomaly。
- [x] DemoConsole: 动作后显示结果摘要 (RFQ 编号 / no_direct_supplier / 缺件数 / 报价数 / 补货量)。

### E. 测试 (tests/test_demo_scenario.py)
- [x] test_rfq_candidates_not_hardcoded (不同企业候选来自各自直接关系)
- [x] test_quotation_prices_not_hardcoded (报价基于目标价×因子, 非固定)
- [x] test_simulate_quotes_idempotent (重复不新增行)
- [x] test_supplier_view_sees_demo_rfq (供应商看到相关 RFQ + 报价)
- [x] test_supplier_view_excludes_non_candidate (非候选看不到)
- [x] test_audit_queue_no_direct_supplier (审核队列含无直接供应商)
- [x] test_audit_queue_empty_after_reset (reset 后审核队列空)
- [x] test_audit_queue_quotation_anomaly (报价异常入队)
- [x] test_reset_clears_supplier_view_and_rfqs (reset 后 RFQ/supplier-view 空)
- [x] test_demo_endpoints_require_auth (无 token 401, demo 不写基线)

## 验收标准 (对照)
1-11: TestClient 端到端验证通过 (见总结文档)
12: 前端 build 通过
13: 后端 78 测试通过 (33 demo + 45 enterprise/rfq)
