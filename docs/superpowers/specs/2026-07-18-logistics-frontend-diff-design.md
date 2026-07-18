# 物流/服务型企业前端差异化设计

## 概述

为 9004 远达供应链服务（segment_name = "物流/服务"）以及同类物流/服务企业，将其前端页面从制造业语义切换为物流/服务语义。后端数据接口不变，仅前端展示层做文案和卡片结构切换。

## 判断机制

抽取共享 composable `useIsLogistics`，复用 HomeView.vue 已有的判断逻辑：

```ts
// composables/useIsLogistics.ts
export function useIsLogistics() {
  const { current } = useEnterpriseContext()
  return computed(() => {
    const seg = current.value?.segment_name || ''
    return seg.includes('物流') || seg.includes('服务') || current.value?.company_id === 9004
  })
}
```

HomeView、ShortageProcurementView、ProductsBomView 三处统一引用。

---

## 页面 1: ShortageProcurementView → 运力与履约

### 页面头

| 字段 | 制造业 | 物流/服务 |
|------|--------|----------|
| 标题 h1 | `缺件与采购` | `运力与履约` |
| 描述 p | 从订单和预测需求导致的缺件出发, 串起推荐动作、RFQ 创建与报价对比闭环。 | 运力缺口与履约执行，从仓储、运输到服务调度，串联资源调度单与供应商协同。 |

### 左侧栏 — 缺件清单 → 资源缺口

| 字段 | 制造业 | 物流/服务 |
|------|--------|----------|
| 栏目标题 | `缺件清单 (N)` | `资源缺口 (N)` |
| 每行标题 b | `item.part_name \|\| item.part_number` | `item.part_name \|\| item.part_number`（数据不变） |
| 每行副标题 span | `{part_number} · 缺口 {shortage_qty} · {severityLabel}` | `{category_name \|\| '通用'} · 缺口 {shortage_qty} 车次 · {severityLabel}` |

### 右侧详情 — 选中缺口

#### 摘要面板

| 字段 | 制造业 | 物流/服务 |
|------|--------|----------|
| 眼标 eyebrow | `当前缺件` | `当前资源缺口` |
| 副标题 hint | `{category_name} · 缺口 {qty} {unit} · 需求 {rqty} · 可用 {aqty}` | `{category_name \|\| '通用'} · 缺口 {qty} 车次 · 需调度 {rqty} · 可调配 {aqty}` |
| 缺口数字标签 | `缺口` | `运力缺口` |
| 按钮 | `从此缺件创建 RFQ` | `从此缺口发起调度` |

#### 影响面板（原"影响订单和产品" → "影响履约"）

| 行 | 制造业 | 物流/服务 |
|----|--------|----------|
| 面板标题 h3 | `影响订单和产品` | `影响履约` |
| 行 1 | 影响订单: {order_numbers} | 影响履约单: {order_numbers}（数据不变） |
| 行 2 | 影响产品: {product_name} | 影响线路/服务: {product_name}（数据不变） |
| 行 3 | 风险等级: {severity} | 紧急程度: {severity}（文案仅改标签） |
| 行 4 | 首选供应商: {name} | 首选服务商: {name}（文案仅改标签） |
| 行 5 | 关系状态: ... | 关系状态: ...（不变） |

#### 推荐动作面板

| 字段 | 制造业 | 物流/服务 |
|------|--------|----------|
| h3 | `推荐动作` | `推荐调度动作` |
| 分类标签 | 采购/生产/销售/协同 | **运力调度/仓储作业/运输配送/服务协同** |
| 动作按钮 | `发 RFQ` | `发起调度` |

### RFQ → 服务调度单

| 字段 | 制造业 | 物流/服务 |
|------|--------|----------|
| 面板标题 h3 | `创建 RFQ` | `发起服务调度` |
| 表单标题 label | RFQ 标题 | 调度单标题 |
| 零件号 | 零件号 | 资源编码（数据不变，改 label） |
| 零件名 | 零件名 | 资源名称（数据不变，改 label） |
| 数量 | 数量 | 调度数量（数据不变，改 label） |
| 目标单价 | 目标单价 | 目标单价（不变） |
| 候选供应商 | 候选供应商ID | 候选服务商ID（改 label） |
| 提交按钮 | `创建 RFQ` | `发起调度` |
| 成功提示 | `RFQ #N 创建成功!` | `调度单 #N 已发起!` |
| 发送按钮 | `发送给供应商` | `发送给服务商` |
| RFQ 列表标题 | `本企业 RFQ 列表` | `服务调度单列表` |
| RFQ 表头 | RFQ 编号/标题/零件/数量/状态/操作 | 调度单号/标题/资源/数量/状态/操作 |

---

## 页面 2: ProductsBomView → 服务资源

### 页面头

| 字段 | 制造业 | 物流/服务 |
|------|--------|----------|
| 标题 h1 | `产品与 BOM` | `服务资源` |
| 描述 p | 按当前企业展示可生产产品、关键物料、BOM 零件和首选供应商。 | 按当前企业展示可服务资源、服务能力与关键资源。 |
| 右侧链接 | `查看缺件与采购` | `查看运力与履约` |

### 汇总栏

| 统计项 | 制造业 | 物流/服务 |
|--------|--------|----------|
| 第 1 项 | `{total_parts}` BOM 零件总数 | `{total_parts}` 服务资源总数 |
| 第 2 项 | `{critical_parts}` 关键件 | `{critical_parts}` 关键资源 |
| 第 3 项 | `{products.length}` 在产产品 | `{products.length}` 在营服务 |

### 产品卡片 → 服务卡片

| 字段 | 制造业 | 物流/服务 |
|------|--------|----------|
| 卡片标题 h2 | `{product_model} · {product_name}` | `{product_model} · {product_name}`（数据不变） |
| 副标题 p | 月产 {capacity} {unit} · {type} · {desc} | 容量 {capacity} {unit} · {type} · {desc}（仅改"月产"为"容量"） |
| 状态标签 | `在产` / `风险` | `运营中` / `风险` |
| 表头 1 | `关键零件` | `关键资源` |
| 表头 2 | `编码` | `编码`（不变） |
| 表头 3 | `品类` | `类型` |
| 表头 4 | `需求量` | `容量需求` |
| 表头 5 | `安全库存` | `安全余量` |
| 表头 6 | `首选供应商` | `首选服务商` |
| 表头 7 | `关键` | `关键`（不变） |
| 空状态 | `当前企业暂无可生产产品` | `当前企业暂无可服务资源` |

---

## 实施策略

1. 先抽取 `composables/useIsLogistics.ts`
2. 修改 `ShortageProcurementView.vue` — 物流语义切换（已完成左侧栏样式调整）
3. 修改 `ProductsBomView.vue` — 物流语义切换
4. 修改 `router/index.ts` — 页面标题随 isLogistics 切换（可选）

## 非目标

- 不改后端 API 和数据流
- 不改 HomeView.vue（已有 isLogistics 模式，保持现状）
- 不改登录/注册页
- 不改供应商工作台页面
