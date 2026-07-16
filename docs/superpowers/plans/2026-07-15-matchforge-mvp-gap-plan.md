# MatchForge MVP Gap Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前“前端可演示 Spike + AI 编排 + 数据底座 + 部分 FastAPI”推进到可真实联调、可闭环演示的 MatchForge MVP。

**Architecture:** 以 FastAPI 作为后端入口，承接 Vue 前端 `/api/v1` 契约，并将 `ai/graph.py` 的 `run_procure_stream()` SSE 流接入 HTTP。MySQL 双 schema（`matchforge` 运营库 + `pc_industry` 事实库）已决策并存；后端需补齐 ORM、路由挂载、前后端契约对齐，以及 RFQ/线索/报价/审核业务闭环。并行存在 `kb/` 知识库 RAG 模块，属于增强能力，不替代 MVP 主链路。

**Tech Stack:** Vue 3 + TypeScript + Pinia + Vite、FastAPI + SQLAlchemy + Pydantic、MySQL 8.0、Redis、Neo4j、Milvus、LangGraph、pytest、vue-tsc。

---

## 1. 当前状态判断

当前项目已从“纯前端 Spike”进入“数据底座就绪 + 后端骨架出现 + 知识库 RAG 并行开发”阶段。采购端仍可通过 mock SSE 完整演示主流程；后端已有 FastAPI 入口和部分路由代码，但尚未与前端真实模式完全对齐。

相对上一版分析，以下工作已经落地：

- `docs/architecture/schema-convergence.md` 已完成双库收敛决策。
- `deploy/docker/mysql/init/01_matchforge_schema.sql` 与 `02_pc_industry_schema.sql` 已补齐 Docker 自动建表。
- `scripts/import_pc_industry_seed.py` 已实现 `pc_industry` CSV 批量导入。
- `api/main.py` 已存在，暴露 `/api/v1/health` 和 `/api/v1/procure/*` 寻源路由。
- `api/routers/procure.py` 已实现 SSE 流式寻源（`/procure/stream`）及 `/spec`、`/match` 非流式接口。
- 新增 `kb/` 知识库模块（16 个文件）、`scripts/kb_cli.py`、`api/routers/chat.py`、`companies.py`、`kb_admin.py`，以及 `tests/test_kb_rag.py`。

项目仍未形成可用 MVP，主要阻塞变为：

- 前后端 Procure SSE **路径与请求体不一致**（前端 `POST /api/v1/procure` + `query`；后端 `POST /api/v1/procure/stream` + `raw_query`）。
- `api/main.py` 仅挂载 `procure` 路由，`auth`、`chat`、`companies`、`kb_admin` 等路由**已实现但未注册**。
- MVP 业务闭环 API（RFQ 提交、供应商线索、运营审核、服务端历史）**仍缺失**。
- 认证仍为前端 localStorage mock；后端 `auth.py` 仅服务知识库 token，未对接 `matchforge.users` 的 buyer/supplier/admin JWT。
- SQLAlchemy 双库 ORM 模型尚未按 schema 收敛文档落地。
- 无 CI；前端无 test 脚本；`api/tests/` 目录不存在。

### 2026-07-15 晚间复勘更新

**新增进展：**

| 模块 | 状态 | 说明 |
|------|------|------|
| Schema 收敛 | ✅ 已决策 | `docs/architecture/schema-convergence.md` |
| Docker MySQL init | ✅ 已补齐 | `deploy/docker/mysql/init/*.sql` |
| pc_industry 种子导入 | ✅ 已实现 | `scripts/import_pc_industry_seed.py` |
| FastAPI 骨架 | ⚠️ 部分 | `api/main.py` + `procure` 路由 |
| Procure SSE 后端 | ⚠️ 部分 | 后端有 `/stream`，与前端契约未对齐 |
| 知识库 RAG | ✅ 新增 | `kb/` + chat/companies/kb_admin 路由（未挂载） |
| AI 单测 | ✅ 16 个文件 | 含 `test_kb_rag.py` |
| MVP 业务 API | ❌ 缺失 | RFQ、supplier、admin 审核、历史 |
| 前端真实接线 | ❌ 大部分 mock | 认证、供应商、审核、RFQ 发送 |
| CI / 前端测试 | ❌ 缺失 | 无 `.github/workflows/`，无 `npm test` |

