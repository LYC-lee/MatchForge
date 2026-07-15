# MatchForge MVP Gap Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前“前端可演示 Spike + AI 编排原型”推进到可真实联调、可闭环演示的 MatchForge MVP。

**Architecture:** 以 FastAPI 作为后端入口，承接 Vue 前端已有 `/api/v1` 契约，并将 `ai/supervisor.py` 的 `run_procure_stream()` 两阶段 SSE 流接入真实 HTTP 服务。当前 MySQL 已出现 `matchforge` 与 `pc_industry` 双 schema，需要先明确 MVP 数据源边界，再落 SQLAlchemy ORM、认证、RFQ、线索、报价和审核 API。

**Tech Stack:** Vue 3 + TypeScript + Pinia + Vite、FastAPI + SQLAlchemy + Pydantic、MySQL 8.0、Redis、Neo4j、Milvus、LangGraph、pytest、vue-tsc。

---

## 1. 当前状态判断

当前项目已经具备较完整的产品方向、前端页面、路由、状态管理、API 契约、AI 编排代码和数据层样例。采购端可以通过 mock SSE 演示“需求输入 -> 规格确认 -> 替代料 -> 供应商匹配 -> RFQ 生成”的核心体验。

相对初版分析，数据库和种子数据已经显著推进：`data/` 下已有 `matchforge` schema、35 家供应商、137 条替代关系、81 条标准字典和 `init_all.py`；`database/` 下已有 `pc_industry` 13 表 DDL、字段字典、CSV 样例和 Demo 验证 SQL。项目还没有形成可用 MVP，主要原因已经从“缺数据库和数据”转为“缺 FastAPI 后端、缺双库收敛决策、缺真实业务接口接线”。

### 2026-07-15 复勘更新

**已有显著进展：**

- `data/` 数据层已落地：包含 `data/mysql_schema.sql`、`data/init_all.py`、`data/suppliers/suppliers.json`、`data/alternatives/alternatives.json`、`data/dictionary/dictionary.json`，并配套 MySQL、Neo4j、Milvus 导入脚本。
- `database/` 16 小时冲刺已完成主要产物：`database/01_schema/01_core_tables_ddl.sql`、`database/01_schema/02_indexes.sql`、字段字典、12 份 CSV 种子数据和 3 条 Demo 验证 SQL。
- 前端主路径 `/app` -> `/procure/:id` 已通过 `web/src/api/procure.ts` 统一 mock/real SSE 入口，事件格式与 `ai/supervisor.py` 基本对齐。
- AI 层已有根目录 `tests/` 单测覆盖，测试缺口主要集中在 API 集成测试、前端测试和 E2E。

**仍然阻塞 MVP：**

- `api/` 仍只有 `requirements.txt`，没有 FastAPI 应用、路由、ORM、服务层和测试。
- 存在 `matchforge` 与 `pc_industry` 双 MySQL schema，后端 ORM 和种子导入路径必须先收敛。
- `deploy/docker-compose.yml` 挂载了 `./docker/mysql/init`，但 `deploy/docker/mysql/init/` 目录和初始化 SQL 仍缺失。
- 认证、RFQ 提交、供应商线索、运营审核和服务端历史仍主要停留在前端 mock/localStorage。
- `/flow` 的旧入口仍可能走 `web/src/api/index.ts` 中另一套 `procureStream()`，需要统一到 `web/src/api/procure.ts`。

## 2. 关键问题分析

### P0 问题：阻塞真实 MVP

