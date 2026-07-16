# 演示场景沙盘后端 实施总结

- **总结时间：** 2026-07-16 17:10
- **分支名：** `codex/demo-scenario-backend`
- **worktree：** `D:\Project\project mvp\MatchForge-demo-scenario-backend`
- **commit hash：** `604f11d`
- **基线：** `main` (commit `f9c9508`)

---

## 1. 修改文件清单

| 文件 | 类型 | 说明 |
|------|------|------|
| `kb/models.py` | 修改 | 新增 8 个 demo 模型 (#20-27) |
| `api/main.py` | 修改 | 注册 demo 路由 + 更新路由文档注释 |
| `api/routers/demo.py` | 新增 | 13 个 /api/v1/demo/* 接口 |
| `kb/demo_calc.py` | 新增 | 核心服务 (场景/缺件/7动作/因果链事件) |
| `database/migrations/05_demo_scenario.sql` | 新增 | MySQL 迁移 (非破坏式) |
| `scripts/seed_demo_scenario.py` | 新增 | 演示场景种子脚本 |
| `tests/test_demo_scenario.py` | 新增 | 23 个测试用例 |
| `docs/superpowers/plans/2026-07-16-demo-scenario-backend-plan.md` | 新增 | 开发计划 |

未删除/未修改任何现有接口；未触碰前端代码；未清空/删除任何业务表数据。

---

## 2. 新增接口清单 (13 个, 前缀 `/api/v1`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/demo/scenarios` | 场景列表 (含 default_mvp_demo) |
| GET | `/demo/state?company_id=` | 当前企业演示状态 (基线只读 + 演示增量) |
| GET | `/demo/events?company_id=&phase=&limit=` | 事件日志 (因果链, 可过滤) |
| GET | `/demo/rfqs?company_id=&status=` | 演示 RFQ 列表 |
| GET | `/demo/rfqs/{rfq_id}/quote-comparison?company_id=` | 报价对比视图 |
| POST | `/demo/scenarios/reset` | 重置场景 (仅清演示数据, 不动基线) |
| POST | `/demo/actions/generate-orders` | 生成订单 (+联动下游/上游/支撑) |
| POST | `/demo/actions/consume-inventory` | 消耗库存 (写 demo override) |
| POST | `/demo/actions/recalculate-shortages` | 重算演示缺件 |
| POST | `/demo/actions/generate-rfq` | 缺件生成 RFQ (仅直接关系候选) |
| POST | `/demo/actions/simulate-quotes` | 模拟候选供应商报价 |
| POST | `/demo/actions/execute-replenishment` | 选择报价并补货入库 |
| POST | `/demo/actions/select-alternative` | 选用替代料来源 (仅直接关系) |

认证：复用 `get_current_user`，保留 demo token (`kb-demo-user`) / admin token 兼容，不破坏 JWT/MySQL 登录。
动作接口强制 `company_id ∈ {9001..9006}`（6 家主视角企业），非主视角企业返回 400。

---

## 3. 新增表/模型清单 (8 个)

| # | 模型 | 表名 | 关键字段 |
|---|------|------|----------|
| 20 | DemoScenario | demo_scenarios | scenario_id(unique), name, status, primary_company_ids |
| 21 | DemoEvent | demo_events | scenario_id, seq, phase, company_id, linked_company_id, event_type, parent_event_id, payload_json |
| 22 | DemoActionLog | demo_action_logs | scenario_id, company_id, action_type, request_json, result_json, event_ids_json, status |
| 23 | DemoCompanyState | demo_company_states | scenario_id, company_id(unique), is_primary, state_json |
| 24 | DemoInventoryOverride | demo_inventory_overrides | scenario_id, company_id, part_number(unique), baseline_on_hand/reserved, consumed_qty, replenished_qty |
| 25 | DemoOrder | demo_orders | scenario_id, company_id, product_id, order_number(DEMO-ORD-), customer_company_id, quantity |
| 26 | DemoRfq | demo_rfqs | scenario_id, company_id, rfq_number(DEMO-RFQ-), candidates_json, status, selected_supplier_company_id |
| 27 | DemoQuotation | demo_quotations | scenario_id, rfq_id, supplier_company_id(unique w/ rfq), unit_price, lead_time_days |

迁移：`database/migrations/05_demo_scenario.sql`（CREATE TABLE IF NOT EXISTS，含 reset/rollback 注释）。SQLite 开发库由 `init_db()` 自动建表。

---

## 4. 测试结果

### 新增测试 `tests/test_demo_scenario.py`
```
23 passed, 567 warnings in 32.94s
```
覆盖：查询接口 / state / events / reset / 7 个动作 / 直接关系供应商限制 / 无直接供应商提示 / reset 后数据恢复 / 基线业务表零污染 / 完整 RFQ 主链路打通 / 非主视角企业拒绝。

### 核心测试 (无回归)
```
tests/test_enterprise_phase1.py + tests/test_enterprise_phase2.py + tests/test_rfq_supplier_loop.py
45 passed, 244 warnings in 31.74s
```

### 关键验证点
- **基线不污染**：完整演示链路后，`kb_production_orders` / `kb_inventory_items` / `kb_rfqs` / `kb_quotations` 行数与数值均未变（`test_baseline_tables_unpolluted`）。
- **直接关系限制**：RFQ 候选均为直接关系企业（`test_generate_rfq_with_direct_supplier` 逐个断言 `_has_direct_relationship`）。
- **无直接供应商**：鼎云 CPU 缺件（首选华芯 9001 非直接关系）-> `no_direct_supplier` 提示，不自动建关系（`test_generate_rfq_no_direct_supplier`）。
- **主链路打通**：缺件 -> RFQ -> 报价 -> 对比 -> 补货 -> 重算缺件消除（`test_full_rfq_chain`），事件因果链覆盖"触发缺件/生成RFQ/创捷收到RFQ/创捷报价/远达运输任务"。

---

## 5. 前端 build 结果

```
cd web && npm run build
> vue-tsc -b && vite build
✓ built in 3.66s
```
vue-tsc 类型检查 + vite build 均通过。本分支未修改任何前端代码，接口为纯新增，不影响前端现有调用。

---

## 6. 未验证项

1. **干净 MySQL 迁移**：`05_demo_scenario.sql` 未在全新 MySQL 上手动执行；SQLite 开发库由 `init_db()` 自动建表，测试已覆盖表结构与逻辑。MySQL 上 `CREATE TABLE IF NOT EXISTS` 语义与 SQLite 一致，风险低。
2. **~30 家环境企业**：当前仅 6 家演示企业链路有 `kb_company_relationships` 种子；扩展环境企业关系未在本分支完成（6 家已足够演示全部流程与"无直接供应商"场景）。
3. **前端控制台 UI**：本分支仅后端；前端接入在 `codex/demo-scenario-frontend` 分支。
4. **并发**：演示场景为单控制台操作，未做并发锁；多用户同时操作同一场景可能产生事件序号竞争（demo 场景可接受）。
5. **长时运行**：事件日志无自动归档，超长演示可能累积大量 `demo_events`（可随时 reset 清理）。

---

## 7. 风险与下一步建议

### 风险
1. **候选供应商匹配为启发式**：基于 segment 关键词 + 直接关系 product_scope 匹配，对非标准品类可能漏配。MVP 6 家电脑制造链场景覆盖充分。
2. **报价为确定性生成**：基于零件号/品类基准价 + 供应商段位浮动因子，非真实市场价（demo 用途可接受）。
3. **langgraph 冷导入慢**：~150s/会话，已知坑（非本分支引入），影响测试启动速度但不影响功能。
4. **demo_company_states 缓存一致性**：每次动作后刷新，`get_demo_state` 也实时重算并刷新，口径一致；无异步更新。

### 下一步建议
1. 前端 `codex/demo-scenario-frontend` 分支接入 `/api/v1/demo/*`，实现悬浮控制台 UI（分阶段按钮 + 事件时间线）。
2. 扩展种子：为 ~30 家环境企业补充 `kb_company_relationships`，使更多候选供应商/客户参与（仍受直接关系限制，不破坏规则）。
3. 在干净 MySQL 上执行 `05_demo_scenario.sql` 验证。
4. 可选：`demo_events` 因果链树形/时间线可视化接口。
5. 可选：演示场景多实例（多个 scenario_id 并行演示）。

---

## 8. 因果链示例 (事件日志, 鼎云主视角)

```
[generate_orders]
鼎云 新增订单 DEMO-ORD-2026-0001 (台式机 200台, 客户 星河)
  ├─ 星河 收到 鼎云 订单需求              [联动: 下游客户]
  ├─ 创捷 预计收到 鼎云 采购需求 (PCBA)   [联动: 直接上游]
  └─ 远达 生成出/入库计划                [联动: 支撑物流]

[consume_inventory]
鼎云 消耗 PCBA 库存 200片
  └─ 远达 库内移动 PCBA                  [联动: 支撑]

[recalculate_shortages]
鼎云 触发缺件 PCBA 缺口 760片
  └─ (PCBA 首选创捷=直接关系) 创捷 下游缺件 PCBA 待询价  [联动: 直接上游]

[generate_rfq]
鼎云 生成 RFQ DEMO-RFQ-2026-0001 (PCBA 760片, 目标单价 380)
  └─ 创捷 收到 RFQ DEMO-RFQ-2026-0001    [联动: 直接上游候选]

[simulate_quotes]
创捷 报价 PCBA 单价 380 交期 15天        [联动: 供应商]

[execute_replenishment]
鼎云 选定 创捷 报价, 执行补货 760片
  ├─ 创捷 确认订单 PCBA 760片            [联动: 供应商]
  └─ 远达 生成运输任务 PCBA 760片 创捷->鼎云  [联动: 支撑物流]

[recalculate_shortages] (补货后)
-> PCBA 缺件消除 (可用库存恢复至 800)
```

无直接供应商场景（鼎云 CPU 缺件，首选华芯 9001 非直接关系）：
```
[generate_rfq]
鼎云 Intel酷睿i7-13700处理器 无可用直接关系供应商
  (直接上下游/支撑关系中无合适供应商, 需要先建立合作关系/人工审核)
  action_status = no_direct_supplier
```
