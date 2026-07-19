# 物流/服务型前端差异化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 9004 远达及同类物流/服务企业切换 ShortageProcurementView 和 ProductsBomView 的前端语义

**Architecture:** 抽取共享 composable `useIsLogistics` 复用判断逻辑，两个 page 组件分别通过 `isLogistics` 控制文案和标签切换。后端数据接口不变。

**Tech Stack:** Vue 3 + TypeScript + Composition API

## Global Constraints

- 不改后端 API 和数据流
- 不改 HomeView.vue（已有 isLogistics 模式）
- 不动原有页面结构和布局，仅切换文案/label
- 使用 `current.value?.segment_name` 判断：含"物流"或"服务"或 `company_id === 9004`
- 所有文本使用中文

---

### Task 1: 抽取 useIsLogistics composable

**Files:**
- Create: `web/src/composables/useIsLogistics.ts`
- Reference: `web/src/composables/useEnterpriseContext.ts`（复用其 current）

**Interfaces:**
- Produces: `useIsLogistics() -> { isLogistics: ComputedRef<boolean> }`

- [ ] **Step 1: 创建 useIsLogistics.ts**

```ts
import { computed } from 'vue'
import { useEnterpriseContext } from './useEnterpriseContext'

export function useIsLogistics() {
  const { current } = useEnterpriseContext()
  const isLogistics = computed(() => {
    const seg = current.value?.segment_name || ''
    return seg.includes('物流') || seg.includes('服务') || current.value?.company_id === 9004
  })
  return { isLogistics }
}
```

- [ ] **Step 2: 验证文件存在和语法**

Run: `npx vue-tsc --noEmit web/src/composables/useIsLogistics.ts`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add web/src/composables/useIsLogistics.ts
git commit -m "feat: extract useIsLogistics shared composable"
```

---

### Task 2: ShortageProcurementView 物流语义切换

**Files:**
- Modify: `web/src/views/ShortageProcurementView.vue`

**Interfaces:**
- Consumes: `useIsLogistics()` composable

- [ ] **Step 1: 在 script 中引入 composable 并删除旧的 isLogistics 内联判断**

在 `<script>` 区域 `import { useEnterpriseContext }` 处附近加入：
```ts
import { useIsLogistics } from '@/composables/useIsLogistics'

const { isLogistics } = useIsLogistics()
```

- [ ] **Step 2: 页面头部标题和描述切换**

```vue
<h1>{{ isLogistics ? '运力与履约' : '缺件与采购' }}</h1>
<p>{{ isLogistics ? '运力缺口与履约执行，从仓储、运输到服务调度，串联资源调度单与供应商协同。' : '从订单和预测需求导致的缺件出发, 串起推荐动作、RFQ 创建与报价对比闭环。' }}</p>
```

- [ ] **Step 3: 左侧栏标题切换**

```vue
<div class="picker-head">{{ isLogistics ? '资源缺口' : '缺件清单' }} ({{ shortages.length }})</div>
```

- [ ] **Step 4: 左侧栏每行副标题、右侧摘要面板文案切换**

左侧每行副标题（约 250 行）：
```vue
<span>{{ isLogistics ? (item.category_name || '通用') + ' · 缺口 ' + item.shortage_qty.toLocaleString() + ' 车次 · ' + severityLabel(item.severity) : item.part_number + ' · 缺口 ' + item.shortage_qty.toLocaleString() + ' · ' + severityLabel(item.severity) }}</span>
```

摘要面板眼标和缺件数字标签（约 260-270 行）：
```vue
<span class="eyebrow">{{ isLogistics ? '当前资源缺口' : '当前缺件' }}</span>
```
```vue
<p class="hint">{{ isLogistics ? (selectedShortage.category_name || '通用') + ' · 缺口 ' + selectedShortage.shortage_qty.toLocaleString() + ' 车次 · 需调度 ' + selectedShortage.required_qty.toLocaleString() + ' · 可调配 ' + selectedShortage.available_qty.toLocaleString() : (selectedShortage.category_name || '物料') + ' · 缺口 ' + selectedShortage.shortage_qty.toLocaleString() + ' ' + (selectedShortage.unit || '') + ' · 需求 ' + selectedShortage.required_qty.toLocaleString() + ' · 可用 ' + selectedShortage.available_qty.toLocaleString() }}</p>
```
```vue
<span>{{ isLogistics ? '运力缺口' : '缺口' }}</span>
```
```vue
<button class="btn-rfq" @click="openRfqForm(selectedShortage)">{{ isLogistics ? '从此缺口发起调度' : '从此缺件创建 RFQ' }}</button>
```

- [ ] **Step 5: 影响面板文案切换**

面板标题（约 279 行）：
```vue
<h3>{{ isLogistics ? '影响履约' : '影响订单和产品' }}</h3>
```

影响行标签：
```vue
<span>{{ isLogistics ? '影响履约单' : '影响订单' }}</span>
```
```vue
<span>{{ isLogistics ? '影响线路/服务' : '影响产品' }}</span>
```
```vue
<span>{{ isLogistics ? '紧急程度' : '风险等级' }}</span>
```
```vue
<span>{{ isLogistics ? '首选服务商' : '首选供应商' }}</span>
```

- [ ] **Step 6: 推荐动作面板文案切换**

```vue
<h3>{{ isLogistics ? '推荐调度动作' : '推荐动作' }}</h3>
```

分类标签映射函数增加物流语义：
```ts
function categoryLabel(c: string) {
  const labels: Record<string, string> = {
    sourcing: isLogistics.value ? '运力调度' : '采购',
    production: isLogistics.value ? '仓储作业' : '生产',
    sales: isLogistics.value ? '运输配送' : '销售',
    collaboration: isLogistics.value ? '服务协同' : '协同',
  }
  return labels[c] || c
}
```

按钮文案：
```vue
<button v-if="action.category === 'sourcing'" class="btn-mini" @click="openRfqFromAction(action)">{{ isLogistics ? '发起调度' : '发 RFQ' }}</button>
```

- [ ] **Step 7: RFQ 表单和列表文案切换**

表单标题：
```vue
<h3>{{ isLogistics ? '发起服务调度' : '创建 RFQ' }}</h3>
```

表单 label（使用 input placeholder 实现）：
```vue
<label><span>{{ isLogistics ? '调度单标题' : '标题' }}</span><input v-model="rfqForm.title" class="input" :placeholder="isLogistics ? '调度单标题' : 'RFQ 标题'" /></label>
```
```vue
<label><span>{{ isLogistics ? '资源编码' : '零件号' }}</span><input v-model="rfqForm.part_number" class="input" :placeholder="isLogistics ? '资源编码' : 'part_number'" /></label>
```
```vue
<label><span>{{ isLogistics ? '资源名称' : '零件名' }}</span><input v-model="rfqForm.part_name" class="input" :placeholder="isLogistics ? '资源名称' : '零件名称'" /></label>
```
```vue
<label><span>{{ isLogistics ? '调度数量' : '数量' }}</span><input v-model.number="rfqForm.quantity" type="number" class="input" /></label>
```
```vue
<label><span>{{ isLogistics ? '候选服务商 ID' : '候选供应商ID' }}</span><input ... /></label>
```

提交按钮：
```vue
<button class="btn-submit" :disabled="creating || !rfqForm.title" @click="submitRfq">{{ creating ? '创建中…' : (isLogistics ? '发起调度' : '创建 RFQ') }}</button>
```

成功提示：
```vue
<span>{{ isLogistics ? '调度单 #' + lastCreatedRfqId + ' 已发起!' : 'RFQ #' + lastCreatedRfqId + ' 创建成功!' }}</span>
```

RFQ 列表标题：
```vue
<h3>{{ isLogistics ? '服务调度单列表' : (isDemo ? '演示 RFQ 列表' : '本企业 RFQ 列表') }} ({{ rfqList.length }})</h3>
```

RFQ 表头（约 358 行）：
```vue
<span>{{ isLogistics ? '调度单号' : 'RFQ 编号' }}</span>
```

- [ ] **Step 8: 构建验证**

Run: `npm run build`
Expected: Build passes

- [ ] **Step 9: Commit**

```bash
git add web/src/views/ShortageProcurementView.vue
git commit -m "feat: logistics semantics for ShortageProcurementView"
```

---

### Task 3: ProductsBomView 物流语义切换

**Files:**
- Modify: `web/src/views/ProductsBomView.vue`

**Interfaces:**
- Consumes: `useIsLogistics()` composable

- [ ] **Step 1: 引入 composable**

在 `<script>` 区域加入：
```ts
import { useIsLogistics } from '@/composables/useIsLogistics'