**当前最大风险：前后端契约分叉**

```
前端 web/src/api/procure.ts:
  POST /api/v1/procure
  body: { query, thread_id, phase, confirmed_spec }

后端 api/routers/procure.py:
  POST /api/v1/procure/stream
  body: { raw_query, thread_id, phase, confirmed_spec }
```

在 `VITE_USE_MOCK=false` 时，即使后端启动，采购主流程仍会因 404 或字段不匹配而失败。

---

## 2. 关键问题分析

### P0 问题：阻塞真实 MVP

- **前后端 Procure 契约未对齐**：路径 `/procure` vs `/procure/stream`，字段 `query` vs `raw_query`。
- **main.py 路由挂载不完整**：`auth`、`chat`、`companies`、`kb_admin` 已实现但未 `include_router`。
- **MVP 认证未接通**：前端 localStorage mock；后端 auth 仅服务 KB，未实现 `matchforge.users` JWT + 角色。
- **RFQ/线索/审核业务 API 缺失**：无 `rfq`、`supplier`、`admin` 路由。
- **双库 ORM 未落地**：schema 收敛文档已有，但 `api/app/models/` 或等效 ORM 结构不存在。

### P1 问题：影响 MVP 完整度

- SSE 双入口：`/app` 走 `procure.ts`（有 mock），`/flow` 走 `index.ts` 的 `procureStream()`（无 mock）。
- 供应商三页、P7 运营审核、HistoryView 仍为页面内 mock 或 localStorage。
- `环境要求.txt` 仍写 `python scripts/seed.py（待开发）`，应同步为 `data/init_all.py` + `scripts/import_pc_industry_seed.py`。
- 知识库 RAG（`kb/`）与 MVP 寻源（`ai/`）是两条并行线，需明确 MVP 演示不依赖 KB 完成度。

### P2 问题：影响质量与上线信心

- 无 `api/tests/`；AI 单测 16 个但不覆盖 HTTP 层。
- 无 CI；前端无 test 脚本。
- 仓库出现 `data/knowledge.db-shm`、`data/knowledge.db-wal`（SQLite WAL 文件），建议加入 `.gitignore`。

---

## 3. 双库事实与收敛方向

> 详见 `docs/architecture/schema-convergence.md`（**已决策**）

| 库 | Schema 文件 | 表数 | 定位 |
|---|---|---:|---|
| `matchforge` | `data/mysql_schema.sql` | 10 | 运营库：用户、认证、RFQ 运营状态、线索 |
| `pc_industry` | `database/01_schema/01_core_tables_ddl.sql` | 13 | 事实库：公司、物料、替代、供应商能力、RFQ、报价 |

MVP 第一阶段：**双库并存**，认证/线索写 `matchforge`，事实数据读写 `pc_industry`。审核复用 `supplier_capabilities.audit_status`。

---

## 4. 目标 MVP 范围

- 采购用户登录 → 自然语言寻源 → SSE 返回规格/替代/匹配/RFQ/线索分级。
- 确认 RFQ → 发送给候选供应商。
- 供应商查看线索 → 提交报价。
- 管理员审核供应商能力或替代料。
- 服务端历史记录。

暂不追求：KB RAG 全量上线、复杂 CRM、支付、库存、质检。

---

## 5. 文件结构规划

### 后端 API（已有 vs 待建）

| 文件 | 状态 | 说明 |
|------|------|------|
| `api/main.py` | ✅ 已有 | 需挂载全部 router |
| `api/routers/procure.py` | ✅ 已有 | 需对齐前端契约 |
| `api/routers/auth.py` | ⚠️ 已有 | KB auth，需扩展 MVP JWT |
| `api/routers/chat.py` | ⚠️ 已有 | KB RAG，未挂载 |
| `api/routers/companies.py` | ⚠️ 已有 | KB，未挂载 |
| `api/routers/kb_admin.py` | ⚠️ 已有 | KB 管理，未挂载 |
| `api/routers/rfq.py` | ❌ 待建 | RFQ CRUD + 提交 |
| `api/routers/supplier.py` | ❌ 待建 | 线索 + 报价 |
| `api/routers/admin.py` | ❌ 待建 | 审核队列 |
| `api/app/db/session.py` 或等效 | ❌ 待建 | 双 engine |
| `api/app/models/*.py` 或等效 | ❌ 待建 | 双库 ORM |

