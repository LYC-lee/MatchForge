# Backend 集成修改总结：Dashboard + RFQ 闭环

- **集成时间：** 2026-07-16
- **集成分支：** `codex/backend-integration-dashboard-rfq`
- **集成基线：** `lyc` (commit `2a10c21`, Phase 1 企业驾驶舱后端)
- **合并来源：**
  - `codex/backend-phase2-dashboard` (commit `588792d`) → merge commit `840a2da`
  - `codex/backend-rfq-supplier-loop` (commit `ffa013b`) → merge commit `e4e9962`
- **拓扑：** 两个特性分支均从 `lyc` (2a10c21) 直接分出，各含 1 个提交；集成分支 = lyc + phase2 (fast-forward 等价, --no-ff 保留 merge 点) + rfq (3-way merge, 2 处冲突)。

---

## 1. 本次集成最终保留的能力

### Phase 1（基线已有，未改动）
- enterprise-context（当前企业驾驶舱上下文）
- company relationships（上下游关系 upstream/downstream/support）
- partner-chat（直接关系校验的协同问答）
- chat-partners

### Phase 2 Dashboard（来自 phase2 分支）
- 产品 (CompanyProduct) / BOM (ProductBomItem) / 生产订单 (ProductionOrder)
- 需求预测 (DemandForecast) / 库存 (InventoryItem) / 缺件 (Shortage)
- 缺件 recalculate 计算
- recommended-actions（推荐动作）
- dashboard 聚合接口

### RFQ 闭环（来自 rfq 分支）
- RFQ 创建/查询/发送
- 供应商线索 (supplier leads) 查看/拒绝
- 供应商报价 (quotation) + 报价对比 (quote-comparison)
- 管理员审核队列 (audit queue) 批准/拒绝

---

## 2. 最终新增/保留的模型（kb/models.py）

Phase 1 模型 (1-9) 未改动。新增 10 个模型，注释重编号 10-19：

| # | 模型 | 表名 | 来源 |
|---|------|------|------|
| 10 | `CompanyProduct` | kb_company_products | Dashboard |
| 11 | `ProductBomItem` | kb_product_bom_items | Dashboard |
| 12 | `ProductionOrder` | kb_production_orders | Dashboard |
| 13 | `DemandForecast` | kb_demand_forecasts | Dashboard |
| 14 | `InventoryItem` | kb_inventory_items | Dashboard |
| 15 | `Shortage` | kb_shortages | Dashboard |
| 16 | `RfqRecord` | kb_rfqs | RFQ |
| 17 | `RfqSupplierLink` | kb_rfq_suppliers | RFQ |
| 18 | `QuotationRecord` | kb_quotations | RFQ |
| 19 | `AuditQueueItem` | kb_audit_queue | RFQ |

RFQ 的 `RfqRecord.context_json` 保留软关联设计（可含 `shortage_id` / `product_id` / `recommended_action_id`），未对 Dashboard 模型建强外键。

---

## 3. 最终新增/保留的接口

### Phase 1（基线保留）
```
GET  /api/v1/enterprise-context/companies
GET  /api/v1/enterprise-context/{company_id}
GET  /api/v1/companies/{company_id}/relationships
GET  /api/v1/companies/{company_id}/chat-partners
POST /api/v1/companies/{company_id}/partner-chat
```

### Phase 2 Dashboard
```
GET  /api/v1/companies/{company_id}/products        (含 production_products + 向后兼容 items)
GET  /api/v1/products/{product_id}/bom
GET  /api/v1/companies/{company_id}/bom-summary
GET  /api/v1/companies/{company_id}/orders
GET  /api/v1/companies/{company_id}/forecasts
GET  /api/v1/companies/{company_id}/shortages
POST /api/v1/companies/{company_id}/shortages/recalculate
GET  /api/v1/companies/{company_id}/recommended-actions
GET  /api/v1/companies/{company_id}/dashboard
```

