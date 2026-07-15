# Industry Segments Field Dictionary

`industry_segments` 用于维护电脑制作全链路的产业环节，是公司库、供应商能力库和后续产业链图谱的基础分类表。

## 1. Table Definition

| field_name | cn_name | type | required | example | note |
|---|---|---|---|---|---|
| `id` | 主键 | bigint | yes | 1 | 自增主键 |
| `segment_code` | 环节编码 | varchar(80) | yes | passive_components | 稳定英文编码，被其他表引用后不应随意改名 |
| `segment_name_cn` | 中文名称 | varchar(120) | yes | 被动元件 | 面向运营和前端展示 |
| `segment_name_en` | 英文名称 | varchar(160) | yes | Passive Components | 面向英文展示、导出和知识图谱 |
| `chain_position` | 链路位置 | varchar(20) | yes | upstream | upstream/midstream/downstream/support |
| `parent_code` | 父级环节编码 | varchar(80) | no | raw_materials | 一级环节为空，二级环节填写父级 segment_code |
| `level` | 层级 | tinyint | yes | 1 | 一级为 1，二级为 2 |
| `description` | 环节说明 | text | no | 电容、电阻、电感等基础电子元件 | 描述该环节的产业范围 |
| `typical_products` | 典型产品 | json | no | ["MLCC","chip_resistor"] | JSON 数组，使用英文或行业常用缩写 |
| `typical_companies` | 代表公司 | json | no | ["Murata","Yageo"] | JSON 数组，仅用于展示和调研参考 |
| `data_scope` | 数据范围 | varchar(50) | yes | sprint_16h | 标记来源于 16 小时冲刺或后续长期库 |
| `source_name` | 来源名称 | varchar(120) | yes | manual_research | 数据来源名称 |
| `source_url` | 来源链接 | varchar(500) | no | https://example.com | 可为空，人工整理时可不填 |
| `confidence_level` | 可信度等级 | varchar(30) | yes | manual | official/authorized/cross_checked/third_party/self_reported/manual/unknown |
| `sort_order` | 排序 | int | yes | 40 | 前端展示和人工维护排序 |
| `is_active` | 是否启用 | boolean | yes | true | 废弃环节不删除，设置为 false |
| `created_at` | 创建时间 | datetime | yes | 2026-07-15 10:00:00 | 数据创建时间 |
| `updated_at` | 更新时间 | datetime | yes | 2026-07-15 10:00:00 | 数据更新时间 |

## 2. Enum Values

### chain_position

| value | cn_name | note |
|---|---|---|
| `upstream` | 上游 | 原材料、芯片、元器件、模组 |
| `midstream` | 中游 | 设计、采购、制造、组装 |
| `downstream` | 下游 | 销售、渠道、交付、售后 |
| `support` | 支撑服务 | 检测认证、数据服务、供应链服务 |

### data_scope

| value | note |
|---|---|
| `sprint_16h` | 16 小时冲刺范围 |
| `mvp` | MVP 阶段扩展 |
| `long_term` | 长期全链路扩展 |

### confidence_level

| value | cn_name | note |
|---|---|---|
| `official` | 官方来源 | 公司官网、官方文档、监管披露 |
| `authorized` | 授权来源 | 授权代理、授权名录 |
| `cross_checked` | 多来源交叉验证 | 两个以上来源一致 |
| `third_party` | 第三方来源 | 数据平台、行业报告 |
| `self_reported` | 平台自报 | 企业自行提交 |
| `manual` | 人工整理 | 团队人工研究录入 |
| `unknown` | 未知 | 暂无可靠来源 |

## 3. Segment Code Rules

- 使用英文小写 snake_case。
- 表达产业环节，不表达单一公司或单一产品型号。
- 一级环节不超过 20 个，避免分类过细导致维护成本过高。
- 二级环节必须填写 `parent_code`。
- 被 `companies` 或 `company_segments` 引用后，`segment_code` 不允许直接改名；如必须改名，应做迁移映射。

## 4. First Batch Segment Codes

```text
raw_materials
semiconductor_chips
memory_storage
passive_components
connectors_cables
pcb_pcba
display_modules
power_battery
thermal_mechanical
product_design
sourcing_distribution
odm_ems_manufacturing
testing_certification
sales_channels
aftersales_recycling
```