- FastAPI 后端缺失：`api/` 目前只有依赖文件，没有 `main.py`、路由、鉴权、数据库模型和业务服务。
- 双 MySQL schema 未收敛：`data/mysql_schema.sql` 面向 `matchforge` 运营库，`database/01_schema/01_core_tables_ddl.sql` 面向 `pc_industry` 产业链事实库；后端不能在未决策的情况下直接建 ORM。
- 前后端真实联调未接通：前端已经定义大量 `/api/v1` 接口，但切到 `VITE_USE_MOCK=false` 后没有后端响应。
- 认证权限不完整：当前是 localStorage mock 认证，路由只检查登录状态，没有 buyer、supplier、admin 的角色隔离。
- RFQ 与线索没有闭环：前端已有 RFQ 编辑、供应商线索和运营审核页面，但“发送 RFQ -> 供应商收到线索 -> 报价/回复 -> 运营审核”没有服务端状态流转。
- Docker MySQL 自动初始化缺失：compose 已挂载 `./docker/mysql/init`，但缺少对应目录和权威初始化 SQL。

### P1 问题：影响 MVP 完整度

- SSE 双入口需要统一：主路径使用 `web/src/api/procure.ts`，旧 P 系列入口仍可能使用 `web/src/api/index.ts` 的 `procureStream()`，事件格式和 mock 行为不完全一致。
- 供应商端未接 API：`SupplierDashboard.vue`、`SupplierProducts.vue`、`SupplierLeads.vue` 主要依赖本地 mock 或页面内数据。
- 运营审核未接 API：`P7AdminAudit.vue` 有审核 UI，但没有使用真实 `getAuditQueue`、`performAudit` 等接口；现有 `pc_industry` schema 更偏向用 `supplier_capabilities.audit_status` 承载审核状态。
- 历史记录本地化：`HistoryView.vue` 使用 localStorage，`P6History.vue` 调 `getRfqs()` 失败时静默置空，无法支持跨设备和真实 RFQ 跟踪。
- 种子导入路径未统一：`data/init_all.py` 已可初始化 `matchforge`，`database/04_seed_data/*.csv` 仍需要后端批量导入脚本和 FK 顺序执行。

### P2 问题：影响质量与上线信心

- 前端没有测试脚本：`web/package.json` 只有 `dev`、`build`、`preview`。
- 缺少 API 集成测试和 E2E 测试：根目录 AI 单测已有，但没有覆盖认证、SSE、RFQ 提交、供应商线索、运营审核等 HTTP 关键路径。
- 缺少 CI：没有自动执行类型检查、单元测试、构建和后端测试的流水线。
- 仓库卫生需要处理：`.gitignore` 已忽略 `node_modules/`，但建议显式补充 `**/node_modules/.tmp/*.tsbuildinfo`；当前工作区还出现未跟踪的 `git_push.bat`，需确认是否应提交。

## 3. 目标 MVP 范围

本计划聚焦一个可演示、可真实联调的最小闭环：

- 采购用户可以登录，输入自然语言寻源需求。
- 后端通过 SSE 返回规格解析、替代料、供应商匹配、RFQ 和线索分级结果。
- 采购用户可以确认 RFQ 并发送给候选供应商。
- 供应商用户可以看到分配给自己的线索，并提交报价或回复。
- 管理员可以查看待审核供应商或关键数据变更，并执行通过/驳回。
- 历史记录保存在服务端，支持按用户查看 RFQ 和线索状态。

暂不追求完整商业化功能，例如复杂 CRM、支付、合同、消息推送、批量导入后台和高级数据治理。

## 4. 文件结构规划

### 后端 API

- Create: `api/main.py`，FastAPI 应用入口，注册路由、CORS、健康检查和 OpenAPI。
- Create: `api/app/core/config.py`，集中读取环境变量。
- Create: `api/app/core/security.py`，密码哈希、JWT 签发、当前用户解析。
- Create: `api/app/db/session.py`，SQLAlchemy engine、session dependency。
- Create: `api/app/models/*.py`，按双库收敛决策建立用户、公司、物料、供应商、RFQ、报价、审核等 ORM 模型。
- Create: `api/app/schemas/*.py`，请求/响应 Pydantic schema。
- Create: `api/app/routers/auth.py`，登录、注册、刷新、当前用户。
- Create: `api/app/routers/procure.py`，`POST /api/v1/procure` SSE 入口。
- Create: `api/app/routers/rfq.py`，RFQ 创建、提交、查询。
- Create: `api/app/routers/supplier.py`，供应商产品、线索、报价。
- Create: `api/app/routers/admin.py`，审核队列和审核操作。
- Create: `api/app/services/*.py`，封装业务逻辑，避免路由直接写复杂流程。

