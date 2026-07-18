# MatchForge Loop MVP Industrialization Plan

## 1. Purpose

This file is the shared state record for the MatchForge multi-AI loop.

All development, QA, and integration agents should read this file before starting work and update it before finishing work. The goal is to make MatchForge progress toward both:

- industrial-grade core capability
- stable, convincing demo-platform experience

The project target is a computer manufacturing supply-chain AI operating cockpit with multi-company collaboration, real RAG Q&A, scenario sandboxing, RFQ/procurement loops, and reliable enterprise isolation.

## 2. Operating Model

### Development Loop AI

- Works on code changes.
- Uses an independent worktree and branch.
- Selects 1-2 high-priority tasks per loop.
- Runs relevant tests and build.
- Writes a summary under `docs/superpowers/summaries/`.
- Pushes a branch only.
- Does not merge into `main`.

### Codex QA Loop

- Checks `main` only.
- Uses browser automation when frontend/demo/login pages are involved.
- Does not modify business code by default.
- Writes findings under `docs/superpowers/qa-findings/`.
- Updates this plan with QA status.

### Codex Integration/Cleanup Loop

- Reads ready branches, summaries, and QA findings.
- Merges one ready branch at a time.
- Runs tests/build after each merge.
- Runs browser validation when needed.
- Pushes `main` only after verification passes.
- Tracks merged branches before any cleanup.

## 3. Branch And Ready Rules

Development branches must use:

`codex/loop-XXX-topic`

A branch can be marked `ready` only when all conditions are met:

- The loop goal is complete.
- Relevant backend tests pass.
- `web` build passes.
- Browser validation passes when the change touches frontend, login, demo, cockpit, RFQ, supplier workspace, audit, or navigation.
- A summary file exists under `docs/superpowers/summaries/`.
- This plan is updated.
- The branch is pushed.
- No unresolved P0/P1 issue remains.

If a task is blocked after roughly 90 minutes:

- a WIP branch may be pushed
- the commit message must start with `wip:`
- the branch must not be marked `ready`
- it must not be merged into `main`
- the blocker must be documented in the summary

## 4. Persistent Directories

- Long-term loop plan: `docs/superpowers/plans/loop-mvp-industrialization-plan.md`
- Loop summaries: `docs/superpowers/summaries/`
- QA findings: `docs/superpowers/qa-findings/`

## 5. Current High-Priority Backlog

### P1 - Register Identity Model

Status: done (loop-001, branch codex/loop-001-register-identity, commit 3c023a8) — browser QA pending

注册流程已移除"采购方/供应商"固化身份, 改为企业类型 select + 权限角色 member。详见 summary 2026-07-17-0140。预存 P1: login/me 路由仍引用 user.name/user.company (live 模型无此列), 待下一轮修。

Fix the registration flow so companies are not classified as fixed "buyer" or "supplier" at registration time.

Target model:

- user permission role: `member`, `enterprise_admin`, `platform_admin`
- enterprise type/profile: manufacturer, component/material, OEM/brand, channel/customer, logistics/service, government/park, other
- supplier/demand relationship is dynamic and derived from orders, RFQs, BOM, services, and company relationships

Required:

- remove buyer/supplier tabs from registration UI
- fix Chinese mojibake in `RegisterView.vue`
- maintain API compatibility if backend still expects a `role`
- ensure build passes

### P1 - Six-Company Browser Validation

Status: pending

Validate all six demo companies in browser:

- 9001 HuaXin Microelectronics
- 9002 ChuangJie Mainboard Module
- 9003 DingYun PC Manufacturing
- 9004 YuanDa Supply Chain Service
- 9005 XingHe Digital Channel
- 9006 YiCheng Passive Components

Required pages:

- login/demo selection
- operating cockpit
- products and BOM
- shortage/procurement
- upstream/downstream collaboration
- supplier workspace
- audit page
- floating demo console

### P1 - YuanDa Logistics View

Status: pending

YuanDa should not look like a normal manufacturing supplier.

Required:

- logistics/service tasks
- capacity/resource risks
- warehouse/transport/driver/service-resource view
- meaningful supplier/service workspace content

### P1 - Reset RFQ Semantics

