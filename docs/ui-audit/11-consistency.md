# 样式一致性与 CSS 工程质量 UI 分析报告

> 审查范围：`web/src` 全部 39 个 `.vue` 文件 + `styles/` 全局样式层。方法：全量 Grep 扫描硬编码色值 / rgba / !important / px 魔法数字，逐文件比对重复 UI 模式与令牌（`tokens.css`）偏离度。

## 1. 现状概述

前端采用「设计令牌（tokens.css，暗色主题）+ Scoped CSS」体系，多数业务页面（ProductsBom、ProcureView、HistoryView、procure/* 组件群）令牌化程度高，部分组件 var(-- 引用达 100+ 次。但样式层存在明显的"两个世界"：① 遗留浅色主题 `global.css` 与新暗色令牌体系并存并被后加载覆盖；② 认证页、企业问答页、演示组件大面积自造平行色板（`#f4f7ff`/`#aeb5c4`/`#343a4d`/`#151924` 等与令牌近似但不等的灰蓝色），完全绕过 tokens.css。UI 模式层面，空态、skeleton、tag 色标、panel-head、grade-card 等被跨页复制 2–6 份，未沉淀为组件。全项目共 39 个 .vue 文件，硬编码十六进制色值约 220 处、rgba() 约 290 处、!important 7 处、px 值约 1100 处（含合理结构尺寸）。

### 量化问题地图（Top 榜）

**硬编码十六进制色值排行**（Grep `#[0-9a-fA-F]{3,8}`）：

| 排名 | 文件 | 数量 |
|---|---|---|
| 1 | views/LoginView.vue | 32 |
| 2 | views/RegisterView.vue | 29 |
| 3 | views/demos/LoginWithHolo.vue | 27 |
| 4 | views/demos/LoginHoloPro.vue | 26 |
| 5 | components/demo/DemoConsole.vue | 25（且 var(-- 引用为 0） |
| 6 | views/CompanyChat.vue | 16 |
| 7 | views/CompanyAssistant.vue | 13 |
| 8 | views/LandingView.vue | 8 |

**rgba() 排行**：RegisterView 38 > LoginView 35 > LoginHoloPro 32 > LoginWithHolo 30 > LandingView 27 > HomeView 10。**!important**（共 7 处）：LandingView×2（:269, :495）、AppHeader×2（:164-165）、DemoConsole×2（:380-381）、ProcureView×1（:446）。**px 值总数排行**：LandingView 91 > ShortageProcurement 79 > DemoConsole 73 > HomeView 59 > LoginView 57 > RegisterView 54。**硬编码 font-size px（绕过字号令牌，共 43 处）**：DemoConsole 10 处最多（:301/:309/:348/:365/:391/:402/:420/:428/:444/:451），SessionHistoryPanel 5 处次之。

**重复最多的 UI 模式**：空态 empty-state（7 处独立实现）、tag 色标类（4 处：Tag.vue 组件 / P7AdminAudit:337-342 / SupplierLeads:338-342 / global.css .tag-*）、skeleton（4 处逐行复制）、panel-head（3 处）、action-type/action-tag 类目色标（2 处）、grade-card（2 处，其中组件版无人引用）、auth 认证页整套样式（2 套零共享）。

## 2. 问题清单

### 🔴 严重（影响可用性/明显缺陷/体验断裂）

1. **双令牌体系冲突，浅色遗留样式后加载覆盖暗色主题**
   [证据 web/src/main.ts:5-6] `import './styles/index.css'` 在前、`import './styles/global.css'` 在后；[证据 styles/global.css:8-37] 定义整套浅色旧令牌（`--color-primary: #2563eb`、`--color-bg: #f8fafc`、`--color-surface: #ffffff`、`--color-text: #1e293b`）；[证据 styles/global.css:56-63] `body { color: var(--color-text); background: var(--color-bg); }` 与 [styles/base.css:16-23] 的暗色 body 规则同优先级但位置靠后 → body 基底实际被刷成浅灰底深字。目前靠各页面自设背景遮盖，属于悬在全局的定时炸弹：任何未设背景的新页面/组件都会"穿帮"成浅色。同时 global.css 还提供 `.btn/.btn-primary/.card/.tag/.empty-state/.table/.steps/.skeleton` 等无作用域全局类（global.css:66-331），与暗色 UI 组件（AppButton/Card/Tag）同名不同皮。

2. **grade-card 一式两份：组件版成为死代码，页面版内联复制**
   [证据 components/procure/GradeCard.vue:34-79 完整实现一套 .grade-card 样式，但全仓 grep 无任何 import/引用]；[证据 views/ChatView.vue:782-797 模板内联 grade-card 结构，:1071-1112 scoped 重新实现同名样式]。两处 `.grade-card__head/.grade-card__body/.grade-card__reasons` 规则高度雷同，今后改分级卡片样式必须改两处（实际只会改到一处），必然漂移。

3. **演示组件 DemoConsole 进入生产外壳，且是全仓唯一 0 令牌组件**
   [证据 App.vue:5,18] `DemoConsole` 被挂载到所有非 blank 布局页面；[证据 components/demo/DemoConsole.vue] 471 行中 var(-- 引用 0 次，自造整套色板（:276 `#242a42/#141927`、:287 `#c7d2fe`、:370 `#7c83ff` 等 25 处十六进制、8 处 rgba），含 2 个 !important（:380-381）与 10 处硬编码 font-size px。它不与任何页面共享视觉语言，却出现在每个正式页面上。

4. **认证双页零共享：同一设计两套并行实现，色板全面绕过令牌**
   [证据 views/LoginView.vue 样式 117 行全部 `.auth-*` 前缀；views/RegisterView.vue 样式 257 行全部 `.register-*` 前缀；两文件相同选择器数为 0，diff 358/374 行]。概念上的一一对应（auth-card↔register-card、auth-input↔register-field）却各自重写；合计 61 个十六进制色值、73 个 rgba，自造 `#f4f7ff`（LoginView:332 等 15 处）、`#aeb5c4`、`#343a4d`（LoginView:343）、`#151924`（LoginView:407）、`#7f8799`（LoginView:388）等与令牌 `--text-primary #e7e9ee`、`--border-default #384052` 近似但不相等的"幽灵令牌"，登录/注册两页之间已产生肉眼可辨的灰阶差异。

### 🟡 中等（不一致、效率低、可感知粗糙）

5. **CompanyChat 与 CompanyAssistant 近复制**：两页样式块共 349 行，diff 仅 152 行，聊天布局/消息气泡/输入区/空态全部重复实现 [证据 views/CompanyChat.vue:246-432 vs views/CompanyAssistant.vue:178-340，连硬编码色值都成对相同：`.chat-empty { color:#d2d8e4 }`（CompanyChat:305 / CompanyAssistant:208）、`#171b26` 面板底（CompanyChat:309 / CompanyAssistant:188）、`.muted { color:#aeb7c8 }`（CompanyChat:349 / CompanyAssistant:257）]。

6. **空态模式 7 处独立实现，其中两份逐行相同**：HistoryView.vue:147-149（`.history__empty-icon { font-size:40px; color:var(--text-tertiary) }` 等）与 AlternativesList.vue:233-235 完全雷同；另有 SessionHistoryPanel:186-187、SuppliersMatch:541、CompanyChat:305、CompanyAssistant:208、P7AdminAudit:344、SupplierDashboard:272，外加 global.css:280-285 的浅色 `.empty-state`。padding 出现 24/32/48px 三种规格，图标字号 24/40/48px 三种规格。

7. **同名类「全局浅色版 + scoped 暗色版」多份拷贝**：`.skeleton` 逐行复制于 P7AdminAudit.vue:346、SupplierLeads.vue:346、SupplierProducts.vue:269（另有 global.css:194 浅色版）；`.card/.card__body` scoped 重定义于 P7AdminAudit:316-317、SupplierLeads:325-326（与 ui/Card.vue 组件三者并存）；`.tag/.tag-*` scoped 重定义于 P7AdminAudit:337-342、SupplierLeads:338-342（与 ui/Tag.vue、global.css 并存）。同名不同源，后人无法判断该改哪份。

8. **类目色标跨页复制且引入令牌外紫色**：HomeView.vue:458-461 `.action-type--*` 与 ShortageProcurementView.vue:525-528 `.action-tag--*` 四类目配色完全相同，其中 `color:#a78bfa; background:rgba(167,139,250,0.12)` 是不在 tokens.css 中的第 6 种语义色，两页各写一份。

9. **基础组件自身绕过令牌**：ui/Chip.vue:15-22 硬编码 `#c5cada/#151924/#343a4d/#f4f7ff`；procure/QueryInput.vue:65-101 硬编码 `#151924/#343a4d/#f4f7ff/#7f8799/#8d95aa/#9aa3b7` 6 处——输入框这类最该统一的元件自造灰蓝板，导致各页输入控件底色存在 `#151924` vs `var(--bg-2) #151823` 的细微分裂。

10. **demo 双登录页为未路由死代码，且样式彻底分裂**：views/demos/LoginHoloPro.vue（332 行）、LoginWithHolo.vue（470 行）未在 router/index.ts 注册（grep 无任何引用），合计 53 个十六进制、62 个 rgba、4+3 个硬编码渐变、7 个硬编码 box-shadow，自造全息霓虹视觉体系，与正式 LoginView 完全两套语言；802 行死代码留在仓内持续干扰检索与重构。

11. **!important 7 处分散在 4 个文件**，多为压全局/组件样式：LandingView.vue:269 `color:#fff !important`、LandingView.vue:495、AppHeader.vue:164-165（margin-top/color 双连）、DemoConsole.vue:380-381、ProcureView.vue:446。说明特异性管理失控，后续主题化时这些都是暗礁。

12. **px 魔法数字普遍化**：font-size 硬编码 43 处（绕过 8 级字号令牌），border-radius 硬编码 10+ 文件（ShortageProcurement 15 处、HomeView/CompanyChat/CompanyAssistant 各 10 处，出现 4/6/8/10/12/14/16/20px 八档而令牌只有 4/6/10/999 四档），box-shadow 硬编码 24 处（LandingView 5 处最多，:669 等）。`#fff` 直接写死 12+ 处（ChatView:1016、CompanyChat:410、StepNav:71/75 等）。

### 🔵 建议（锦上添花）

13. **panel-head 模式 3 处**：HomeView.vue:362-369、CompanyChat.vue:249-254、DemoConsole.vue:330 各自实现「标题+描述+操作区」卡片头，可抽 `PanelHeader` 或纳入 Card 组件 slot。
14. **SourceBadge.vue:87-113 手写 rgba 边框色**（`rgba(34,197,94,0.3)` 等），可在 tokens.css 增补 `--success-border/--warning-border/--danger-border` 语义令牌（现有 accent-border 先例）。
15. **LandingView.vue 硬编码装饰色**（:677 `#86efac`、:695 `#bbf7d0`、:669 `#60a5fa` 渐变端点）建议沉淀为 `--gradient-*` 或装饰令牌，便于落地页整体换肤。
16. **App.vue 外壳背景渐变**（App.vue:24-27）为全局唯一定位装饰，可抽为 `--gradient-app-shell` 令牌复用到 blank 布局页。

## 3. 优化方案

按优先级排序（P0 立即做，P1 随下个迭代，P2 择机）：

**P0-1｜拆除双令牌体系（解决 #1）**
- 做什么：将 `styles/global.css` 中仍在用的类（`.skeleton/.empty-state/.table` 的调用方）迁移为暗色 scoped 或新组件后，**删除 global.css 并从 main.ts:6 移除导入**；保留 tokens.css 为唯一令牌源。
- 为什么：浅色 body 基底 + 无作用域全局类是全局性视觉炸弹，且与 scoped 同名类互相覆盖，不确定性最高。
- 改法：涉及 styles/global.css（删）、main.ts（改 1 行）、AdminKnowledge.vue:209-254（其 scoped `.card/.btn-primary` 已自备，验证无碍）、SupplierDashboard.vue:149 `.table`（已有 scoped 版 :256-258）。删除后逐页目检一次背景。

**P0-2｜grade-card 归一（解决 #2）**
- 做什么：ChatView.vue:782-797 改用 `components/procure/GradeCard.vue` 组件，删除 ChatView.vue:1071-1112 的内联样式。
- 为什么：消除一式两份中最危险的一处（功能组件级复制）。
- 改法：涉及 ChatView.vue（模板+样式）、必要时给 GradeCard 增加 props 以覆盖 ChatView 的展示差异。

**P0-3｜DemoConsole 退出生产外壳或令牌化（解决 #3）**
- 做什么：确认 DemoConsole 的产品定位——若为内部演示工具，用 `import.meta.env.DEV` 门控挂载（App.vue:18）并迁入 `demos/`；若需保留则全量替换 25 处色值为令牌。
- 为什么：它是唯一 0 令牌组件却出现在每个正式页面，拉低整体一致性基线。
- 改法：涉及 App.vue、components/demo/DemoConsole.vue。

**P1-4｜抽 AuthLayout 统一认证双页（解决 #4）**
- 做什么：新建 `components/auth/AuthLayout.vue`（品牌侧栏+卡片插槽）与 `AuthFormField` 输入元件，把 `#f4f7ff→--text-primary`、`#aeb5c4→--text-tertiary`、`#343a4d→--border-default`、`#151924→--bg-2`、`#7f8799→placeholder 用 --text-tertiary` 全部映射回令牌；LoginView/RegisterView 只保留业务逻辑与差异文案。
- 为什么：一次消除 61 个色值 + 73 个 rgba 的最大硬编码源头，并根治登录/注册灰阶分裂。
- 改法：涉及 views/LoginView.vue、views/RegisterView.vue，预计各瘦身 60%+；顺手将 demos/ 两个死登录页删除（见 P1-7）。

**P1-5｜抽 EmptyState / Skeleton / StatusTag 三个基础组件（解决 #6/#7/#8）**
- 做什么：`ui/EmptyState.vue`（icon/title/desc props，统一 48px padding + 40px 图标一档）；`ui/Skeleton.vue`（height props）；扩展 `ui/Tag.vue` 增加 `collaboration` 类型并在 tokens.css 增补 `--violet: #a78bfa / --violet-soft` 语义令牌（或归入现有 notice）。
- 为什么：空态 7 份、skeleton 4 份、tag 4 份、类目色标 2 份，是重复面最广的一组模式。
- 改法：涉及 HistoryView、AlternativesList、SessionHistoryPanel、SuppliersMatch、CompanyChat、CompanyAssistant、P7AdminAudit、SupplierDashboard、SupplierLeads、SupplierProducts、HomeView、ShortageProcurementView 共 12 个文件的局部替换。

**P1-6｜合并 CompanyChat/CompanyAssistant 聊天骨架（解决 #5）**
- 做什么：抽 `components/chat/ChatScaffold.vue`（侧栏+消息区+输入区布局与全部气泡/输入样式），两页只传侧栏内容与发送逻辑；硬编码 `#c7cfdd/#d8deea/#171b26` 等统一映射令牌。
- 为什么：350 行样式砍掉约一半，且两个 AI 问答入口视觉自此锁定一致。

**P1-7｜清理死代码（解决 #10）**
- 做什么：删除 views/demos/LoginHoloPro.vue、LoginWithHolo.vue（未路由、无引用），如舍不得视觉效果可归档到仓外。
- 为什么：802 行死代码是检索噪声与重构时的误判源。

**P2-8｜令牌补强 +  lint 防线（解决 #9/#11/#12/#14）**
- 做什么：① tokens.css 增补 `--text-on-accent: #fff`、`--violet*`、`--success-border` 等缺口令牌；② QueryInput.vue、Chip.vue 的 10 处硬编码色值映射回令牌；③ 清除 7 个 !important（用提高选择器特异性或调整加载顺序替代）；④ 引入 stylelint 规则 `color-no-hex` + `declaration-property-value-disallowed-list`（禁 font-size 直写 px），CI 拦截新增硬编码。
- 为什么：前 7 项是还旧账，本项是防止新账——43 处硬编码字号与八档圆角说明仅靠自觉无法守住令牌体系。
- 改法：涉及 tokens.css、QueryInput.vue、Chip.vue、LandingView.vue、AppHeader.vue、DemoConsole.vue、ProcureView.vue，新增 .stylelintrc 与 CI 步骤。
