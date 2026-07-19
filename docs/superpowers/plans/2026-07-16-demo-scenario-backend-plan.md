# 演示场景沙盘后端 开发计划

- **创建日期：** 2026-07-16
- **分支：** `codex/demo-scenario-backend`
- **worktree：** `D:\Project\project mvp\MatchForge-demo-scenario-backend`
- **基线：** `main` (commit `f9c9508`)

---

## 1. 目标

实现"演示场景沙盘后端"，支持 6 家演示主视角企业登录后，通过悬浮演示控制台手动推进运营数据变化。

### 核心约束
1. 6 家演示公司（9001-9006）是可登录主视角企业。
2. 其他约 30 家企业是产业链环境企业（候选供应商/替代料来源/客户需求来源）。
3. 演示控制台只能操作当前登录公司。
4. 操作当前公司时，相关直接上下游/支撑企业按因果关系同步产生合理变化。
5. RFQ 候选供应商仅允许当前企业的直接上下游/支撑关系企业参与。
6. 若直接关系中无合适供应商，明确提示"无可用直接关系供应商，需要先建立合作关系/人工审核"，不自动建立关系，不推荐非直接企业。
7. 原始基线数据不能被污染（基线业务表只读）。
8. 不复制整库，不清空业务表。
9. 支持随时重置整个演示场景。

---

## 2. 设计方案：场景隔离 + 增量覆盖

### 2.1 核心原则
- 所有演示变化（订单/库存/RFQ/报价/事件/动作日志）都带 `scenario_id`（默认 `default_mvp_demo`）。
- 基线业务表（`kb_production_orders` / `kb_inventory_items` / `kb_rfqs` / `kb_quotations` / `kb_shortages` ...）**只读**，不被污染。
- 演示可用库存 = `baseline_on_hand - baseline_reserved - consumed_qty + replenished_qty`（消耗/补货记录在 `demo_inventory_overrides`，不改 `kb_inventory_items`）。
- 演示缺件 = (基线需求 + 演示订单需求) × BOM − 演示可用库存（不写入 `kb_shortages`，缓存在 `demo_company_states`）。
- 演示 RFQ 全链路使用 `demo_rfqs` / `demo_quotations` 场景内表，不写入 `kb_rfqs` / `kb_quotations`。
- 重置场景只删除该 `scenario_id` 下的演示数据，不触碰基线业务表。

### 2.2 新增表/模型（8 个，`kb/models.py` #20-27）
| # | 模型 | 表名 | 职责 |
|---|------|------|------|
| 20 | DemoScenario | demo_scenarios | 场景注册（scenario_id/name/status/主视角企业） |
| 21 | DemoEvent | demo_events | 事件日志（因果链 parent_event_id + 联动企业） |
| 22 | DemoActionLog | demo_action_logs | 动作执行审计（请求/结果/事件ID） |
| 23 | DemoCompanyState | demo_company_states | 企业状态快照（基线+演示增量聚合） |
| 24 | DemoInventoryOverride | demo_inventory_overrides | 库存增量（consumed/replenished） |
| 25 | DemoOrder | demo_orders | 演示生成订单（场景内） |
| 26 | DemoRfq | demo_rfqs | 演示询价单（candidates_json 存直接关系候选） |
| 27 | DemoQuotation | demo_quotations | 演示供应商报价 |

迁移脚本：`database/migrations/05_demo_scenario.sql`（非破坏式 CREATE TABLE IF NOT EXISTS + reset/rollback 注释）。

### 2.3 新增接口（13 个，`api/routers/demo.py`）
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /demo/scenarios | 场景列表 |
| GET | /demo/state | 当前企业演示状态（基线+增量） |
| GET | /demo/events | 事件日志（因果链，可按企业/阶段过滤） |
| GET | /demo/rfqs | 演示 RFQ 列表 |
| GET | /demo/rfqs/{id}/quote-comparison | 报价对比 |
| POST | /demo/scenarios/reset | 重置场景（仅清演示数据） |
| POST | /demo/actions/generate-orders | 生成订单（联动下游/上游/支撑） |
| POST | /demo/actions/consume-inventory | 消耗库存（写 demo override） |
| POST | /demo/actions/recalculate-shortages | 重算演示缺件 |
| POST | /demo/actions/generate-rfq | 从缺件生成 RFQ（仅直接关系候选） |
| POST | /demo/actions/simulate-quotes | 模拟候选供应商报价 |
| POST | /demo/actions/execute-replenishment | 选择报价并补货入库 |
| POST | /demo/actions/select-alternative | 选用替代料来源（仅直接关系） |

### 2.4 分阶段按钮 + 阶段内自动联动
采用"分阶段按钮 + 每阶段内部自动联动"方案，整体流程：
1. `generate-orders` → 新增订单（联动：下游收到需求 / 上游预见采购 / 支撑生成物流计划）
2. `consume-inventory` → 消耗库存（联动：上游收到消耗信号 / 支撑库内移动）
3. `recalculate-shortages` → 重算缺件（联动：直接上游收到缺件信号 / 无直接供应商标记）
4. `generate-rfq` → 缺件生成 RFQ（联动：候选供应商收到 RFQ；无候选则提示）
5. `simulate-quotes` → 模拟报价（联动：供应商报价事件）
6. `execute-replenishment` → 选择报价补货（联动：供应商确认订单 / 支撑生成运输任务）
7. `select-alternative` → 替代料（联动：替代供应商提供替代料）