### 数据与部署（大部分已完成）

| 文件 | 状态 |
|------|------|
| `docs/architecture/schema-convergence.md` | ✅ |
| `deploy/docker/mysql/init/01_matchforge_schema.sql` | ✅ |
| `deploy/docker/mysql/init/02_pc_industry_schema.sql` | ✅ |
| `scripts/import_pc_industry_seed.py` | ✅ |
| `data/init_all.py` | ✅ |
| `api/db_init.py` | ✅（AI 工具用简化 init） |

### 知识库（并行模块，非 MVP 阻塞）

| 文件 | 状态 |
|------|------|
| `kb/`（16 文件） | ✅ |
| `scripts/kb_cli.py` | ✅ |
| `tests/test_kb_rag.py` | ✅ |

---

## 6. 任务进度快照

| Task | 进度 | 判断 |
|---|---:|---|
| Task 0 双库收敛 | **100%** | `schema-convergence.md` 已决策 |
| Task 1 FastAPI 骨架 | **60%** | main + health + procure；其他 router 未挂载 |
| Task 2 Schema + Docker init | **85%** | init SQL 已有；ORM 缺失 |
| Task 3 认证权限 | **25%** | KB auth 有；MVP JWT + 前端接线缺失 |
| Task 4 Procure SSE | **70%** | 后端有 stream；前后端契约未对齐 |
| Task 5 种子自动化 | **90%** | `init_all.py` + `import_pc_industry_seed.py` 已有 |
| Task 6 RFQ/历史 | **0%** | 前后端均缺 |
| Task 7 供应商线索/报价 | **0%** | 页面 mock |
| Task 8 运营审核 | **0%** | 页面 mock |
| Task 9 前端主流程收敛 | **15%** | 主路径 mock 可用；真实模式不通 |
| Task 10 测试/CI | **20%** | AI + KB 单测 16 个；无 API test、无 CI |

---

## 7. 实施任务

### Task 0: 双库 Schema 收敛决策 ✅ 已完成

- [x] `docs/architecture/schema-convergence.md` 已写入双库职责、跨库关联键、审核模型、ORM 分配、Docker init、种子命令。

### Task 1: 完善 FastAPI 应用骨架

**Files:**
- Modify: `api/main.py`
- Modify: `api/routers/__init__.py`
- Create: `api/tests/test_health.py`

- [ ] Step 1: 在 `main.py` 中挂载 `auth`、`chat`、`companies`、`kb_admin` router（KB 能力可选启用）。
- [ ] Step 2: 预留 `rfq`、`supplier`、`admin` router 挂载位。
- [ ] Step 3: 编写 `test_health.py`，断言 `/api/v1/health` 返回 `{"status": "ok"}`。
- [ ] Step 4: 运行 `uvicorn api.main:main --reload`，确认 OpenAPI 页面列出全部已挂载路由。

### Task 2: 落地双库 ORM 与 Docker 验证

**Files:**
- Create: `api/db/session.py`（或 `api/app/db/session.py`）
- Create: `api/models/` 最小 ORM
- Review: `deploy/docker/mysql/init/*.sql`

- [ ] Step 1: 实现 `MATCHFORGE_DATABASE_URL` 和 `PC_INDUSTRY_DATABASE_URL` 双 engine。
- [ ] Step 2: 建立最小 ORM：`User`、`Enterprise`、`Lead`（matchforge）；`Part`、`Supplier`、`SupplierCapability`、`RFQ`、`Quotation`（pc_industry）。
- [ ] Step 3: 运行 `docker compose -f deploy/docker-compose.yml up -d mysql`，验证两个 schema 自动初始化。
- [ ] Step 4: 运行 `python data/init_all.py` 和 `python scripts/import_pc_industry_seed.py`，确认种子数据可导入。

