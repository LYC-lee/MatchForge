# 设计系统与基础组件 UI 分析报告

> 审查范围：`web/src/styles/tokens.css`、`base.css`、`global.css`、`index.css`，`web/src/components/ui/` 下 AppButton.vue、Card.vue、Chip.vue、Tag.vue。审查视角：令牌完备性、组件 API 设计、组件视觉质量、全局样式副作用、深色主题语义化。

## 1. 现状概述

项目存在**两套并行样式体系**：新深色体系由 `tokens.css`（背景五级、三级边框/文本、靛蓝主色、四档语义色、间距/圆角/阴影/字号/过渡令牌）+ `base.css`（reset、深色 body、滚动条样式）构成，经 `index.css` 聚合；旧浅色体系 `global.css`（蓝色主色 #2563eb、浅色中性色、`.btn/.card/.tag/.alert/.skeleton` 等全局类）在 `main.ts` 中**后于** index.css 加载，同名令牌与元素样式覆盖新体系。基础组件四个：AppButton（4 变体 × 3 尺寸 + loading，API 较规整）、Card（title/subtitle/elevated + 三插槽）、Chip（仅 label + click，硬编码色值）、Tag（9 种 type + AltLevel 映射，等宽字体）。深色基调统一，但新旧体系混用导致部分页面出现浅色组件，且令牌层缺 z-index、行高、字重、容器宽度等关键类别。

## 2. 问题清单

### 🔴 严重（影响可用性/明显缺陷/体验断裂）

**S1. `global.css` 浅色令牌与 body 样式后加载，系统性覆盖深色体系**
`main.ts:5-6` 先 `import './styles/index.css'`（含 tokens+base）后 `import './styles/global.css'`，同优先级下后者胜出：
- `--radius-lg` 被从 10px 覆盖为 12px（`tokens.css:52` vs `global.css:37`）——Card.vue:26、LandingView、ChatView 等 20+ 处 `var(--radius-lg)` 全部拿到非设计值；
- `--shadow-sm` 被从 `rgba(0,0,0,0.3)` 覆盖为 `rgba(0,0,0,0.05)`（`tokens.css:56` vs `global.css:40`），`--shadow-lg` 同被覆盖（`global.css:42`）——深色背景上阴影近乎不可见，层级感丢失；
- `body` 背景被覆盖为浅色 `#f8fafc`、文字色 `#1e293b`（`global.css:28,31,53-61` vs `base.css:20-21`），目前仅靠 `App.vue:23-31` 的 `.app-shell` 自带深色背景遮住，overscroll 区域及任何未铺底容器会露浅色底；未显式设色的文本继承深色字色，在深色背景上有隐形风险；
- 链接色被覆盖为 `#2563eb`（`global.css:63-66` vs `base.css:26-33`），脱离靛蓝主色体系，且 hover 仍是 `--accent` #6366f1，出现"常态蓝、悬停靛"的断裂；
- `line-height` 1.6 覆盖 1.55（`global.css:57` vs `base.css:19`）。

**S2. 新旧两套组件样式真实混用，同一产品两种视觉语言**
`global.css` 的全局类并非死代码，仍被多个视图使用：
- `AdminKnowledge.vue:149,159,165` 使用 `.btn-primary/.btn-secondary` → 蓝色 #2563eb / 白底按钮（`global.css:93-110`），与其余页面的靛蓝 AppButton 完全不一致；
- `SupplierProducts.vue:135,138,139` 使用 `.tag .tag-gray/.tag-yellow/.tag-green` → 浅色 pastel 标签（`global.css:150-182`，如 `#dcfce7` 底）出现在深色表格中，与 Tag.vue 的 dark soft 色系并存；
- `.skeleton` 浅色 shimmer（`#f1f5f9/#e2e8f0` 渐变，`global.css:206-217`）被 `P7AdminAudit.vue:177`、`SupplierProducts.vue:116`、`SupplierLeads.vue:202` 用在深色卡片内，加载时出现亮白色块闪烁；
- `.empty-state` 引用 `--color-text-secondary` #64748b（`global.css:285-290`），被 `SupplierDashboard.vue:175` 等多处使用，色值游离于新文本令牌之外。

**S3. Tag 的 L5 语义映射错误，误导采购判断**
`Tag.vue:19-26` 将 `L5` 映射为 `tag--danger`（红色 #ef4444），但领域定义 L5 为"仅参考"（`types/procure.ts:14` 注释："L1 完全等效 … L5 仅参考"），旧调色板中 L5 也是中性灰 `#9ca3af`（`global.css:25`）。"仅参考"被渲染成最高告警色，会让采购方把可参考料误读为风险料。

