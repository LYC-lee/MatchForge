# MatchForge 前端技术亮点总结

> 项目：电子元器件 AI 替代料寻源助手（MatchForge / 智配）
> 日期：2026-07-15
> 技术栈：Vue 3 + TypeScript + Pinia + Vue Router + Vite + Axios

---

## 一、Axios 拦截器链与 Token 自动刷新

### 核心设计

```typescript
// 请求拦截器 — 自动注入 Bearer Token
api.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token && config.headers) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

// 响应拦截器 — 401 自动刷新 + 重试队列
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    if (error.response?.status === 401 && !originalRequest._retry) {
      const newToken = await refreshAccessToken()  // 防并发刷新
      originalRequest.headers.Authorization = `Bearer ${newToken}`
      return api(originalRequest)                   // 透明重放原始请求
    }
  }
)
```

### 技术亮点

| 特性 | 实现方式 |
|------|---------|
| **防并发 Token 刷新** | `refreshPromise` 单例 + `pendingQueue` 队列，同时触发多个 401 时只发一次 refresh，其余排队等待结果 |
| **请求透明重放** | 原始请求标记 `_retry`，刷新成功后自动重放，调用方无感知 |
| **Mock/Real 双模式** | 环境变量 `VITE_USE_MOCK` 控制：mock 模式本地续期 session，real 模式调用 `POST /api/v1/auth/refresh` |
| **统一错误收敛** | `normalizeError()` 将 AxiosError 统一收敛为 `{ code, message, status, traceId }`，含中文错误映射 |
| **SSE AbortSignal 合并** | `combineAbortSignals()` 支持多个 controller 叠加取消 |

### 新增 API 封装

```
parseQuery / getAlternatives / matchSuppliers / generateRfq / submitRfq
getSuppliers / getSupplierDetail / onboardSupplier
getRfqs / getRfqDetail
getAuditQueue / performAudit / getAdminMetrics
getLeads
```

---

## 二、AI 对话式界面（ChatView）

### 架构

```
ChatView.vue（主视图）
 ├── ChatMessage.vue（消息气泡组件）
 │    ├── 用户消息（右对齐、靛蓝色背景）
 │    ├── AI 消息（左对齐、暗色背景）
 │    └── 系统消息（居中、半透明）
 ├── 内嵌结构化结果（动态 slot）
 │    ├── SpecConfirm（规格确认表）
 │    ├── AlternativesList（替代料列表）
 │    ├── SuppliersMatch（供应商勾选）
 │    ├── RfqEditor（询价单编辑器）
 │    └── GradeCard（线索分级卡）
 └── 输入栏（自适应 textarea + 快捷键）
```

### 技术亮点

| 特性 | 实现方式 |
|------|---------|
| **流式打字效果** | SSE 进度变化实时更新 AI 消息 `content`，`▌` 光标 CSS 闪烁动画 |
| **内嵌结构化结果** | 通过 Vue `slot` 机制在对话气泡中嵌入复杂卡片，保持消息列表的线性滚动 |
| **两阶段 SSE 门控** | 第一阶段（parse + normalize）→ 用户确认规格 → 第二阶段（alternatives + match + gen_rfq + grade） |
| **自动历史保存** | `watch(phase)` 在 done 时自动写入 localStorage 历史记录 |
| **欢迎空态引导** | 示例 chips 一键填充 + 快捷键 `Enter` 发送 / `Shift+Enter` 换行 |

---

## 三、结构化结果卡组件体系

### 组件清单

| 组件 | 用途 | 关键 Props |
|------|------|-----------|
| `SpecConfirm` | 规格字段编辑 + 缺失标黄 + 低置信 `?` 提示 | `spec, gating` |
| `AlternativesList` | 替代料列表（trusted/risky 分区） | `alternatives, originalPart` |
| `ParamDiffTable` | 参数差异对比表（绿一致/黄差异/红风险） | `diffs` |
| `SuppliersMatch` | 供应商勾选列表 + 匹配度 + 能力匹配提示 | `suppliers, selectedIds` |
| `RfqEditor` | 询价单编辑 + 侧栏结构化字段 + 复制/导出 | `rfqDoc, spec, alternatives` |
| `GradeCard` | 线索分级展示（等级字母 + 分数 + 理由） | `grade` |
| `AgentTimeline` | 6 智能体执行进度时间线 | `agents` |
| `StepNav` | 步骤导航指示器 | `agents` |

