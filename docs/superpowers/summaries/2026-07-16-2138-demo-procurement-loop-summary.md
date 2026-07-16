# 演示沙盘闭环增强总结 (demo-procurement-loop)

**生成时间**: 2026-07-16 21:38
**实施 AI**: Claude Code (glm-5-2-260617)
**分支**: main (working tree, 未提交)
**前置**: demo-state-merge-dashboard (2026-07-16 20:20)

---

## 1. 问题

上一阶段完成 demo 沙盘数据与驾驶舱统计打通 (订单/缺件/动作合并展示), 但 demo 模式下的主线页面 (缺件与采购 / 供应商工作台 / 供应商线索 / 审核管理) 仍调用真实业务接口, 未走 demo action 闭环:
- ShortageProcurementView 在 demo 模式调真实 createRfq/sendRfq/recalculateShortages, 看不到 demo RFQ。
- SupplierDashboard/SupplierLeads 调真实 /suppliers/{id}/leads, 看不到 demo RFQ。
- P7AdminAudit 调真实审核队列, 看不到 demo 派生审核项。
- DemoConsole 执行动作后无结果反馈。
- simulate_quotes 非幂等, 重复执行产生重复报价行。
- 无供应商视角接口, 无 demo 审核队列接口。

## 2. 修改文件清单

| 文件 | 类型 | 改动 |
|---|---|---|
| `kb/demo_calc.py` | 修改 | `simulate_quotes` 幂等 (已有报价原地刷新, uq_demo_quote_supplier 保证唯一, 不重复写事件); 新增 `get_supplier_demo_view` (供应商视角: candidates_json 含本企业的 demo RFQ + 自己的报价 + 相关事件); 新增 `get_demo_audit_queue` (从 no_direct_supplier 事件 + 超目标价 1.5x 报价派生只读审核队列); 移除冗余 relationship_missing 派生源 (已由 no_direct_supplier 事件覆盖)。 |
| `api/routers/demo.py` | 修改 | 新增 GET /demo/supplier-view, GET /demo/audit-queue; 更新路由文档。 |
| `web/src/api/demo.ts` | 修改 | 新增 DemoRfqRecord/DemoRfqCandidate/DemoQuotationRecord/DemoQuoteComparison/DemoSupplierRfqItem/DemoSupplierView/DemoAuditItem/DemoAuditQueue 类型; 新增 getDemoRfqs/getDemoSupplierView/getDemoQuoteComparison/getDemoAuditQueue; action 函数支持可选参数 (part_number/rfq_id/supplier_company_id/quantity/target_price/lead_time_days)。 |
| `web/src/composables/useDemo.ts` | 新增 | 统一 demo 模式 composable: isDemo 判定 + demoRfqs/supplierView/auditQueue/comparison 数据 + 动作执行 (generateRfq/simulateQuotes/executeReplenishment/recalculateShortages) + lastResult/actionError + onDemoRefresh 联动。 |
| `web/src/components/demo/DemoConsole.vue` | 修改 | 动作后显示结果摘要 (RFQ 编号 / no_direct_supplier / 缺件数 / 报价数 / 补货量), 新增 .demo-console__result 样式。 |
| `web/src/views/ShortageProcurementView.vue` | 修改 | demo 模式分支: 调 demo action (generateRfq/simulateQuotes/executeReplenishment/recalculateShortages), 显示 demo RFQ 列表 + 报价对比 + 模拟报价/执行补货按钮 + no_direct_supplier 提示 + 演示沙盘标签; 真实模式不变。 |
| `web/src/views/supplier/SupplierDashboard.vue` | 修改 | demo 模式取 supplierView, 统计/最近线索从 demo RFQ 派生; 真实模式不变。 |
| `web/src/views/supplier/SupplierLeads.vue` | 修改 | demo 模式映射 demo RFQ 为线索, 显示我的报价/中标状态, 报价按钮提示"由采购方模拟报价统一生成"; 真实模式不变。 |
| `web/src/views/P7AdminAudit.vue` | 修改 | demo 模式取 auditQueue, 只读 (不显示通过/驳回), 显示 no_direct_supplier/quotation_anomaly; 真实模式不变。 |
| `tests/test_demo_scenario.py` | 修改 | 新增 10 个测试 (见下)。 |
| `docs/superpowers/plans/2026-07-16-demo-procurement-loop-plan.md` | 新增 | 开发计划 |
| `docs/superpowers/summaries/2026-07-16-2138-demo-procurement-loop-summary.md` | 新增 | 本总结 |