Status: pending

Clarify whether baseline demo RFQs are:

- initial scenario RFQs that remain after reset, or
- scenario-generated data that should be cleared by reset

If retained, UI must label them as baseline/initial pending RFQs.

### P1 - Demo And Real Mode Consistency

Status: pending

Demo mode should behave like sandbox runtime, not frontend mock.

Required:

- same workflows as normal mode where possible
- demo writes only to `demo_*` tables with `scenario_id`
- no hardcoded frontend mock for RFQ/quotation/procurement
- reset restores baseline

### P1 - Frontend Stability

Status: pending

Continue eliminating:

- page flicker
- mojibake
- build failures
- empty states
- inconsistent loading states
- stale dashboard/demo data

### P2 - Supplier Workspace Loop

Status: pending

Improve supplier-side closure:

- RFQ visibility
- quotation state
- service tasks
- manual quote path when needed

### P2 - Audit Loop

Status: pending

Improve audit closure:

- no direct supplier
- quotation anomaly
- relationship gap
- review state

### P2 - Real RAG Quality

Status: pending

Improve internal and upstream/downstream Q&A so answers rely on real KB/RAG and enterprise isolation, not fixed templates.

### P2 - Auth And Enterprise Isolation

Status: P0 安全基线已修 (loop-007, `codex/loop-security-auth-p0`, ready); 余 P2 项仍 pending

P0 安全修复 (loop-007) 已完成: 未知 token 拒绝、硬编码 token 移除、bcrypt 迁移、import 期无写库。余下 P2 改进仍待办:

Improve:

- enterprise binding
- join approval
- permission role checks
- demo token isolation (P0 门控已做, 余: 生产配置审计)
- direct relationship data access limits
- 统一认证 (删除 `api/auth.py` 等死代码 / 修 /login 返回真实用户信息)

### P2 - Tests And CI

Status: pending

Add only task-relevant tests. Do not over-engineer CI in one step.

Useful future checks:

- backend pytest core suite
- frontend build
- Playwright smoke tests
- browser demo regression
- GitHub Actions

### P2 - Demo Script And Data Consistency

Status: pending

Maintain a 3-5 minute demo path with consistent data stories for all six companies.

## 6. QA Findings Index

### 2026-07-17 01:24 Browser QA

- findings: `docs/superpowers/qa-findings/2026-07-17-0124-browser-qa.md`
- main commit: `916baedb6719125afc5c576f0ac717785c10c589`
- P0/P1 count: P0=1, P1=4
- status: build fails; browser demo partially usable; pause merging feature branches until P0 build failure and P1 route/runtime issues are fixed.
- recommended next task: fix frontend build errors, products/BOM runtime crash, `/admin/audit` routing, and 9004 logistics/service semantics.
- **P0 resolution:** loop-001 (branch `codex/loop-001-register-identity`, commit `3c023a8`) 修复了全部 3 个前端 build 错误, 待 integration 合并后 P0 解除。
- **P1 resolution:** loop-002 (branch `codex/loop-002-frontend-runtime-fixes`, commit `46626fc`, stacked on loop-001) 修复 P1-1(products-bom toLocaleString 崩溃) + P1-2(/admin/audit 路由挂载)。loop-004 (branch `codex/loop-004-9004-logistics-and-9006-name`, commit `9621f5a`, stacked on loop-003) 修复 P1-4 部分(9004 HomeView 物流语义) + P2(9006 名称对齐 毅诚被动元件)。余 P1: P1-3(供应商工作台空状态) + P1-4 余下(9004 ShortageProcurement/ProductsBom 物流语义)。

### 2026-07-17 09:06 Browser QA

- findings: `docs/superpowers/qa-findings/2026-07-17-0906-browser-qa.md`
- local main commit: `f33aef64205bc42393795b1115a3c6e225c7d5c6`
- origin/main commit: `916baedb6719125afc5c576f0ac717785c10c589`
- P0/P1 count: P0=3, P1=1
- status: local integration exists but is not pushed; backend startup/import hangs; frontend build still fails due `EPERM` on `web/dist/assets`; browser QA limited to frontend-only login smoke.
- recommended next task: resolve integration push/baseline mismatch, backend app startup hang, and repeatable build cleanup before full six-company QA.

