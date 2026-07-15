# MatchForge MVP Gap Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前“前端可演示 Spike + AI 编排原型”推进到可真实联调、可闭环演示的 MatchForge MVP。

**Architecture:** 以 FastAPI 作为后端入口，承接 Vue 前端已有 `/api/v1` 契约，并将 `ai/supervisor.py` 的两阶段 SSE 流接入真实 HTTP 服务。MySQL 承载用户、供应商、物料、RFQ、报价与审核等核心业务数据，Neo4j/Milvus 在 MVP 阶段先以最小种子数据接入，后续再扩展检索质量。

**Tech Stack:** Vue 3 + TypeScript + Pinia + Vite、FastAPI + SQLAlchemy + Pydantic、MySQL 8.0、Redis、Neo4j、Milvus、LangGraph、pytest、vue-tsc。

---

## 1. 当前状态判断

当前项目已经具备较完整的产品方向、前端页面、路由、状态管理、API 契约和 AI 编排代码。采购端可以通过 mock SSE 演示“需求输入 -> 规格确认 -> 替代料 -> 供应商匹配 -> RFQ 生成”的核心体验。

项目还没有形成可用 MVP，主要原因是后端 API、核心数据库、真实种子数据和业务闭环尚未落地。供应商端、运营审核、RFQ 提交、历史记录和角色权限目前大多停留在 UI 或本地 mock 阶段。

## 2. 关键问题分析

### P0 问题：阻塞真实 MVP

- FastAPI 后端缺失：`api/` 目前只有依赖文件，没有 `main.py`、路由、鉴权、数据库模型和业务服务。
- 核心业务表缺失：`database/01_schema/` 只有 `industry_segments` DDL，缺少用户、公司、物料、供应商、替代料、RFQ、报价、线索和审核表。
- 种子数据缺失：README 提到的 `data/` 目录不存在，供应商数据、替代料图谱、标准字典和向量索引都没有初始化链路。
- 前后端真实联调未接通：前端已经定义大量 `/api/v1` 接口，但切到 `VITE_USE_MOCK=false` 后没有后端响应。
- 认证权限不完整：当前是 localStorage mock 认证，路由只检查登录状态，没有 buyer、supplier、admin 的角色隔离。
- RFQ 与线索没有闭环：前端已有 RFQ 编辑、供应商线索和运营审核页面，但“发送 RFQ -> 供应商收到线索 -> 报价/回复 -> 运营审核”没有服务端状态流转。

### P1 问题：影响 MVP 完整度

- 两套采购流程并行：`/app`、`/procure/:id`、`/chat` 与 `/flow`、`/spec-confirm`、`/alternatives`、`/supplier-match`、`/rfq-edit` 数据流不统一。
- 供应商端未接 API：`SupplierDashboard.vue`、`SupplierProducts.vue`、`SupplierLeads.vue` 主要依赖本地 mock 或页面内数据。
- 运营审核未接 API：`P7AdminAudit.vue` 有审核 UI，但没有使用真实 `getAuditQueue`、`performAudit` 等接口。
- 历史记录本地化：`HistoryView.vue` 使用 localStorage，`P6History.vue` 仍有详情跳转缺口，无法支持跨设备和真实 RFQ 跟踪。
- 部署初始化不完整：`deploy/docker-compose.yml` 引用了 `./docker/mysql/init`，但初始化 SQL 脚本尚未配套。

### P2 问题：影响质量与上线信心

- 前端没有测试脚本：`web/package.json` 只有 `dev`、`build`、`preview`。
- 缺少 API 集成测试和 E2E 测试：没有覆盖认证、SSE、RFQ 提交、供应商线索、运营审核等关键路径。
- 缺少 CI：没有自动执行类型检查、单元测试、构建和后端测试的流水线。
- 仓库卫生需要处理：`web/node_modules/.tmp/*.tsbuildinfo` 这类缓存文件不应进入 git 跟踪范围。

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
- Create: `api/app/models/*.py`，用户、公司、物料、供应商、RFQ、报价、审核等 ORM 模型。
- Create: `api/app/schemas/*.py`，请求/响应 Pydantic schema。
- Create: `api/app/routers/auth.py`，登录、注册、刷新、当前用户。
- Create: `api/app/routers/procure.py`，`POST /api/v1/procure` SSE 入口。
- Create: `api/app/routers/rfq.py`，RFQ 创建、提交、查询。
- Create: `api/app/routers/supplier.py`，供应商产品、线索、报价。
- Create: `api/app/routers/admin.py`，审核队列和审核操作。
- Create: `api/app/services/*.py`，封装业务逻辑，避免路由直接写复杂流程。