### 2.5 因果链示例（事件日志）
```
鼎云新增订单 DEMO-ORD-2026-0001
  ├─ 星河收到 鼎云 订单需求          (联动: 下游)
  ├─ 创捷预计收到 鼎云 采购需求      (联动: 直接上游)
  └─ 远达生成出/入库计划            (联动: 支撑)
鼎云消耗 PCBA 库存 200片
鼎云触发缺件 PCBA 缺口 760片
鼎云生成 RFQ DEMO-RFQ-2026-0001
  └─ 创捷收到 RFQ DEMO-RFQ-2026-0001 (联动: 直接上游候选)
创捷报价 PCBA 单价 380 交期 15天
鼎云选定 创捷 报价, 执行补货 760片
  ├─ 创捷确认订单 PCBA 760片        (联动: 供应商)
  └─ 远达生成运输任务 PCBA 760片    (联动: 支撑物流)
```

---

## 3. 待办与进度

### 已完成 ✅
- [x] 探索项目结构（models/api/migrations/tests/plans）
- [x] 创建 worktree + 分支 `codex/demo-scenario-backend`
- [x] 新增 8 个 demo 模型 + 迁移脚本 `05_demo_scenario.sql`
- [x] 实现 `kb/demo_calc.py` 核心服务（场景管理 + 缺件计算 + 7 个动作 + 因果链事件）
- [x] 实现 `api/routers/demo.py`（13 个接口）+ 注册到 `api/main.py`
- [x] 实现种子脚本 `scripts/seed_demo_scenario.py`
- [x] 编写测试 `tests/test_demo_scenario.py`（23 个用例，全部通过）
- [x] 运行核心测试（phase1 15 + phase2 16 + rfq 14 = 45 全过，无回归）
- [x] 前端 `npm run build` 通过（vue-tsc 类型检查 + vite build）

### 未完成 / 风险 ⚠️
- [ ] 前端控制台 UI 未实现（本分支仅后端；前端在 `codex/demo-scenario-frontend` 分支）
- [ ] 真实 ~30 家环境企业的产业链关系未在本分支扩展种子（当前 6 家企业链路已足够演示全部流程与"无直接供应商"场景）
- [ ] MySQL 迁移脚本 `05_demo_scenario.sql` 已提供但未在干净 MySQL 上执行验证（SQLite 开发库由 `init_db()` 自动建表，测试已通过）
- [ ] langgraph 冷导入仍慢（~150s/会话，已知坑，非本分支引入）

### 当前风险
1. **候选供应商匹配为启发式**：基于 segment 关键词 + 直接关系 product_scope 匹配；对非标准品类可能漏配。MVP 演示场景（6 家电脑制造链）覆盖充分。
2. **demo_company_states 为缓存**：每次动作后刷新，`get_demo_state` 也会实时重算并刷新，口径一致。
3. **报价价格为确定性生成**：基于零件号/品类基准价 + 供应商段位浮动因子，不随机到离谱，但非真实市场价。

---

## 4. 测试矩阵

| 用例 | 覆盖点 | 状态 |
|------|--------|------|
| test_demo_scenarios / test_demo_state / test_demo_events_empty | 查询接口 | ✅ |
| test_generate_orders (+联动事件 +基线不污染) | 生成订单 | ✅ |
| test_generate_orders_rejects_non_primary | 非主视角企业拒绝 | ✅ |
| test_consume_inventory (+override +基线不变) | 消耗库存 | ✅ |
| test_consume_inventory_auto_pick | 自动选零件 | ✅ |
| test_recalculate_shortages | 重算缺件 | ✅ |
| test_recalculate_after_order_increases_demand | 演示订单推高需求 | ✅ |
| test_generate_rfq_with_direct_supplier | 直接关系候选 | ✅ |
| test_generate_rfq_no_direct_supplier | 无直接供应商提示 | ✅ |
| test_generate_rfq_action_log_status | action_log 状态 | ✅ |
| test_simulate_quotes (+合理价格) | 模拟报价 | ✅ |
| test_simulate_quotes_no_rfq | 无 RFQ 兜底 | ✅ |
| test_execute_replenishment (+关闭RFQ +远达运输) | 补货入库 | ✅ |
| test_execute_replenishment_resolves_shortage | 入库后缺件消除 | ✅ |
| test_select_alternative_rejects_non_direct | 非直接关系拒绝 | ✅ |
| test_select_alternative_with_direct | 直接关系替代 | ✅ |
| test_select_alternative_no_direct | 无直接替代提示 | ✅ |
| test_reset_restores_baseline | 重置恢复基线 | ✅ |
| test_baseline_tables_unpolluted | 基线业务表零污染 | ✅ |
| test_full_rfq_chain | 完整主链路打通 | ✅ |

---

## 5. 下一步建议
1. 前端 `codex/demo-scenario-frontend` 分支接入 `/api/v1/demo/*` 接口，实现悬浮控制台 UI。
2. 扩展种子：为 ~30 家环境企业补充 `kb_company_relationships`，使更多候选供应商/客户参与（仍受直接关系限制）。
3. 在干净 MySQL 上执行 `05_demo_scenario.sql` 验证（SQLite 已由测试覆盖）。
4. 可选：为 `demo_events` 增加因果链可视化（树形/时间线）接口。
