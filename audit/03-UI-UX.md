# UI/UX 设计审计报告

> 审计范围：`web/src/views`、`web/src/components`、`web/src/styles`（共 39 个 .vue + 4 个样式文件，约 1.34 万行）
> 审计方式：只读代码审查，逐页面核对信息架构、主路径、表单校验、加载/空/错误/成功四态、响应式、一致性、无障碍，并对 `docs/ui-audit`（2026-07-17）既有结论逐条复验。
> 标注约定：【已确认事实】= 本次在代码中直接核实；【合理推断】= 由代码证据推导；【尚未验证】= 需运行时或工具进一步确认；【缺少材料】= 无法判断。

---

## 1. 领域概述

### 1.1 真实实现了什么

前端是一个 Vue3 + TS + Pinia 的单页应用，包含 **19 条路由**（`web/src/router/index.ts:5-31`），可分为五组：

| 组 | 页面 | 真实状态 |
|---|---|---|
| 公开 | Landing `/`、Login `/login`、Register `/register` | 完整实现，深色视觉，Landing 8 张配图均存在（`web/public/assets/`）【已确认事实】 |
| 寻源主流程 | ChatView `/chat`、ProcureView `/procure/:id`、HistoryView `/history` | 对话式寻源为主入口，向导式 ProcureView 仅从历史记录进入；规格确认→替代料→供应商→RFQ→线索分级全链路卡片化【已确认事实】 |
| 经营驾驶舱 | HomeView `/app`、ProductsBomView、ShortageProcurementView | 真实 API + mock 降级，四块面板 + 缺件→手工 RFQ→报价对比闭环【已确认事实】 |
| 问答 | CompanyChat（上下游协同）、CompanyAssistant（企业内部） | 非流式 RAG 问答 + 客户端渐进 reveal + 引用回显【已确认事实】 |
| 供应商/管理 | SupplierDashboard/Leads/Products、P7AdminAudit、AdminKnowledge | 供应商线索报价可用；**SupplierProducts 是纯本地假数据**（`SupplierProducts.vue:46-56`）【已确认事实】 |

### 1.2 主路径步数（采购商发需求 → 看匹配结果 → 发询价）

以侧栏「AI 寻源」入口计算（`AppHeader.vue:18`）：

1. 点侧栏「AI 寻源」→ `/chat`
2. 输入需求（或点示例 chip）→ 发送（`ChatView.vue:219-237`）
3. 等待 parse/normalize，在规格确认卡核对并点「确认规格，继续寻源」（`SpecConfirm.vue:99-102`）
4. 等待 alternatives + match 完成，查看替代料卡与供应商卡
5. 勾选供应商 → 点「生成询价单」（`SuppliersMatch` emit generate）
6. 在 RfqEditor 编辑 → 点「标记已发送」（`RfqEditor.vue:323-330`）

**共 6 个用户动作**，主路径可理解性尚可：进度有 AgentTimeline 实时反馈、规格确认有缺失/低置信标黄、供应商卡有「能力匹配非现货承诺」免责声明（`SuppliersMatch.vue:121-127`）。但存在三个断点：
- 第 6 步「标记已发送」**只置前端本地 flag**（`stores/procure.ts:408-410`），UI 上没有任何真正推送/通知供应商的动作与后续引导，README 宣称的「询价单生成 → 分级线索推给上游」在寻源工作流 UI 上是断的【已确认事实：前端仅置 flag；后端是否有副作用——尚未验证】；
- 系统内存在**两条互不相干的 RFQ 路径**：AI 寻源 RFQ（/chat）与缺件页手工 RFQ 表单（`ShortageProcurementView.vue:321-341`），两者文案相似但数据不通，用户无法判断该用哪条【已确认事实】；
- 从历史记录恢复有两套体验：ChatView 内历史面板在对话内重建气泡（`SessionHistoryPanel` → `openSession`），HistoryView 页「查看」跳转向导页 `/procure/:id`（`HistoryView.vue:23-25`），同一份会话两种形态【已确认事实】。

### 1.3 逐页面四态覆盖矩阵

