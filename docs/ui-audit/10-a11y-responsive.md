# 可访问性（a11y）与响应式专项审查报告

> 审查范围：`web/src` 全部 `.vue` / `.css`（Grep 全量扫描 aria- / role= / tabindex / @media / :focus / outline / alt= / prefers-reduced-motion 等模式），并对 `ChatView.vue`、`ProcureView.vue`、`LoginView.vue`、`AppHeader.vue`、`SuppliersMatch.vue`（对比表格）、`P7AdminAudit.vue`、`SupplierDashboard/Leads.vue`、`ChatMessage.vue`、`SpecConfirm.vue`、`AppButton.vue`、`tokens.css`、`base.css` 等做逐行精读。
> 对比度结论均按 WCAG 相对亮度公式对 `tokens.css` 实际色值计算得出。

## 1. 现状概述

前端为全自研组件的深色主题 SPA。语义化基础尚可：`index.html` 有 `lang="zh-CN"` 与标准 viewport；登录/注册表单用 `<label>` 包裹控件；`ChatView` 用 `<details>/<summary>` 做时间线折叠；表格页普遍使用 `<table><thead><th>`。但整体 a11y 投入极少：全代码库 `aria-*` 仅 5 处、无 `tabindex`、无 `:focus-visible`、无 `prefers-reduced-motion`；焦点样式以「`outline: none` + 边框变色」为主，经实测焦点指示对比度仅约 1.5:1，远低于 WCAG 3:1。响应式方面多数页面有 640–1100px 区间的断点，但断点值不统一（640/700/768/820/920/960/980/1100 共 8 种），核心页面 `ChatView` 完全没有任何媒体查询。28 个文件共 80 处动画/过渡，全部无降级。

## 2. 问题清单

### 🔴 严重（影响可用性/明显缺陷/体验断裂）

1. **全站焦点可见性体系失效，键盘用户无法定位焦点**
   - 所有输入控件统一 `outline: none`，焦点仅表现为边框变色：[证据 web/src/views/LoginView.vue:407 `outline: none`；web/src/views/P7AdminAudit.vue:312-313；web/src/components/procure/SuppliersMatch.vue:441-443；web/src/components/procure/RfqEditor.vue:438-441；web/src/views/ChatView.vue:984]
   - 焦点边框 `border-color: var(--accent-border)`（rgba(99,102,241,0.35)）在输入底色 `#151924` 上混合后仅 **1.53:1**，`box-shadow: 0 0 0 3px var(--accent-soft)`（12% alpha）仅 **1.13:1**，远低于 WCAG 1.4.11 / 2.4.7 要求的 3:1（LoginView.vue:408）。
   - 按钮/链接/标签页没有任何 `:focus-visible` 样式：[证据 web/src/components/ui/AppButton.vue:30-67 全文无 focus 规则；web/src/views/P7AdminAudit.vue:308 `.tab` 无 focus 规则]。
   - 全库 grep 不到一处 `:focus-visible`、一处 `tabindex`。

2. **完全无 `prefers-reduced-motion` 支持，且存在不可停止的持续动画（WCAG 2.2.2 / 2.3.3）**
   - 28 个文件 80 处 `animation/transition`；`prefers-reduced-motion` grep 命中 0 处。
   - 登录页全息投影 Canvas 用 `requestAnimationFrame` 无限循环绘制扫描线/光束，无暂停、无降级：[证据 web/src/views/LoginView.vue:235-237 `animId = requestAnimationFrame(draw)`]。
   - 无限循环动画多处：spinner（AppButton.vue:77）、`.pulse`（StepNav.vue:82-87）、骨架屏 shimmer（P7AdminAudit.vue:346-347）、消息淡入位移（ChatMessage.vue:263-266）、平滑滚动 `scroll-behavior: smooth`（ChatView.vue:901）。

3. **对话流与状态变化对读屏完全不可见（WCAG 4.1.3 Status Messages）**
   - 消息列表容器无任何 live region 语义：[证据 web/src/views/ChatView.vue:694 `<div ref="chatContainer" class="chat__msgs">`]——流式 token、进度文案（"正在匹配供应商…"）、断流错误条（ChatView.vue:809-818）、线索分级结果全部静默插入 DOM，读屏用户无法感知。
   - 登录错误同样无 `role="alert"`：[证据 web/src/views/LoginView.vue:303 `<p v-if="error" class="auth-error">`]。