### 数据与部署

- Review: `data/mysql_schema.sql`，`matchforge` 运营库 10 表 schema。
- Review: `database/01_schema/01_core_tables_ddl.sql`，`pc_industry` 产业链事实库 13 表 schema。
- Create: `docs/architecture/schema-convergence.md`，记录 MVP 数据源边界、表映射和收敛路径。
- Create: `deploy/docker/mysql/init/01_matchforge_schema.sql`，docker-compose 初始化使用的 `matchforge` schema。
- Create: `deploy/docker/mysql/init/02_pc_industry_schema.sql`，如果保留双库，初始化 `pc_industry` schema。
- Create: `scripts/import_pc_industry_seed.py`，按 FK 顺序导入 `database/04_seed_data/*.csv`。
- Reuse: `data/init_all.py`，继续初始化 `matchforge`、Neo4j 和 Milvus 种子数据。

### 前端接线

- Modify: `web/src/router/index.ts`，增加角色权限检查。
- Modify: `web/src/stores/auth.ts`，真实模式调用后端认证接口，mock 模式保留本地演示。
- Modify: `web/src/api/index.ts`，对齐后端响应结构，补齐 RFQ、supplier、admin 调用。
- Modify: `web/src/views/P5RfqEdit.vue` 或 `web/src/components/procure/RfqEditor.vue`，接入真实 RFQ 提交。
- Modify: `web/src/views/supplier/SupplierLeads.vue`，接入真实线索和报价 API。
- Modify: `web/src/views/P7AdminAudit.vue`，接入真实审核 API。
- Modify: `web/src/views/HistoryView.vue` 和 `web/src/views/P6History.vue`，使用服务端历史。

### 测试与工程化

- Create: `api/tests/test_auth.py`，认证 API 测试。
- Create: `api/tests/test_procure.py`，SSE 最小路径测试。
- Create: `api/tests/test_rfq.py`，RFQ 提交与查询测试。
- Create: `api/tests/test_supplier.py`，供应商线索与报价测试。
- Create: `api/tests/test_admin.py`，审核队列测试。
- Modify: `web/package.json`，增加前端测试脚本。
- Create: `.github/workflows/ci.yml`，执行后端测试、前端类型检查和构建。

## 5. 实施任务

### Task 0: 双库 Schema 收敛决策

**Files:**
- Create: `docs/architecture/schema-convergence.md`
- Review: `data/mysql_schema.sql`
- Review: `database/01_schema/01_core_tables_ddl.sql`
- Review: `database/06_handoff/01_retrospective.md`

- [ ] Step 1: 明确 `matchforge` 与 `pc_industry` 的职责边界：`matchforge` 承载用户、会话、线索和 AI 运营状态，`pc_industry` 承载公司、物料、替代关系、供应商能力、RFQ 和报价事实。
- [ ] Step 2: 决定 MVP 第一个 FastAPI 版本是否双库连接。建议第一阶段双库读取，认证和线索写 `matchforge`，物料/供应商/RFQ/报价读写 `pc_industry`。
- [ ] Step 3: 记录跨库关联键：`part_id`、`supplier_id`、`rfq_id`、`enterprise_id/company_id` 的映射规则。
- [ ] Step 4: 明确审核模型：MVP 先复用 `pc_industry.supplier_capabilities.audit_status`，只有需要通用审核队列时再新建 `audit_items`。
- [ ] Step 5: 将结论写入 `docs/architecture/schema-convergence.md`，作为后端 ORM 和迁移的依据。

### Task 1: 建立 FastAPI 应用骨架