## 3. 是否发现并移除了写死逻辑

**未发现新增写死逻辑。** 现有 demo_calc.py 的定价/交期均为确定性规则 (基于 part_number/品类/segment/企业ID), 输入来自 DB (BOM/库存/订单/关系), 符合"确定性算法 + DB 输入"要求。

**移除的冗余**: `get_demo_audit_queue` 原计划从 demo_company_states 派生 relationship_missing 审核项, 但该语义已由 no_direct_supplier 事件覆盖 (recalculate_shortages/generate_rfq 在发现首选供应商无直接关系时即写事件)。移除后审核队列仅来自 demo events + demo quotations, reset 后随演示数据清空, 不残留基线派生项。

**修复的非幂等**: `simulate_quotes` 原每次调用都新增 DemoQuotation 行; 现已改为已有报价原地刷新 (价格随 target_price/因子更新, 不新增行, 不重复写 quote_received 事件), 由 DB 唯一约束 uq_demo_quote_supplier 保证。

## 4. demo 动态生成规则说明

所有 demo 数据基于当前 DB + scenario 状态动态计算, 不写死:

- **缺件**: (基线需求 + demo 订单需求) × BOM 用量 - 演示可用库存 (baseline - consumed + replenished)。来源: kb_production_orders + kb_forecasts + demo_orders + kb_inventory_items + demo_inventory_overrides + product_bom_items。
- **RFQ 候选供应商**: 仅从当前企业的直接上下游/支撑关系 (kb_company_relationships) 中, 按 segment 品类关键词 + 关系 product_scope + 伙伴 typical_products 匹配。首选供应商若为直接关系则置顶 (match_score 0.95, 其他 0.7)。无直接关系候选 -> no_direct_supplier, 不自动建立关系。
- **报价单价**: RFQ 目标价 × 供应商因子 (segment: 芯片1.02/PCBA0.98/被动0.95/分销1.08 + 企业ID尾数微调), 非固定同一组。不同供应商因子不同 -> 报价不同。
- **报价交期**: 供应商 segment 典型交期中值 (芯片28/PCBA16/被动11/分销5天)。
- **补货量**: RFQ 数量 (max(1, rfq.quantity))。
- **供应商视角 RFQ**: demo_rfqs.candidates_json 含本企业 ID 的行 + demo_quotations (本企业报价) + demo_events (company_id 或 linked_company_id = 本企业)。
- **审核队列**: demo_events (event_type=no_direct_supplier) + demo_quotations (unit_price > target_price × 1.5)。

## 5. 数据落库说明

所有 demo 变更写入 demo_* 表, 带 scenario_id (default_mvp_demo), 不触碰基线业务表:

| 表 | 写入动作 |
|---|---|
| demo_orders | generate-orders |
| demo_inventory_overrides | consume-inventory / execute-replenishment / select-alternative |
| demo_rfqs | generate-rfq / select-alternative |
| demo_quotations | simulate-quotes (幂等刷新) / select-alternative |
| demo_events | 所有动作 (因果链 parent_event_id) |
| demo_action_logs | 所有动作 (request/result/event_ids) |
| demo_company_states | 每次动作后刷新缓存 |

reset_scenario 仅 DELETE 该 scenario_id 下的 demo_* 行, 不动 kb_production_orders/kb_inventory_items/kb_rfqs/kb_quotations。

## 6. 测试与 build 结果