| 页面 | 加载 | 空 | 错误 | 成功 | 缺失/缺陷项 |
|---|---|---|---|---|---|
| LandingView | — | — | — | 静态页 | 无需四态 |
| LoginView | ✓（AppButton loading） | — | ✓ `:303` | ✓ 跳转 | 缺客户端校验；矮视口裁剪 `:318` |
| RegisterView | ✓ | — | ✓ `:300` | ✓ 跳转 | 仅校验密码一致，无必填/邮箱/强度校验 `:30-35` |
| HomeView | ✓ `:127` | ✓ 各面板 `:167/195/219/245` | **✗ error 定义但从不渲染** | ✓ | 失败静默降级 mock 且标签显示「暂无数据」`:89-91` |
| ProductsBomView | ✓ `:105` | ✓ `:145/168` | ✓ 降级提示 `:106` | ✓ | — |
| ShortageProcurementView | ✓ `:230` | ✓ `:253/315/355` | 部分（创建 RFQ 有 `:336`；发送/重算静默失败 `:161-163/199-201`） | ✓ `:344` | RFQ 状态英文直出 `:370` |
| ChatView | ✓ 思考中+AgentTimeline | ✓ welcome `:696` | ✓ 错误气泡+断流条 `:809-818` | ✓ | IME 未处理 `:212` |
| ProcureView | ✓ `:142` | ✓ isVague `:156` | **✗ streamError 无渲染出口** | ✓ | 移动端步骤条被顶栏遮挡 `:322-324` |
| HistoryView | ✓ `:56` | ✓ `:67` | ✓ `:62` | ✓ | 删除无确认 `:95`；「开始寻源」错链 `/` `:27-29`；无搜索 |
| CompanyChat | ✓ `:148/211` | ✓ `:164/186` | ✓ `:149`+错误气泡 `:104` | ✓ | IME 未处理 `:223` |
| CompanyAssistant | ✓ `:149` | ✓ `:124` | ✓ 错误气泡 `:57-62` | ✓ | IME 未处理 `:158` |
| AdminKnowledge | 部分（仅刷新按钮态） | ✓ `:197` | **✗ catch 仅 console.error `:37-38`** | ✓ | 全量生成无确认 `:147-149`；任务状态英文直出 `:178` |
| P7AdminAudit | ✓ skeleton `:177` | ✓ `:217` | ✓ `:178` | ✓ | **demo 模式内容整体消失 `:177-181`**；通过/驳回无确认、失败静默 `:142-160` |
| SupplierDashboard | ✓ `:116` | ✓ `:175` | ✓ `:117` | ✓ | declined 译「已拒绝」`:88`（与他页不一致） |
| SupplierLeads | ✓ skeleton `:202` | ✓ `:224` | ✓ `:203` | ✓ | **demo 模式列表整体消失 `:202-206`**；declined 译「已关闭」`:116` 而 Tab 写「已拒绝」`:221`；原生 `prompt()` `:140` |
| SupplierProducts | ✓ skeleton `:114` | ✓ `:121` | —（无 API） | ✓ | **全页假数据无标注 `:46-56`**；新增只改本地数组 `:30-40` |

### 1.4 旧审计（docs/ui-audit, 2026-07-17）结论复验

| 旧结论 | 复验结果 |
|---|---|
| global.css 浅色覆盖深色令牌 | **仍成立**（`main.ts:5-6` 导入顺序未变；`global.css:53-61` body 浅底深字覆盖 `base.css:16-24`，`--radius-lg` 10px→12px 冲突） |
| RfqEditor 手改正文被抹 / MLCC 硬编码 / slice(0,3) | **仍成立**（`RfqEditor.vue:150-170`、`121-122`、`100-107`） |
| urgent 排序沉底 | **仍成立**（`useDashboard.ts:20-22` 无 urgent 映射；`ShortageProcurementView.vue:55` 同用） |
| SSE 断流零反馈 | **部分修复**：ChatView 已加断流条（`:809-818`）；ProcureView 仍无出口 |
| 中文 IME 误发送（3 处） | **仍成立**（`ChatView.vue:212`、`CompanyChat.vue:223`、`CompanyAssistant.vue:158`） |
| Tag L5→danger 红 | **仍成立**（`Tag.vue:24`） |
| P7AdminAudit demo 队列消失 | **仍成立**（`:177-181`），且同构 bug 存在于 SupplierLeads（`:202-206`） |
| 供应商工作台错链 /products-bom | **部分成立**：链接仍在（`SupplierDashboard.vue:188`），但文案已改为「查看当前企业的可生产产品与 BOM」；真正问题是 `/supplier/products` 无导航入口 |
| 登录页 overflow:hidden | **仍成立**（`LoginView.vue:318`） |
| Landing 开发者黑话 | **仍成立**（`LandingView.vue:198-199`） |
| demos 僵尸代码 | **仍成立**（`views/demos/` 2 个未挂路由 .vue + 6 个 demo-*.html） |
| AdminKnowledge / SupplierProducts 浅色风格 | **已修复**（两页现均使用深色令牌） |
| HomeView mock 时标签「暂无数据」矛盾 | **仍成立**（`HomeView.vue:89-91`） |
| GradeCard 死代码 | **仍成立**（全 src 无引用）；新发现 `QueryInput.vue` 同为死代码 |
| 供应商 declined 翻译不一致 | **仍成立**（三处三种文案） |

---

## 2. 问题清单

### 问题 1：RFQ 编辑器字段改动静默抹掉手工正文，且品名硬编码 MLCC

