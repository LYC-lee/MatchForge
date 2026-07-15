# 03 - 种子数据导入说明（03_seed_import_notes.md）

> 数据库：`pc_industry`
> 种子目录：[../04_seed_data/](../04_seed_data/)
> 规范：[../NAMING_CONVENTIONS.md](../NAMING_CONVENTIONS.md) §8

## 1. 导入前置

1. 已执行 [01_core_tables_ddl.sql](01_core_tables_ddl.sql) + [02_indexes.sql](02_indexes.sql)，13 张表已建
2. MySQL 客户端能访问 `pc_industry` 库（docker-compose 默认 `matchforge-mysql`，root 密码 `matchforge123`）
3. CSV 均为 UTF-8 with BOM（utf-8-sig），Excel 与 `LOAD DATA INFILE` 均可识别

## 2. 导入顺序（按外键依赖）

必须按下面顺序导入，否则外键约束会失败：

| 顺序 | 文件 | 表 | 依赖 |
|---:|---|---|---|
| 1 | `01_industry_segments_seed.csv` | industry_segments | 无（segment_code 为业务键） |
| 2 | `03_categories_seed.csv` | categories | 无 |
| 3 | `02_companies_seed.csv` | companies | 无 |
| 4 | `09_company_segments_seed.csv` | company_segments | companies, industry_segments(segment_code) |
| 5 | `08_spec_definitions_seed.csv` | spec_definitions | categories |
| 6 | `04_parts_seed.csv` | parts | categories |
| 7 | `06_part_alternatives_seed.csv` | part_alternatives | parts(×2) |
| 8 | `05_suppliers_seed.csv` | suppliers | companies（可空） |
| 9 | `10_supplier_capabilities_seed.csv` | supplier_capabilities | suppliers, categories |
| 10 | `07_rfqs_seed.csv` | rfqs | parts（可空） |
| 11 | `12_rfq_suppliers_seed.csv` | rfq_suppliers | rfqs, suppliers |
| 12 | `13_quotations_seed.csv` | quotations | rfqs, suppliers |
| 13 | `11_data_sources_seed.csv` | data_sources | 无 |

## 3. 导入方式

### 方式 A：mysqlcli + LOAD DATA（推荐）

```powershell
# 每张表一条命令。注意：CSV 含 BOM，用 CHARACTER SET utf8mb4 忽略 BOM。
docker exec -i matchforge-mysql mysql -u root -pmatchforge123 pc_industry -e "
LOAD DATA LOCAL INFILE '/dev/stdin'
INTO TABLE industry_segments
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' LINES TERMINATED BY '\n'
IGNORE 1 LINES
(segment_code,segment_name_cn,segment_name_en,chain_position,parent_code,level,description,typical_products,typical_companies,data_scope,source_name,source_url,confidence_level,sort_order,is_active,updated_at)
SET created_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP;
" < database/04_seed_data/01_industry_segments_seed.csv
```

> 注：`typical_products` / `typical_companies` 为 JSON 列，`LOAD DATA` 会以字符串写入，MySQL 自动校验 JSON 合法性。含 BOM 的首列名需注意；若首行 BOM 导致列名错位，可先用 `sed -i '1s/^\xEF\xBB\xBF//'` 去 BOM 或用方式 B。

### 方式 B：Python 脚本批量导入（最稳）

```python
# 示例：用 pymysql + csv 逐行 INSERT，自动处理 BOM/JSON/None
import csv, json, pymysql
conn = pymysql.connect(host="127.0.0.1", user="root", password="matchforge123", database="pc_industry", charset="utf8mb4")
# 按 §2 顺序遍历 CSV，跳过表头，None 空串处理，JSON 字段 json.dumps
# ...（建议封装为 database/scripts/import_seed.py，下一阶段实现）
```

### 方式 C：phpMyAdmin / DBeaver 图形导入

逐表导入 CSV，选 UTF-8、逗号分隔、双引号限定、跳过首行。

## 4. 验证

```sql
USE pc_industry;
SELECT 'industry_segments' t, COUNT(*) n FROM industry_segments
UNION ALL SELECT 'companies', COUNT(*) FROM companies
UNION ALL SELECT 'company_segments', COUNT(*) FROM company_segments
UNION ALL SELECT 'categories', COUNT(*) FROM categories
UNION ALL SELECT 'spec_definitions', COUNT(*) FROM spec_definitions
UNION ALL SELECT 'parts', COUNT(*) FROM parts
UNION ALL SELECT 'suppliers', COUNT(*) FROM suppliers
UNION ALL SELECT 'supplier_capabilities', COUNT(*) FROM supplier_capabilities
UNION ALL SELECT 'part_alternatives', COUNT(*) FROM part_alternatives
UNION ALL SELECT 'rfqs', COUNT(*) FROM rfqs
UNION ALL SELECT 'rfq_suppliers', COUNT(*) FROM rfq_suppliers
UNION ALL SELECT 'quotations', COUNT(*) FROM quotations
UNION ALL SELECT 'data_sources', COUNT(*) FROM data_sources;
-- 期望: 15 / 30 / 30 / 10 / 18 / 50 / 20 / 24 / 30 / 5 / 12 / 7 / 10
```

导入后跑 [../05_validation/](../05_validation/) 下 3 条 Demo 查询验证闭环。

## 5. 清空重导

```sql
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE quotations; TRUNCATE rfq_suppliers; TRUNCATE rfqs;
TRUNCATE supplier_capabilities; TRUNCATE suppliers;
TRUNCATE part_alternatives; TRUNCATE parts;
TRUNCATE spec_definitions; TRUNCATE company_segments;
TRUNCATE companies; TRUNCATE categories; TRUNCATE industry_segments; TRUNCATE data_sources;
SET FOREIGN_KEY_CHECKS = 1;
```