### 数据与部署

- Create: `database/01_schema/01_core_tables_ddl.sql`，核心 MySQL DDL。
- Create: `deploy/docker/mysql/init/01_core_tables_ddl.sql`，docker-compose 初始化使用的 SQL。
- Create: `data/seed/suppliers.json`，最小供应商样例。
- Create: `data/seed/parts.json`，最小物料样例。
- Create: `data/seed/alternatives.json`，最小替代料样例。
- Create: `scripts/seed.py`，将 JSON 种子数据导入 MySQL，后续可扩展 Neo4j/Milvus。

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

### Task 1: 建立 FastAPI 应用骨架

**Files:**
- Create: `api/main.py`
- Create: `api/app/core/config.py`
- Create: `api/app/db/session.py`
- Create: `api/app/routers/health.py`
- Test: `api/tests/test_health.py`

- [ ] Step 1: 创建 FastAPI 应用入口，暴露 `/api/v1/health`。
- [ ] Step 2: 增加配置读取，支持 `DATABASE_URL`、`JWT_SECRET_KEY`、`CORS_ORIGINS`。
- [ ] Step 3: 增加数据库 session dependency，但健康检查先不依赖数据库。
- [ ] Step 4: 编写 `test_health.py`，断言健康检查返回 `{"status": "ok"}`。
- [ ] Step 5: 运行 `pytest api/tests/test_health.py -v`，确认通过。
- [ ] Step 6: 运行 `uvicorn main:app --reload`，确认 OpenAPI 页面可访问。

### Task 2: 落地核心 MySQL DDL

**Files:**
- Create: `database/01_schema/01_core_tables_ddl.sql`
- Create: `deploy/docker/mysql/init/01_core_tables_ddl.sql`
- Modify: `database/01_schema/README.md`

- [ ] Step 1: 建立 `users`、`companies`、`company_segments`、`categories`、`parts` 表。
- [ ] Step 2: 建立 `suppliers`、`supplier_capabilities`、`part_alternatives` 表。
- [ ] Step 3: 建立 `rfqs`、`rfq_suppliers`、`quotations`、`audit_items` 表。
- [ ] Step 4: 给账号、型号、供应商、RFQ 状态字段补齐唯一索引和查询索引。
- [ ] Step 5: 将同一份 DDL 复制到 `deploy/docker/mysql/init/01_core_tables_ddl.sql`。
- [ ] Step 6: 运行 `docker compose -f deploy/docker-compose.yml up -d mysql`，确认 MySQL 可启动并完成初始化。

### Task 3: 实现真实认证与角色权限

**Files:**
- Create: `api/app/core/security.py`
- Create: `api/app/models/user.py`
- Create: `api/app/schemas/auth.py`
- Create: `api/app/routers/auth.py`
- Modify: `web/src/stores/auth.ts`
- Modify: `web/src/router/index.ts`
- Test: `api/tests/test_auth.py`

- [ ] Step 1: 后端实现密码哈希、登录 JWT、注册用户和刷新 token。
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
- [ ] Step 2: 调用 `ai.supervisor.stream_procure`，将事件以 `text/event-stream` 返回。
- [ ] Step 3: 保持事件格式与 `web/src/api/sse.ts` 对齐：`start`、`progress`、`result`、`error`、`end`。
- [ ] Step 4: 增加异常处理，AI 失败时返回 SSE `error` 事件，而不是直接断开连接。
- [ ] Step 5: 编写测试，mock supervisor 事件流，断言 SSE 输出包含 `start`、`result`、`end`。
- [ ] Step 6: 设置 `VITE_USE_MOCK=false`，运行前端采购主流程，确认可以收到真实 SSE。

### Task 5: 建立最小种子数据链路

**Files:**
- Create: `data/seed/suppliers.json`
- Create: `data/seed/parts.json`
- Create: `data/seed/alternatives.json`
- Create: `scripts/seed.py`
- Create: `api/tests/test_seed_data.py`

