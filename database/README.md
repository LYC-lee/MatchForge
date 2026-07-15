# MatchForge Database Workspace

本目录承接“电脑全链路数据库 16 小时冲刺执行计划”的数据库交付物，覆盖范围冻结、表结构、字段字典、导入模板、样例数据、验证查询和收尾复盘。

> 冲刺状态：**已完成 16h 交付**（2026-07-15）
> 数据库：`pc_industry`（MySQL 8.0）
> 业务闭环：`需求 -> 物料 -> 替代料 -> 供应商 -> RFQ -> 报价`

## 目录结构

```text
database/
  00_scope/              # 范围冻结、首批品类与产业环节
  01_schema/             # ER 草案、MySQL DDL、索引、导入说明
  02_field_dictionary/   # 字段字典、枚举值、可信度规则
  03_import_templates/   # CSV 导入模板（5 类）
  04_seed_data/          # 首批样例数据（12 份 CSV）
  05_validation/         # 闭环验证查询（3 条 Demo 链路）
  06_handoff/            # 收尾复盘、下一步、未纳入本轮范围
  NAMING_CONVENTIONS.md  # 数据库文件夹/文件/表/字段命名规范
```

## 交付物清单（16h 冲刺）

| 目录 | 文件 | 状态 |
|---|---|---|
| 00_scope | [01_scope_freeze.md](00_scope/01_scope_freeze.md) 范围冻结 | ✅ |
| 00_scope | [03_initial_segments.md](00_scope/03_initial_segments.md) 首批 15 环节 | ✅ |
| 01_schema | [01_industry_segments_ddl.sql](01_schema/01_industry_segments_ddl.sql) 产业环节表 DDL | ✅ |
| 01_schema | [01_core_tables_ddl.sql](01_schema/01_core_tables_ddl.sql) 13 表合并 DDL | ✅ |
| 01_schema | [02_indexes.sql](01_schema/02_indexes.sql) 补充复合索引 | ✅ |
| 01_schema | [03_er_diagram.md](01_schema/03_er_diagram.md) ER 关系图 | ✅ |
| 01_schema | [03_seed_import_notes.md](01_schema/03_seed_import_notes.md) 种子导入说明 | ✅ |
| 02_field_dictionary | [01_field_dictionary.md](02_field_dictionary/01_field_dictionary.md) 13 表字段字典 | ✅ |
| 02_field_dictionary | [01_industry_segments_dictionary.md](02_field_dictionary/01_industry_segments_dictionary.md) 产业环节字段字典 | ✅ |
| 03_import_templates | [01_companies_template.csv](03_import_templates/01_companies_template.csv) ~ [05_rfqs_template.csv](03_import_templates/05_rfqs_template.csv) | ✅ |
| 04_seed_data | [01_industry_segments_seed.csv](04_seed_data/01_industry_segments_seed.csv) ~ [13_quotations_seed.csv](04_seed_data/13_quotations_seed.csv) | ✅ |
| 05_validation | [01_demo_chain_missing_part.sql](05_validation/01_demo_chain_missing_part.sql) 缺货找替代 | ✅ |
| 05_validation | [02_demo_chain_spec_search.sql](05_validation/02_demo_chain_spec_search.sql) 按参数找料 | ✅ |
| 05_validation | [03_demo_chain_bom_risk.sql](05_validation/03_demo_chain_bom_risk.sql) BOM 风险预演 | ✅ |
| 06_handoff | [01_retrospective.md](06_handoff/01_retrospective.md) 收尾复盘 | ✅ |

## 13 张核心表

`industry_segments` · `companies` · `company_segments` · `categories` · `parts` ·
`spec_definitions` · `suppliers` · `supplier_capabilities` · `part_alternatives` ·
`rfqs` · `rfq_suppliers` · `quotations` · `data_sources`

## 样例数据量

15 环节 / 30 公司 / 30 公司-环节 / 10 品类 / 18 规格定义 / 50 物料 / 20 供应商 /
24 供应商能力 / 30 替代关系 / 5 RFQ / 12 RFQ-供应商 / 7 报价 / 10 数据来源。
全部来自可说明来源（产业链分析文档 + `data/suppliers.json` + `data/alternatives.json`）。

## 快速使用

```powershell
# 1. 建库建表（13 表 + 索引）
docker exec -i matchforge-mysql mysql -u root -pmatchforge123 < database/01_schema/01_core_tables_ddl.sql
docker exec -i matchforge-mysql mysql -u root -pmatchforge123 pc_industry < database/01_schema/02_indexes.sql

# 2. 按 FK 顺序导入 12 份种子 CSV（见 01_schema/03_seed_import_notes.md）

# 3. 跑 3 条 Demo 链路验证
docker exec -i matchforge-mysql mysql -u root -pmatchforge123 pc_industry < database/05_validation/01_demo_chain_missing_part.sql
```

## 本轮不做

采购订单、库存批次、生产工单、质量检验、售后 RMA、复杂权限审批流、全量 Neo4j/Milvus 同步。
这些保留 `10_` 起步的扩展目录，见 [06_handoff/01_retrospective.md](06_handoff/01_retrospective.md)。

## 与 matchforge 库的关系

`pc_industry`（本库，13 表）是产业链事实源；`matchforge`（`data/` 层，10 表）是 MVP Spike 的 AI 寻源运营库。
两库 Phase 1-2 通过 `part_id` / `supplier_id` 外键收敛合一，详见 [06_handoff/01_retrospective.md §4](06_handoff/01_retrospective.md)。