### 后端测试
```
pytest tests/test_demo_scenario.py tests/test_enterprise_phase1.py tests/test_enterprise_phase2.py tests/test_rfq_supplier_loop.py
=> 78 passed (33 demo + 45 enterprise/rfq), 1027 warnings in 61.05s
```
新增 10 个 demo 测试:
- test_rfq_candidates_not_hardcoded
- test_quotation_prices_not_hardcoded
- test_simulate_quotes_idempotent
- test_supplier_view_sees_demo_rfq
- test_supplier_view_excludes_non_candidate
- test_audit_queue_no_direct_supplier
- test_audit_queue_empty_after_reset
- test_audit_queue_quotation_anomaly
- test_reset_clears_supplier_view_and_rfqs
- test_demo_endpoints_require_auth

### 前端 build
```
cd web && npm run build
> vue-tsc -b && vite build
✓ built in 4.00s
```
TypeScript 类型检查 (含新 Demo 类型) + Vite 打包均通过。

### 端到端运行时验证 (TestClient, demo-token, 鼎云 9003)
```
1. 初始: demo_orders=0, shortages=3
2. 生成订单: DEMO-ORD-2026-0001, 4事件, active=1
3. 重算缺件: shortage=4, no_direct=3
4. 动态缺件: CPU-I7-13700(缺口980,critical) / PCBA(缺口960,critical) / DDR5(缺口300,medium)
5. 生成RFQ(PCBA): DEMO-RFQ-2026-0001, 候选=2 (创捷9002分0.95, 星河9005分0.7, 均直接关系)
6. 模拟报价: 2家 (创捷¥380交期15天, 星河¥418交期5天), 最低¥380
6b. 幂等: requote=True, 报价数仍=2 (无重复)
7. 执行补货: 补货960, 缺件 4->3, RFQ已关闭
8. 供应商视角(创捷9002): 收到RFQ=1, 已报价=是
9. 无直接供应商(CPU): no_direct_supplier=True, "需要先建立合作关系/人工审核"
10. 审核队列: 4项 (3 no_direct_supplier + 1 quotation_anomaly 因低目标价)
11. 重置: 订单=0, RFQ=0, 供应商RFQ=0, 审核项=0 (全归零)
12. 基线未污染: kb_production_orders 无 DEMO-ORD, kb_rfqs 无 DEMO-RFQ
```

## 7. 未验证项

| 项 | 原因 |
|---|---|
| 浏览器端 Vue 运行时渲染 | 未启动前端 dev server + 后端联调; 仅 build + TestClient 数据契约验证。类型安全 + 数据契约已验证, 预期渲染正确。 |
| 真实账号登录不走 demo 合并 | 已通过 is_demo 隔离逻辑 + test_demo_endpoints_require_auth 验证 (无 token 401, demo 不写基线); 未做真实账号浏览器联调。 |
| 真实 LLM RAG / Milvus | 测试走离线降级; 与本次改动无关。 |
| tests/test_auth_mysql.py | 文件不存在 (历史已知)。 |

## 8. 下一步建议

1. **提交**: `git add -A && git commit -m "feat(demo): procurement loop closure (supplier view + audit queue + idempotent quotes)"`, 建议分支 codex/demo-procurement-loop -> PR to main。
2. **浏览器联调**: 启动后端 + 前端 dev, 演示账号登录鼎云整机, 逐项验证验收标准 1-11 的前端渲染。
3. **供应商手动报价**: 当前 demo 模式供应商视角只读 (报价由采购方 simulate-quotes 统一生成); 若需供应商手动报价, 可新增 /demo/actions/supplier-quote 接口。
4. **审核闭环**: 当前 demo 审核队列只读; 若需审批, 可给 demo audit items 加 reviewed 状态 + /demo/audit-queue/{id}/review 接口。
5. **datetime.utcnow 迁移**: 仍有大量 DeprecationWarning, 建议后续批量替换 datetime.now(timezone.utc)。