### Task 3: 对齐 Procure SSE 前后端契约（P0 紧急）

**Files:**
- Modify: `api/routers/procure.py` 或 `web/src/api/procure.ts`
- Modify: `web/src/api/sse.ts`（如需要）

- [ ] Step 1: 统一路径为 `POST /api/v1/procure`（后端增加 alias）或前端改为 `/procure/stream`（二选一，推荐后端加 alias 兼容前端）。
- [ ] Step 2: 统一请求体字段：后端同时接受 `query` 和 `raw_query`。
- [ ] Step 3: 验证 SSE 事件格式一致：`start`、`progress`、`result`、`error`、`end`。
- [ ] Step 4: `VITE_USE_MOCK=false` 下跑通 `/app` -> `/procure/:id` 完整寻源流程。

### Task 4: 实现 MVP 认证与角色权限

**Files:**
- Modify: `api/routers/auth.py`
- Modify: `web/src/stores/auth.ts`
- Modify: `web/src/router/index.ts`
- Create: `api/tests/test_auth.py`

- [ ] Step 1: 基于 `matchforge.users` 实现注册、登录、JWT 刷新（与 KB auth 分离或共存）。
- [ ] Step 2: JWT claims 携带 `buyer`/`supplier`/`admin` 角色。
- [ ] Step 3: 前端 `VITE_USE_MOCK=false` 时调用真实 auth API。
- [ ] Step 4: 路由 meta 增加角色守卫。
- [ ] Step 5: 编写 auth API 测试。

### Task 5: 实现 RFQ 提交与历史记录

**Files:**
- Create: `api/routers/rfq.py`
- Modify: `web/src/api/index.ts`
- Modify: `web/src/components/procure/RfqEditor.vue`
- Modify: `web/src/views/HistoryView.vue`、`P6History.vue`

- [ ] Step 1: 后端 RFQ 创建、提交、列表、详情。
- [ ] Step 2: 提交时写 `rfqs` + `rfq_suppliers`，状态 `draft` -> `sent`。
- [ ] Step 3: 前端“发送 RFQ”调用 `submitRfq`。
- [ ] Step 4: 历史页面读服务端。

### Task 6: 接入供应商线索与报价

**Files:**
- Create: `api/routers/supplier.py`
- Modify: `web/src/views/supplier/Supplier*.vue`

- [ ] Step 1: 供应商线索列表（按当前 supplier 用户过滤）。
- [ ] Step 2: 报价/回复接口，写 `quotations`。
- [ ] Step 3: 供应商页面移除 mock。

### Task 7: 接入运营审核

**Files:**
- Create: `api/routers/admin.py`
- Modify: `web/src/views/P7AdminAudit.vue`

- [ ] Step 1: 审核队列基于 `supplier_capabilities.audit_status`。
- [ ] Step 2: 通过/驳回/备注接口。
- [ ] Step 3: P7 页面接真实 API。

### Task 8: 统一前端主流程

**Files:**
- Modify: `web/src/views/P1Home.vue`
- Modify: `web/src/api/index.ts`

- [ ] Step 1: P 系列统一走 `web/src/api/procure.ts`。
- [ ] Step 2: 区分 mock/真实模式文案。
- [ ] Step 3: `npm run build` 通过。

### Task 9: 补齐测试、CI 与文档同步

**Files:**
- Create: `api/tests/test_procure.py`、`test_rfq.py` 等
- Create: `.github/workflows/ci.yml`
- Modify: `web/package.json`、`.gitignore`、`环境要求.txt`、`README.md`

- [ ] Step 1: 增加 `api/tests/` 覆盖 health、procure SSE、auth。
- [ ] Step 2: 前端增加 Vitest + `test` 脚本。
- [ ] Step 3: CI 执行 `pytest tests`、`pytest api/tests`、`npm run build`。
- [ ] Step 4: 同步 `环境要求.txt` 启动命令和种子导入说明。
- [ ] Step 5: `.gitignore` 补充 `*.db-shm`、`*.db-wal`。