**Files:**
- Create: `api/main.py`
- Create: `api/app/core/config.py`
- Create: `api/app/db/session.py`
- Create: `api/app/routers/health.py`
- Test: `api/tests/test_health.py`

- [ ] Step 1: 创建 FastAPI 应用入口，暴露 `/api/v1/health`。
- [ ] Step 2: 增加配置读取，支持 `MATCHFORGE_DATABASE_URL`、`PC_INDUSTRY_DATABASE_URL`、`JWT_SECRET_KEY`、`CORS_ORIGINS`。
- [ ] Step 3: 增加数据库 session dependency，但健康检查先不依赖数据库。
- [ ] Step 4: 编写 `test_health.py`，断言健康检查返回 `{"status": "ok"}`。
- [ ] Step 5: 运行 `pytest api/tests/test_health.py -v`，确认通过。
- [ ] Step 6: 运行 `uvicorn main:app --reload`，确认 OpenAPI 页面可访问。

### Task 2: 接入现有 Schema 与 Docker 初始化

**Files:**
- Create: `deploy/docker/mysql/init/01_matchforge_schema.sql`
- Create: `deploy/docker/mysql/init/02_pc_industry_schema.sql`
- Create: `api/app/models/base.py`
- Create: `api/app/models/user.py`
- Create: `api/app/models/industry.py`
- Modify: `api/app/db/session.py`

- [ ] Step 1: 将 `data/mysql_schema.sql` 复制或整理为 `deploy/docker/mysql/init/01_matchforge_schema.sql`，保持凭据和库名与 `deploy/docker-compose.yml` 一致。
- [ ] Step 2: 将 `database/01_schema/01_core_tables_ddl.sql` 整理为 `deploy/docker/mysql/init/02_pc_industry_schema.sql`；如果 DDL 不含 `CREATE DATABASE pc_industry`，补充建库和 `USE pc_industry`。
- [ ] Step 3: 在 `api/app/db/session.py` 中支持 `MATCHFORGE_DATABASE_URL` 和 `PC_INDUSTRY_DATABASE_URL` 两个 engine/session dependency。
- [ ] Step 4: 先建立最小 ORM：`matchforge.users`、`matchforge.enterprises`、`pc_industry.companies`、`pc_industry.parts`、`pc_industry.suppliers`、`pc_industry.rfqs`、`pc_industry.rfq_suppliers`、`pc_industry.quotations`。
- [ ] Step 5: 运行 `docker compose -f deploy/docker-compose.yml up -d mysql`，确认 MySQL 可启动并完成两个 schema 初始化。
- [ ] Step 6: 用 MySQL CLI 分别查询 `matchforge.users` 和 `pc_industry.parts`，确认表存在。

### Task 3: 实现真实认证与角色权限

**Files:**
- Create: `api/app/core/security.py`
- Create: `api/app/models/user.py`
- Create: `api/app/schemas/auth.py`
- Create: `api/app/routers/auth.py`
- Modify: `web/src/stores/auth.ts`
- Modify: `web/src/router/index.ts`
- Test: `api/tests/test_auth.py`

- [ ] Step 1: 后端基于 `matchforge.users` 实现密码哈希、登录 JWT、注册用户和刷新 token。
- [ ] Step 2: 定义 `buyer`、`supplier`、`admin` 三种角色，并在 JWT claims 中携带角色。
- [ ] Step 3: 前端 `auth` store 在 `VITE_USE_MOCK=false` 时调用 `/api/v1/auth/login`、`/api/v1/auth/register`、`/api/v1/auth/refresh`。
- [ ] Step 4: 前端路由 `meta` 增加允许角色，限制 `/admin/audit` 仅 admin 访问，`/supplier/*` 仅 supplier 和 admin 访问。
- [ ] Step 5: 编写认证测试，覆盖注册、登录、刷新、错误密码、角色返回。
- [ ] Step 6: 运行 `pytest api/tests/test_auth.py -v` 和 `cd web && npm run build`。