4. **报价弹层无任何对话框语义与焦点管理（WCAG 4.1.2 / 2.4.3）**
   - [证据 web/src/views/supplier/SupplierLeads.vue:265-293]：`div.modal-overlay` 无 `role="dialog"` / `aria-modal` / `aria-labelledby`；打开后焦点不进入弹层、Tab 可穿透到背景；无 Esc 关闭、无关闭后焦点还原。键盘与读屏用户几乎无法完成报价流程。

5. **主按钮「白字 + 靛蓝底」对比度 4.47:1，不达 AA（4.5:1）**
   - 实测 `#ffffff` on `--accent #6366f1` = **4.47:1**；sm/md 尺寸字号 13–14px 属正常文本：[证据 tokens.css:20；web/src/components/ui/AppButton.vue:45 `.btn--primary { background: var(--accent); color: #fff; }`；ChatView.vue:997 `.chat__send` 同款]。
   - `--accent #6366f1` 作为文字色在 `--bg-1` 上仅 **4.22:1**、在 `--bg-2` 上 **3.96:1**，同样不达 AA：[证据 AppHeader.vue:163-167 `.enterprise-source`（11px accent 字）；P7AdminAudit.vue:310 `.tab.active { color: var(--accent) }`；P7AdminAudit.vue:342 `.tag-blue { color: var(--accent) }`；P7AdminAudit.vue:295 `.notice-bar--demo`]。

### 🟡 中等（不一致、效率低、可感知粗糙）

6. **div 点击卡片键盘不可达**：供应商工作台快捷入口为 `<div class="quick-card" @click="router.push(...)">`，无 role/tabindex/键盘事件 [证据 web/src/views/supplier/SupplierDashboard.vue:183-197]。
7. **表单控件缺可访问名称**：聊天输入框只有 placeholder（ChatView.vue:820-827）；QueryInput textarea（QueryInput.vue:31-38）；审核搜索框（P7AdminAudit.vue:213）；供应商搜索/筛选下拉（SuppliersMatch.vue:145-158）；规格表行内编辑输入框依赖相邻单元格文字，无 `aria-label`（SpecConfirm.vue:69-75）。
8. **标签页组件无语义**：审核页 tab 为普通按钮 + `.active` 类，无 `role="tablist/tab"`、`aria-selected`、方向键导航 [证据 P7AdminAudit.vue:204-212]。
9. **装饰性字符会被读屏朗读**：导航图标是字母/符号文本（AppHeader.vue:59 `<span class="nav__icon">{{ item.icon }}</span>`，值为 'D'/'B'/'!'/'🔍'）；消息头像 'U'/'M'/'●'（ChatMessage.vue:157-161）；StepNav 的 ✓/! 状态点（StepNav.vue:33-35）——均未 `aria-hidden`，状态信息也无文字等价。
10. **核心页面 ChatView 无任何 @media**：历史侧边栏 fixed 280px（ChatView.vue:883-896）在 ≤375px 宽屏上近乎全屏遮挡且无背景遮罩；历史开关 fixed 定位（ChatView.vue:855-871）易与内容重叠。
11. **移动端布局冲突**：`ProcureView` 二级顶栏 `position: sticky; top: 56px`（ProcureView.vue:322-324）未随移动端顶栏下移（AppHeader.vue:298 topbar 在 ≤920px 时 top:48px+56px 高）而重叠；`App.vue` 主区 `padding-top: 104px`（App.vue:42-47）与 `ChatView` 自身 `min-height: calc(100vh - 56px)`（ChatView.vue:846-848）口径不一致。
12. **断点值碎片化**：全库 8 种断点（640/700/768/820/920/960/980/1100），同一应用壳层用 920（App.vue:42、AppHeader.vue:274），页面却各用 768（ProcureView.vue:546）、960（LoginView.vue:428）、980（ShortageProcurementView.vue:572），920–960px 区间布局口径互斥。
13. **表格可访问性细节缺失**：`<th>` 无 `scope="col"`（SuppliersMatch.vue:190-193、SupplierDashboard.vue:151-158、SpecConfirm.vue:56）；对比表无 `<caption>` 或 aria 说明（SuppliersMatch.vue:187）。
14. **输入框静止边框对比度仅 1.5–1.8:1**（`#343a4d` on `#151924` = 1.55，`--border-default` on `--bg-1` = 1.82），弱视力用户难以辨认输入区域边界 [证据 tokens.css:11；LoginView.vue:407]。
15. **图标按钮仅靠 `title` 命名**：历史开关（ChatView.vue:688）、关闭按钮（ChatView.vue:812）、复制/重试（ChatMessage.vue:201-239）无 `aria-label` / `aria-expanded`，`title` 在触屏与键盘下不可见。

