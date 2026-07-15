# MatchForge Database Workspace

本目录用于承接“电脑全链路数据库 16 小时冲刺执行计划”的数据库交付物，包括范围冻结、表结构、字段字典、导入模板、样例数据、验证查询和后续扩展记录。

## 目录结构

```text
database/
  00_scope/              # 0-1h：范围冻结、首批品类、首批产业环节
  01_schema/             # 1-3h、10-12h：ER 草案、MySQL DDL、表关系说明
  02_field_dictionary/   # 3-5h：字段字典、枚举值、数据可信度规则
  03_import_templates/   # 5-7h：CSV/Excel 导入模板
  04_seed_data/          # 7-10h：首批样例数据
  05_validation/         # 12-14h：闭环验证查询和验收记录
  06_handoff/            # 14-16h：收尾复盘、下一步、未纳入本轮范围
  NAMING_CONVENTIONS.md  # 数据库文件夹、文件、表、字段命名规范
```

## 当前冲刺范围

16 小时内只支撑最小闭环：

```text
需求 -> 物料 -> 替代料 -> 供应商 -> RFQ
```

本轮不实现完整采购、库存、生产、质量、售后流程，只保留后续扩展边界。

## 使用方式

1. 先阅读 `NAMING_CONVENTIONS.md`，确认目录、文件、表、字段命名方式。
2. 在 `00_scope/` 固化首批品类和产业环节。
3. 在 `01_schema/` 编写 ER 草案和 MySQL DDL。
4. 在 `02_field_dictionary/` 编写字段字典。
5. 在 `03_import_templates/` 放 CSV/Excel 模板。
6. 在 `04_seed_data/` 放首批样例数据。
7. 在 `05_validation/` 放 Demo 查询和验收记录。
8. 在 `06_handoff/` 记录本轮未做内容和下一步任务。