### Task 4: 接入 Procure SSE 主流程

**Files:**
- Create: `api/app/schemas/procure.py`
- Create: `api/app/routers/procure.py`
- Create: `api/app/services/procure_service.py`
- Modify: `ai/supervisor.py` only if the HTTP contract requires a small adapter
- Test: `api/tests/test_procure.py`

- [ ] Step 1: 实现 `POST /api/v1/procure`，请求体支持 `query`、`thread_id`、`phase`、`confirmed_spec`。
- [ ] Step 2: 调用 `ai.supervisor.run_procure_stream()`，将事件以 `text/event-stream` 返回。
- [ ] Step 3: 保持事件格式与 `web/src/api/sse.ts` 对齐：`start`、`progress`、`result`、`error`、`end`。
- [ ] Step 4: 增加异常处理，AI 失败时返回 SSE `error` 事件，而不是直接断开连接。
- [ ] Step 5: 编写测试，mock supervisor 事件流，断言 SSE 输出包含 `start`、`result`、`end`。
- [ ] Step 6: 设置 `VITE_USE_MOCK=false`，运行前端采购主流程，确认可以收到真实 SSE。

### Task 5: 自动化现有种子数据链路

**Files:**
- Reuse: `data/init_all.py`
- Reuse: `data/suppliers/suppliers.json`
- Reuse: `data/alternatives/alternatives.json`
- Reuse: `data/dictionary/dictionary.json`
- Create: `scripts/import_pc_industry_seed.py`
- Create: `api/tests/test_seed_data.py`

- [ ] Step 1: 保留 `data/init_all.py` 作为 `matchforge`、Neo4j、Milvus 的初始化入口，不再新建 `data/seed/*.json`。
- [ ] Step 2: 新建 `scripts/import_pc_industry_seed.py`，按 `database/01_schema/03_seed_import_notes.md` 的 FK 顺序导入 `database/04_seed_data/*.csv`。
- [ ] Step 3: 导入逻辑使用 upsert 或先清空样例数据的事务策略，保证重复执行结果可预期。
- [ ] Step 4: 测试验证 seed 后可以查到 `matchforge.suppliers`、`matchforge.material_dictionary`、`pc_industry.parts`、`pc_industry.part_alternatives`、`pc_industry.quotations`。
- [ ] Step 5: 在 README 或环境文档中补充初始化命令：`python data/init_all.py` 和 `python scripts/import_pc_industry_seed.py`。

### Task 6: 实现 RFQ 提交与历史记录

**Files:**
- Create: `api/app/models/rfq.py`
- Create: `api/app/schemas/rfq.py`
- Create: `api/app/routers/rfq.py`
- Create: `api/app/services/rfq_service.py`
- Modify: `web/src/api/index.ts`
- Modify: `web/src/components/procure/RfqEditor.vue`
- Modify: `web/src/views/P5RfqEdit.vue`
- Modify: `web/src/views/HistoryView.vue`
- Modify: `web/src/views/P6History.vue`
- Test: `api/tests/test_rfq.py`

- [ ] Step 1: 后端实现 RFQ 创建、提交、列表、详情接口。
- [ ] Step 2: 提交 RFQ 时写入 `rfqs` 和 `rfq_suppliers`，状态从 `draft` 变为 `sent`。
- [ ] Step 3: 前端“发送 RFQ”调用真实提交接口，成功后展示服务端返回的 RFQ 编号。
- [ ] Step 4: 历史页面从服务端读取 RFQ 列表，替代 localStorage 作为真实模式数据源。
- [ ] Step 5: 测试覆盖创建草稿、提交给供应商、按用户查询历史。
- [ ] Step 6: 手动验证采购用户完成一次 RFQ 发送后，历史页面可看到记录。

### Task 7: 接入供应商线索与报价