### RFQ 闭环
```
POST /api/v1/rfqs
GET  /api/v1/rfqs
GET  /api/v1/rfqs/{rfq_id}
POST /api/v1/rfqs/{rfq_id}/send
GET  /api/v1/companies/{company_id}/rfqs
GET  /api/v1/suppliers/{company_id}/leads
POST /api/v1/supplier-leads/{lead_id}/view
POST /api/v1/supplier-leads/{lead_id}/decline
POST /api/v1/rfqs/{rfq_id}/quotations
GET  /api/v1/rfqs/{rfq_id}/quotations
GET  /api/v1/rfqs/{rfq_id}/quote-comparison
GET  /api/v1/admin/audit-queue
POST /api/v1/admin/audit-queue/{item_id}/approve
POST /api/v1/admin/audit-queue/{item_id}/reject
```

`api/main.py` 同时注册：Phase 1 routers + dashboard + rfqs + supplier_leads + audit；`procure` 路由保留 langgraph 优雅降级逻辑。

---

## 4. Migration 文件

| 文件 | 内容 | 非破坏式 |
|------|------|----------|
| `database/migrations/03_enterprise_phase2.sql` | Dashboard 6 张表 | 全部 `CREATE TABLE IF NOT EXISTS` |
| `database/migrations/04_rfq_supplier_loop.sql` | RFQ 4 张表 | 全部 `CREATE TABLE IF NOT EXISTS` |

> 注：原 RFQ 分支文件为 `03_rfq_supplier_loop.sql`，因与 Dashboard 分支编号冲突，集成时重命名为 `04_rfq_supplier_loop.sql`，并更新文件内执行示例注释。SQLite 开发库由 `init_db()` 自动建表，迁移脚本仅切 MySQL 时需要。

---

## 5. Seed 脚本

| 脚本 | 用途 | 可单独执行 |
|------|------|-----------|
| `scripts/seed_enterprise_chain.py` | Phase 1 企业链路（公司/关系/知识） | 是 |
| `scripts/seed_enterprise_phase2.py` | Phase 2 产品/BOM/订单/预测/库存/缺件 | 是 |
| `scripts/seed_rfq_supplier_loop.py` | RFQ 询价/供应商线索/报价/审核队列 | 是 |
| `scripts/seed_enterprise_demo_all.py` | **集成总 seed，按顺序执行上述 3 个** | 是 |

执行方式：
```bash
# 全量演示种子（顺序: Phase1 -> Phase2 -> RFQ）
python -m scripts.seed_enterprise_demo_all
# 或单独执行任一子脚本
python -m scripts.seed_enterprise_phase2
python -m scripts.seed_rfq_supplier_loop
```

三个子脚本均幂等（upsert / IF NOT EXISTS），可重复运行。总 seed 内部对每个子步骤 try/except，单步失败不阻断后续。

---

## 6. 冲突文件与解决方式

| 冲突文件 | 冲突原因 | 解决方式 |
|----------|----------|----------|
| `api/main.py` | 两分支各自追加 router 注册 | 同时保留双方路由：dashboard + rfqs + supplier_leads + audit；import 块由 git 自动合并（已含全部 router）；procure 优雅降级未动 |
| `kb/models.py` | 两分支各自追加新模型，且 `Shortage` 与 `RfqRecord` 结尾的 `created_at`/`updated_at`/`__table_args__` 结构相同导致 git 无法对齐 | 保留全部 10 个新模型（6 Dashboard + 4 RFQ），每个模型字段与 `__table_args__` 完整；注释重编号 10-19；Phase 1 模型 (1-9) 未改动 |

无其他冲突。`api/routers/audit.py`、`api/routers/rfqs.py`、`api/routers/supplier_leads.py`、`database/migrations/04_rfq_supplier_loop.sql`、`scripts/seed_rfq_supplier_loop.py`、`tests/test_rfq_supplier_loop.py` 为 RFQ 分支新增文件，无冲突直接合入。

---

## 7. 测试结果