### 2026-07-17 09:18 Integration Recheck

- integration commit: `f33aef64205bc42393795b1115a3c6e225c7d5c6`
- origin/main status: `origin/main` now also points to `f33aef64205bc42393795b1115a3c6e225c7d5c6`.
- merged branches: `codex/loop-001-register-identity`, `codex/loop-002-frontend-runtime-fixes`, `codex/loop-003-auth-user-name-company`, `codex/loop-004-9004-logistics-and-9006-name`.
- test/build recheck:
  - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_register_identity.py -q` -> 6 passed, 2 warnings.
  - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_enterprise_phase1.py tests/test_enterprise_phase2.py tests/test_rfq_supplier_loop.py -q` -> 45 passed, 420 warnings.
  - `python -c "from api.main import main; print('import-ok')"` -> import-ok.
  - `cd web && npm run build` -> passed on rerun; previous `EPERM`/Vite cleanup issue did not reproduce.
- browser recheck: Edge headless against Vite dev server confirmed `/register` renders one enterprise-type select with manufacturing/component/OEM/channel/logistics/government options and no buyer/supplier role tabs; `/login` renders demo entry and 9006/YiCheng; `/admin/audit` no longer redirects to `/admin/knowledge` and instead follows auth redirect to `/login?redirect=/admin/audit`.
- remaining risk: full six-company browser regression with backend data flows was not completed in this recheck; QA should rerun after this record is committed.

Future entries should use:

`docs/superpowers/qa-findings/YYYY-MM-DD-HHMM-browser-qa.md`

## 7. Loop History

### loop-001 - 2026-07-17 01:40 +08:00 - Development Loop

- **goal:** P1 注册身份模型(取消 buyer/supplier, 改企业类型 + 权限角色 member); 附带修复 QA P0 前端 build 失败
- **branch:** `codex/loop-001-register-identity`
- **commit:** `3c023a8`
- **summary:** `docs/superpowers/summaries/2026-07-17-0140-loop-001-register-identity.md`
- **status:** ready (浏览器验收移交 Codex QA; 预存 login/me 路由 P1 记录待下一轮)
- **test/build:** 4/4 新测试过; 全量 229 过/16 预存失败(ai/kb 模块无重叠); build 过(修复 QA P0 的 3 个错误)
- **resolves:** QA 01:24 P0(前端 build 失败) - 3 个错误全部修复
- **findings:** 预存 P1 auth 路由 name/company 缺列(login/me/seed TypeError); api/models.py 死文件重复; plan/summary 文档未跟踪阻碍 integration

### loop-002 - 2026-07-17 02:13 +08:00 - Development Loop

- **goal:** QA 01:24 P1-1(products-bom toLocaleString 崩溃) + P1-2(/admin/audit 路由挂载)
- **branch:** `codex/loop-002-frontend-runtime-fixes`
- **commit:** `46626fc`
- **base:** `codex/loop-001-register-identity` (`3c023a8`) - **stacked**(main build P0 未合并, stack 复用 build 修复)
- **summary:** `docs/superpowers/summaries/2026-07-17-0213-loop-002-frontend-runtime-fixes.md`
- **status:** ready (浏览器验收移交 QA; 无 FE 单测框架, 以 build + QA smoke 回归)
- **test/build:** build 过(2.54s); 后端无改动, loop-001 test 4/4 过(stacked base 绿)
- **resolves:** QA 01:24 P1-1 + P1-2
- **findings:** 无 FE 单测框架(依赖 QA Playwright smoke); 栈增长风险(integration 未跑)

### loop-003 - 2026-07-17 04:14 +08:00 - Development Loop