### 设计原则

- **完全受控组件** — 所有数据通过 props 传入，事件通过 emit 向上传递
- **状态无侵入** — 不直接修改 store，由父组件协调数据流
- **暗色主题** — 基于 CSS 变量系统（`tokens.css`），统一使用 `--bg-*` / `--text-*` / `--border-*` 变量

---

## 四、供应商端页面（MVP）

### 页面结构

```
/supplier                   供应商工作台（Dashboard）
  ├── 统计卡片（活跃线索/产品数/新询价/响应率）
  ├── 最近线索表格（分级 + 状态 + 操作）
  └── 快速入口（产品管理/线索管理/企业信息）

/supplier/products          产品管理
  ├── 添加产品表单（品类/型号/品牌/封装/MOQ/库存）
  └── 产品列表（型号/品牌/库存状态/上架状态）

/supplier/leads             线索管理
  ├── Tab 筛选（全部/新线索/已成交）
  ├── 搜索过滤
  └── 线索卡片（采购方/月用量/MOQ/分级/操作）
```

### 技术亮点

- **角色预留** — auth store 已有 `role: 'buyer' | 'supplier' | 'admin'`，可接入权限控制
- **Mock 先行** — 加载动画 + setTimeout 模拟后端延迟，平滑过渡到真实 API
- **骨架屏** — `shimmer` 动画加载占位

---

## 五、运营后台（MVP）

### 页面结构

```
/admin/audit                运营审核
  ├── 统计概览（待审替代料/待审供应商/累计审核/平均响应）
  ├── Tab 切换（替代料审核 / 供应商审核）
  ├── 实时搜索过滤
  └── 审核操作（通过 / 驳回含原因 / 标记风险）
```

### 技术亮点

- **队列实时更新** — 审核操作后自动从队列移除并更新统计
- **搜索即过滤** — `computed` 依赖 `searchQuery`，无需手动触发
- **来源追溯** — 每条待审项展示来源类型（`llm_inferred` / 分销商数据等）

---

## 六、工程化基建

| 维度 | 实现 |
|------|------|
| **路由架构** | 15+ 路由，`beforeEach` 自动鉴权 + 页面标题 + layout 控制 |
| **状态管理** | Pinia stores：`auth`（本地 session + 注册/登录/登出）、`procure`（两阶段寻源流程） |
| **Mock SSE** | `mock/sse.ts` 严格按真实事件契约模拟 6 智能体 + 可中断 |
| **Mock 数据** | `mock/data.ts` 真实 MLCC 型号数据 + 5 级替代料 + 5 家供应商 |
| **暗色主题** | CSS 变量系统（背景/文本/边框/主色/状态色/渐变动画） |
| **TypeScript** | 全量类型定义（`types/procure.ts`），`vue-tsc --noEmit` 零错误 |

---

## 七、文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/api/index.ts` | **重写** | 拦截器链 + Token 刷新 + 统一错误 + 新 API 封装 |
| `src/views/ChatView.vue` | **新增** | AI 对话式界面主视图 |
| `src/components/chat/ChatMessage.vue` | **新增** | 消息气泡组件（用户/AI/系统） |
| `src/components/procure/GradeCard.vue` | **新增** | 线索分级独立组件 |
| `src/views/supplier/SupplierDashboard.vue` | **新增** | 供应商工作台 |
| `src/views/supplier/SupplierProducts.vue` | **新增** | 产品管理 |
| `src/views/supplier/SupplierLeads.vue` | **新增** | 线索管理 |
| `src/views/P7AdminAudit.vue` | **重写** | 运营审核（统计概览 + 搜索 + 完整队列） |
| `src/router/index.ts` | **修改** | 新增 chat + 3 个供应商路由 |
| `src/components/layout/AppHeader.vue` | **修改** | 侧边栏导航 + pageTitle 更新 |