**S4. 全套基础组件无键盘焦点样式，可访问性断裂**
AppButton.vue（29-77 行全文）、Chip.vue（10-27 行全文）、Tag.vue（36-55 行全文）均无 `:focus`/`:focus-visible` 样式；`base.css` 亦无全局 focus ring（全项目 grep `focus-visible` 零命中）。按钮 reset 掉了默认 outline（`base.css:35-40` 未保留），键盘 Tab 导航在核心交互元素上完全不可见。B 端工具用户高频键盘操作，此为可用性缺陷。

### 🟡 中等（不一致、效率低、可感知粗糙）

**M1. 令牌体系关键类别缺漏**
- **无 z-index 令牌**：全项目散布魔法数 1/2/10/40/44/45/50/60/90/100（`AppHeader.vue:101,231`、`ChatView.vue:859,889`、`ProcureView.vue:325`、`DemoConsole.vue:258`、`SupplierLeads.vue:350` 等），层级关系（header 60 > 其下拉 50 > chat 浮层 45/44 > procure 40，modal 100 > DemoConsole 90）靠巧合维持，新增浮层极易穿插错乱；
- **无行高、字重令牌**：`font-weight: 500/600` 硬编码于 AppButton.vue:36、Card.vue:38、Tag.vue:43 等；行高仅 body 一处且被 global.css 覆盖；
- **无容器宽度/布局常量令牌**：`.page-container` 960px（`global.css:220-224`）、QueryInput 720px（`QueryInput.vue:61`）、App.vue 的 sidebar 256px / header 56px / 断点 920px（`App.vue:35,42-46`）各自硬编码；
- **无 focus-ring、overlay/scrim、blur 令牌**：`backdrop-filter` blur 值 12/14/16/18px 四处散布（`ProcureView.vue:327`、`LandingView.vue:234,384`、`ChatView.vue:892`、`AppHeader.vue:107,240`）；modal 遮罩 `rgba(0,0,0,0.6)` 就地书写（`SupplierLeads.vue:350`）；
- **无 on-accent 文本令牌**：`#fff` 硬编码（`AppButton.vue:45`）；间距刻度缺 20px 档（`tokens.css:40-47`）。

**M2. 语义色只有 base + soft 两档，派生色被迫就地硬编码**
`tokens.css:26-34` 的 success/warning/notice/danger 无 `-border`/`-hover` 变体（仅 accent 有），导致 AppButton danger 变体硬编码 `rgba(239,68,68,0.3)` 边框与 `rgba(239,68,68,0.2)` 悬停底（`AppButton.vue:59-64`）。同类需求在每个视图各自再写一遍只是时间问题。

**M3. Chip 使用游离于令牌外的"幽灵色板"**
`Chip.vue:17-19,24` 硬编码 `#c5cada / #151924 / #343a4d / #f4f7ff`，与令牌 `--text-secondary #c4cad6`、`--bg-2 #151823`、`--border-subtle #2b3140`、`--text-primary #e7e9ee` **近似但不等**；同一色板还出现在 `QueryInput.vue:65-66`。改令牌时这些角落不会跟着变，形成永久视觉漂移。

**M4. Card 头部条件渲染缺陷：仅传 actions 插槽时整个头部消失**
`Card.vue:9` `v-if="title || $slots.header"` 不含 `$slots.actions`，而 actions 的渲染嵌在 header 内（`Card.vue:16`）。只提供 `#actions` 的卡片将静默丢失操作区。另 `card__body:empty { display: none }`（`Card.vue:42`）为死代码——body 始终渲染。

**M5. Chip API 过薄，不满足筛选场景**
`Chip.vue:2-7`：props 仅 `label`，无 `selected/active` 状态（Chip 的典型用途即筛选/单选，现有 hover 态无法表达"已选中"）、无 `disabled`、无尺寸档位；`<button>` 未写 `type`（`Chip.vue:7`），在 `<form>` 内会默认 `type="submit"` 触发表单提交；亦无 `aria-pressed`。

**M6. base.css 全局副作用风险**
- `ul,ol { list-style: none }`（`base.css:51-54`）+ `* { margin:0; padding:0 }`（`base.css:1-7`）对任何富文本/v-html 渲染内容（如 AI 对话输出的 Markdown 列表）是破坏性的，列表将无缩进无符号；
- `input,textarea,select` 设了深色背景（`base.css:42-49`）但不 reset `border`，浏览器默认边框与深色底混搭，各视图只得再各自处理；
- 滚动条 hover 色 `#4a5168` 硬编码（`base.css:73`），与令牌 `--border-strong #4b556b`（`tokens.css:12`）近似重复；且无 Firefox `scrollbar-color` 兜底；
- 无 `prefers-reduced-motion` 处理，spin/shimmer/全站过渡不可降级。