---

## 8. 前端真实接线清单

| 页面/模块 | 当前状态 | 目标 API | 阻塞原因 |
|---|---|---|---|
| `auth.ts` | localStorage mock | `/api/v1/auth/*` | MVP JWT 未实现 |
| `/app` -> `/procure/:id` | mock 可用；real 不通 | `POST /api/v1/procure` SSE | 路径/字段不匹配 |
| `/flow` / `P1Home` | 走 `index.ts`，无 mock | 统一到 `procure.ts` | 双入口 |
| `RfqEditor` | emit 本地 sent | `submitRfq` | 后端缺失 |
| `HistoryView` | localStorage | 服务端 RFQ 历史 | 后端缺失 |
| `Supplier*` | 页面 mock | `/api/v1/supplier/*` | 后端缺失 |
| `P7AdminAudit` | 页面 mock | `/api/v1/admin/*` | 后端缺失 |
| KB chat/companies | 未接线 | `/api/v1/chat/*`、`/companies/*` | router 未挂载 |

---

## 9. 五人分工建议

### A. 后端负责人：FastAPI 路由挂载与 MVP 业务 API

- **当前重点：** Task 1（挂载 router）、Task 3（契约对齐）、Task 4-7（RFQ/supplier/admin）。
- 与前端负责人优先对齐 Procure SSE 路径和请求体。
- 验收：`VITE_USE_MOCK=false` 采购主流程可跑通。

### B. 数据负责人：ORM 落地与种子验证

- **当前重点：** Task 2（双库 ORM）、Task 5 种子命令文档同步。
- Schema 收敛已完成，转向 ORM 实现和 Docker init 验证。
- 验收：双库 ORM 可查询，`init_all.py` + `import_pc_industry_seed.py` 可重复执行。

### C. AI 接入负责人：Procure SSE 与 Agent 数据源

- **当前重点：** 协助 Task 3 契约对齐；确保 `ai/graph.py` 的 `run_procure_stream()` 事件格式稳定。
- 逐步让 alternatives/match 读取 `pc_industry`、Neo4j、Milvus 事实数据。
- 验收：SSE 事件 `start/progress/result/end` 与前端 `sse.ts` 一致。

### D. 前端负责人：真实模式接线

- **当前重点：** Task 3（procure.ts 对齐）、Task 5-8 前端部分、Task 9（P 系列收敛）。
- 移除供应商/审核/RFQ mock，接入真实 API。
- 验收：buyer/supplier/admin 三类用户完成各自核心动作。

### E. 测试与交付负责人：CI 与文档同步

- **当前重点：** Task 9（api/tests、CI、文档、`gitignore`）。
- 维护手动验收清单。
- 验收：CI 绿灯；`环境要求.txt` 与 README 启动步骤准确。

### 并行节奏（更新版）

- **第 1 天（当前）：** 后端对齐 Procure 契约 + 挂载已有 router；数据落地最小 ORM；前端确认 mock/real 切换。
- **第 2-3 天：** MVP 认证 + RFQ 提交 + 服务端历史；供应商线索 API。
- **第 4-5 天：** 运营审核 + 前端全面接线 + API 测试。
- **第 6 天：** 端到端演示回归；KB RAG 作为加分项，不阻塞 MVP。

---

## 10. P4 数据交付物交接清单

P4 数据工作**已完成**，后续重点是 ORM 消费和导入脚本验证：

- `docs/architecture/schema-convergence.md` ✅
- `data/mysql_schema.sql`、`data/init_all.py` ✅
- `database/01_schema/01_core_tables_ddl.sql` ✅
- `deploy/docker/mysql/init/*.sql` ✅
- `scripts/import_pc_industry_seed.py` ✅
- `database/04_seed_data/*.csv` ✅
- `database/05_validation/*.sql` ✅
- `database/06_handoff/01_retrospective.md` ✅

---

## 11. 知识库 RAG 模块（并行，非 MVP 阻塞）