### 🔵 建议（锦上添花）

16. 缺「跳到主内容」skip link；主区 `<main>` 已具备（App.vue:15），补一个 visually-hidden 链接即可。
17. 复制成功「已复制」（ChatMessage.vue:215）、审核操作静默失败（P7AdminAudit.vue:147-149 `catch {}`）等结果反馈建议进 live region。
18. 侧栏 `<aside class="sidebar">`（AppHeader.vue:38）与聊天历史 `<aside>`（ChatView.vue:838）建议加 `aria-label` 区分 landmark。
19. LandingView 图片 alt 已齐（LandingView.vue:116-181 ✓）；登录页装饰 Canvas 建议加 `aria-hidden="true"`（LoginView.vue:246）。
20. 状态点仅颜色区分（StepNav 的 running/done、供应商 ✓/✗ 确认态 SuppliersMatch.vue:329-339），建议加文字/形状冗余编码。
21. 全库仅 5 处 `aria-*`（AppHeader.vue:57、CitationList.vue:34、HomeView.vue:103、LandingView.vue:115、DemoConsole.vue:204），RouterLink 的激活态虽有默认 `aria-current`，整体仍建议建立 a11y lint（如 eslint-plugin-vuejs-accessibility）防退化。

## 3. 优化方案

**P0-1 建立全局焦点可见性令牌与规则**（对应问题 1、14）
- 做什么：在 `tokens.css` 新增 `--focus-ring: #a5b4fc`（在 `--bg-1` 上 ≈7:1），在 `base.css` 加 `:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }` 全局兜底；各输入控件把「`outline:none` + 边框变色」改为「`:focus-visible` 时 outline + 保留边框变色」；`AppButton.vue`、`.tab`、`.nav__link`、`.welcome__chip`、`.sups__sort-btn` 补 `:focus-visible` 规则。同时把输入框静止边框从 `--border-subtle` 提到 `--border-strong`（1.45→约 2.9:1）或加深底色。
- 为什么：一次改动覆盖全站键盘定位问题，成本最低收益最大。
- 涉及：`tokens.css`、`base.css`、`AppButton.vue`、`AppHeader.vue`、各含 `outline: none` 的 12 处组件。

**P0-2 全站 reduced-motion 降级**（对应问题 2）
- 做什么：在 `base.css` 末尾加 `@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; scroll-behavior: auto !important; } }`；`LoginView.vue` 的 `onMounted` 里先 `matchMedia('(prefers-reduced-motion: reduce)')` 判断，命中则只静态绘制一帧、不启动 `requestAnimationFrame`。
- 为什么：WCAG 2.2.2/2.3.3 为 A 级要求；Canvas 无限动画目前连暂停手段都没有。
- 涉及：`base.css`、`LoginView.vue`（demos 下两个登录页同款可一并处理）。

**P0-3 对话与状态区域 live region 化**（对应问题 3、6 部分）
- 做什么：`ChatView.vue:694` 消息容器加 `role="log" aria-live="polite" aria-label="对话消息"`（配合流式场景可在流式期间 `aria-busy="true"`）；断流/警告条（ChatView.vue:809-818）与登录错误（LoginView.vue:303）加 `role="alert"`；`textarea` 加 `aria-label="输入寻源需求"`。
- 为什么：对话寻源是核心交互，读屏用户当前完全无法使用流式反馈。
- 涉及：`ChatView.vue`、`LoginView.vue`、`RegisterView.vue`、`QueryInput.vue`。