**M7. Tag 一律使用等宽字体，中文标签排版粗糙**
`Tag.vue:46` `font-family: var(--font-mono)`：CJK 字符在 mono 栈中走回退字体，与 ASCII 数字/字母宽度不一致，"L3 级"、"需工程评估"类中英混排标签参差；且 11px + 600 字重下中文笔画偏挤。

**M8. 令牌语义重复/混淆**
`--bg-elevated: #1e2230`（`tokens.css:7`）与 `--bg-3: #1c2030`（`tokens.css:6`）相差仅 1-2 个色阶，命名一个编号、一个语义，使用方无法判断该用谁（实际 AppButton.vue:54 用 elevated，SupplierDashboard.vue:290 也用 elevated，而多数处用 bg-2/3）。

**M9. Tag 的 type 混合两个抽象层级**
`Tag.vue:6` 的 9 种 type 中，`match/diff/risk` 实为 `success/warning/danger` 的领域别名（`Tag.vue:53-55` 逐行重复定义），与 `level` 的领域映射混在一起，API 表面积无谓扩大；调用方需理解两套命名。另外空 `value` 且非 level 时渲染一个无文字的空胶囊（`Tag.vue:11-15,33`）。

**M10. 双 reset、双 body 规则，文件职责不清**
`global.css:45-51` 与 `base.css:1-7` 的 universal reset 完全重复；`global.css:53-61` 与 `base.css:16-24` 的 body 规则互相打架；`index.css:1-2` 只聚合 tokens+base，global.css 却由 main.ts 单独引入——样式入口两处，后来者很难判断加载顺序与覆盖关系。

### 🔵 建议（锦上添花）

**B1. 深色令牌语义化分层**：`--bg-0..3` 编号式命名可保留，但建议增加语义别名（`--surface-base/--surface-raised/--surface-overlay`），并将 `:root` 改为 `:root, [data-theme="dark"]` 作用域，为将来的浅色主题/主题切换留口（当前令牌全部暗色硬编码，无切换机制）。

**B2. AppButton 细节**：spinner 边框色改用 `currentColor`（`AppButton.vue:72-73` 硬编码白，danger/ghost 变体上白 spinner 与红字/灰字不协调）；`transition: all`（`AppButton.vue:38`）建议枚举 `background-color, border-color, color`；loading 态加 `aria-busy="true"`；补 icon 插槽与 `block` 属性（登录/注册页提交按钮目前靠父级类 `.auth-submit` 拉宽，见 `LoginView.vue:304`）。

**B3. Tag 增强**：提供 `size`（当前固定 22px 高）、`variant="soft|outline"`、前置状态 dot；mono 字体改为仅数值场景可选。

**B4. 间距刻度补 20px 档**：现有 4/8/12/16/24/32/48（`tokens.css:40-47`），16→24 跳档间缺中间值，卡片密集排版常见 20px 需求。

**B5. 阴影令牌在深色背景下整体偏弱**：`--shadow-md` 仅 `rgba(0,0,0,0.35)`（`tokens.css:57`），深色 UI 的阴影需要更高不透明度 + 更大弥散才能感知；Card 的 elevated 区分度（`Card.vue:29`）目前较微妙，可配合 1px 顶部高光边增强层级。

**B6. 补 Firefox 滚动条样式**：`scrollbar-color: var(--border-strong) var(--bg-1)`（`base.css:61-74` 仅 webkit）。

## 3. 优化方案

**P0-1. 拆除 `global.css`，终结双体系并存（最高优先级）**
- 做什么：从 `main.ts:6` 移除 `import './styles/global.css'`；把仍在用的全局类用深色令牌重写后收敛到一处。
- 为什么：它正在覆盖圆角/阴影/body/链接色（S1），并供养着两套按钮/标签/骨架屏（S2）。不拆除，任何令牌治理都会被它架空。
- 改法：① 新建 `web/src/styles/utilities.css` 由 `index.css` 聚合，用深色令牌重写 `.skeleton`（底色 `--bg-3`/高光 `--bg-elevated`）、`.empty-state`（`--text-tertiary`）；② `AdminKnowledge.vue:149,159,165` 三个全局类按钮改为 `<AppButton variant="primary|secondary">`；③ `SupplierProducts.vue:135,138,139` 改用 `<Tag type="neutral|warning|success" :value="...">`；④ 确认无其他引用后删除 `global.css` 文件；⑤ 同步删除被覆盖的 body 浅色规则依赖。

**P0-2. 修正 Tag 的 L5 映射**
- 做什么：`Tag.vue:24` `L5: 'tag--danger'` 改为 `'tag--neutral'`。
- 为什么：L5"仅参考"不是风险信号（S3），红色会系统性误导寻源结论的读法。
- 改法：改 1 行映射；顺带将 `types/procure.ts:14` 的等级语义注释与映射表对齐注释。