- [ ] Step 1: 准备 5 家供应商、10 个物料、20 条替代关系的 JSON 样例数据。
- [ ] Step 2: `scripts/seed.py` 支持 `--database-url` 参数，导入 MySQL。
- [ ] Step 3: 导入逻辑使用 upsert，重复执行不会产生重复数据。
- [ ] Step 4: 测试验证 seed 后可以查到供应商、物料和替代关系。
- [ ] Step 5: 在 README 或环境文档中补充 seed 命令：`python scripts/seed.py --database-url mysql+pymysql://matchforge:matchforge123@localhost:3306/matchforge`。

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
- Create: `api/app/models/audit.py`
- Create: `api/app/schemas/admin.py`
- Create: `api/app/routers/admin.py`
- Create: `api/app/services/admin_service.py`
- Modify: `web/src/views/P7AdminAudit.vue`
- Test: `api/tests/test_admin.py`

- [ ] Step 1: 后端实现审核队列列表，支持按状态过滤。
- [ ] Step 2: 实现审核通过、驳回、补充来源备注接口。
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
- [ ] Step 3: 所有真实 SSE 调用统一走 `web/src/api/procure.ts`，避免 `api/index.ts` 和 `api/procure.ts` 双入口分叉。
- [ ] Step 4: 更新页面文案，区分 mock 演示模式和真实联调模式。
- [ ] Step 5: 运行 `cd web && npm run build`，确认类型检查通过。

### Task 10: 补齐测试、CI 与仓库卫生

**Files:**
- Modify: `web/package.json`
- Create: `.github/workflows/ci.yml`
- Modify: `.gitignore`
- Create: `web/src/__tests__/auth.spec.ts` if Vitest is introduced
- Create: `web/src/__tests__/router.spec.ts` if Vitest is introduced

- [ ] Step 1: 将 `web/node_modules/.tmp/*.tsbuildinfo` 加入 `.gitignore`。
- [ ] Step 2: 增加前端测试依赖和 `test` 脚本，至少覆盖 auth store 和路由权限。
- [ ] Step 3: 增加 CI，执行 `pytest`、`cd web && npm run build`、`cd web && npm run test`。
- [ ] Step 4: 在 CI 中缓存 Python 和 npm 依赖，保持流水线可重复。
- [ ] Step 5: 运行完整本地检查，确认后端测试、前端测试和构建全部通过。

## 6. 建议实施顺序

第一阶段先完成后端骨架、核心 DDL、认证和 Procure SSE。完成后，采购主流程可以在 `VITE_USE_MOCK=false` 下真实联调。

第二阶段完成种子数据、RFQ 提交、服务端历史、供应商线索和报价。完成后，MVP 具备采购到供应商响应的业务闭环。

第三阶段完成运营审核、前端主流程收敛、测试、CI 和部署初始化。完成后，项目具备试点演示和持续迭代基础。

## 7. 验收标准

- `docker compose -f deploy/docker-compose.yml up -d mysql redis neo4j milvus postgres` 可以启动核心基础设施。
- `python scripts/seed.py --database-url mysql+pymysql://matchforge:matchforge123@localhost:3306/matchforge` 可以重复执行且不产生重复数据。
- `uvicorn main:app --reload` 可以启动 FastAPI，并访问 `/docs` 和 `/api/v1/health`。
- `VITE_USE_MOCK=false` 时，采购端可以完成一次真实 SSE 寻源流程。
- buyer 用户可以提交 RFQ，supplier 用户可以看到线索并报价，admin 用户可以处理审核。
- 非 admin 用户访问 `/admin/audit` 被前端和后端共同拦截。
- `pytest`、`cd web && npm run build`、`cd web && npm run test` 均通过。

## 8. 风险与控制

- AI 结果不稳定：MVP 阶段保留确定性 fallback 和最小 seed 数据，确保演示不依赖大规模数据质量。
- 数据库设计过度膨胀：第一版只覆盖闭环所需字段，不引入复杂 CRM、合同、支付和消息系统。
- 前端双流程继续分裂：所有真实寻源请求统一走一个 SSE API，页面只负责不同交互形态。
- 角色权限遗漏：每个受保护接口后端都做 dependency 检查，前端路由守卫只作为用户体验优化。
- 测试成本上升：优先覆盖认证、SSE、RFQ、供应商线索、审核五条关键路径。

## 9. 自检结果

- Spec coverage: 已覆盖当前分析中的后端缺失、数据库缺失、种子数据缺失、真实联调、认证权限、RFQ/线索/审核闭环、测试和部署问题。
- Placeholder scan: 文档没有使用 TBD、TODO 或“以后实现”作为任务内容；所有任务均给出明确文件路径和验收动作。
- Type consistency: 前端路径、后端模块名、API 方向和现有项目结构保持一致；未要求重构已有 AI agent 结构。
