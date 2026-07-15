# Initial Industry Segments

本文定义 16 小时冲刺版产业环节库的第一批范围。产业环节用于回答“某家公司处在电脑制作全链路的哪个位置”，并为公司库、品类库、供应商能力库和知识图谱关系提供基础分类。

## 1. 分层原则

电脑制作全链路按 `chain_position` 分为四类：

| chain_position | 含义 | 说明 |
|---|---|---|
| `upstream` | 上游 | 原材料、芯片、元器件、关键模组 |
| `midstream` | 中游 | 设计、采购、制造、组装、测试 |
| `downstream` | 下游 | 品牌销售、渠道、交付、售后 |
| `support` | 支撑服务 | 检测认证、数据服务、供应链服务 |

## 2. 第一批产业环节

| segment_code | segment_name_cn | segment_name_en | chain_position | level | parent_code |
|---|---|---|---|---:|---|
| raw_materials | 原材料与基础材料 | Raw Materials | upstream | 1 | |
| semiconductor_chips | 半导体芯片 | Semiconductor Chips | upstream | 1 | |
| memory_storage | 内存与存储 | Memory and Storage | upstream | 1 | |
| passive_components | 被动元件 | Passive Components | upstream | 1 | |
| connectors_cables | 连接器与线束 | Connectors and Cables | upstream | 1 | |
| pcb_pcba | PCB 与 PCBA | PCB and PCBA | upstream | 1 | |
| display_modules | 显示与交互模组 | Display and Interaction Modules | upstream | 1 | |
| power_battery | 电源与电池 | Power and Battery | upstream | 1 | |
| thermal_mechanical | 散热与结构件 | Thermal and Mechanical Parts | upstream | 1 | |
| product_design | 整机设计与工程开发 | Product Design and Engineering | midstream | 1 | |
| sourcing_distribution | 采购寻源与分销 | Sourcing and Distribution | midstream | 1 | |
| odm_ems_manufacturing | ODM/EMS 制造组装 | ODM EMS Manufacturing | midstream | 1 | |
| testing_certification | 测试认证与质量 | Testing Certification and Quality | support | 1 | |
| sales_channels | 销售渠道与交付 | Sales Channels and Delivery | downstream | 1 | |
| aftersales_recycling | 售后维修与回收 | Aftersales and Recycling | downstream | 1 | |

## 3. 本轮优先环节

16 小时冲刺优先使用以下 5 个环节建立 Demo 数据：

```text
passive_components
memory_storage
connectors_cables
sourcing_distribution
odm_ems_manufacturing
```

原因：

- 与当前 MatchForge 的元器件寻源、替代料推荐、供应商匹配最相关。
- 可以快速找到代表公司和样例物料。
- 能覆盖“物料 -> 供应商 -> RFQ”的最小闭环。

## 4. 后续扩展规则

- 新增环节时必须先分配稳定的 `segment_code`。
- `segment_code` 一旦被公司库引用，不允许随意改名。
- 如果需要细分二级环节，使用 `parent_code` 指向一级环节。
- 不确定归属的公司可以先挂到一级环节，不要临时创建模糊分类。
