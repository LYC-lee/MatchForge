# 供应商端（工作台 / 线索 / 产品）UI 分析报告

## 1. 现状概述

供应商端三个页面均为深色主题自研样式，复用设计令牌（`--bg-2`、`--accent` 等）与 `AppButton`，整体视觉基调与采购方端一致。结构为：工作台（统计卡 + 最近线索表 + 快速入口）、线索页（统计条 + 状态 Tab + 卡片流 + 报价弹层）、产品页（内联添加表单 + 产品卡片流）。三页同时支持真实 API 与演示沙盘双数据源，demo 分支逻辑内嵌在组件内。主要问题是：共享组件（`components/ui/Card.vue`、`Tag.vue`）完全未被使用，各页重复自绘且参数互不一致；线索状态机的文案、色彩、流转交互粗糙；产品页为纯前端 mock，无持久化、无编辑/删除/搜索；信息架构上工作台快速入口错链到采购方页面。

## 2. 问题清单

### 🔴 严重（影响可用性/明显缺陷/体验断裂）

1. **工作台"产品与 BOM"快速入口错链到采购方页面**：点击后跳到 `/products-bom`（采购方的产品 BOM 视图），而非 `/supplier/products`，供应商被带入另一个角色的信息空间，且供应商自己的产品管理页反而没有入口。[证据 SupplierDashboard.vue:188 `router.push('/products-bom')`]

2. **产品管理页是纯假数据，无任何持久化**：`onMounted` 里 `setTimeout(400ms)` 注入 4 条硬编码产品，新增只 push 进本地 `ref` 数组，刷新即丢失；无编辑、无删除、无搜索、无分页。供应商的核心资产（产品目录）在此完全不可真实管理。[证据 SupplierProducts.vue:46-56 `setTimeout(() => { products.value = [...]`、:33 `id: \`P${Date.now()}\``]

3. **同一状态两页文案矛盾**：`declined` 在工作台译为"已拒绝"，在线索页译为"已关闭"；而线索页 demo 映射又把"RFQ 关闭"直接塌缩成 `declined`——供应商无法分辨是"我拒绝了"还是"采购方关闭了"，状态语义被两页各自改写。[证据 SupplierDashboard.vue:88 `declined: '已拒绝'`、SupplierLeads.vue:116 `declined: '已关闭'`、SupplierLeads.vue:88 `(i.rfq_status === 'closed' ? 'declined' : 'sent')`]

4. **拒绝线索使用浏览器原生 `prompt()`**：白底原生对话框与全站深色主题完全断裂，且无取消保护、无输入校验。[证据 SupplierLeads.vue:140 `const note = prompt('拒绝理由（可选）:')`]

5. **关键操作失败被静默吞掉**："标记已查看""拒绝"两处 `catch {}` 空实现，接口失败时用户看到的状态与后端实际状态不一致，无任何提示。[证据 SupplierLeads.vue:133-135、:144-146 `// 静默失败`]

6. **demo 模式下线索状态机塌缩，Tab 出现恒空死区**：demo 分支只产出 `quoted / sent / declined` 三态，`viewed` 永远不会出现，"已查看"Tab 恒为空；`handleView`/`handleDecline` 在 demo 下直接 return，按钮却被 `v-if="!isDemo"` 隐藏，卡片在 demo 下零操作可用但未在视觉上说明只读（仅顶部一条 notice）。[证据 SupplierLeads.vue:88、:129 `if (isDemo.value) return`、:255-257]

### 🟡 中等（不一致、效率低、可感知粗糙）

7. **共享组件零复用，三页重复自绘且参数互相打架**：项目已有 `Card.vue`（`--radius-lg`、padding `--space-5`）与 `Tag.vue`（height 22px、font-mono、tag--success 等），三页均未引入，而是各自重写 `.card`/`.tag`：工作台卡片 `var(--radius-lg)`（10px），线索页卡片硬编码 `8px`，弹层硬编码 `12px`，notice-bar 硬编码 `6px`。[证据 SupplierLeads.vue:325 `border-radius: 8px`、:351 `border-radius: 12px`、SupplierDashboard.vue:233；对照 components/ui/Card.vue:26、Tag.vue:48-55]

8. **状态标签存在两套并行类名体系**：工作台用 `state-pending/state-new/state-contacted/state-won/state-lost`（把线索状态硬套 CRM 话术，quoted→"won"、declined→"lost"），线索页用 `tag-blue/tag-yellow/tag-green/tag-gray`，同一状态在两页由不同类名、不同命名语义渲染，维护时极易改漏。[证据 SupplierDashboard.vue:96-99、:266-270；SupplierLeads.vue:123、:339-342]

