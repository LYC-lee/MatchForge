# 电脑全链路数据库 - 字段字典

> 数据库：`pc_industry` (MySQL 8.0)
> 覆盖范围：13 张核心表
> 更新日期：2026-07-15
> 规范对齐：[../NAMING_CONVENTIONS.md](../NAMING_CONVENTIONS.md)（枚举值统一小写）
> DDL 对应：[../01_schema/01_core_tables_ddl.sql](../01_schema/01_core_tables_ddl.sql)

---

## 目录

1. [industry_segments - 产业环节表](#1-industry_segments)
2. [companies - 公司主体表](#2-companies)
3. [company_segments - 公司-产业环节关系表](#3-company_segments)
4. [categories - 物料品类表](#4-categories)
5. [parts - 物料主数据表](#5-parts)
6. [spec_definitions - 品类规格字段定义表](#6-spec_definitions)
7. [suppliers - 供应商主体表](#7-suppliers)
8. [supplier_capabilities - 供应商能力表](#8-supplier_capabilities)
9. [part_alternatives - 替代料关系表](#9-part_alternatives)
10. [rfqs - RFQ询价单表](#10-rfqs)
11. [rfq_suppliers - RFQ-供应商关联表](#11-rfq_suppliers)
12. [quotations - 报价记录表](#12-quotations)
13. [data_sources - 数据来源表](#13-data_sources)

---

## 1. industry_segments

**表名：** `industry_segments` · **中文名：** 产业环节表
> 权威定义见 [../01_schema/01_industry_segments_ddl.sql](../01_schema/01_industry_segments_ddl.sql)；`segment_code` 为稳定业务键，被 `company_segments` 引用。

| 中文名 | 英文名 | 类型 | 是否必填 | 示例值 |
|--------|--------|------|----------|--------|
| 主键ID | id | BIGINT AUTO_INCREMENT | 是(自增) | 1 |
| 环节编码 | segment_code | VARCHAR(80) | 是(唯一) | passive_components |
| 环节中文名 | segment_name_cn | VARCHAR(120) | 是 | 被动元件 |
| 环节英文名 | segment_name_en | VARCHAR(160) | 是 | Passive Components |
| 链路位置 | chain_position | VARCHAR(20) | 是 | upstream |
| 父环节编码 | parent_code | VARCHAR(80) | 否 | NULL |
| 层级 | level | TINYINT | 否(默认1) | 1 |
| 环节说明 | description | TEXT | 否 | MLCC/电阻等被动元件制造环节 |
| 典型产品 | typical_products | JSON | 否 | ["MLCC","chip_resistor"] |
| 典型公司 | typical_companies | JSON | 否 | ["Murata","TDK","Yageo"] |
| 数据范围 | data_scope | VARCHAR(50) | 否(默认sprint_16h) | sprint_16h |
| 数据来源 | source_name | VARCHAR(120) | 否(默认manual_research) | manual_research |
| 来源链接 | source_url | VARCHAR(500) | 否 | NULL |
| 数据可信度 | confidence_level | VARCHAR(30) | 否(默认manual) | manual |
| 排序 | sort_order | INT | 否(默认0) | 40 |
| 是否启用 | is_active | BOOLEAN | 否(默认TRUE) | TRUE |
| 创建时间 | created_at | DATETIME | 否(默认) | 2026-07-15 10:00:00 |
| 更新时间 | updated_at | DATETIME | 否(默认) | 2026-07-15 10:30:00 |

> `chain_position` 取值：`upstream` 上游 / `midstream` 中游 / `downstream` 下游 / `support` 支撑服务。首批 15 个一级环节见 [../00_scope/03_initial_segments.md](../00_scope/03_initial_segments.md)。

---

## 2. companies

**表名：** `companies` · **中文名：** 公司主体表

| 中文名 | 英文名 | 类型 | 是否必填 | 示例值 |
|--------|--------|------|----------|--------|
| 主键ID | id | INT AUTO_INCREMENT | 是(自增) | 1 |
| 公司名称 | name | VARCHAR(200) | 是 | 村田制作所(Murata) |
| 英文名称 | name_en | VARCHAR(200) | 否 | Murata Manufacturing Co., Ltd. |
| 别名/简称 | name_alias | VARCHAR(500) | 否 | 村田/Murata |
| 国家 | country | VARCHAR(50) | 否 | 日本 |
| 地区 | region | VARCHAR(50) | 否 | 京都 |
| 官网 | website | VARCHAR(500) | 否 | https://www.murata.com |
| 公司简介 | description | TEXT | 否 | 全球MLCC龙头，份额约40% |
| 数据可信度 | confidence_level | ENUM | 否(默认unknown) | official |
| 数据来源名称 | source_name | VARCHAR(200) | 否 | 公司官网 |
| 数据来源链接 | source_url | VARCHAR(500) | 否 | https://www.murata.com/en-global/about |
| 创建时间 | created_at | DATETIME | 否(默认) | 2026-07-15 10:00:00 |
| 更新时间 | updated_at | DATETIME | 否(默认) | 2026-07-15 10:30:00 |

> `confidence_level` 枚举：`official` / `authorized` / `cross_checked` / `third_party` / `self_reported` / `manual` / `unknown`（对齐命名规范 §6）

---

## 3. company_segments

**表名：** `company_segments` · **中文名：** 公司-产业环节关系表
> 通过 `segment_code` 关联 `industry_segments`（稳定业务键，不依赖自增 id）。

| 中文名 | 英文名 | 类型 | 是否必填 | 示例值 |
|--------|--------|------|----------|--------|
| 主键ID | id | BIGINT AUTO_INCREMENT | 是(自增) | 1 |
| 公司ID | company_id | BIGINT | 是 | 1 |
| 产业环节编码 | segment_code | VARCHAR(80) | 是 | passive_components |
| 角色 | role | VARCHAR(50) | 否 | 制造商 |
| 是否主要环节 | is_primary | TINYINT(1) | 否(默认0) | 1 |
| 创建时间 | created_at | DATETIME | 否(默认) | 2026-07-15 10:00:00 |

---

## 4. categories

**表名：** `categories` · **中文名：** 物料品类表

| 中文名 | 英文名 | 类型 | 是否必填 | 示例值 |
|--------|--------|------|----------|--------|
| 主键ID | id | INT AUTO_INCREMENT | 是(自增) | 1 |
| 品类名称 | name | VARCHAR(50) | 是(唯一) | MLCC |
| 父品类ID | parent_id | INT | 否 | NULL |
| 品类说明 | description | TEXT | 否 | 多层陶瓷电容器 |
| 创建时间 | created_at | DATETIME | 否(默认) | 2026-07-15 10:00:00 |

---

## 5. parts

**表名：** `parts` · **中文名：** 物料主数据表

| 中文名 | 英文名 | 类型 | 是否必填 | 示例值 |
|--------|--------|------|----------|--------|
| 主键ID | id | INT AUTO_INCREMENT | 是(自增) | 1 |
| 料号/型号 | part_number | VARCHAR(100) | 是 | GRM188R71H104KA93D |
| 品牌 | brand | VARCHAR(100) | 是 | Murata |
| 品类ID | category_id | INT | 是 | 1 |
| 品类名称 | category_name | VARCHAR(50) | 是 | MLCC |
| 规格参数 | specs | JSON | 否 | {"封装":"0603","容值":"0.1uF","温度系数":"X7R","额定电压":"50V"} |
| 生命周期 | lifecycle_status | ENUM | 否(默认active) | active |
| Datasheet链接 | datasheet_url | VARCHAR(500) | 否 | https://www.murata.com/... |
| 物料描述 | description | TEXT | 否 | 0603 0.1uF 50V X7R MLCC贴片电容 |
| 数据可信度 | confidence_level | ENUM | 否(默认unknown) | official |
| 数据来源 | source_name | VARCHAR(200) | 否 | 立创商城 |
| 来源链接 | source_url | VARCHAR(500) | 否 | https://www.szlcsc.com/... |
| 创建时间 | created_at | DATETIME | 否(默认) | 2026-07-15 10:00:00 |
| 更新时间 | updated_at | DATETIME | 否(默认) | 2026-07-15 10:30:00 |

> `lifecycle_status` 枚举：`active` / `nrnd` / `eol` / `obsolete` / `unknown`

---

## 6. spec_definitions

**表名：** `spec_definitions` · **中文名：** 品类规格字段定义表

| 中文名 | 英文名 | 类型 | 是否必填 | 示例值 |
|--------|--------|------|----------|--------|
| 主键ID | id | INT AUTO_INCREMENT | 是(自增) | 1 |
| 品类ID | category_id | INT | 是 | 1 |
| 字段英文名 | field_name | VARCHAR(50) | 是 | capacitance |
| 字段中文名 | field_label | VARCHAR(100) | 是 | 容值 |
| 字段类型 | field_type | ENUM | 否(默认string) | enum |
| 单位 | unit | VARCHAR(20) | 否 | uF |
| 是否必填 | is_required | TINYINT(1) | 否(默认0) | 1 |
| 枚举值 | enum_values | VARCHAR(500) | 否 | X7R,X5R,C0G |
| 排序 | sort_order | INT | 否(默认0) | 0 |
| 创建时间 | created_at | DATETIME | 否(默认) | 2026-07-15 10:00:00 |

> `field_type` 枚举：`string` / `number` / `enum` / `boolean`

---

## 7. suppliers

**表名：** `suppliers` · **中文名：** 供应商主体表

| 中文名 | 英文名 | 类型 | 是否必填 | 示例值 |
|--------|--------|------|----------|--------|
| 主键ID | id | INT AUTO_INCREMENT | 是(自增) | 1 |
| 关联公司ID | company_id | INT | 否 | 5 |
| 供应商名称 | name | VARCHAR(200) | 是 | 立创商城(LCSC) |
| 所在地 | location | VARCHAR(100) | 否 | 深圳 |
| 评分 | rating | DECIMAL(3,2) | 否(默认0) | 4.80 |
| 审核状态 | status | ENUM | 否(默认pending) | approved |
| 联系电话 | contact_phone | VARCHAR(50) | 否 | 0755-12345678 |
| 联系邮箱 | contact_email | VARCHAR(100) | 否 | sales@lcsc.com |
| 数据来源 | source_name | VARCHAR(200) | 否 | 供应商自填 |
| 来源链接 | source_url | VARCHAR(500) | 否 | https://www.szlcsc.com |
| 创建时间 | created_at | DATETIME | 否(默认) | 2026-07-15 10:00:00 |
| 更新时间 | updated_at | DATETIME | 否(默认) | 2026-07-15 10:30:00 |

> `status` 枚举：`pending` / `approved` / `rejected` / `needs_review`

---

## 8. supplier_capabilities

**表名：** `supplier_capabilities` · **中文名：** 供应商能力表

| 中文名 | 英文名 | 类型 | 是否必填 | 示例值 |
|--------|--------|------|----------|--------|
| 主键ID | id | INT AUTO_INCREMENT | 是(自增) | 1 |
| 供应商ID | supplier_id | INT | 是 | 1 |
| 品类ID | category_id | INT | 是 | 1 |
| 品类名称 | category_name | VARCHAR(50) | 是 | MLCC |
| 代理/覆盖品牌 | brand_names | VARCHAR(500) | 否 | Murata,YAGEO,TDK,Samsung SEMCO |
| 最小起订量 | moq | INT | 否 | 1000 |
| 交期（天） | lead_time_days | INT | 否 | 7 |
| 供货区域 | region | VARCHAR(100) | 否 | 华南 |
| 审核状态 | audit_status | ENUM | 否(默认pending) | approved |
| 审核备注 | audit_note | TEXT | 否 | 已核实授权代理资质 |
| 数据来源 | source_name | VARCHAR(200) | 否 | 供应商自填+实地审核 |
| 创建时间 | created_at | DATETIME | 否(默认) | 2026-07-15 10:00:00 |
| 更新时间 | updated_at | DATETIME | 否(默认) | 2026-07-15 10:30:00 |

> `audit_status` 枚举：`pending` / `approved` / `rejected` / `needs_review`

---

## 9. part_alternatives

**表名：** `part_alternatives` · **中文名：** 替代料关系表

| 中文名 | 英文名 | 类型 | 是否必填 | 示例值 |
|--------|--------|------|----------|--------|
| 主键ID | id | INT AUTO_INCREMENT | 是(自增) | 1 |
| 原物料ID | original_part_id | INT | 是 | 10 |
| 替代物料ID | alternative_part_id | INT | 是 | 25 |
| 原型号 | original_part_number | VARCHAR(100) | 是 | GRM188R71H104KA93D |
| 替代型号 | alternative_part_number | VARCHAR(100) | 是 | CL10B104KB8NNNC |
| 替代等级 | level | ENUM | 是(默认l3) | l2 |
| 等级描述 | level_desc | VARCHAR(100) | 否 | 向上兼容：耐压更高 |
| 置信度 | confidence | DECIMAL(3,2) | 否(默认0.80) | 0.95 |
| 参数差异说明 | param_diff | TEXT | 否 | 原型号50V/0.1uF；替代型号50V/0.1uF |
| 风险说明 | risk_note | TEXT | 否 | 需确认焊接工艺兼容性 |
| 数据来源 | source_name | VARCHAR(200) | 否 | Datasheet规格比对 |
| 来源链接 | source_url | VARCHAR(500) | 否 | https://www.murata.com |
| 审核状态 | review_status | ENUM | 否(默认pending) | approved |
| 审核人 | reviewed_by | VARCHAR(50) | 否 | zhang.san |
| 审核时间 | reviewed_at | DATETIME | 否 | 2026-07-15 12:00:00 |
| 创建时间 | created_at | DATETIME | 否(默认) | 2026-07-15 10:00:00 |
| 更新时间 | updated_at | DATETIME | 否(默认) | 2026-07-15 10:30:00 |

**替代等级说明（小写，对齐命名规范 §6）：**

| 等级 | 含义 |
|------|------|
| l1 | 完全等效：关键参数全部一致，可直接替换 |
| l2 | 向上兼容：替代参数优于原型号，一般可直接替换 |
| l3 | 功能兼容需调整：主体兼容，个别差异需工程师评估 |
| l4 | 封装不兼容：电气兼容但物理不兼容，需改板 |
| l5 | 仅供参考：信息不足或弱关联，不建议直接替换 |

> 置信度 <0.7 的替代进入人工审核队列（review_status = needs_review），前端折叠在"仅供参考"区。

---

## 10. rfqs

**表名：** `rfqs` · **中文名：** RFQ询价单表

| 中文名 | 英文名 | 类型 | 是否必填 | 示例值 |
|--------|--------|------|----------|--------|
| 主键ID | id | INT AUTO_INCREMENT | 是(自增) | 1 |
| 询价单号 | rfq_number | VARCHAR(50) | 是(唯一) | RFQ-2026-001 |
| 询价标题 | title | VARCHAR(200) | 否 | 急寻0.1uF 0603 X7R电容10万PCS |
| 原始需求描述 | raw_query | TEXT | 否 | 客户产线缺料，急需Murata或同等替代0.1uF 0603 X7R 50V 10万PCS |
| 目标物料ID | part_id | INT | 否 | 10 |
| 目标料号 | part_number | VARCHAR(100) | 否 | GRM188R71H104KA93D |
| 需求数量 | quantity | INT | 否 | 100000 |
| 单位 | unit | VARCHAR(20) | 否(默认pcs) | pcs |
| 目标单价（USD） | target_price | DECIMAL(12,4) | 否 | 0.0150 |
| 期望交期（周） | lead_time_weeks | INT | 否 | 2 |
| 是否接受替代料 | accept_alternatives | TINYINT(1) | 否(默认1) | 1 |
| 场景 | scenario | ENUM | 否(默认stockout) | stockout |
| 状态 | status | ENUM | 否(默认draft) | sent |
| 创建人 | created_by | VARCHAR(50) | 否 | li.si |
| 创建时间 | created_at | DATETIME | 否(默认) | 2026-07-15 10:00:00 |
| 更新时间 | updated_at | DATETIME | 否(默认) | 2026-07-15 10:30:00 |

**场景说明：** `stockout` 缺货 · `cost_reduction` 降本 · `new_sourcing` 新寻源

**状态说明：** `draft` 草稿 · `sent` 已发送 · `quoted` 已报价 · `closed` 已关闭 · `cancelled` 已取消

---

## 11. rfq_suppliers

**表名：** `rfq_suppliers` · **中文名：** RFQ-供应商关联表

| 中文名 | 英文名 | 类型 | 是否必填 | 示例值 |
|--------|--------|------|----------|--------|
| 主键ID | id | INT AUTO_INCREMENT | 是(自增) | 1 |
| RFQ ID | rfq_id | INT | 是 | 1 |
| 供应商ID | supplier_id | INT | 是 | 3 |
| 匹配分数 | match_score | DECIMAL(3,2) | 否(默认0) | 0.92 |
| 匹配原因 | match_reason | TEXT | 否 | 品类匹配+品牌覆盖+区域符合+交期满足 |
| 状态 | status | ENUM | 否(默认pending) | sent |
| 发送时间 | sent_at | DATETIME | 否 | 2026-07-15 11:00:00 |
| 创建时间 | created_at | DATETIME | 否(默认) | 2026-07-15 10:00:00 |

> `status` 枚举：`pending` / `sent` / `responded` / `declined`

---

## 12. quotations

**表名：** `quotations` · **中文名：** 报价记录表

| 中文名 | 英文名 | 类型 | 是否必填 | 示例值 |
|--------|--------|------|----------|--------|
| 主键ID | id | INT AUTO_INCREMENT | 是(自增) | 1 |
| RFQ ID | rfq_id | INT | 是 | 1 |
| 供应商ID | supplier_id | INT | 是 | 3 |
| 报价料号 | part_number | VARCHAR(100) | 否 | CL10B104KB8NNNC |
| 单价（USD） | unit_price | DECIMAL(12,4) | 是 | 0.0120 |
| 最小起订量 | moq | INT | 否 | 5000 |
| 报价交期（天） | lead_time_days | INT | 否 | 5 |
| 库存数量 | stock_qty | INT | 否 | 200000 |
| 报价有效期 | valid_until | DATE | 否 | 2026-08-15 |
| 是否有库存 | is_in_stock | TINYINT(1) | 否(默认0) | 1 |
| 备注 | note | TEXT | 否 | 可提供三星替代料，库存充足 |
| 创建时间 | created_at | DATETIME | 否(默认) | 2026-07-15 14:00:00 |

---

## 13. data_sources

**表名：** `data_sources` · **中文名：** 数据来源表

| 中文名 | 英文名 | 类型 | 是否必填 | 示例值 |
|--------|--------|------|----------|--------|
| 主键ID | id | INT AUTO_INCREMENT | 是(自增) | 1 |
| 来源名称 | name | VARCHAR(200) | 是 | 立创商城 |
| 来源类型 | type | ENUM | 否(默认official) | marketplace |
| 来源链接 | url | VARCHAR(500) | 否 | https://www.szlcsc.com |
| 可靠性 | reliability | ENUM | 否(默认medium) | high |
| 最后核实日期 | last_checked | DATE | 否 | 2026-07-15 |
| 创建时间 | created_at | DATETIME | 否(默认) | 2026-07-15 10:00:00 |

**来源类型说明：** `official` 官方 · `industry_report` 行业报告 · `news` 新闻 · `marketplace` 现货商城 · `internal` 内部数据

**可靠性说明：** `high` 高 · `medium` 中 · `low` 低

---

## 附录：公共字段说明

| 字段 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `id` | BIGINT AUTO_INCREMENT | 自增主键，系统自动生成 | 1 |
| `created_at` | DATETIME | 记录创建时间，默认当前时间 | 2026-07-15 10:00:00 |
| `updated_at` | DATETIME | 记录最后更新时间，自动更新 | 2026-07-15 10:30:00 |
| `confidence_level` | VARCHAR(30) | 数据可信度：official/authorized/cross_checked/third_party/self_reported/manual/unknown | official |
| `source_name` | VARCHAR | 数据来源名称 | 立创商城 |
| `source_url` | VARCHAR | 数据来源链接（URL） | https://www.szlcsc.com |

> 注：`confidence_level` 用 VARCHAR(30) 而非 ENUM，保留扩展空间；取值由应用层约束，对齐命名规范 §6。`industry_segments` 额外用 `segment_code` 作为稳定业务键（被 `company_segments` 外键引用）。

---

## 附录：CSV模板与样例数据清单

| 文件 | 对应表 | 位置 |
|----------|--------|------|
| `01_companies_template.csv` | companies | [../03_import_templates/](../03_import_templates/) |
| `02_parts_template.csv` | parts | [../03_import_templates/](../03_import_templates/) |
| `03_supplier_capabilities_template.csv` | supplier_capabilities | [../03_import_templates/](../03_import_templates/) |
| `04_part_alternatives_template.csv` | part_alternatives | [../03_import_templates/](../03_import_templates/) |
| `05_rfqs_template.csv` | rfqs | [../03_import_templates/](../03_import_templates/) |
| `01_industry_segments_seed.csv` ~ `07_rfqs_seed.csv` | 13 表样例 | [../04_seed_data/](../04_seed_data/) |

每个 CSV 模板均含公共字段：`source_name` / `source_url` / `confidence_level` / `updated_at`，JSON 字段用合法 JSON 字符串。