**P1-4 弹层对话框规范化**（对应问题 4）
- 做什么：`SupplierLeads.vue:265` 弹层加 `role="dialog" aria-modal="true" aria-labelledby`（指向 h3）；打开时聚焦第一个输入框、Esc 关闭、关闭后焦点还原因「提交报价」按钮；背景加 `inert` 或焦点圈禁。
- 为什么：报价是供应商核心变现动作，键盘/读屏不可用等于流程断裂。
- 涉及：`SupplierLeads.vue`，可抽一个 `useModalA11y` composable 复用。

**P1-5 修正对比度不达标的令牌用法**（对应问题 5）
- 做什么：① 文字场景的 `--accent` 改用 `--accent-hover #818cf8`（6.33:1 达标）：`P7AdminAudit.vue:310 .tab.active`、`:342 .tag-blue`、`:295 .notice-bar--demo`、`AppHeader.vue:163-167 .enterprise-source`。② 主按钮二选一：文字改 `#fff` + 底色加深为 `--accent-active #4f46e5`（6.29:1），或在 `tokens.css` 新增 `--accent-text: #eef0ff` 并配合加深底色；涉及 `AppButton.vue:45`、`ChatView.vue:997`、`LoginView.vue:417`。
- 为什么：4.47/4.22 与 4.5 只差毫厘，改 token 用法即可全量达标，不动品牌色。

**P1-6 交互语义补齐**（对应问题 6、8、9、13、15）
- 做什么：quick-card 改 `<RouterLink>` 或 `<button>`（SupplierDashboard.vue:183-197）；审核 tabs 改 `role="tablist"` + `aria-selected` + 左右方向键切换（P7AdminAudit.vue:204-212）；所有图标按钮补 `aria-label`，历史开关补 `:aria-expanded="showHistory"`（ChatView.vue:688）；装饰图标/头像统一 `aria-hidden="true"`（AppHeader.vue:59、ChatMessage.vue:157-161），StepNav 每步加 `:aria-label="`${label}：${状态文字}`"`；表格 `<th scope="col">`、对比表加 `<caption>`。
- 涉及：上述各文件。

**P2-7 响应式收敛与 ChatView 移动端补齐**（对应问题 10、11、12）
- 做什么：在 `tokens.css` 定义 3 档断点注释约定（建议 640 / 920 / 1100，与应用壳层对齐），逐步替换 700/768/820/960/980；给 `ChatView.vue` 补 `@media (max-width: 920px)`：历史侧边栏改全宽抽屉 + 半透明遮罩 + 点击遮罩关闭；`ProcureView.vue:322` 的 sticky top 改为 `top: 104px`（≤920px 时）或用 CSS 变量与 AppHeader 联动；统一 `App.vue` 与 `ChatView` 的视口高度口径。
- 涉及：`ChatView.vue`、`ProcureView.vue`、`App.vue`、`AppHeader.vue`、各页面媒体查询。

**P3-8 工程化防退化**（对应问题 16-21）
- 做什么：引入 `eslint-plugin-vuejs-accessibility`；在 `App.vue` 加 skip link；审核操作结果、复制反馈接入统一 live region 工具；表格/标签页封装为带 a11y 语义的基础组件放入 `components/ui/`。

---

### 附：关键色对实测对比度（基于 tokens.css，WCAG 相对亮度）

| 前景 / 背景 | 实测 | AA 正常文本(4.5) | 结论 |
|---|---|---|---|
| `--text-tertiary #a3adbf` on `--bg-1 #0f1117` | 8.35 | ✅ | 达标（标题/辅助文本无虞） |
| `--text-secondary #c4cad6` on `--bg-2` | 10.76 | ✅ | 达标 |
| `--accent #6366f1`（文字）on `--bg-1` / `--bg-2` | 4.22 / 3.96 | ❌ | 不达标 |
| `#fff` on `--accent #6366f1`（主按钮） | 4.47 | ❌ | 不达标（差 0.03） |
| `#fff` on `--accent-active #4f46e5` | 6.29 | ✅ | 可作替代底色 |
| `--accent-hover #818cf8` on `--bg-1` | 6.33 | ✅ | 可作 accent 文字色 |
| `--warning / --notice / --danger / --success` on `--bg-1` | 9.84 / 6.73 / 5.01 / 8.28 | ✅ | 达标 |
| 焦点边框混合色 on 输入底色 | 1.53 | ❌（需 3:1） | 远低于 1.4.11 |
| 输入框静止边框 on 底色 | 1.55–1.82 | ❌（需 3:1） | 边界难辨认 |
