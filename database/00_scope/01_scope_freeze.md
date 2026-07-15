# 01 - 范围冻结（0-1h）

> 冲刺：电脑全链路数据库 16 小时冲刺
> 数据库：`pc_industry`（MySQL 8.0）
> 冻结日期：2026-07-15
> 关联文档：[../../docs/电脑全链路数据库16小时冲刺执行计划.md](../../docs/电脑全链路数据库16小时冲刺执行计划.md)

## 1. 冲刺目标

16 小时内交付一套**可演示、可扩展**的电脑全链路数据库最小底座，支撑：

```
需求 -> 物料 -> 替代料 -> 供应商 -> RFQ
```

不追求完整 ERP/MES，只做“能开始录数据、能支撑 Demo、后续能扩展”的最小版本。

## 2. 第一版闭环

```
采购需求(NL/结构化)
  -> 匹配 parts 物料
  -> 推荐 part_alternatives 替代料
  -> 匹配 supplier_capabilities 供应商
  -> 生成 rfqs 询价单
  -> 回收 quotations 报价
```

## 3. 首批品类（5 个）

| 品类 | 英文 | 说明 | 优先级 |
|---|---|---|---|
| MLCC | mlcc | 多层陶瓷电容，替代料数据最充分 | P0 |
| 贴片电阻 | resistor | 与 MLCC 同属被动元件，规格结构相似 | P0 |
| 连接器 | connector | JST/Molex/TE 交叉引用清晰 | P1 |
| DRAM | dram | 存储，颗粒型号体系成熟 | P1 |
| SSD | ssd | 存储，主控+颗粒组合 | P2 |

> 散热在长期计划中补入；16 小时冲刺聚焦上面 5 个，且物料样例以 MLCC / 电阻 / 连接器 为主。

## 4. 首批产业环节（5 个，覆盖上中下游）

| 环节 | 层级 | 代表公司类型 |
|---|---|---|
| 元器件制造 | 上游 | Murata / TDK / Yageo / Samsung Electro-Mechanics |
| 模组制造 | 上游 | 存储模组、连接器模组厂 |
| 分销 | 中游 | Arrow / Avnet / Digi-Key / Mouser / 立创商城 / 云汉芯城 |
| ODM/EMS | 中游 | Foxconn / Quanta / Compal / Wistron / BYD Electronic |
| 检测认证 | 中游 | SGS / UL / TÜV Rheinland / Bureau Veritas |

> 完整 8 段产业链（原材料/元器件/模组/设计/采购/制造/质量/渠道）见
> [../../docs/电脑制作全链路产业链分析.md](../../docs/电脑制作全链路产业链分析.md)，本轮只冻结上表 5 个环节入样例数据。

## 5. 13 张核心表（必做）

`industry_segments` · `companies` · `company_segments` · `categories` · `parts` ·
`spec_definitions` · `suppliers` · `supplier_capabilities` · `part_alternatives` ·
`rfqs` · `rfq_suppliers` · `quotations` · `data_sources`

## 6. 明确不做（本轮）

- 采购订单 PO、库存批次、生产工单、质量检验、售后 RMA
- 复杂权限系统、审批流
- 全量 Neo4j / Milvus 同步（仅预留 `confidence_level` / `source_*` / `specs JSON` 字段边界）
- BOM 风险分析（链路 C 仅用样例查询演示，不建 BOM 表）

> 这些内容保留后续扩展目录前缀 `10_` 起步，见 [NAMING_CONVENTIONS.md §2](../NAMING_CONVENTIONS.md#2-目录命名规范)。

## 7. 验收标准

- [x] 13 张表 DDL 可在 MySQL 8.0 执行通过
- [x] 字段字典覆盖每张表（中文名/英文名/类型/必填/示例）
- [x] 5 类 CSV 导入模板 + 7 份样例数据
- [x] 样例数据支撑 3 条 Demo 链路（缺货找替代 / 按参数找料 / BOM 风险）
- [x] 每条关键数据有 `source_name` + `confidence_level`，可溯源

## 8. 与 matchforge 库的关系

| 库 | 表数 | 定位 | 阶段 |
|---|---|---|---|
| `matchforge` | 10 | MVP Spike AI 寻源运营库（供应商/产品/询价/线索） | Phase 0 Spike |
| `pc_industry` | 13 | 产业链全链路知识库（公司/物料/规格/替代/RFQ/报价 + 溯源） | 16h 冲刺底座 |

两库在 MVP 阶段并存：`pc_industry` 沉淀产业链事实数据（公司/物料/替代/供应商能力），
`matchforge` 承载寻源会话与线索流转。长期将以外键 `company_id` / `part_id` 收敛合一，
见 [06_handoff/01_retrospective.md](../06_handoff/01_retrospective.md)。
