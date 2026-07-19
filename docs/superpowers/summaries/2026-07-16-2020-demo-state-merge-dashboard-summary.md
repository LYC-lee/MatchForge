# 演示沙盘数据与经营驾驶舱打通总结 (demo-state-merge-dashboard)

**生成时间**: 2026-07-16 20:20
**实施 AI**: Claude Code (glm-5-2-260617)
**分支**: main (working tree, 未提交)

---

## 1. 问题

演示悬浮控制台点击"生成新订单"后, `/api/v1/demo/actions/generate-orders` 已写入 `demo_orders` 表 (事件日志可见 `order_created`), 但首页经营驾驶舱"待交付订单"不增加。根因: `useDashboard` 只拉 `/companies/{id}/dashboard` 基线, 未合并 `/demo/state` 的演示增量。

## 2. 修改文件清单

| 文件 | 类型 | 改动 |
|---|---|---|
| `kb/demo_calc.py` | 修改 | `_compute_company_state`: 构建 product_map, `demo_orders` 列表项补全 `id`/`product_id`/`product_model`/`customer_company_id`/`due_date`/`unit`/`created_at`; 新增 `demo_orders_active_count` / `demo_orders_active_quantity` 汇总。保留原字段, 不破坏测试。 |
| `web/src/api/demo.ts` | 修改 | 新增 `DemoOrderItem` / `DemoShortageItem` / `DemoRfqItem` / `DemoInventoryItem` / `DemoDirectPartner` 类型; `DemoState` 显式化 `demo_orders` / `demo_shortages` / `demo_rfqs` / 汇总字段。 |
| `web/src/api/enterprise.ts` | 修改 | `DashboardOrder` / `DashboardShortage` / `DashboardAction` 各加 `is_demo?: boolean` 标记。 |
| `web/src/composables/useDashboard.ts` | 修改 | demo 模式 (`auth.user.is_demo`) 下 `fetchDashboard` 追加 `getDemoState`; 新增 `mapDemoOrder` / `mapDemoShortage` / `mapDemoShortageToAction` / `mergeDemoIntoDashboard`: demo 订单置顶并入 `orders_summary.items` 并重算 `active_count`/`total`/`active_total_quantity`/`by_status`/`by_priority`; demo 缺件并入 `shortages.items`; 由 demo 缺件合成 sourcing 推荐动作。`onDemoRefresh` 已绑定 `fetchDashboard` -> 自动重合并。负数 id 区分演示数据。 |
| `web/src/views/HomeView.vue` | 修改 | 订单行给 `is_demo` 订单加"演示"轻量标签; 缺件行/推荐动作行也加演示标识; 新增 `.demo-badge` / `.demo-badge--inline` 样式。卡片/缺件/动作已读合并后的 `dashboard`。 |
| `docs/superpowers/plans/2026-07-16-demo-state-merge-dashboard-plan.md` | 新增 | 开发计划 |
| `docs/superpowers/summaries/2026-07-16-2020-demo-state-merge-dashboard-summary.md` | 新增 | 本总结 |

## 3. 后端改动说明

仅 `_compute_company_state` 一处, 纯读取 `demo_orders` 表 + `dc.get_products` 的 product_map, **不写任何表, 不改路由, 不污染基线**。

`demo_orders` 项由精简 6 字段扩展为 13 字段 (可完整映射 `DashboardOrder`), 并新增两个活跃统计字段供前端直接相加 (避免在前端重复实现 active 状态判定):

```python
"demo_orders_active_count": demo_orders_active_count,        # status in (open|confirmed|in_progress)
"demo_orders_active_quantity": demo_orders_active_quantity,   # 活跃订单 quantity 之和
```

reset 后 `demo_orders` 为空 -> `demo_orders_active_count=0` -> 前端合并增量为 0 -> 自动恢复基线。

## 4. 前端改动说明