| 组件 | 状态 | 说明 |
|------|------|------|
| `kb/` 模块 | ✅ 16 文件 | 公司知识生成、RAG 检索、向量索引 |
| `scripts/kb_cli.py` | ✅ | init/generate/incremental/rebuild-index/stats |
| `api/routers/chat.py` | ⚠️ 未挂载 | 单公司/多公司 RAG 问答 |
| `api/routers/companies.py` | ⚠️ 未挂载 | 公司列表/详情/知识状态 |
| `api/routers/kb_admin.py` | ⚠️ 未挂载 | 知识生成/重建索引/任务状态 |
| `tests/test_kb_rag.py` | ✅ | KB RAG 单测 |

KB 模块可独立演示，但不替代 MVP 寻源主链路。MVP 演示优先级：Procure SSE > RFQ 闭环 > KB RAG。

---

## 12. 建议实施顺序

**Phase 0 ✅ 已完成：** 数据底座、schema 收敛、Docker init、种子导入脚本。

**Phase 1 🔴 当前最关键：** Procure 契约对齐 + router 挂载 + 双库 ORM + MVP 认证。完成后 `VITE_USE_MOCK=false` 采购主流程可联调。

**Phase 2：** RFQ 提交、服务端历史、供应商线索/报价、运营审核。完成后 MVP 业务闭环。

**Phase 3：** 前端收敛、API 测试、CI、文档同步、KB RAG 挂载（可选）。

---

## 13. 验收标准

- [x] `docs/architecture/schema-convergence.md` 存在且内容完整。
- [x] `deploy/docker/mysql/init/` 包含双库 init SQL。
- [x] `python data/init_all.py` 和 `python scripts/import_pc_industry_seed.py` 可执行。
- [ ] `POST /api/v1/procure`（或对齐后的路径）前后端契约一致，`VITE_USE_MOCK=false` 采购流程可跑通。
- [ ] `uvicorn api.main:main --reload` 启动后 OpenAPI 列出 auth/procure/rfq/supplier/admin 路由。
- [ ] buyer 提交 RFQ → supplier 看到线索并报价 → admin 处理审核。
- [ ] 非 admin 访问 `/admin/audit` 被前后端共同拦截。
- [ ] `pytest tests` + `pytest api/tests` + `npm run build` 通过。
- [ ] `环境要求.txt` 启动步骤与当前脚本一致。

---

## 14. 风险与控制

- **契约分叉：** 优先统一 Procure SSE 路径和字段，再扩展其他 API。
- **双轨后端：** MVP 寻源（`ai/` + procure router）与 KB RAG（`kb/` + chat/companies router）需明确边界，避免 main.py 混乱。
- **双库分裂：** 通过 service/repository 层隔离，禁止路由直接感知 schema 细节。
- **演示依赖 KB：** MVP 演示不依赖 KB 完成度；KB 作为 Phase 3 加分项。
- **文档滞后：** `环境要求.txt` 和 README 需与 `init_all.py`、`import_pc_industry_seed.py` 同步。

---

## 15. 自检结果

- Spec coverage: 已覆盖最新复勘后的 schema 收敛完成、FastAPI 部分落地、Procure 契约分叉、KB RAG 并行模块、任务进度更新、五人分工调整。
- Placeholder scan: 无 TBD/TODO 占位；已完成项已标记 `[x]`。
- Type consistency: SSE 函数对齐 `ai/graph.py` 的 `run_procure_stream()`；种子路径对齐 `data/init_all.py` 和 `scripts/import_pc_industry_seed.py`。

---

## 16. 2026-07-16 集成进展更新（Dashboard + RFQ 后端集成）

> 本章为追加章节，不改动原文。记录两个后端特性分支集成进展。详见 [backend-integration-dashboard-rfq-summary.md](backend-integration-dashboard-rfq-summary.md)。

### 16.1 集成分支状态

- **集成分支：** `codex/backend-integration-dashboard-rfq`
- **基线：** `lyc` (2a10c21, Phase 1 已完成)
- **合并来源：**
  - `codex/backend-phase2-dashboard` (588792d) -> merge commit 840a2da
  - `codex/backend-rfq-supplier-loop` (ffa013b) -> merge commit e4e9962
