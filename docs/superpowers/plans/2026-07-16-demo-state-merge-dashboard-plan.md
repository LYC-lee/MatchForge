# 演示沙盘数据与经营驾驶舱打通计划 (demo-state-merge-dashboard)

> 目标: 让演示账号下的经营驾驶舱真实反映 demo scenario 的变化。点击悬浮控制台按钮后, 驾驶舱卡片/订单列表/缺件风险/推荐动作随沙盘数据刷新。

## 1. 问题根因

- 悬浮控制台 `DemoConsole` 每次动作后 `emitDemoRefresh()`; `useDashboard` 已监听 `onDemoRefresh` 并重新拉取。
- 但 `useDashboard.fetchDashboard` 只拉 `/companies/{id}/dashboard` (基线) + `/orders` + `/forecasts`, **没有拉 `/demo/state`**, 也未合并 `demo_orders` / `demo_shortages`。
- 后端 `/demo/state` 已返回 `demo_orders` / `demo_shortages` / `demo_rfqs`, 但 `demo_orders` 明细字段不足 (缺 `id` / `product_id` / `product_model` / `due_date` / `customer_company_id`), 无法直接映射到 `DashboardOrder`。
- 结果: 演示订单写入 `demo_orders` 表成功 (事件日志可见 order_created), 但首页"待交付订单"不增加。

## 2. 策略 (前端最小闭环 + 后端小范围补字段)

| 层 | 决策 |
|---|---|
| 后端 | 仅在 `_compute_company_state` 给 `demo_orders` 明细补字段 (id/product_id/product_model/due_date/customer_company_id/unit/created_at) + 新增 `demo_orders_active_count` / `demo_orders_active_quantity` 汇总。**不污染基线表, 不改路由**。 |
| 前端 | `useDashboard` 在 `is_demo` 时额外拉 `getDemoState`, 用 adapter 合并 demo 订单/缺件/动作到 `dashboard` 聚合对象。 |
| 隔离 | 合并只在 `auth.user.is_demo === true` 启用; 真实账号只看基线/业务数据。 |
| 重置 | reset 后 `/demo/state` 返回空演示数据, 合并结果 = 基线, 自动恢复。 |

## 3. 修改清单

### 后端
| 文件 | 改动 |
|---|---|
| `kb/demo_calc.py` | `_compute_company_state`: 构建 product_map, 把 `demo_orders` 列表项补全为可映射 DashboardOrder 的结构; 新增 `demo_orders_active_count` / `demo_orders_active_quantity`。保留原有字段不破坏测试。 |

### 前端
| 文件 | 改动 |
|---|---|
| `web/src/api/demo.ts` | 补齐 `DemoOrderItem` / `DemoShortageItem` / `DemoRfqItem` / `DemoInventoryItem` 类型; `DemoState` 显式化 `demo_orders` / `demo_shortages` / `demo_rfqs` / 汇总字段。 |
| `web/src/api/enterprise.ts` | `DashboardOrder` / `DashboardShortage` / `DashboardAction` 增加 `is_demo?: boolean` 标记字段。 |
| `web/src/composables/useDashboard.ts` | demo 模式下 `fetchDashboard` 追加 `getDemoState`; 新增 `mergeDemoIntoDashboard` 合并 demo 订单/缺件/推荐动作, 重算 `orders_summary` 统计; `onDemoRefresh` 已绑定 `fetchDashboard` (自动重合并)。 |
| `web/src/views/HomeView.vue` | 订单列表行给 `is_demo` 订单加"演示"轻量标签; 卡片/缺件/动作已读合并后的 `dashboard`。 |

## 4. 验收对照

1. 登录演示账号 → 鼎云整机 (9003) ✓ (DEFAULT_DEMO_COMPANY_ID=9003)
2. 初始"待交付订单" = 基线 active_count (demo 数据为空, 合并为 0 增量)
3. 点"生成新订单" → 事件日志 order_created + `/demo/state.demo_orders` +1
4. 驾驶舱"待交付订单" +1 (合并后 active_count = 基线 + demo_orders_active_count)
5. 订单列表出现 demo 订单 (带"演示"标签)
6. 点"重新计算缺件" → demo_shortages 反映新需求 → 缺件风险卡片 + 推荐动作出现 demo 采购动作
7. 点"重置场景" → `/demo/state` 演示数据清空 → 合并结果回到基线
8. 后端测试: test_demo_scenario / test_enterprise_phase1+2 / test_rfq_supplier_loop
9. 前端 build: `cd web && npm run build`

## 5. 约束

- 不把 demo 数据写回 `kb_production_orders` / `kb_inventory_items` 等基线表。
- 不删现有 dashboard / RFQ / auth / RAG 功能。
- 不引入新 mock 固定回答。
- 不破坏真实账号模式 (合并仅 `is_demo` 启用)。