9. **工作台与线索页的统计视觉/口径不一致**：工作台是 4 列大数字 `stat-card`（`--font-size-3xl`），线索页是横向 `stat-chip`（`--font-size-2xl`）；工作台"活跃线索"排除 `quoted`（已报价不算活跃？供应商正等结果的反而被隐藏），线索页统计又无"活跃"概念。[证据 SupplierDashboard.vue:63、:229-237；SupplierLeads.vue:104-112、:318-320]

10. **报价弹层不用 AppButton，按钮样式自成第三套**：`btn-submit` 用 `--gradient-accent` 渐变（全站主按钮均为纯色 `--accent`），`btn-cancel` 手写边框按钮；同问题在 ShortageProcurementView 也存在，说明缺少共享 Modal/表单按钮约定。[证据 SupplierLeads.vue:289-290、:365-367]

11. **弹层输入框层级色错误**：Modal 背景 `--bg-1`，输入框背景 `--bg-2`，输入框比底色更亮，违背"输入区下凹"的深色层级惯例（工作台卡片是 `--bg-2`、其内输入应是 `--bg-3`）。产品页表单恰好用了 `--bg-3`，两页表单控件底色不一致。[证据 SupplierLeads.vue:351 `background: var(--bg-1)`、:362 `background: var(--bg-2)`；SupplierProducts.vue:213 `background: var(--bg-3)`]

12. **报价默认值直接预填采购方目标价**：`unit_price: lead.target_price || 0`，把买方底价作为卖方报价默认锚点，商业逻辑上引导供应商按底价报价；且 `unit_price <= 0` 只 disable 按钮，无错误提示文案。[证据 SupplierLeads.vue:153、:290 `:disabled="submitting || quoteForm.unit_price <= 0"`]

13. **供应商最关心中标结果，真实模式下无处可见**：demo 分支展示了"我的报价""已选定"徽标，真实 API 分支没有渲染任何报价回执/中标状态；已报价线索只有一个绿色"已报价"文字，看不到自己报的价格和交期。[证据 SupplierLeads.vue:250-251（仅 `v-if="isDemo"`）、:258 `quoted-tag`]

14. **工作台 loading 是值快照而非响应式**：demo 分支 `loading.value = demo.loadingSupplier.value` 只在 `fetchLeads` 调用瞬间取值，之后 demo 加载完成不会回写，骨架/加载条可能卡住。[证据 SupplierDashboard.vue:23、SupplierLeads.vue:39]

15. **线索列表效率低**：无排序（新线索不按时间/金额排）、无搜索、无分页、Tab 无计数徽标；`buyer_name` 缺失时 fallback 为 `企业{id}`，露出内部 ID。[证据 SupplierLeads.vue:217-221、:77 `` `企业${i.buyer_company_id}` ``]

16. **产品页双状态维度堆叠且控件可点击性弱**：`stock===0` 显示"缺货"黄 tag，`status` 又有"已上架/已下架" toggle，P004 同时挂"缺货+已下架"两个信号，语义重叠；`status-toggle` 是无边框类 tag 样式，无 hover 指针反馈外的 affordance，无确认/撤销。[证据 SupplierProducts.vue:138-146、:252-264]

17. **产品表单缺基础校验与编辑闭环**：必填仅 disable 按钮无提示；无"编辑"入口，改库存只能下架再上架；品类硬编码 5 项与平台品类体系未打通。[证据 SupplierProducts.vue:106 `:disabled="!formData.partNumber || !formData.brand"`、:58 `categories`]

18. **细节粗糙点**："查看全部 ->"用 ASCII 箭头；空态引号中英混排（"添加产品"为直角引号）；mock 日期为未来日期 2026-07-14；产品页缺 `eyebrow` 企业名（另两页有）。[证据 SupplierDashboard.vue:145；SupplierProducts.vue:124、:49、:64-65]

### 🔵 建议（锦上添花）

19. 工作台"最近线索"表格缺目标价、交期两列——这正是供应商决定"接不接"的首要信息，建议替换"RFQ 编号"为次要位置，新增目标价/交期/操作直达报价。[证据 SupplierDashboard.vue:152-158]

20. 统计卡顺序建议按供应商心智排序：新询价待处理（行动项）→ 已报价待结果 → 活跃 → 总数；`newInquiries` 为 0 时不应再渲染警告黄。[证据 SupplierDashboard.vue:121-138、:131]

21. 线索卡片 meta 已取到 `match_score`/`match_reason` 但未展示，建议加"匹配度"徽标帮助供应商判断中标概率。[证据 SupplierLeads.vue:86-87]