- **所属模块**：寻源工作流 / `components/procure/RfqEditor.vue`
- **严重程度**：致命
- **影响范围**：所有使用 RFQ 编辑器的采购用户；非 MLCC 品类（电阻、钽电容、连接器等均在供应商品类字典中）生成错误询价单
- **发现依据**：`RfqEditor.vue:150-170`（fieldValues 深度 watch 全量重建正文，手工 textarea 修改（`:198-202`）在任意字段编辑后被 `buildRfqFromFields()` 覆盖）；`RfqEditor.vue:121-122`（模板 `一、品名` 下硬写 `多层陶瓷贴片电容 (MLCC)`，`part_name` 字段定义于 `:32` 却从未进入模板）
- **问题描述**：① 用户在正文里手改的内容，只要再碰任何一个结构化字段就被无提示地重建覆盖；② 无论查什么料，生成的询价单品名永远是「多层陶瓷贴片电容 (MLCC)」；③ 替代料自动硬取前 3 个非 L5（`:100-107`），用户无法选择纳入哪些
- **可能后果**：发出的正式询价单内容错误/丢失，采购事故；非 MLCC 场景产品不可用
- **推荐解决方案**：确立单一数据源——字段区改动前先快照手工正文脏标记，重建时弹确认或将正文锁定为「模板视图/手改视图」二选一；品名改用 `f('part_name')`；替代料改为勾选「纳入询价单」
- **修改成本**：中
- **优先级**：P0
- **是否影响当前上线**：是
- **是否需要重构**：否（组件内状态机调整）
- **验收标准**：手改正文后编辑任意字段，正文不被覆盖或有显式确认；用电阻类需求生成的 RFQ 品名不含「MLCC」；RFQ 中替代料条目可由用户勾选决定

### 问题 2：demo 模式下审核队列与供应商线索列表整体消失（v-if/v-else 条件链 bug）

- **所属模块**：管理端 `views/P7AdminAudit.vue`、供应商端 `views/supplier/SupplierLeads.vue`
- **严重程度**：致命
- **影响范围**：演示账号（当前主要演示路径）下两个页面的全部核心内容
- **发现依据**：`P7AdminAudit.vue:177-181`（`v-if="loading"` → `v-else-if="error"` → `v-if="isDemo"` 提示条 → `template v-else` 主体内容；demo 时命中 isDemo 分支，主体统计/列表永不渲染，`:269-271` 的只读提示成为死代码）；`SupplierLeads.vue:202-206` 完全同构
- **问题描述**：demo 登录后打开审核管理/供应商线索，只能看到一条「演示沙盘数据」提示条，队列/列表不渲染，尽管 `unifiedItems`/`demoLeads` 已正确准备了 demo 数据
- **可能后果**：演示链路两个关键页面呈空白，直接阻断「采购发 RFQ → 供应商收线索 → 报价」的演示闭环
- **推荐解决方案**：把 demo 提示条改为独立 `v-if` 的非互斥元素（与 loading/error 的 v-else 链解耦），主体内容用 `v-if="!loading && !error"` 渲染
- **修改成本**：低
- **优先级**：P0
- **是否影响当前上线**：是（演示账号必现）
- **是否需要重构**：否
- **验收标准**：demo 账号下审核队列、供应商线索列表正常渲染，且操作区显示只读提示

### 问题 3：高危不可逆操作零确认、零反馈

- **所属模块**：会话历史、审核管理、知识库管理
- **严重程度**：严重
- **影响范围**：数据安全与演示稳定性
- **发现依据**：`SessionHistoryPanel.vue:103-107`（单击 × 即删，无确认，按钮还 `opacity:0` hover 才可见 `:236-253`）；`HistoryView.vue:18-21,95`（同样单击直删）；`P7AdminAudit.vue:142-160`（通过/驳回单击生效、catch 静默、驳回不强制备注、无 submitting 态）；`AdminKnowledge.vue:51-59,147-149`（留空 ID + 勾选强制重生成 = 全量重建，单击即发，无确认；对比同页重建索引却有 confirm `:68`）
- **问题描述**：四类不可逆操作均无二次确认；失败时多数静默（catch 为空或仅 console），用户无法区分「成功」与「没反应」
- **可能后果**：误删会话/误驳回/误触发全量重建，且无法察觉失败
- **推荐解决方案**：新建共享 ConfirmDialog 组件接入四处；驳回强制填备注；所有操作按钮加 submitting 态；失败用页面内错误条反馈
- **修改成本**：低-中
- **优先级**：P0
- **是否影响当前上线**：是
- **是否需要重构**：否
- **验收标准**：四处操作均有确认弹层；驳回无备注时按钮禁用；操作失败出现可见错误提示；确认前不发起请求

### 问题 4：供应商「产品管理」页是纯本地假数据且无任何标注

- **所属模块**：供应商端 `views/supplier/SupplierProducts.vue`
- **严重程度**：严重
- **影响范围**：供应商角色的核心页面之一；产品可信度
- **发现依据**：`SupplierProducts.vue:46-56`（onMounted 用 setTimeout 400ms 写入 4 条硬编码产品模拟加载）；`:30-40`（新增产品仅 unshift 进本地数组，无任何 API 调用，刷新即丢）；页面无任何「演示数据」标识（对比其他 demo 页面均有 notice-bar）
- **问题描述**：页面标题「产品管理」、按钮「确认添加」均为真实功能语义，实际是内存数组；与其他页面的 mock 降级不同，这里连降级都不是——根本没有接 API 的尝试
- **可能后果**：用户（或演示观众）误以为产品已入库，对平台能力产生错误认知；演示时刷新露馅
- **推荐解决方案**：MVP 阶段二选一——接真实产品 API；或在页头加「演示数据，暂不持久化」标注条并禁用表单提交语义
- **修改成本**：低
- **优先级**：P0
- **是否影响当前上线**：是
- **是否需要重构**：否
- **验收标准**：页面有明确数据性质标注，或新增/上下架走真实接口并持久化