**Files:**
- Create: `api/app/models/quotation.py`
- Create: `api/app/schemas/supplier.py`
- Create: `api/app/routers/supplier.py`
- Create: `api/app/services/supplier_service.py`
- Modify: `web/src/views/supplier/SupplierDashboard.vue`
- Modify: `web/src/views/supplier/SupplierProducts.vue`
- Modify: `web/src/views/supplier/SupplierLeads.vue`
- Test: `api/tests/test_supplier.py`

- [ ] Step 1: 后端实现供应商线索列表接口，按当前 supplier 用户过滤。
- [ ] Step 2: 实现报价或回复接口，写入 `quotations` 并更新 `rfq_suppliers` 状态。
- [ ] Step 3: 供应商线索页面移除页面内 mock 数据，改为调用真实 API。
- [ ] Step 4: 供应商工作台统计从后端读取待处理线索、已报价数量和转化状态。
- [ ] Step 5: 测试覆盖供应商只能看到自己的线索，不能访问其他供应商线索。
- [ ] Step 6: 手动验证 supplier 角色登录后可以提交一次报价。

### Task 8: 接入运营审核

**Files:**
- Create: `api/app/schemas/admin.py`
- Create: `api/app/routers/admin.py`
- Create: `api/app/services/admin_service.py`
- Modify: `web/src/views/P7AdminAudit.vue`
- Test: `api/tests/test_admin.py`

- [ ] Step 1: 后端实现审核队列列表，第一版基于 `pc_industry.supplier_capabilities.audit_status` 按状态过滤。
- [ ] Step 2: 实现审核通过、驳回、补充来源备注接口，更新 `audit_status`、`audit_note` 或等效字段；如果字段不足，在 schema 收敛文档中记录新增字段。
- [ ] Step 3: 前端运营审核页面移除本地 mock 队列，改为调用真实 API。
- [ ] Step 4: 路由和后端 dependency 都限制 admin 角色访问。
- [ ] Step 5: 测试覆盖非 admin 访问返回 403，admin 可以审核并改变状态。
- [ ] Step 6: 手动验证 admin 角色可以处理一条审核记录。

### Task 9: 统一前端主流程

**Files:**
- Modify: `web/src/router/index.ts`
- Modify: `web/src/views/HomeView.vue`
- Modify: `web/src/views/ProcureView.vue`
- Modify: `web/src/views/ChatView.vue`
- Modify: `web/src/views/P1Home.vue`
- Modify: `web/src/stores/procure.ts`

- [ ] Step 1: 确定 MVP 主路径为 `/app` -> `/procure/:id`，`/chat` 作为对话入口复用同一 store。
- [ ] Step 2: 保留 P 系列页面作为备用分步入口，明确导航入口和数据来源。
- [ ] Step 3: 所有真实 SSE 调用统一走 `web/src/api/procure.ts`，避免 `api/index.ts` 和 `api/procure.ts` 双入口分叉；`P1Home.vue` 也切到同一入口。
- [ ] Step 4: 更新页面文案，区分 mock 演示模式和真实联调模式。
- [ ] Step 5: 运行 `cd web && npm run build`，确认类型检查通过。

### Task 10: 补齐测试、CI 与仓库卫生

**Files:**
- Modify: `web/package.json`
- Create: `.github/workflows/ci.yml`
- Modify: `.gitignore`
- Create: `web/src/__tests__/auth.spec.ts` if Vitest is introduced
- Create: `web/src/__tests__/router.spec.ts` if Vitest is introduced

- [ ] Step 1: 将 `**/node_modules/.tmp/*.tsbuildinfo` 加入 `.gitignore`。
- [ ] Step 2: 增加前端测试依赖和 `test` 脚本，至少覆盖 auth store 和路由权限。
- [ ] Step 3: 增加 CI，执行 `pytest`、`cd web && npm run build`、`cd web && npm run test`。
- [ ] Step 4: 在 CI 中缓存 Python 和 npm 依赖，保持流水线可重复。
- [ ] Step 5: 运行完整本地检查，确认后端测试、前端测试和构建全部通过。