const { isLogistics } = useIsLogistics()
```

- [ ] **Step 2: 页面头部文案切换**

```vue
<h1>{{ isLogistics ? '服务资源' : '产品与 BOM' }}</h1>
<p>{{ isLogistics ? '按当前企业展示可服务资源、服务能力与关键资源。' : '按当前企业展示可生产产品、关键物料、BOM 零件和首选供应商。' }}</p>
```

右侧链接：
```vue
<RouterLink :to="isLogistics ? '/shortage-procurement' : '/shortage-procurement'" class="action-link">{{ isLogistics ? '查看运力与履约' : '查看缺件与采购' }}</RouterLink>
```

- [ ] **Step 3: 汇总栏文案切换**

```vue
<span>{{ isLogistics ? '服务资源总数' : 'BOM 零件总数' }}</span>
```
```vue
<span>{{ isLogistics ? '关键资源' : '关键件' }}</span>
```
```vue
<span>{{ isLogistics ? '在营服务' : '在产产品' }}</span>
```

- [ ] **Step 4: 产品卡片→服务卡片文案切换**

副标题（`product-head` 内的 p 标签）：
```vue
<p>{{ isLogistics ? '容量 ' + (product.monthly_capacity?.toLocaleString() || '-') + ' ' + (product.unit || '') : '月产 ' + (product.monthly_capacity?.toLocaleString() || '-') + ' ' + (product.unit || '') }}{{ product.product_type ? ' · ' + product.product_type : '' }}{{ product.description ? ' · ' + product.description : '' }}</p>
```

状态标签：
```vue
<span class="status-pill" :class="product.status === 'at_risk' ? 'status-pill--risk' : 'status-pill--ok'">{{ product.status === 'at_risk' ? '风险' : (isLogistics ? '运营中' : '在产') }}</span>
```

展开表格表头：
```vue
<div class="bom-row bom-row--head">
  <span>{{ isLogistics ? '关键资源' : '关键零件' }}</span>
  <span>编码</span>
  <span>{{ isLogistics ? '类型' : '品类' }}</span>
  <span>{{ isLogistics ? '容量需求' : '需求量' }}</span>
  <span>{{ isLogistics ? '安全余量' : '安全库存' }}</span>
  <span>{{ isLogistics ? '首选服务商' : '首选供应商' }}</span>
  <span>关键</span>
</div>
```

空状态：
```vue
<div v-if="!loading && !products.length" class="empty-line">{{ isLogistics ? '当前企业暂无可服务资源' : '当前企业暂无可生产产品' }}</div>
```

- [ ] **Step 5: 构建验证**

Run: `npm run build`
Expected: Build passes

- [ ] **Step 6: Commit**

```bash
git add web/src/views/ProductsBomView.vue
git commit -m "feat: logistics semantics for ProductsBomView"
```