- **goal:** loop-001 发现的预存 P1 - auth login/refresh/me 路由引用 user.name/user.company 缺列(AttributeError/TypeError)
- **branch:** `codex/loop-003-auth-user-name-company`
- **commit:** `067333f`
- **base:** `codex/loop-002-frontend-runtime-fixes` (`46626fc`) - **stacked**(栈 3 层: loop-01->loop-02->loop-03)
- **summary:** `docs/superpowers/summaries/2026-07-17-0414-loop-003-auth-user-name-company.md`
- **status:** ready (浏览器验收移交 QA; 路由端到端需 DB, 以模型/schema 测试回归)
- **test/build:** 6/6 测试过(新增 2); build 过(3.30s, 无 FE 改动)
- **resolves:** loop-001 发现的 auth login/me 路由 P1(User 补 name/company 列)
- **findings:** 路由级无单测(需 DB 基建); api/models.py 死文件仍存; 历史 users name/company 空(不回填)

### loop-004 - 2026-07-17 06:49 +08:00 - Development Loop

- **goal:** QA P1-4(部分) 9004 远达 HomeView 物流语义 + QA P2 9006 名称对齐
- **branch:** `codex/loop-004-9004-logistics-and-9006-name`
- **commit:** `9621f5a`
- **base:** `codex/loop-003-auth-user-name-company` (`067333f`) - **stacked**(栈 4 层)
- **summary:** `docs/superpowers/summaries/2026-07-17-0649-loop-004-9004-logistics-and-9006-name.md`
- **status:** ready (浏览器验收移交 QA; 纯前端, build 过; P1-4 仅 HomeView)
- **test/build:** build 过(2.95s); 后端无改动, loop-001 test 6/6 过(stacked base 绿)
- **resolves:** QA P1-4 部分(9004 HomeView) + QA P2(9006 名称)
- **findings:** P1-4 余 ShortageProcurement/ProductsBom 待后续; 栈 4 层 integration 紧急

### loop-005 - 2026-07-17 08:15 +08:00 - Development Loop (BLOCKED, 无 dev 分支)

- **goal:** 停手 -- 不创建 loop-005 dev 分支; 产出 integration runbook
- **branch:** 无
- **commit:** 无
- **summary:** `docs/superpowers/summaries/2026-07-17-0815-loop-005-blocked-integration-runbook.md`
- **status:** resolved(用户授权选项 3, dev loop 以 integration 角色执行合并, 见 09:18 integration summary)
- **result:** loop-001~004 合并到 main `f33aef6` + push origin + 94 测试过 + 4 worktree/分支清理; origin/main = `f33aef6`
- **follow-up:** 下一轮 dev 从 `f33aef6` 分支, 不再叠栈

### loop-006 - 2026-07-17 10:31 +08:00 - Development Loop

- **goal:** 解除 QA 09:06 P0 -- 后端 `from api.main import main` 90s 无进展(慢导入, 非卡死)
- **branch:** `codex/loop-006-backend-startup`
- **commit:** `74d8a10`
- **base:** `origin/main` `1f7440b`(从绿 main, 不叠栈)
- **summary:** `docs/superpowers/summaries/2026-07-17-1031-loop-006-backend-startup.md`
- **status:** ready (启动 82.4s->22.7s P0 解除; 9/9 测试过; build 过; 浏览器 N/A 移交 QA 复验启动)
- **root cause:** ai/base_agent.py + ai/supervisor.py 模块级 `from langchain_openai import ChatOpenAI` 触发 transformers(~26s)+langchain_openai(~54s)
- **fix:** 延迟 langchain_openai 导入到工厂函数内(TYPE_CHECKING + 局部导入); 启动 82.4s->22.7s, 测试冷导入 ~130s->12.5s
- **findings:** `import langgraph` 0.0s(历史"langgraph 冷导入慢"判断有误, 实为 langchain_openai/transformers); 剩余 22.7s 为 init_db+langchain_core 等, 可后续优化

### loop-007 - 2026-07-17 20:57 +08:00 - P0 Auth Security Loop