### 问题 5：urgent 优先级在排序中沉底

- **所属模块**：经营驾驶舱、缺件与采购 / `composables/useDashboard.ts`
- **严重程度**：严重
- **影响范围**：HomeView 推荐动作、ShortageProcurementView 推荐动作的排序正确性
- **发现依据**：`useDashboard.ts:20-22`（severityRank 仅映射 critical/high/medium/low，无 urgent）；`useDashboard.ts:76`（demo 动作 priority 会产生 `'urgent'`）；`useDashboard.ts:239-242`（sortedActions 按 severityRank(priority) 排序 → urgent=0 沉底）；`ShortageProcurementView.vue:53-56` 同样用法
- **问题描述**：最紧急的「urgent」动作在推荐列表中排到最后
- **可能后果**：采购优先处理低优先事项，紧急缺件被延误
- **推荐解决方案**：severityRank 增加 `urgent: 5`（或统一 priority/severity 词表）
- **修改成本**：低
- **优先级**：P0
- **是否影响当前上线**：是
- **是否需要重构**：否
- **验收标准**：含 urgent 动作的列表中 urgent 排首位

### 问题 6：三个对话页均未处理中文 IME 合成态，选词回车即误发送

- **所属模块**：ChatView、CompanyChat、CompanyAssistant
- **严重程度**：严重
- **影响范围**：所有中文输入用户（目标用户即中文采购）
- **发现依据**：`ChatView.vue:212-217`（handleKeydown 无 `e.isComposing` 判断）；`CompanyChat.vue:223`、`CompanyAssistant.vue:158`（`@keydown.enter="send()"` 同样无判断）；全 src 搜索 `isComposing` 0 命中
- **问题描述**：拼音输入法候选词状态下按 Enter 选词会直接触发发送
- **可能后果**：大量半截内容误发送，触发无意义寻源请求（有 LLM 调用成本）
- **推荐解决方案**：三处 Enter 处理统一加 `if (e.isComposing) return`；顺手抽共享 ChatInput 组件
- **修改成本**：低
- **优先级**：P0
- **是否影响当前上线**：是
- **是否需要重构**：否
- **验收标准**：中文输入法选词 Enter 不发送；英文输入 Enter 正常发送

### 问题 7：浅色 global.css 后加载覆盖深色令牌，双视觉语言并存

- **所属模块**：样式体系 / `styles/global.css`、`main.ts`
- **严重程度**：严重
- **影响范围**：全局；所有依赖 `--radius-lg`、body 底色、全局 `.btn/.card/.tag` 类的组件
- **发现依据**：`main.ts:5-6`（index.css 先、global.css 后）；`global.css:6-43` 重定义 `--radius-lg: 12px`（tokens.css:52 为 10px）、`global.css:53-61` body 浅底 `#f8fafc` 深字（覆盖 base.css:16-24 的深色）；`global.css:63-66` 链接色 `#2563eb` 覆盖 base.css:26-33；两套 `* { margin:0; padding:0 }` reset 重复
- **问题描述**：深色设计令牌与浅色遗留全局样式同时生效，后者覆盖前者；虽然各页面 scoped 样式大多显式铺了深色背景使肉眼难以察觉，但令牌语义已被污染
- **可能后果**：任何新组件若信任令牌就会拿到错误圆角/颜色；overscroll 露浅色底；维护者困惑
- **推荐解决方案**：main.ts 移除 global.css 导入；存量全局类（skeleton/empty-state/btn/tag-*）用深色令牌重写或迁入组件；tokens.css 归一为唯一令牌源
- **修改成本**：中
- **优先级**：P1
- **是否影响当前上线**：否（肉眼症状少），但阻塞视觉统一
- **是否需要重构**：部分是（样式体系归一）
- **验收标准**：main.ts 无 global.css；`--radius-lg` 单一来源；全站无浅色残留可见面

### 问题 8：无角色分流导航、管理页无权限引导、孤儿路由、无 404

- **所属模块**：信息架构 / `router/index.ts`、`components/layout/AppHeader.vue`
- **严重程度**：严重
- **影响范围**：全部登录用户；多角色演示场景
- **发现依据**：`AppHeader.vue:14-23`（8 个入口平铺混排：采购/协同/知识库管理/供应商工作台并列，无分组无角色过滤）；`router/index.ts:38-45`（守卫只验登录不验角色）；`/history`、`/admin/audit`、`/supplier/products`、`/supplier/leads` 均无侧栏入口（供应商两页仅能从工作台按钮进入）；router 无 `/:pathMatch(.*)*` 404 路由
- **问题描述**：采购、供应商、管理员三种角色看到完全相同的导航；普通用户可直达 `/admin/knowledge`、`/admin/audit`（依赖后端 403 兜底，前端无引导）；输错 URL 白屏
- **可能后果**：角色认知混乱；管理页面对非管理员暴露（UI 层）；坏链无兜底
- **推荐解决方案**：路由加 `meta.roles`，导航按角色过滤并分组（寻源/经营/供应商/管理）；侧栏补历史记录入口；加 404 页；管理页在前端做角色判断并给「无权限」态
- **修改成本**：中
- **优先级**：P1
- **是否影响当前上线**：演示多角色切换时影响明显
- **是否需要重构**：否（路由与导航配置层调整）
- **验收标准**：不同角色导航不同；四孤儿路由可达；任意错误 URL 渲染 404 页

