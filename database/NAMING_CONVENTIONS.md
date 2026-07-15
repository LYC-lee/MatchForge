# 数据库命名规范

本文定义 `database/` 目录、数据库文件、数据模板、MySQL 表和字段的命名规范。目标是让业务、数据、后端和 AI 团队使用同一套名字，减少后续迁移和对接成本。

## 1. 总体原则

- 目录名、文件名、表名、字段名统一使用英文小写。
- 多个单词使用 snake_case，例如 `supplier_capabilities`。
- 不使用空格、中文、特殊符号和拼音缩写。
- 名称表达业务含义，不使用 `data1`、`table_new`、`temp_final` 这类临时名。
- 表名使用复数名词，例如 `companies`、`parts`、`rfqs`。
- 字段名使用单数语义，例如 `company_id`、`part_number`。
- 所有关键业务表必须能追溯数据来源和更新时间。

## 2. 目录命名规范

目录使用两位数字前缀表示执行顺序：

```text
00_scope
01_schema
02_field_dictionary
03_import_templates
04_seed_data
05_validation
06_handoff
```

规则：

- `00_` 到 `09_` 用于 16 小时冲刺内的交付物。
- 后续长期扩展从 `10_` 开始，例如 `10_bom`、`11_procurement`。
- 一个目录只放一种类型的交付物，不混放 SQL、CSV、设计文档。

## 3. 文件命名规范

文件名格式：

```text
<order>_<domain>_<artifact>.<ext>
```

示例：

```text
01_core_tables_ddl.sql
02_core_tables_er.md
01_companies_template.csv
02_parts_template.csv
01_companies_seed.csv
01_demo_chain_missing_part.sql
```

规则：

- `order` 使用两位数字，表示同目录内阅读或执行顺序。
- `domain` 表示业务域，例如 `companies`、`parts`、`suppliers`、`rfqs`。
- `artifact` 表示文件用途，例如 `template`、`seed`、`ddl`、`dictionary`、`query`。
- SQL 文件使用 `.sql`。
- 可人工编辑的数据模板优先使用 `.csv`。
- 说明文档使用 `.md`。

## 4. MySQL 表命名规范

第一版核心表统一使用复数名词：

| 表名 | 含义 |
|---|---|
| `industry_segments` | 产业环节 |
| `companies` | 公司主体 |
| `company_segments` | 公司与产业环节关系 |
| `categories` | 物料品类 |
| `parts` | 物料主数据 |
| `spec_definitions` | 品类规格字段定义 |
| `suppliers` | 供应商主体 |
| `supplier_capabilities` | 供应商能力 |
| `part_alternatives` | 替代料关系 |
| `rfqs` | 询价需求 |
| `rfq_suppliers` | RFQ 目标供应商 |
| `quotations` | 报价记录 |
| `data_sources` | 数据来源 |

关系表命名：

```text
<entity_a>_<entity_b>
```

示例：

```text
company_segments
rfq_suppliers
```

如果关系本身有明确业务含义，使用业务名：

```text
supplier_capabilities
part_alternatives
quotations
```

## 5. 字段命名规范

通用字段：

| 字段名 | 说明 |
|---|---|
| `id` | 主键 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |
| `deleted_at` | 软删除时间，第一版可选 |
| `source_name` | 数据来源名称 |
| `source_url` | 数据来源链接 |
| `confidence_level` | 可信度等级 |
| `review_status` | 审核状态 |

外键字段：

```text
<singular_entity>_id
```

示例：

```text
company_id
category_id
supplier_id
part_id
rfq_id
source_id
```

布尔字段：

```text
is_<state>
has_<object>
```

示例：

```text
is_active
is_verified
has_datasheet
```

时间字段：

```text
<event>_at
```

示例：

```text
created_at
updated_at
submitted_at
quoted_at
expires_at
```

数量和金额字段：

```text
quantity
moq
unit_price
target_price
lead_time_days
```

## 6. 枚举值命名规范

枚举值统一使用小写英文。

可信度等级：

```text
official
authorized
cross_checked
third_party
self_reported
manual
unknown
```

审核状态：

```text
pending
approved
rejected
needs_review
```

替代等级：

```text
l1
l2
l3
l4
l5
```

RFQ 状态：

```text
draft
sent
quoted
closed
cancelled
```

生命周期状态：

```text
active
nrnd
eol
obsolete
unknown
```

## 7. CSV 模板命名规范

模板文件放在 `03_import_templates/`：

```text
01_companies_template.csv
02_parts_template.csv
03_supplier_capabilities_template.csv
04_part_alternatives_template.csv
05_rfqs_template.csv
```

模板规则：

- 第一行必须是英文列名。
- 第二行可以放一条示例数据。
- 必须包含 `source_name`、`source_url`、`confidence_level`、`updated_at`。
- JSON 字段用合法 JSON 字符串，例如 `{"capacitance":"1uF","package":"0805"}`。

## 8. 样例数据命名规范

样例数据放在 `04_seed_data/`：

```text
01_industry_segments_seed.csv
02_companies_seed.csv
03_categories_seed.csv
04_parts_seed.csv
05_suppliers_seed.csv
06_part_alternatives_seed.csv
07_rfqs_seed.csv
```

规则：

- 样例数据必须来自可说明来源，不能混入无法解释的 AI 编造事实。
- 如为人工整理，`confidence_level` 使用 `manual`。
- 不确定的数据必须使用 `unknown`，不要猜测。

## 9. SQL 命名规范

DDL 文件放在 `01_schema/`：

```text
01_core_tables_ddl.sql
02_indexes.sql
03_seed_import_notes.md
```

验证查询放在 `05_validation/`：

```text
01_demo_chain_missing_part.sql
02_demo_chain_spec_search.sql
03_demo_chain_bom_risk.sql
```

规则：

- 建表 SQL 使用 `CREATE TABLE IF NOT EXISTS`。
- 字段和表注释优先使用英文，业务说明写在字段字典中。
- 重要查询文件需要在文件顶部说明用途、输入和期望输出。

## 10. 禁止命名

不要使用：

```text
test.csv
new_table.sql
final_final.sql
data.xlsx
临时表.sql
供应商数据.csv
parts2.csv
```

推荐改为：

```text
01_supplier_capabilities_template.csv
01_core_tables_ddl.sql
02_companies_seed.csv
```
