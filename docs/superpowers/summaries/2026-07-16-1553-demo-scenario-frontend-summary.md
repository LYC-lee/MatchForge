# MatchForge 演示场景前端总结

## 分支名

codex/demo-scenario-frontend

## commit hash

999a8ac (实现提交；最终分支 HEAD 以 git log 为准)

## 修改文件清单

- web/src/App.vue
- web/src/api/demo.ts
- web/src/components/demo/DemoConsole.vue
- web/src/components/layout/AppHeader.vue
- web/src/composables/useDashboard.ts
- web/src/composables/useDemoRefresh.ts
- web/src/composables/useEnterpriseContext.ts
- web/src/composables/useRfq.ts
- web/src/data/demoCompanies.ts
- web/src/router/index.ts
- web/src/stores/auth.ts
- web/src/views/LoginView.vue
- web/src/views/ProductsBomView.vue
- web/src/views/supplier/SupplierDashboard.vue
- web/src/views/supplier/SupplierLeads.vue
- docs/superpowers/plans/2026-07-16-demo-scenario-frontend-plan.md
- docs/superpowers/summaries/2026-07-16-1553-demo-scenario-frontend-summary.md

## 页面变化清单

- 登录页新增 6 家演示企业选择下拉、快捷企业按钮和“进入演示”入口。
- 登录后侧边栏不再显示企业切换下拉，只展示当前绑定企业、角色、链路环节和数据来源。
- demo 账号下显示右下角悬浮演示控制台，真实账号隐藏。
- 控制台支持阶段按钮和最近事件日志，操作成功后刷新当前页面数据。
- 驾驶舱、产品与 BOM、缺件/RFQ、供应商工作台和线索页接入 demo 刷新信号。

## 接入接口清单

- GET /api/v1/demo/state
- GET /api/v1/demo/events
- POST /api/v1/demo/scenarios/reset
- POST /api/v1/demo/actions/generate-orders
- POST /api/v1/demo/actions/consume-inventory
- POST /api/v1/demo/actions/recalculate-shortages
- POST /api/v1/demo/actions/generate-rfq
- POST /api/v1/demo/actions/simulate-quotes
- POST /api/v1/demo/actions/execute-replenishment
- POST /api/v1/demo/actions/select-alternative

## build 结果

- `cd web && npm run build`: 通过。

## 未验证项

- 未连接后端 demo 分支做按钮级端到端验证。
- 未验证后端最终事件字段与前端兼容字段是否完全一致。
- 未验证真实账号登录响应是否包含 `company_id`。

## 风险与下一步建议

- 后端 demo 接口不可用时，前端会明确提示，不回退为固定假数据。
- 建议后端稳定 demo event schema 后补一次 UI 字段对齐。
- 建议真实认证接口补充企业绑定字段，确保普通账号也固定企业视角。