### 问题 9：移动端 ProcureView 步骤条被顶栏遮挡；断点与容器宽失控

- **所属模块**：响应式 / `views/ProcureView.vue`、`App.vue`、`AppHeader.vue`
- **严重程度**：中等
- **影响范围**：≤920px 视口下的寻源向导页；全局响应式一致性
- **发现依据**：`ProcureView.vue:322-324`（sticky topbar `top:56px`）；移动端全局头部实际占 104px（AppHeader 侧栏变顶条 48px `:274-298` + topbar `top:48px` height 56px `:298`；App.vue:42-47 `padding-top:104px` 可佐证）；断点统计：640/700/768/820/920/960/980/1100 至少 8 套；max-width：900/960/1100/1180/1200/1240/1280/1320/1360 共 9 种；另 `ChatView.vue:883-896` 历史侧栏 fixed 280px 无移动端适配
- **问题描述**：移动端进入 `/procure/:id` 时步骤条 sticky 在 56px 处，被 104px 高的全局头部遮挡
- **可能后果**：移动端用户看不到寻源进度，主路径可感知性受损
- **推荐解决方案**：sticky 偏移令牌化（`--header-h: 56px` / `--header-h-mobile: 104px`）；断点统一为 640/920/1280 三档；容器宽收敛为三档；ChatView 历史侧栏小屏改全宽抽屉
- **修改成本**：低-中
- **优先级**：P1
- **是否影响当前上线**：仅移动端；桌面端演示不受影响
- **是否需要重构**：否
- **验收标准**：≤920px 下 ProcureView 步骤条完全可见；全站断点≤3 套

### 问题 10：无障碍系统性缺失（焦点/动效/读屏/弹层/对比度）

- **所属模块**：全局 a11y
- **严重程度**：中等（B 端内部工具场景）；若投标有合规要求则严重
- **影响范围**：键盘用户、读屏用户、前庭敏感用户
- **发现依据**：全 src 搜索 `prefers-reduced-motion`、`focus-visible`、`aria-live`、`role="dialog"`、`role="alert"` 均 **0 命中**【已确认事实】；`outline: none` 13+ 处（如 `LoginView.vue:407`、`SpecConfirm.vue:149`、`RfqEditor.vue:438`），焦点指示仅靠 border 变色；`LoginView.vue:235-237` 无限 rAF 动画无降级（注册页同）；`SessionHistoryPanel.vue:236-253` 删除按钮 `opacity:0` hover 才现，键盘/触屏不可达；`SupplierLeads.vue:265-266` 报价弹层无 dialog 语义、无焦点圈禁、无 Esc 关闭；`ChatView.vue:694` 消息流无 live region；错误提示（如 `LoginView.vue:303`）无 `role="alert"`；`SpecConfirm.vue:69-75` 表格输入框无 label/aria-label
- **问题描述**：无障碍基础设施为零。主按钮白字/靛蓝对比度 4.47:1、accent 文字 4.22:1 不达 AA 4.5:1【尚未验证：数字沿用 docs/ui-audit/10，本次未用工具重新测量】
- **可能后果**：键鼠以外用户不可用；企业采购合规审查被卡
- **推荐解决方案**：全局 `:focus-visible` 规则（`--focus-ring` 令牌）；`prefers-reduced-motion` 媒体查询统一关闭动画，登录页 Canvas 在 reduced-motion 下不启动；ChatView 消息区加 `aria-live="polite"`、错误条加 `role="alert"`；弹层加 `role="dialog"` + 焦点管理 + Esc；hover-only 按钮改为恒显；对比度微调到 AA
- **修改成本**：中
- **优先级**：P1
- **是否影响当前上线**：否（除非客户有合规条款）
- **是否需要重构**：否
- **验收标准**：键盘 Tab 全程可见焦点；reduced-motion 下无动画；读屏可感知新消息与错误；弹层 Esc 可关且焦点不逃逸

### 问题 11：HomeView 后端失败静默降级 mock，数据源标签显示「暂无数据」误导

- **所属模块**：经营驾驶舱 / `views/HomeView.vue`、`composables/useDashboard.ts`
- **严重程度**：中等
- **影响范围**：后端不可用时所有访问驾驶舱的用户
- **发现依据**：`useDashboard.ts:203-215`（catch 后降级 mock 并置 `dataSource='mock'`，error 有值）；`HomeView.vue` 全文无 `error` 渲染【已确认事实：Grep 0 命中】；`HomeView.vue:89-91`（mock 时标签文案为「暂无数据」——但页面正展示着 mock 数据）
- **问题描述**：接口挂了用户看到的是完整「数据」，唯一提示是角落一个写着「暂无数据」的灰标签，语义自相矛盾
- **可能后果**：用户把演示数据当经营实况做决策
- **推荐解决方案**：mock 降级时显示醒目黄色提示条（参考 ShortageProcurementView `:231` 的 notice-bar 做法），标签文案改「本地兜底数据」
- **修改成本**：低
- **优先级**：P1
- **是否影响当前上线**：后端不稳定时是
- **是否需要重构**：否
- **验收标准**：断网/后端 500 时驾驶舱出现明确降级提示，且不与展示内容矛盾