- **冲突解决：** 2 处
  - `api/main.py`：同时保留 dashboard + rfqs + supplier_leads + audit 路由注册，procure 优雅降级保留。
  - `kb/models.py`：保留全部 10 个新模型（6 Dashboard + 4 RFQ），注释重编号 10-19，Phase 1 模型未动。
- **migration 重命名：** `03_rfq_supplier_loop.sql` -> `04_rfq_supplier_loop.sql`（避免与 Dashboard 分支 03 编号冲突）。
- **新增总 seed：** `scripts/seed_enterprise_demo_all.py`（顺序执行 Phase1 + Phase2 + RFQ）。

### 16.2 Phase 1 已完成

- enterprise-context（当前企业驾驶舱上下文）
- company relationships（upstream / downstream / support）
- partner-chat（直接关系校验协同问答）
- chat-partners

### 16.3 Phase 2 已完成（Dashboard 数据能力）

- CompanyProduct / ProductBomItem / ProductionOrder / DemandForecast / InventoryItem / Shortage 六个模型
- products（含 `production_products` + 向后兼容 `items`）/ bom / bom-summary / orders / forecasts / shortages
- shortages/recalculate 缺件物化计算
- recommended-actions 推荐动作
- dashboard 聚合接口

### 16.4 RFQ 闭环已完成

- RfqRecord / RfqSupplierLink / QuotationRecord / AuditQueueItem 四个模型
- RFQ 创建/查询/发送
- supplier leads 查看/拒绝
- quotations 报价 + quote-comparison 对比
- admin audit queue 批准/拒绝
- `context_json` 软关联（shortage_id / product_id / recommended_action_id），未对 Dashboard 建强外键

### 16.5 当前测试状态

- **核心三件套：** `pytest tests/test_enterprise_phase1.py tests/test_enterprise_phase2.py tests/test_rfq_supplier_loop.py` -> **45 passed**（Phase1: 15, Phase2: 17, RFQ: 13）
- **supervisor async：** 39 passed（安装 `pytest-asyncio` 后历史 47 个 ai/ async 失败全部修复）
- **全量 `pytest tests`：** 171 passed / 2 failed
  - 2 failed 均在 `test_kb_rag.py`，属**历史环境问题，非本次集成引入**：
    - `test_stats`（36==30）：测试隔离问题，单独运行通过。
    - `test_rebuild_from_source_of_truth`（indexed 0）：`rebuild_vector_index(drop_first=False)` 幂等跳过已同步 chunk，测试断言与逻辑不匹配。

### 16.6 当前前端 build 状态

- `cd web && npm install && npm run build` -> **成功**（1.60s，无错误）
- 产物含 ShortageProcurementView / SupplierLeads / SupplierDashboard / RfqEditor / P7AdminAudit / ProductsBomView 等视图。

### 16.7 已知风险

- **langgraph 冷导入慢：** 约 150s/进程，非失败；procure 路由已优雅降级。
- **MySQL / Milvus / Neo4j 未在本地真实验证：** 基础测试基于 SQLite + local 向量库 + hashbow 降级。
- **全量测试 ai/ async 历史失败：** 已通过安装 `pytest-asyncio` 解决；剩余 2 个 kb_rag 失败为历史测试隔离/断言问题，与本次集成无关。
- **`kb/models.py` 模型注释重编号：** 仅注释序号 10-19 调整，不影响表名/字段/逻辑。

### 16.8 下一阶段建议

1. 前端接入 `/dashboard` 聚合接口（替换 mock）。
2. 前端接入 RFQ / supplier / audit 真实接口。
3. 后续再考虑 `kpi_snapshots` / `risk_alerts` 模型与接口。
4. 后续再考虑认证收紧（当前 admin 校验轻量）和生产部署安全。
5. 后续再验证 MySQL / Milvus / Neo4j 真实环境（Docker 部署 + 迁移脚本）。
6. 修复 kb_rag 2 个历史测试（test_rebuild 断言 + test_stats 隔离）。
7. 集成分支核心测试全过 + 前端 build 通过，建议合并回 `main`。