## 6. 建议实施顺序

第零阶段先完成双库收敛决策，明确 `matchforge` 与 `pc_industry` 的边界、后端 ORM 指向和审核模型。这个阶段不写业务接口，先避免后续后端在两套 schema 之间反复摇摆。

第一阶段完成 FastAPI 骨架、Docker MySQL 初始化、最小 ORM、真实认证和 Procure SSE HTTP 包装。完成后，采购主流程可以在 `VITE_USE_MOCK=false` 下真实联调。

第二阶段完成现有种子数据自动化、RFQ 提交、服务端历史、供应商线索和报价。完成后，MVP 具备采购到供应商响应的业务闭环。

第三阶段完成运营审核、前端主流程收敛、测试、CI 和部署初始化收尾。完成后，项目具备试点演示和持续迭代基础。

## 7. 五人分工建议

### A. 后端负责人：FastAPI 与业务闭环

**主要目标:** 把现有前端 `/api/v1` 契约接成可用 HTTP 服务。

- 负责 Task 1、Task 3、Task 6、Task 7、Task 8 的后端部分。
- 交付 `api/main.py`、认证路由、RFQ 路由、供应商线索/报价路由、运营审核路由。
- 与数据负责人确认 ORM 使用 `matchforge` 和 `pc_industry` 的边界。
- 与前端负责人共同对齐接口响应结构，避免前端再写额外 mock 分支。
- 验收标准：`uvicorn main:app --reload` 可启动，`/docs` 可访问，认证/RFQ/供应商/审核 API 有测试覆盖。

### B. 数据负责人：双库收敛、DDL 与种子导入

**主要目标:** 让 MySQL、Neo4j、Milvus 的初始化过程可重复、可验证。

- 负责 Task 0、Task 2、Task 5。
- 交付 `docs/architecture/schema-convergence.md`、`deploy/docker/mysql/init/*.sql`、`scripts/import_pc_industry_seed.py`。
- 维护 `data/init_all.py` 与 `database/04_seed_data/*.csv` 的导入说明。
- 给后端负责人提供稳定的表结构、字段含义、关联键和 Demo 数据。
- 验收标准：Docker MySQL 启动后自动建表，`python data/init_all.py` 与 `python scripts/import_pc_industry_seed.py` 可重复执行。

### C. AI 接入负责人：Procure SSE 与 Agent 数据源

**主要目标:** 将 `ai/supervisor.py` 的流式寻源结果稳定暴露给 FastAPI 和前端。

- 负责 Task 4，并协助 Task 5 中 Neo4j/Milvus 数据验证。
- 确认 `run_procure_stream()` 的入参、事件格式和错误事件与 `web/src/api/sse.ts` 完全一致。
- 将替代料和供应商匹配逐步从纯 LLM/mock 转为读取 `pc_industry`、Neo4j、Milvus 的事实数据。
- 编写或维护 `api/tests/test_procure.py` 中对 SSE 的 mock 测试。
- 验收标准：`VITE_USE_MOCK=false` 时采购主流程能收到 `start`、`progress`、`result`、`end` 事件。

### D. 前端负责人：真实模式接线与角色体验

**主要目标:** 把采购端、供应商端、运营端从 mock 页面接到真实 API。

- 负责 Task 3、Task 6、Task 7、Task 8、Task 9 的前端部分。
- 修改 `web/src/stores/auth.ts`、`web/src/router/index.ts`、`web/src/api/index.ts`、`web/src/api/procure.ts`。
- 接通 RFQ 发送、服务端历史、供应商线索/报价、运营审核页面。
- 统一 `/app`、`/procure/:id`、`/chat`、`/flow` 的 SSE 调用入口。
- 验收标准：buyer、supplier、admin 三类用户在真实模式下只能访问自己的页面，并能完成各自核心动作。