### 问题 12：ProcureView（向导页）SSE 断流零反馈

- **所属模块**：寻源工作流 / `views/ProcureView.vue`
- **严重程度**：中等
- **影响范围**：从历史记录进入向导页且遇到断流的用户
- **发现依据**：`ProcureView.vue:21-39`（storeToRefs 未取 `streamError/streamNotice`），模板无断流 UI；对比 ChatView 已有断流条 `ChatView.vue:809-818`
- **问题描述**：向导页断流后 AgentTimeline 永远转圈，无任何错误提示与重试入口
- **推荐解决方案**：渲染 streamError 横幅 + 重试按钮；或中期将 ProcureView 合并进 ChatView 单一工作流（推荐，见问题 20）
- **修改成本**：低
- **优先级**：P1
- **是否影响当前上线**：边缘路径（仅历史记录入口）
- **是否需要重构**：否
- **验收标准**：向导页断流时出现可见错误与重试

### 问题 13：表单校验普遍薄弱

- **所属模块**：认证、缺件 RFQ 表单、供应商报价
- **严重程度**：中等
- **影响范围**：数据质量与出错成本
- **发现依据**：`RegisterView.vue:30-35`（仅校验两次密码一致；姓名/公司/账号可空、无邮箱格式、无密码强度——尽管 placeholder 承诺「至少 8 位，包含字母和数字」`:293`）；`LoginView.vue:22-33`（空账号密码可提交）；`ShortageProcurementView.vue:339`（仅 `!rfqForm.title` 禁用，数量可为 0/负数，候选供应商 ID 为逗号分隔手输 `:334`）；`SupplierLeads.vue:290`（报价仅 `unit_price>0`，MOQ/交期可为负）；`RfqEditor.vue:323-330`（必填字段缺失时「标记已发送」不拦截，仅有警告条 `:232-239`）
- **推荐解决方案**：注册/登录加必填+格式校验与行内错误；RFQ/报价表单数量类字段加 min=1 与行内提示；RfqEditor 必填缺失时禁用「标记已发送」；供应商候选改为从关系列表多选而非手输 ID
- **修改成本**：中
- **优先级**：P1
- **是否影响当前上线**：否（后端有校验兜底时）
- **是否需要重构**：否
- **验收标准**：上述空值/非法值在提交前被行内拦截并给出中文提示

### 问题 14：Landing 页混入开发者黑话，且与实际产品定位漂移

- **所属模块**：公开页 / `views/LandingView.vue`
- **严重程度**：中等
- **影响范围**：首因效应；对外演示
- **发现依据**：`LandingView.vue:198-199`（「Ready for Spike」「先演示完整寻源链路，再接真实数据和后端鉴权」——内部开发话术）；`LandingView.vue:143`（「介绍页只讲产品，不承载业务操作」——设计原则当标题）；定位漂移：Landing 全文只讲「替代料寻源工具」，而应用内品牌副标题已是「产业链 AI 经营驾驶舱」（`AppHeader.vue:44`），驾驶舱/缺件/BOM/协同问答/供应商端在 Landing 均无体现；`LandingView.vue:63-67` 指标「10 min 目标完成一次替代寻源」无出处【尚未验证】
- **可能后果**：访客对产品能力形成错误/过窄预期；开发者话术损害专业感
- **推荐解决方案**：删除黑话段落，CTA 改为「预约演示/进入工作台」；按当前实际能力重写 Landing（或将副标题收敛回寻源定位）；「10 min」等数字标注为目标值或删除
- **修改成本**：低
- **优先级**：P1
- **是否影响当前上线**：对外演示时是
- **是否需要重构**：否
- **验收标准**：Landing 无内部术语；宣称能力与路由内实际页面一一对应

### 问题 15：Tag 组件将 L5「仅供参考」映射为 danger 红色

- **所属模块**：设计系统 / `components/ui/Tag.vue`
- **严重程度**：中等
- **影响范围**：替代料卡片的风险语义（采购判断场景）
- **发现依据**：`Tag.vue:18-27`（L5→`tag--danger`）；L5 语义为「仅作参考」（`AlternativesList.vue:56`），global.css:25 中 L5 本是灰色 `#9ca3af`
- **问题描述**：最弱证据等级的料被标成与「危险/错误」同色的红色，而红色在采购语义中应留给真正的风险项；且与 L4（橙色 notice）形成「更危险」的视觉误读
- **推荐解决方案**：L5 改 `tag--neutral`
- **修改成本**：低
- **优先级**：P1
- **是否影响当前上线**：否，但影响判断准确性
- **是否需要重构**：否
- **验收标准**：L5 标签为中性灰色，与 L1-L4 色阶语义一致

### 问题 16：交互一致性差：同类操作多套实现