**P0-3. 建立全局焦点可见体系**
- 做什么：新增 `--focus-ring: 0 0 0 3px var(--accent-soft)` 与 `--focus-border: var(--accent-border)` 令牌；`base.css` 加 `:focus-visible` 全局规则；AppButton/Chip 补焦点样式。
- 为什么：S4，键盘导航当前不可见，B 端高频键盘场景硬伤；也统一了目前各视图 input 各自实现的 focus 风格（`LoginView.vue:408`、`AdminKnowledge.vue:236` 等 6+ 处近似重复）。
- 改法：`base.css` 增加 `:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px }`；AppButton.vue、Chip.vue 各加 `.btn:focus-visible/.chip:focus-visible { border-color: var(--accent-border); box-shadow: var(--focus-ring) }`。

**P1-1. 令牌补齐：z-index、focus、overlay、blur、布局常量、语义派生色**
- 做什么：tokens.css 增加：`--z-dropdown: 50; --z-header: 60; --z-overlay: 90; --z-modal: 100; --z-toast: 110`；`--overlay-scrim: rgba(0,0,0,0.6)`；`--blur-sm/md/lg: 12/16/18px`；`--layout-header-h: 56px; --layout-sidebar-w: 256px; --container-sm: 720px; --container-md: 960px; --container-lg: 1200px`；语义色补 `--success-border/--warning-border/--notice-border/--danger-border`（0.3 透明度档）与 hover 档；`--text-on-accent: #fff`；`--space-7: 20px`（或论证后保持跳档）。
- 为什么：M1/M2。目前魔法数已遍布 15+ 文件，趁组件数量尚可收敛。
- 改法：tokens.css 增节；App.vue:35、SupplierLeads.vue:350、AppHeader.vue:101,231、ChatView.vue:859,889 等替换为令牌引用；AppButton.vue:62-64 的硬编码 rgba 换 `--danger-border`。

**P1-2. 重构 Chip：令牌化 + 选中态 + 表单安全**
- 做什么：色值全部换令牌（`--text-secondary/--bg-2/--border-subtle`，hover 用 `--accent-soft/--accent-border`）；新增 `selected?: boolean`（选中态 `background: var(--accent-soft); border-color: var(--accent-border); color: var(--text-primary)` + `aria-pressed`）、`disabled`；`<button type="button">`；补 `:focus-visible`。
- 为什么：M3/M5。Chip 当前只有 QueryInput 一处使用（`QueryInput.vue:48-53`），是低成本改造窗口期；QueryInput.vue:65-66 的同源硬编码一并令牌化。
- 改法：Chip.vue 样式块重写 + props 扩展。

**P1-3. 修 Card 头部渲染条件**
- 做什么：`Card.vue:9` 改为 `v-if="title || $slots.header || $slots.actions"`。
- 为什么：M4，仅传 actions 时操作区静默丢失，属组件契约缺陷。
- 改法：1 行；同时删除死代码 `card__body:empty`（`Card.vue:42`）或改为有实际意义的紧凑态。

**P2-1. 收敛 base.css 副作用**
- 做什么：`ul,ol` 的 `list-style: none` 限定到布局类作用域（或新增 `.rich-text` 类恢复列表样式供 v-html/Markdown 容器使用）；`input,textarea,select` 补 `border: 1px solid var(--border-default); border-radius: var(--radius-md)` 的统一基线；滚动条色值换令牌 + 补 `scrollbar-color`。
- 为什么：M6。AI 对话寻源必然渲染富文本，全局列表抹平迟早咬人。
- 改法：base.css 局部改写；ChatMessage 等渲染容器加 `.rich-text`。

**P2-2. Tag 排版与 API 收敛**
- 做什么：默认字体改 `--font-sans`，mono 通过 `mono?: boolean` 显式开启（数值/参数对比场景保留）；`match/diff/risk` 三个别名 type 标注 `@deprecated`，调用方迁往语义 type；空文本时 `v-if="text"` 不渲染。
- 为什么：M7/M9，中英混排标签观感与 API 表面积双改善。
- 改法：Tag.vue 样式与 props；ChatView.vue:792、ProcureView.vue:263 等调用点核对。

**P2-3. 背景层级令牌去重与语义化**
- 做什么：`--bg-elevated` 与 `--bg-3` 合并为一个，或明确分工：`--bg-3` 用于常规容器底、`--bg-elevated` 专用于浮起态（hover/popover）并拉开色差（如 `#232840`）；视情况引入 `[data-theme]` 作用域与 `--surface-*` 语义别名。
- 为什么：M8/B1，消除"两个几乎一样的令牌该用谁"的决策噪音，为浅色主题留路。
- 改法：tokens.css 改值/改名，全局 grep 替换引用（当前 elevated 仅 3 处引用，成本低）。
