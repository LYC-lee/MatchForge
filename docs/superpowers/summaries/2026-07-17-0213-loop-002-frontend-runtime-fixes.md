# MatchForge Loop-002 Summary - QA P1 前端运行时修复

- **Time:** 2026-07-17 02:13 +08:00
- **Role:** Development Loop AI (loop-002)
- **Goal:** QA 01:24 的 2 个 P1 前端运行时问题: `/products-bom` 的 `toLocaleString()` 空值崩溃 + `/admin/audit` 路由未挂载(redirect 到 knowledge)。
- **Branch:** `codex/loop-002-frontend-runtime-fixes`
- **Commit:** `46626fc`
- **Base:** `origin/codex/loop-001-register-identity` (`3c023a8`) -- **stacked**(见第 7 节风险)
- **Ready 状态:** ready (浏览器验收移交 Codex QA; 无 FE 单测框架, 以 build + QA Playwright smoke 为回归)

## 1. 修改文件清单

- `web/src/views/ProductsBomView.vue` - 第 160 行 `part.required_qty.toLocaleString()` 空值崩溃兜底
- `web/src/router/index.ts` - `/admin/audit` 由 redirect 改为挂载 `P7AdminAudit.vue`

## 2. 修改说明

**P1-1 products-bom 崩溃:** QA 报 `Cannot read properties of undefined (reading 'toLocaleString')`。`ProductsBomView.vue:160` 对 `part.required_qty` 直接 `.toLocaleString()`, 当 BOM item 的 `required_qty` 为 undefined 时崩溃。改为 `part.required_qty?.toLocaleString() || '-'`, 与同文件 `safety_stock_qty`(161 行) / `monthly_capacity`(130 行) 的兜底模式一致。QA 报告的行号 317:44 是 vite sourcemap 偏移, 实际源码为 160 行。

**P1-2 /admin/audit 路由:** `router/index.ts:26` 将 `/admin/audit` redirect 到 `/admin/knowledge`, 导致审核页 `P7AdminAudit.vue` 不可达, no_direct_supplier/异常报价审核闭环无法验收。改为 `component: () => import('@/views/P7AdminAudit.vue')`, meta `{ requiresAuth: true, title: '审核管理' }`, 与其他鉴权路由一致。

## 3. 数据变更说明

**无数据变更。** 纯前端(template + 路由配置)修改, 不涉及数据库/seed/migration。

## 4. 测试与 Build 结果

- **前端 build:** `npm run build` 通过 (`vue-tsc -b && vite build`, ✓ built in 2.54s)。build 同时验证: P7AdminAudit.vue 导入解析成功 + template 改动类型正确。
- **后端:** 本轮**无后端改动**。stacked base(loop-01)后端与已验证态一致; 跑 `tests/test_register_identity.py` 4/4 通过(24.55s)确认 stacked base 绿。
- **全量后端 pytest:** 未重跑(本轮无后端改动, loop-001 已验证 229 过/16 预存失败)。

## 5. 浏览器验收结果

**未做浏览器运行时验收, 明确移交 Codex QA 验收。**

无前端单测框架(vitest/@vue/test-utils 未安装, 无现存 FE 测试), 引入属过度工程化。回归覆盖以 QA Playwright smoke 为准, 建议重点验收:
- `/products-bom` 展开产品 BOM, 含 `required_qty` 缺失的 item 不再崩溃, 显示 `-`
- `/admin/audit` 直接可达, 展示审核队列(no_direct_supplier / 报价异常项), 不再 redirect 到知识库页
- demo 登录各企业访问上述页面无回归

## 6. 未验证项

- 浏览器运行时(移交 QA)。
- `P7AdminAudit.vue` 页面实际内容渲染(路由已挂载, 但页面内数据/权限/只读态未浏览器验证)。
- QA 01:24 余 2 个 P1 未触及: 供应商工作台"正在拉取"缺内容(#3)、9004 远达制造语义(#4)。

## 7. 风险

1. **stacked 分支:** loop-002 基于 `codex/loop-001-register-identity`(未合并), 非 `origin/main`。原因: origin/main 仍含 QA P0 build 失败(loop-01 修了但未合并), 直接从 main 分支无法通过 build 验证; stack 复用 loop-01 的 build 修复, 避免重复改动与合并冲突。**integration 必须先合并 loop-001, 再合并 loop-002**(loop-002 是 loop-001 的超集 + 2 个 P1 修复)。
2. **栈增长风险:** integration loop 未调度, dev loop 持续 stack 会使分支链变长。强烈建议尽快跑 integration 合并 loop-01+loop-02(共解 P0 + 3 P1)。
3. **无 FE 单测框架:** 本轮 2 个 bug 修复无单测防回归, 依赖 QA Playwright smoke。QA 已建议增 Playwright smoke(6 家登录 + action + reset baseline), 建议后续轮次落实。
4. **P7AdminAudit 页面内容未验:** 路由挂载只解决"可达", 页面内审核队列数据/权限/只读态需 QA 浏览器验证。

## 8. 下一步建议

1. **Codex QA 浏览器验收**本轮(products-bom 不崩溃 + /admin/audit 可达)。
2. **integration loop 优先合并** loop-001 + loop-002 到 main(解除 P0 build + 3 个 P1), 阻止栈增长。
3. **下一轮 dev loop** 候选(择一):
   - QA P1 #4 / 待办 #3: 9004 远达物流语义(按 `company_segment`/`company_role` 切换服务能力/运力/履约风险标签, 而非制造 BOM 模板) -- 演示影响大, 跨多视图, 可能需拆 2 轮。
   - loop-001 发现的预存 P1: auth login/refresh/me 路由 `user.name`/`user.company` 缺列(TypeError) -- 小步, 解锁真实 auth。
   - QA P1 #3 / 待办 #6: 供应商工作台"正在拉取"空状态语义。
4. 若 integration 仍未跑, 下一轮 stack on loop-002, 并再次强调 integration 优先。

## 9. 元信息

- **branch:** `codex/loop-002-frontend-runtime-fixes`
- **commit:** `46626fc`
- **base:** `codex/loop-001-register-identity` (`3c023a8`), stacked
- **worktree:** `D:/Project/project mvp/MatchForge-loop-002-frontend-runtime-fixes`
- **ready:** yes(目标完成 + build 过 + 后端 stacked base 绿 + 浏览器验收移交 QA; 解除 QA 01:24 的 P1-1 与 P1-2)