- **所属模块**：设计系统与组件复用
- **严重程度**：中等
- **影响范围**：全站维护成本与体验一致性
- **发现依据**【均已确认事实】：
  - 状态标签 4+ 套：`Tag.vue` 组件、`HomeView.vue:471-485` `.sev`、`ShortageProcurementView.vue:554-558` `.status-pill`、`SupplierDashboard.vue:261-270` `.state-*`、`P7AdminAudit.vue:337-342` 与 `SupplierLeads.vue:338-342` 各自的 `.tag-*`（同名不同义）
  - 空态 5+ 套：global.css `.empty-state`、各页 `.empty-line`、`.chat-empty`、`sess-panel__empty`、`sups__empty`
  - 加载 4+ 套：global.css `.loading-spinner`、各页 `.loading-bar`、两处 `.skeleton`（global.css:207 浅色版 + 各页深色版如 `SupplierLeads.vue:346`）、各种 spinner
  - 对话输入区 3 套：`ChatView.vue:819-833`（textarea+Enter 发送）、`CompanyChat.vue:217-227`、`CompanyAssistant.vue:157-161`（单行 input）
  - 按钮 2 套：`AppButton` 组件与大量原生 button 本地类（ShortageProcurementView、AdminKnowledge、DemoConsole 基本不用 AppButton）
  - 登录/注册两套平行样式：`auth-*`（LoginView）vs `register-*`（RegisterView），且 ~180 行 Canvas 动画代码逐字复制（`LoginView.vue:50-241` ≈ `RegisterView.vue:51-232`）
  - 死代码：`GradeCard.vue`（0 引用，线索卡在 ChatView:782-801 与 ProcureView:254-268 内联重复实现 2 份）、`QueryInput.vue`（0 引用）
- **推荐解决方案**：收敛为 StatusTag/EmptyState/Skeleton/ChatInput 共享组件；ChatView/ProcureView 线索卡改用 GradeCard；登录注册抽 AuthLayout；Canvas 动画抽 composable
- **修改成本**：中
- **优先级**：P1
- **是否影响当前上线**：否
- **是否需要重构**：部分是
- **验收标准**：同类模式各只有 1 个共享实现；死代码删除

### 问题 17：HistoryView「开始寻源」错链到 Landing 页

- **所属模块**：历史记录 / `views/HistoryView.vue`
- **严重程度**：轻微
- **发现依据**：`HistoryView.vue:27-29`（`newProcure` 跳 `/`）；`:70-71`（空态文案「去首页试试」+ 按钮「开始寻源」，实际去了公开 Landing）
- **问题描述**：空态 CTA 把登录用户带回公开介绍页而非 `/chat`
- **推荐解决方案**：改为 `router.push('/chat')`
- **修改成本**：低
- **优先级**：P2
- **是否影响当前上线**：否
- **是否需要重构**：否
- **验收标准**：空态点击「开始寻源」进入 /chat

### 问题 18：供应商端状态文案三处不一致 + 原生 prompt + 静默失败

- **所属模块**：供应商端 / `SupplierDashboard.vue`、`SupplierLeads.vue`
- **严重程度**：轻微
- **发现依据**：declined 译文：`SupplierDashboard.vue:88`「已拒绝」、`SupplierLeads.vue:116`「已关闭」、`SupplierLeads.vue:221` Tab 又写「已拒绝」；`SupplierLeads.vue:140` 原生 `prompt('拒绝理由（可选）:')`；`:128-147` 查看/拒绝 catch 静默；`ShortageProcurementView.vue:370` RFQ 状态英文枚举直出（draft/sent/quoted/closed），`AdminKnowledge.vue:178` 任务状态英文直出
- **推荐解决方案**：状态字典抽共享模块统一中英文映射；拒绝理由改内联弹层；失败加错误提示；英文枚举全部中文化
- **修改成本**：低
- **优先级**：P2
- **是否影响当前上线**：否
- **是否需要重构**：否
- **验收标准**：同一状态全站一个中文名；无原生 prompt/alert（管理页 confirm 除外，统一换 ConfirmDialog 后一并消灭）

### 问题 19：demos 僵尸代码与演示控制台硬编码

- **所属模块**：工程卫生 / `views/demos/`、`components/demo/DemoConsole.vue`
- **严重程度**：轻微
- **发现依据**：`views/demos/LoginWithHolo.vue`、`LoginHoloPro.vue` 未挂路由（router 无记录）+ 同目录 6 个 demo-*.html；`DemoConsole.vue` 硬编码色值 25+ 处（`:259-471`，如 `#111520/#394258/#7c83ff`），挂载于所有非空白页（`App.vue:18`），仅 demo 用户可见（`DemoConsole.vue:191`）
- **推荐解决方案**：删除 demos 目录与 6 个 html（Git 历史可查）；DemoConsole 色值令牌化
- **修改成本**：低
- **优先级**：P2
- **是否影响当前上线**：否
- **是否需要重构**：否
- **验收标准**：views/demos 不存在；DemoConsole 无硬编码色值

### 问题 20：寻源 RFQ「发送」后的闭环断点与双工作流割裂