### E. 测试与交付负责人：CI、回归与仓库卫生

**主要目标:** 保证每个阶段可以稳定回归，避免演示前集成失控。

- 负责 Task 10，并协助所有任务补齐测试命令和验收记录。
- 增加 `.gitignore` 规则，处理 `node_modules/.tmp/*.tsbuildinfo` 等缓存文件。
- 建立 `.github/workflows/ci.yml`，执行后端 pytest、前端 build、前端 test。
- 维护一份手动验收清单：登录、寻源、RFQ、供应商报价、运营审核、历史记录。
- 验收标准：本地和 CI 都能通过 `pytest`、`cd web && npm run build`、`cd web && npm run test`。

### 并行节奏

- 第 1 天：数据负责人完成 Task 0 决策，后端负责人搭 FastAPI 骨架，前端负责人梳理真实接口差异，AI 负责人确认 SSE 契约，测试负责人补仓库卫生。
- 第 2-3 天：后端和数据完成双库 session、ORM、Docker init；AI 接入 `/procure`；前端接认证和主采购流。
- 第 4-5 天：完成 RFQ、供应商线索、报价、运营审核闭环；测试负责人补 API 测试和 CI。
- 第 6 天：全员做一次端到端演示回归，只修阻塞 MVP 的问题，不扩展新功能。

## 8. 验收标准

- `docs/architecture/schema-convergence.md` 明确记录 `matchforge` 与 `pc_industry` 的职责边界、跨库关联键和后续合并方向。
- `docker compose -f deploy/docker-compose.yml up -d mysql redis neo4j milvus postgres` 可以启动核心基础设施，MySQL 启动后自动拥有权威初始化 schema。
- `python data/init_all.py` 可以初始化 `matchforge`、Neo4j 和 Milvus 相关种子数据。
- `python scripts/import_pc_industry_seed.py` 可以导入 `database/04_seed_data/*.csv`，重复执行结果可预期。
- `uvicorn main:app --reload` 可以启动 FastAPI，并访问 `/docs` 和 `/api/v1/health`。
- `VITE_USE_MOCK=false` 时，采购端可以完成一次真实 SSE 寻源流程。
- buyer 用户可以提交 RFQ，supplier 用户可以看到线索并报价，admin 用户可以处理审核。
- 非 admin 用户访问 `/admin/audit` 被前端和后端共同拦截。
- `pytest`、`cd web && npm run build`、`cd web && npm run test` 均通过。

## 9. 风险与控制

- AI 结果不稳定：MVP 阶段保留确定性 fallback 和最小 seed 数据，确保演示不依赖大规模数据质量。
- 双库长期分裂：先写 schema 收敛文档，后端第一版只允许通过明确的 repository/service 层访问数据库，禁止页面或路由直接感知两套 schema 的细节。
- 数据库设计过度膨胀：第一版只覆盖闭环所需字段，不引入复杂 CRM、合同、支付、库存、质检、RMA 和消息系统。
- 前端双流程继续分裂：所有真实寻源请求统一走一个 SSE API，页面只负责不同交互形态。
- 角色权限遗漏：每个受保护接口后端都做 dependency 检查，前端路由守卫只作为用户体验优化。
- 测试成本上升：优先覆盖认证、SSE、RFQ、供应商线索、审核五条关键路径。

## 10. 自检结果

- Spec coverage: 已覆盖复勘后的后端缺失、双库收敛、现有种子数据自动化、真实联调、认证权限、RFQ/线索/审核闭环、五人分工、测试和部署问题。
- Placeholder scan: 文档没有使用 TBD、TODO 或“以后实现”作为任务内容；所有任务均给出明确文件路径和验收动作。
- Type consistency: 前端路径、后端模块名、API 方向和现有项目结构保持一致；SSE 接入函数已对齐 `ai.supervisor.run_procure_stream()`，种子数据路径已对齐现有 `data/` 和 `database/04_seed_data/`。