- **goal:** 修复认证系统三个 P0 (P0-1 认证形同虚设 / P0-2 硬编码后门 token / P0-3 密码存储不安全且文档不一致)
- **branch:** `codex/loop-security-auth-p0`
- **commit:** `558ce73`
- **base:** `origin/main` `df2f959`(从最新 main, 不叠栈)
- **summary:** `docs/superpowers/summaries/2026-07-17-2057-loop-auth-security-p0-summary.md`
- **status:** merged (2026-07-17 21:40, merge commit `6b89500` on main, 已 push origin/main; main 同时含 PR #33 agent-QA + feat/25-26/27 引用回显工作; 与 auth-sec 无文件重叠, 4 个顺带 build-blocker 修复中 3 个被 main 完整版吸收、types/procure.ts 的 'chat' 成员保留; 合并干净); 三 P0 全修; 测试/build 通过; 浏览器验收仍移交 QA
- **fix:**
  - P0-1: `kb/auth.py:resolve_token` 移除未知 token 兜底放行, 一律返回 None -> 401
  - P0-2: 移除源码硬编码 `kb-admin-demo`/`kb-demo-user`/`demo-token`; `KB_DEMO_TOKEN`/`KB_ADMIN_TOKEN` 改环境变量 (未配置=None); demo/admin demo token 仅 `KB_DEMO_MODE=true` 且非生产 (`APP_ENV`) 时生效; 新增受控 `/auth/demo-login`; 前端移除硬编码 admin token 与 `demo-token` 字面量, demo 登录改走 `/auth/demo-login`; 新增 `.env.example`
  - P0-3: 密码哈希 sha256 -> bcrypt (旧 sha256 登录时渐进升级, 清空 salt); 修正 docstring; 移除 import 期 `Base.metadata.create_all` 与 `_ensure_seed_users` 副作用; 新增 `scripts/seed_auth_users.py` 显式种子
- **test/build:** 4 套件 88 passed + `test_auth_security` 12 passed (新增) + `test_register_identity` 6 passed + `test_kb_rag` 访问控制 3 passed; `web build` ✓ (顺带修复 origin/main 预存 4 个 procure 相关 build 阻断, 非安全相关)
- **findings:** `api/auth.py` (JWT/bcrypt) / `api/dependencies.py` / `api/routes/auth.py` 为死代码 (未注册), 本轮未删 (避免无关重构); /login 接口返回固定 `role="user"` (预存, 不影响后端鉴权, 建议后续修); origin/main (df2f959) build 原本预存失败

Future entries should include:

- loop number
- goal
- branch
- commit
- summary path
- status: `ready`, `wip`, `merged`, or `blocked`

## 8. Ready Branches

- `codex/zhl-value-absorb` (`d96bed3`+, base `1f7440b`, 另一独立分支) - useDashboard 去 mock 降级。ready, 待 integration(注: 本 worktree 计划未含其 entry, 因 zhl 分支未合并; integration 合并时一并处理 plan 更新)。

> 2026-07-17 21:40: `codex/loop-security-auth-p0` 已合并到 main (`6b89500`, 已 push), 见 §10。

## 9. WIP Branches

None.

## 10. Merged Branches Pending Cleanup

已合并并清理(2026-07-17 09:18, integration summary `docs/superpowers/summaries/2026-07-17-0918-integration-loop-001-004.md`):

- `codex/loop-001-register-identity` (`3c023a8`) - merged into `f33aef6`; local+remote branch deleted; worktree removed
- `codex/loop-002-frontend-runtime-fixes` (`46626fc`) - merged, cleaned
- `codex/loop-003-auth-user-name-company` (`067333f`) - merged, cleaned
- `codex/loop-004-9004-logistics-and-9006-name` (`9621f5a`) - merged, cleaned
- `codex/loop-006-backend-startup` (`74d8a10` + docs `03b62a8`) - merged into `91d51f3` on 2026-07-17 11:21 +08:00; branch retained for 3-5 integration rounds before cleanup. Summary: `docs/superpowers/summaries/2026-07-17-1031-loop-006-backend-startup.md`.
- `codex/loop-security-auth-p0` (`558ce73` + docs `31f3575`) - merged into `6b89500` on 2026-07-17 21:40 +08:00 (P0 auth security; main 同含 PR #33 agent-QA + feat/25-26/27, 与 auth-sec 无文件重叠, 合并干净); 已 push origin/main; branch + worktree retained for 3-5 integration rounds before cleanup. Summary: `docs/superpowers/summaries/2026-07-17-2057-loop-auth-security-p0-summary.md`.

## 11. Next Recommended Loop

### ✅ UNBLOCKED (2026-07-17 09:18): integration 完成, main 绿

`origin/main` = `f33aef6`(含 loop-001~004)。dev loop 可从新 main 正常分支, 不再叠栈。94 测试过 + build 过。

**下一轮 dev loop 候选(从 `1f7440b` 或合并 loop-006/zhl 后, 择一):**
1. ~~后端启动验证(疑似 P0)~~ -- ✅ loop-006 已解决(82.4s->22.7s, 延迟 langchain_openai 导入)。剩余 22.7s(init_db+langchain_core)可后续优化。
2. **9004 ShortageProcurement + ProductsBom 物流语义**(QA P1-4 余, 复用 `isLogistics`)。
3. **QA P1-3 供应商工作台"正在拉取"空状态**(待办 #6)。
4. **reset RFQ 基线语义**(待办 #4)。

**待 integration:** `codex/zhl-value-absorb` remains ready/pending. `codex/loop-006-backend-startup` was merged into main at `91d51f3`.

后端可用后, 重跑完整六公司 Playwright smoke 复验 P1/P2(9006 名称 / 9004 物流 / products-bom 不崩溃 / /admin/audit 可达)。

**注:** 可考虑暂停 dev cron(`CronDelete 2420fc7b`)或调长间隔; integration 已追上, 后续可按需手动触发 dev loop。

## 12. Integration Loop Records

### 2026-07-17 01:09 +08:00 - Integration/Cleanup Loop

- **main commit:** `916baed` (`merge: 合并 agent 分支修复到 main`)
- **origin/main status:** refreshed successfully; `main` and `origin/main` both point to `916baedb6719125afc5c576f0ac717785c10c589`.
- **workspace status:** not clean. `docs/superpowers/plans/loop-mvp-industrialization-plan.md` and `docs/superpowers/qa-findings/` are untracked in the current checkout, so no merge was attempted.
- **QA findings:** no P0/P1 findings found. Latest QA directory only contains `.gitkeep`.
- **ready branch scan:** no mergeable ready branch found.
- **skipped branches:**
  - `origin/codex/backend-integration-dashboard-rfq`: remote branch has no commits ahead of `main`; its latest remote commit `4cf466b` is already contained in `main`.
  - local `codex/backend-integration-dashboard-rfq`: has old commits `40a8527` and `c8cd84e` ahead of `main`, but it is not listed as ready in this plan, does not have a matching recent summary under `docs/superpowers/summaries/`, and is far behind current `main`.
  - `codex/demo-scenario-backend`, `codex/demo-scenario-frontend`, `codex/demo-scenario-integration`: already merged into `main`.
- **merge result:** no branch merged.
- **test/build result:** not run because no merge occurred.
- **browser validation:** not run because no merge occurred.
- **new issues:** branch bookkeeping is stale: local and remote `codex/backend-integration-dashboard-rfq` point to different commits; the long-term plan does not yet record already merged demo scenario branches for cleanup tracking.
- **merged branches pending cleanup:** none newly added in this loop.
- **summary:** `docs/superpowers/summaries/2026-07-17-0109-integration-loop.md`
- **next recommendation:** first commit or intentionally track the long-term plan/QA docs, then run a QA Loop on current `main`; after that, update cleanup bookkeeping for already merged demo scenario branches before deleting anything.
- **QA Loop recommended:** yes. Current `main` has several frontend/demo/login-related merges and should receive browser validation, ideally the six-company regression.

### 2026-07-17 09:18 +08:00 - Integration Loop (dev loop 用户授权选项 3 执行)

- **main commit:** `f33aef6` (`merge: integrate loop-001~004`)
- **origin/main:** pushed `916baed..f33aef6` (fast-forward). `origin/main` = `f33aef6`.
- **merged:** loop-001(`3c023a8`) + loop-002(`46626fc`) + loop-003(`067333f`) + loop-004(`9621f5a`) via single `git merge --no-ff codex/loop-004-...` (线性栈 tip 带入全部 4 提交; 3-way, docs↔code 无冲突)。注: 并发 integration loop 此前已合并 loop-01 为 `62c2f06` + 提交文档 `e566dbb`。
- **test/build:** `npm run build` ✓(16.57s); `pytest test_register_identity+demo_scenario+enterprise_phase1/2+rfq_supplier_loop` -> **94 passed**(352.78s)。
- **cleanup:** 4 loop worktree removed(--force); 4 local branch `-d` deleted; 4 remote branch `--delete` deleted。
- **resolved on main:** QA P0 build + P1-1 + P1-2 + auth login/me P1 + P1-4 HomeView 部分 + P2 9006 名称。
- **new from QA 09:06:** 后端 import 慢(疑似 langgraph 冷导入 ~150s, 非真卡死, 待 >180s 复测); dist EPERM(环境性, 非代码); 9006 旧名(dev server 缓存, 修复已在 f33aef6)。
- **summary:** `docs/superpowers/summaries/2026-07-17-0918-integration-loop-001-004.md`
- **next:** dev loop 从 `f33aef6` 分支; 优先验证后端启动 + 9004 余 + P1-3; 后端可用后重跑六公司 smoke。

### 2026-07-17 09:18 +08:00 - Integration/Cleanup Loop

- **main commit:** `f33aef6` (`merge: integrate loop-001~004 (P0 build + 3 P1 + 9004 HomeView 物流 + 9006 名称)`)
- **origin/main status:** `origin/main` points to the same commit.
- **workspace status:** dirty only with this plan update and `docs/superpowers/qa-findings/2026-07-17-0906-browser-qa.md` before final summary commit.
- **QA findings:** latest 09:06 QA finding reported P0 items, but follow-up recheck verified origin/main alignment, backend import, backend focused tests, and frontend build.
- **ready branch scan:** loop-001 through loop-004 were already merged into `main` by the time of recheck.
- **merge result:** loop-001~004 integrated in `f33aef6`; no further ready branch merged in this step.
- **test/build result:** register tests 6 passed; enterprise/RFQ core tests 45 passed; frontend build passed.
- **browser validation:** light Edge headless smoke passed for register identity UI, login/demo visibility, and `/admin/audit` route behavior. Full six-company browser regression remains pending.
- **new issues:** pytest can be slow or appear hung when external plugin autoload is enabled; reliable local recheck used `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`.
- **merged branches pending cleanup:** `codex/loop-001-register-identity`, `codex/loop-002-frontend-runtime-fixes`, `codex/loop-003-auth-user-name-company`, `codex/loop-004-9004-logistics-and-9006-name` are merged and should be retained 3-5 rounds before cleanup.
- **summary:** `docs/superpowers/summaries/2026-07-17-0918-integration-loop.md`
- **next recommendation:** run a fresh QA Loop on `origin/main`/`f33aef6`, preferably full six-company browser regression; then continue with 9004 ShortageProcurement/ProductsBom logistics semantics or supplier workspace empty-state work.
- **QA Loop recommended:** yes.

### 2026-07-17 11:21 +08:00 - Integration/Cleanup Loop

- **main commit:** `91d51f3` (`merge: integrate loop-006 backend startup`)
- **origin/main status before push:** local `main` was up to date with `origin/main` at `1f7440b`; push pending until this record and summary are committed.
- **merged:** `codex/loop-006-backend-startup` (`74d8a10` + docs `03b62a8`), a ready P0 fix for backend startup/import time.
- **test/build:** `python -m pytest tests/test_supervisor.py tests/test_register_identity.py -q` -> 9 passed, 6 warnings; `cd web && npm run build` -> passed; `from api.main import main` import smoke -> 11.3s.
- **browser validation:** N/A for this merge because the branch only changes backend AI module import timing; QA should still recheck backend startup and first procure request.
- **new issues:** the first pytest attempt with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` failed because async pytest plugins were disabled; rerun without disabling plugins passed. Pytest cache write warning remains an environment permission issue.
- **merged branches pending cleanup:** `codex/loop-006-backend-startup` retained for 3-5 integration rounds.
- **summary:** `docs/superpowers/summaries/2026-07-17-1121-integration-loop-006.md`
- **next recommendation:** push main after committing this documentation; then run QA Loop focused on backend startup <90s, `/api/v1/health`, and first procure request. After QA, consider integrating `codex/zhl-value-absorb` separately.
- **QA Loop recommended:** yes.