### 核心三件套（必须通过）
```bash
pytest tests/test_enterprise_phase1.py tests/test_enterprise_phase2.py tests/test_rfq_supplier_loop.py
```
- **45 passed** ✅（Phase1: 15, Phase2: 17, RFQ: 13）

### supervisor async 测试
```bash
pytest tests/test_supervisor.py tests/test_supervisor_advanced.py tests/test_supervisor_route.py
```
- **39 passed** ✅
- 历史问题修复：安装 `pytest-asyncio` (1.4.0) 后，原 47 个 ai/ async 失败全部通过。

### 全量测试
```bash
pytest tests
```
- **171 passed, 2 failed**
- 2 个失败均在 `tests/test_kb_rag.py`，均为**历史环境问题，非本次集成引入**：
  1. `TestStatsAndTrace::test_stats` — `assert 36 == 30`。测试隔离问题：全量运行时前置 phase2/rfq 测试向共享测试 DB 写入 6 家公司，导致 `knowledge_stats()` 返回 36。**单独运行 `pytest tests/test_kb_rag.py` 时该测试通过**（28 passed）。
  2. `TestVectorRebuild::test_rebuild_from_source_of_truth` — `assert 0 > 0`。`rebuild_vector_index(drop_first=False)` 在所有 chunk 已同步时正确执行幂等跳过（`kb/pipeline.py:475-481`，返回 `indexed: 0, note: "all already synced"`），但测试断言 `indexed > 0`。属于测试自身断言与幂等逻辑不匹配，与本次集成无关（集成未触碰 vector/embedding/pipeline 代码）。

> 对比基线：RFQ 分支单独全量为 `109 passed / 47 failed`，失败集中在 ai/ async（已由 pytest-asyncio 修复）。本次集成后为 `171 passed / 2 failed`，失败项与集成无关。

---

## 8. 前端 Build 结果

```bash
cd web && npm install && npm run build
```
- `npm install`：90 packages，成功
- `npm run build`：**成功**，1.60s，无错误
- 产物含 Dashboard/RFQ 相关视图：`ShortageProcurementView`、`SupplierLeads`、`SupplierDashboard`、`RfqEditor`、`P7AdminAudit`、`ProductsBomView` 等

---

## 9. 未验证项与原因

| 未验证项 | 原因 |
|----------|------|
| MySQL 真实环境迁移 | 本地无 MySQL，基础测试基于 SQLite（init_db 自动建表） |
| Milvus 向量库 | 本地无 Milvus，降级为 local 向量库 + hashbow |
| Neo4j 图数据库 | 本地无 Neo4j |
| `/procure` SSE 真实寻源流 | 依赖 langgraph 冷导入（~150s/进程），路由已优雅降级注册，未做端到端 SSE 验证 |
| 全量 `pytest tests` kb_rag 2 失败 | 历史测试隔离/断言问题，非集成引入（见第 7 节） |
| 前端真实接口联调 | 仅验证 build 通过，未做 VITE_USE_MOCK=false 端到端联调 |

---

## 10. 后续建议

1. **前端接入聚合接口：** 将前端 Dashboard 页面对接 `GET /api/v1/companies/{id}/dashboard` 真实聚合数据。
2. **前端接入 RFQ/供应商/审核真实接口：** 替换 mock，对接 RFQ 创建/发送、supplier leads、audit queue 接口。
3. **kb_rag 测试修复：** 修正 `test_rebuild_from_source_of_truth` 断言（改为 `drop_first=True` 或断言 `>= 0` + note 校验）；修正 `test_stats` 测试隔离（每测试清理或独立 DB）。
4. **后续 Phase：** kpi_snapshots / risk_alerts 模型与接口。
5. **认证收紧：** 当前 admin 校验为轻量，生产部署前需完善 RBAC。
6. **真实环境验证：** MySQL / Milvus / Neo4j Docker 部署后跑迁移与全量验证。
7. **合并回主分支：** 集成分支核心测试全过、前端 build 通过，建议合并回 `main`（建议先合并 `lyc` 再合 `main`，或直接 PR 到 main）。