**合并流程** (`useDashboard.fetchDashboard`):
1. 并发拉 `/dashboard` + `/orders` + `/forecasts` (基线)
2. `is_demo` 时追加 `getDemoState(companyId)`
3. `mergeDemoIntoDashboard(dash, demo, companyId)` 原地 mutate:
   - 订单: demo 订单置顶 -> `orders_summary.items`; `active_count += demo_orders_active_count`; `total/active_total_quantity/by_status/by_priority` 同步累加
   - 缺件: demo 缺件置顶 -> `shortages.items`
   - 动作: demo `shortage` 类型缺件 -> 合成 sourcing 推荐动作置顶 -> `recommended_actions.items`
4. `orders.value = dash.orders_summary.items` (含 demo 订单)
5. `onDemoRefresh` -> `fetchDashboard` (控制台每次动作后 `emitDemoRefresh` 触发重合并)

**隔离**: 合并只在 `auth.user.is_demo === true` 启用; 真实账号不调 `/demo/state`, 只看基线/业务数据。`getDemoState` 失败时 `console.warn` 并跳过, 不阻断基线驾驶舱。

**UI**: demo 订单/缺件/动作带"演示"标签, 负数 id 避免与基线主键冲突。

## 5. 测试与 build 结果

### 后端测试
```
pytest tests/test_demo_scenario.py
=> 23 passed, 567 warnings in 70.82s

pytest tests/test_enterprise_phase1.py tests/test_enterprise_phase2.py tests/test_rfq_supplier_loop.py
=> 45 passed, 244 warnings in 38.69s
```

### 前端 build
```
cd web && npm run build
> vue-tsc -b && vite build
✓ built in 1.91s
```
TypeScript 类型检查 (含新 `is_demo` 字段 / Demo 子类型) + Vite 打包均通过。

### 端到端运行时验证 (TestClient, demo-token, 鼎云 9003)
```
基线 dashboard: active_count=4, total=5
初始 demo state: demo_orders_active_count=0
生成订单: DEMO-ORD-2026-0001, 事件数=4 (order_created + 下游 + 上游 + 支撑)
合并后 demo state: demo_orders_active_count=1, quantity=200
  demo 订单: product_model=DY-DT-Pro, due_date=2026-08-15, customer_company_id=9005
  -> 前端合并后待交付订单 = 4 + 1 = 5  ✓ 增加
重算缺件: shortage_count 3 -> 4  ✓ 反映 demo 需求
reset 后: demo_orders_active_count=0, demo_shortages_total=3  ✓ 恢复基线
```

## 6. 未验证项

| 项 | 原因 |
|---|---|
| 浏览器端 Vue 运行时渲染 | 未启动前端 dev server + 后端联调; 仅 build + TestClient 数据契约验证。合并逻辑类型安全且数据契约已验证, 预期渲染正确。 |
| 真实 LLM RAG / Milvus | 测试走离线降级; 与本次改动无关。 |
| demo 合并在非 HomeView 页面的刷新 | 控制台在非驾驶舱页操作时 HomeView 未挂载, listener 不触发; 但返回 HomeView 时 `watch immediate` 重新拉取, 数据仍为最新。 |
| `tests/test_auth_mysql.py` | 文件不存在 (历史已知)。 |

## 7. 下一步建议

1. **提交**: `git add -A && git commit -m "feat(demo): merge demo state into dashboard (orders/shortages/actions)"`, 建议分支 `codex/demo-state-merge-dashboard` -> PR to main。
2. **浏览器联调**: 启动后端 `uvicorn api.main:main --port 8000` + 前端 `npm run dev`, 演示账号登录鼎云整机, 逐项验证验收标准 1-8。
3. **可选增强**: demo 订单点击跳转订单详情; demo 缺件"发起 RFQ"直接触发 `/demo/actions/generate-rfq` 而非跳采购页。
4. **datetime.utcnow 迁移**: 仍存在大量 DeprecationWarning, 建议后续批量替换 `datetime.now(timezone.utc)`。
5. **统一 demo token 常量**: 前端 'demo-token' 与后端 KB_DEMO_TOKEN 'kb-demo-user' 仍双字面量。