- **所属模块**：信息架构 / ChatView、ProcureView、RfqEditor
- **严重程度**：中等
- **影响范围**：核心闭环「询价单生成 → 分级线索推给上游」的用户认知
- **发现依据**：`stores/procure.ts:408-410`（markRfqSent 仅置本地 flag）；`RfqEditor.vue:323-330`（按钮即「标记已发送」，点击后仅变「已发送 ✓」，无推送对象、无下一步引导）；寻源 RFQ 与缺件页手工 RFQ（`ShortageProcurementView.vue:112-154`，走真实 `/rfq` 接口并可「发送给供应商」`:346`）是两套数据和语义；ProcureView（向导）与 ChatView（对话）两套工作流并存且互不跳转
- **问题描述**：AI 寻源生成的 RFQ 在 UI 上无法真正送达供应商——能真发送的只有缺件页手工 RFQ。用户无法从界面理解两者关系，「标记已发送」后流程即终止，线索分级卡之后没有任何动作
- **可能后果**：README 宣称的闭环在 UI 层断裂；演示时观众问「然后呢」无答案
- **推荐解决方案**：MVP 阶段最小动作：RfqEditor 发送区明确文案「本询价单为草稿，前往『缺件与采购』创建正式 RFQ 并发送」+ 一键携带参数跳转；中期合并 ProcureView 与 ChatView 为单一工作流、两条 RFQ 路径合一
- **修改成本**：低（文案+跳转）/ 中（合并）
- **优先级**：P1
- **是否影响当前上线**：闭环演示时是
- **是否需要重构**：中期需要（双工作流合一）
- **验收标准**：用户在 AI 寻源 RFQ 卡片上能看到明确的下一步路径并一键到达；不出现「发送」无实际语义的按钮

---

## 3. 事实与推断标注汇总

**【已确认事实】**（均有上文文件:行号证据）
- 问题 1、2、3、4、5、6、7、8、9、11、12、13、15、16、17、18、19、20 的全部代码证据
- Landing 8 张配图存在于 `web/public/assets/`
- 全 src 0 处 `prefers-reduced-motion` / `focus-visible` / `aria-live` / `role="dialog"` / `role="alert"` / `isComposing`
- 旧审计 16 条结论的逐条复验结果（见 1.4 表）：12 条仍成立、2 条部分成立、2 条已修复（AdminKnowledge/SupplierProducts 浅色、ChatView 断流反馈）
- 主路径 6 步、四态矩阵中各「✓/✗」标记

**【合理推断】**
- 移动端 ProcureView 步骤条被遮挡（由三处 CSS 数值推导：AppHeader 移动端 48+56px vs sticky top:56px，未真机截图验证）
- 「urgent 沉底」的实际排序表现（由 severityRank 缺映射 + sort 用法推导，未运行时验证）
- 双 RFQ 路径会造成用户困惑（由两套界面语义推导）

**【尚未验证】**
- 对比度具体数值（4.47:1 / 4.22:1 沿用 docs/ui-audit/10，本次未用测量工具重算）
- 「标记已发送」是否在后端有副作用（前端仅见本地 flag，未审后端接口）
- Landing「10 min 目标完成一次替代寻源」的数据出处
- 各页面真实渲染效果（本次为纯代码审计，未启动 dev server 截图核对；demo 消失类 bug 已通过条件链逻辑确认，但视觉呈现未截图）

**【缺少材料】**
- 无真实用户/采购角色的可用性测试数据
- 无设计稿或 PRD 级的导航/角色权限规格，无法判断「8 入口平铺」是有意为之还是欠设计
- 无移动端适配的目标设备清单

---

## 4. 领域评分

### 评分一：视觉体系与设计系统 —— 5 / 10

依据：
- 加分：深色令牌体系完整（tokens.css 背景/边框/文本/状态色/圆角/阴影/字阶俱全）；核心工作流组件（AlternativesList 的 L5 折叠区、SuppliersMatch 的免责声明+对比视图、AgentTimeline）设计成熟度高于一般 MVP；旧审计指出的浅色残留页面已修复。
- 扣分：global.css 双视觉语言仍并存（问题 7）；同类模式 4-5 套重复实现、2 个死组件（问题 16）；登录/注册两页 ~180 行复制代码与 DemoConsole 25+ 硬编码（问题 19）；L5 误用 danger 色（问题 15）。

### 评分二：交互可用性与任务完成度 —— 4 / 10

依据：
- 加分：主路径 6 步可达且有实时进度反馈；四态覆盖率约 80%（1.3 矩阵）；ChatView 断流反馈已补上。
- 扣分：两个致命正确性缺陷直接破坏核心交付物与演示路径（问题 1 RFQ 抹字+MLCC 硬编码、问题 2 demo 队列/列表消失）；urgent 沉底（问题 5）；IME 误发送（问题 6）；高危操作零确认（问题 3）；供应商产品页假数据无标注（问题 4）；「发送」闭环在 UI 上断裂（问题 20）。这些都是「UI 导致业务结果错误」级别的问题，不是美观问题。
- 无障碍基础设施为零（问题 10）与无角色导航（问题 8）进一步拉低企业场景可用性。

**总评**：MatchForge 前端的主流程骨架与组件设计意识明显好于多数原型阶段项目，且旧审计后已有实质修复（断流反馈、浅色系页面、demo 标注）。但当前仍有一批「页面看起来正常、业务结果却是错的」的 P0 缺陷，修复成本低（多数为低/中成本），建议在下一轮迭代优先清零问题 1-6，再推进视觉统一（问题 7、16）与导航角色化（问题 8）。