22. 报价弹层缺 Esc 关闭、焦点圈定与提交成功反馈（toast/状态条），关闭即无感知。[证据 SupplierLeads.vue:265]

23. 产品列表对多 SKU 场景建议改为表格视图 + 批量上下架；库存为 0 的"缺货"可与低库存阈值（如 <MOQ×2）合并为库存健康度一列。

## 3. 优化方案

**P0-1 修正信息架构与路由（半天）**：`SupplierDashboard.vue:188` 快速入口改为 `/supplier/products`；若确需保留 BOM 入口则单列并标注"采购视图"。同时在产品页补上 `eyebrow` 企业名，与其他两页页头对齐。理由：这是供应商端最明显的角色越界断裂。

**P0-2 统一线索状态字典并抽成共享模块（1 天）**：新建 `web/src/utils/leadStatus.ts`，集中定义 `{ pending, sent, viewed, quoted, declined, closed }` 的 label/语义色，工作台与线索页共同引用；`declined` 统一为"已拒绝"，`closed` 独立为"已关闭"并在 demo 映射中不再塌缩（`SupplierLeads.vue:88` 的 `closed→declined` 改为 `closed`）；弃用 `state-won/state-lost` 这套 CRM 命名。理由：状态语义矛盾是当前最大的认知风险，且消除两套 tag 类名是后续一切一致性的前提。

**P0-3 替换原生 prompt + 补齐失败反馈（1 天）**：`SupplierLeads.vue:140` 的 `prompt()` 换成与报价弹层同款的内联确认弹层（可顺带抽出 `AppModal` 到 `components/ui/`）；`handleView`/`handleDecline` 的 `catch{}` 至少回滚乐观状态并 toast 报错。理由：原生弹窗是当前视觉断裂最严重的一点，静默失败直接导致数据不可信。

**P0-4 产品页接入真实 API 或明确降级为演示态（2-3 天）**：对接企业产品接口（`api/enterprise.ts` 已有企业域封装可扩展）；在接口未就绪前，页面顶部加与线索页一致的"演示数据"notice，避免用户误以为数据已保存。同时补编辑（行内改库存/MOQ）、删除、按品类/关键字筛选。理由：产品目录是供应商的根基数据，纯本地 mock 属于功能性缺陷。

**P1-1 复用共享组件，收敛卡片/标签/按钮参数（1 天）**：三页 `.card` 替换为 `components/ui/Card.vue`，状态徽标替换为 `Tag.vue`（或在其上扩展 lead 语义 type）；圆角全部走令牌（卡片 `--radius-lg`、tag `--radius-sm`），删除 `8px/12px/6px` 硬编码；弹层按钮改用 `AppButton`（primary/ghost），移除渐变 `btn-submit`。理由：一次替换即可消灭 #7/#8/#10 三个中等问题及后续漂移。

**P1-2 修正表单控件层级色（0.5 天）**：统一约定输入控件底色为 `var(--bg-3)`（页面/卡片 `--bg-2`、弹层 `--bg-1` 之上均成立），改 `SupplierLeads.vue:362` 的 `--bg-2`；报价弹层 `.modal-info` 与输入区间保持同一对比逻辑。理由：深色层级错误是小改动高收益的可感知粗糙点。

**P1-3 让"报价后"状态可见（1 天）**：真实模式下在线索卡片展示"我的报价"（单价/交期）与采购方反馈（中标/未中/失效），复用 demo 分支已有的 `meta-quote/meta-win` 样式；已报价线索允许"修改报价"。理由：供应商报价后最关心结果，当前只能看到"已报价"三个字，是信息优先级倒置。

**P2-1 优化工作台信息优先级（0.5 天）**：统计卡按"新询价待处理 → 已报价 → 活跃 → 总数"排序，0 时不渲染警告色；最近线索表加目标价、交期列，"处理"按钮带 query 直达对应线索（`/supplier/leads?focus={id}`）。理由：把第一屏让给行动项而非虚荣指标。

**P2-2 修复 demo loading 快照与 demo 只读表达（0.5 天）**：`loading` 改为 computed 合并 `demo.loadingSupplier`；demo 模式在线索卡片操作区渲染"演示模式 · 只读"徽标替代空白。理由：消除加载卡死隐患，并明确 demo 下的交互预期。

**P2-3 报价锚点改为成本导向（0.5 天）**：`openQuote` 不再用 `target_price` 预填单价，改为留空 + placeholder 提示"目标价 ¥X"；`unit_price<=0` 时在按钮旁给错误文案而非仅 disable。理由：避免平台默认引导供应商贴底价报价的商业伦理与体验问题。
