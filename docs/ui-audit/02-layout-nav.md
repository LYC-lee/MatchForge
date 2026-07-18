# 整体布局与导航信息架构 UI 分析报告

> 审查范围：`web/src/App.vue`、`web/src/components/layout/AppHeader.vue`、`web/src/components/layout/StepNav.vue`、`web/src/router/index.ts`，并抽查 `HomeView.vue`、`ProcureView.vue`、`supplier/SupplierDashboard.vue` 等视图的实际布局用法。

## 1. 现状概述

应用采用经典"左侧固定边栏（256px）+ 顶部固定栏（56px）"双栏 Chrome：边栏承载品牌、企业上下文卡、8 项主导航与"数据边界"说明，顶栏展示"企业名 / 页面标题"面包屑与用户区（`AppHeader.vue:38-91`）。`App.vue` 通过 `padding-left/top` 让出 Chrome 区域，≤920px 时边栏转为顶部横向滚动条，顶栏下移至 48px。寻源工作流页（ProcureView）在全局 Chrome 内再叠加一条 sticky 步骤条，内嵌 StepNav 展示 6 个智能体阶段状态（仅展示、不可点击）。路由共 17 条，其中 6 条为旧路径重定向，守卫仅校验登录。各页面容器自成一体，max-width 从 640px 到 1360px 不等。

## 2. 问题清单

### 🔴 严重（影响可用性/明显缺陷/体验断裂）

1. **多角色（采购方/供应商/管理端）无任何导航分流与权限收敛**
   主导航是静态数组，8 个入口平铺混排：采购方功能（驾驶舱/产品 BOM/缺件采购/AI 寻源/协同问答）、管理端功能（数据与知识库）与"供应商工作台"并列展示，不按角色过滤。[证据 web/src/components/layout/AppHeader.vue:14-23] `const mainNav = [ { to: '/app' ... }, ... { to: '/supplier', icon: 'S', label: '供应商工作台' } ]`
   路由守卫只校验 `requiresAuth`，无 role/permission meta，供应商账号登录后可见并进入全部采购方与管理端页面。[证据 web/src/router/index.ts:38-45] `if (to.meta.requiresAuth && !(await auth.validateSession()))`
   项目中不存在任何角色驱动的导航判断（全仓检索 `is_supplier|role === 'buyer'` 无匹配）。

2. **ProcureView 的 sticky 步骤条在 ≤920px 时被全局顶栏遮挡**
   步骤条偏移写死 `top: 56px`，只适配桌面端 56px 顶栏；但 ≤920px 时头部总高为 48px 横条 + 56px 顶栏 = 104px，sticky 条会被压住约 48px，StepNav 与"← 新寻源"部分不可见。[证据 web/src/views/ProcureView.vue:322-329] `.procure__topbar { position: sticky; top: 56px; ... }` 对照 [web/src/App.vue:42-47] `@media (max-width: 920px) { .app-main { padding-top: 104px } }` 与 [web/src/components/layout/AppHeader.vue:298] `.topbar { top: 48px; ... }`。ProcureView 自身的 768px 媒体查询只做了换行，未修正 top 与 z-index。[证据 web/src/views/ProcureView.vue:546-560]
   同理，侧栏摘要 `top: 128px` 也是按桌面双栏高度推演的魔法数字。[证据 web/src/views/ProcureView.vue:392-394]

3. **入口缺失与孤儿路由：审核管理、历史记录在导航中不可达；无 404 兜底**
   `/admin/audit`（审核管理）注册于路由但全仓无任何导航/链接指向它（仅 API 层有 audit-queue 方法），只能通过手输 URL 进入。[证据 web/src/router/index.ts:26]
   `/history`（历史记录）不在主导航 8 项中，全仓无 `to="/history"` 链接，唯一关联入口是旧路径重定向 `/flow/history`。[证据 web/src/components/layout/AppHeader.vue:14-23、web/src/router/index.ts:24-25]
   路由表无 `/:pathMatch(.*)*` 兜底，未知路径会渲染带 Chrome 的空白页，且顶栏标题回退为"经营驾驶舱"，产生误导性面包屑。[证据 web/src/router/index.ts:5-31、web/src/components/layout/AppHeader.vue:12] `String(route.meta.title || '经营驾驶舱')`

### 🟡 中等（不一致、效率低、可感知粗糙）

4. **页面容器宽度规范缺失，全站 9 种 max-width**
   1360px（HomeView）、1320px（ShortageProcurement）、1280px（ProductsBom）、1240px/1200px（ProcureView 正文/顶条）、1100px（SupplierDashboard、SupplierProducts、SupplierLeads、P7AdminAudit）、960px（History）、900px/800px（ChatView 混用两档）、640px（CompanyAssistant）。[证据 web/src/views/HomeView.vue:277、web/src/views/ShortageProcurementView.vue:413、web/src/views/ProductsBomView.vue:175、web/src/views/ProcureView.vue:331,377、web/src/views/supplier/SupplierDashboard.vue:204、web/src/views/P7AdminAudit.vue:281、web/src/views/HistoryView.vue:108、web/src/views/ChatView.vue:849,968、web/src/views/CompanyAssistant.vue:233]
   同 B 端工具内切换页面时内容边界持续跳动，无统一栅格体感。

5. **响应式断点各自为政，无断点令牌**
   全局 Chrome 用 920px（App.vue:42、AppHeader.vue:274），页面层用 1100/640（HomeView.vue:504,510）、768（ProcureView.vue:546、SupplierDashboard.vue:296）、980/700（ShortageProcurementView.vue:572,577）、700（ProductsBomView.vue:292）。Chrome 断点与内容断点之间（768–920px）存在布局叠层失控区间（见问题 2）。

6. **当前企业信息在首屏重复 3 次**
   边栏企业卡（公司名+细分+角色+数据来源）、顶栏面包屑（公司名）、驾驶舱 context-bar（公司名+角色+来源标签）同时出现。[证据 web/src/components/layout/AppHeader.vue:49-55,80、web/src/views/HomeView.vue:83-100] 顶栏信息密度本就有限，重复公司名挤压了真正的位置线索。

7. **导航激活态在深层页面断裂**
   高亮依赖 `router-link-exact-active`，但 `/procure/:id`（工作流）、`/supplier/products`、`/supplier/leads`、`/history`、`/admin/audit` 均无对应精确匹配项，进入这些页面后边栏无任何激活指示，用户失去"我在哪"的反馈。[证据 web/src/components/layout/AppHeader.vue:186-190]

8. **图标体系三套混用**
   主导航用字母代号（D/B/!/C/AI/K/S）却给"AI 寻源"用 emoji 🔍；供应商工作台快捷卡又用另一套 emoji（📋📦🏢）。[证据 web/src/components/layout/AppHeader.vue:15-22、web/src/views/supplier/SupplierDashboard.vue:184-194] 字母代号对新用户无语义（"K"=知识库、"C"=协同），且与"全站无第三方组件库、自研设计令牌"的精致基调不符。

9. **StepNav 只读不可交互、无可访问性语义**
   步骤渲染为纯 `div`，完成态不能回跳到对应阶段（规格确认/替代料等锚点已在页面内存在），无 `role="list"`/`aria-current="step"`。[证据 web/src/components/layout/StepNav.vue:24-40]
   另外 LABELS 含 `chat: '智能问答'` 共 7 项映射，但 ProcureView 文案写"6 个智能体阶段"，映射与业务口径存在冗余。[证据 web/src/components/layout/StepNav.vue:16、web/src/views/ProcureView.vue:172]

10. **6 条重定向旧路径反映 IA 演进未收尾**
    `/flow`、`/spec-confirm`、`/alternatives`、`/supplier-match`、`/rfq-edit` 全部 redirect 到 `/chat`，`/flow/history` → `/history`，说明信息架构已从"多页分步流程"演进为"单会话驱动"，但旧路由仍保留 `name` 且无 meta.title，经这些路径进入时 `document.title` 变成"MatchForge - MatchForge 智配"。[证据 web/src/router/index.ts:19-25,39]

11. **移动端 Chrome 双条堆叠过高且为脆弱魔法数字**
    ≤920px 时横向边栏 `min-height: 48px`（实际高度由内容撑开，未锁定）+ 顶栏 56px = 约 104px 常驻 chrome，`App.vue` 的 `padding-top: 104px`、顶栏的 `top: 48px`、边栏的 `min-height: 48px` 三处数字互相硬耦合，任何一处字号/内边距调整都会错位。[证据 web/src/components/layout/AppHeader.vue:279,298、web/src/App.vue:45] 且 8 个导航项横向滚动，无"更多"收纳，首项与末项可达性差。

### 🔵 建议（锦上添花）

12. **flowNav 死代码**：`const flowNav = []` 恒为空，对应"保留流程入口"区块永不渲染，是上一轮 IA 的残留。[证据 web/src/components/layout/AppHeader.vue:25,64-70]

13. **blank 布局双轨判定**：`App.vue` 同时用 `route.meta.layout !== 'blank'` 和硬编码 `blankPaths` 集合，而路由里 `/`、`/login`、`/register` 已带 `meta.layout: 'blank'`，硬编码集合冗余且易腐。[证据 web/src/App.vue:8-9、web/src/router/index.ts:6-8]

14. **边栏常驻"数据边界"说明卡**：产品策略文案长期占据导航黄金位置，更适合收入帮助中心或首次引导。[证据 web/src/components/layout/AppHeader.vue:72-75]

15. **退出入口位置与密度**：顶栏右侧仅"头像+姓名+退出"，无用户菜单承载"个人设置/切换企业/帮助"，后续扩展必然再改顶栏。[证据 web/src/components/layout/AppHeader.vue:84-90]

## 3. 优化方案

**P0-1 建立角色化导航模型（对应问题 1、3）**
- 做什么：给路由加 `meta.roles: ['buyer'|'supplier'|'admin']`，主导航改为"分组 + 按角色过滤"：采购组（驾驶舱/产品 BOM/缺件采购/AI 寻源/历史记录）、协同组（上下游协同/企业问答/知识库）、供应商组（工作台/产品/线索）、管理组（知识库/审核）。
- 为什么：B2B 多角色产品的第一 IA 原则是"看到即我能用"；当前平铺 8 项既泄露管理端入口，也让供应商首屏认知超载。
- 改法：`router/index.ts` 增加 roles meta 与守卫校验；`AppHeader.vue` 的 mainNav 改为带 `group`/`roles` 的配置数组，按 `auth.user`/`useEnterpriseContext().current.role` 过滤并用 `sidebar__label` 分组渲染；把 `/history`、`/admin/audit` 纳入对应分组，消灭孤儿路由。

**P0-2 修复 sticky 偏移体系（对应问题 2、11）**
- 做什么：在 `tokens.css` 增加布局令牌 `--header-h: 56px`、`--header-h-mobile: 104px`、`--sidebar-w: 256px`，`App.vue`、`AppHeader.vue`、`ProcureView.vue` 全部引用令牌；ProcureView 的 sticky top 改为 `calc(var(--header-h))` 并在 920px 断点切换为 `calc(var(--header-h-mobile))`。
- 为什么：三处硬编码（48/56/104/128）已造成移动端步骤条被遮的真实缺陷；令牌化是一劳永逸的修法。
- 改法：tokens.css 新增变量；App.vue:35-47、AppHeader.vue:229,279,298、ProcureView.vue:324,394 替换字面量。

**P0-3 增加 404 兜底与标题回退修正（对应问题 3）**
- 做什么：路由表末尾加 `{ path: '/:pathMatch(.*)*', component: NotFoundView }`；顶栏标题回退从"经营驾驶舱"改为空态或"页面"。
- 为什么：错误路径下展示错误面包屑属于信任损耗。
- 改法：router/index.ts + AppHeader.vue:12。

**P1-1 收敛容器宽度与断点（对应问题 4、5）**
- 做什么：定义三档内容宽度令牌——`--content-narrow: 760px`（问答/表单类：CompanyAssistant、Login）、`--content-default: 1200px`（列表/工作流：History、Procure、Chat、供应商三页、审核）、`--content-wide: 1360px`（数据密集驾驶舱：Home、Shortage、ProductsBom）；断点统一为 640/920/1280 三档，写入 tokens.css，各视图 scoped 样式引用。
- 为什么：9 种宽度 + 5 套断点是全站"粗糙感"的最大来源，且 768–920px 区间是当前布局失控带。
- 改法：tokens.css 增加变量；逐视图替换 max-width 与 @media 字面量（涉及 10 个 view 文件，机械替换）。

**P1-2 顶栏去重 + 用户菜单（对应问题 6、15）**
- 做什么：顶栏面包屑去掉公司名（边栏企业卡已承担），改为"分组名 / 页面标题"；右侧头像改为下拉菜单（个人信息、切换企业、帮助、退出）。
- 为什么：释放顶栏信息密度，为角色切换（P0-1）提供落点。
- 改法：AppHeader.vue:79-91；菜单可复用现有 `dropdown` 模式（若无则新增一个轻量组件）。

**P1-3 导航激活态覆盖深层路由（对应问题 7）**
- 做什么：导航配置增加 `activeMatch: string[]`（如 AI 寻源匹配 `/chat`、`/procure`；供应商工作台匹配 `/supplier`），用 `useRoute().path` startsWith 判断替代 `router-link-exact-active`。
- 为什么：工作流页是全站核心转化路径，不能没有位置反馈。
- 改法：AppHeader.vue:14-23,58,186。

**P2-1 统一图标体系（对应问题 8）**
- 做什么：引入一套线性 SVG icon（内联组件或 sprite），替换字母代号与 emoji；导航图标统一 20px、currentColor。
- 为什么：三套图标混用直接拉低 B 端专业感；字母代号无辨识度。
- 改法：新增 `components/ui/AppIcon.vue` + icons 目录；AppHeader.vue、SupplierDashboard.vue 替换。

**P2-2 StepNav 可交互化与语义化（对应问题 9）**
- 做什么：done 态渲染为 `<button>` 并 emit `jump(name)`，由 ProcureView 滚动到对应 Card 锚点；容器加 `role="list"`、当前步加 `aria-current="step"`；清理 LABELS 中未使用的 `chat` 映射或与"6 个智能体"文案对齐。
- 为什么：工作流页纵向长度大，步骤回跳是高频效率操作。
- 改法：StepNav.vue 模板与 props；ProcureView.vue:135 接收事件并复用现有 `scrollIntoView` 逻辑（:116）。

**P2-3 清理 IA 演进残留（对应问题 10、12、13、14）**
- 做什么：重定向路由去掉 `name`、统一加注释标明保留期限；删除 flowNav 死代码；`App.vue` 只保留 `meta.layout` 单轨判定；"数据边界"文案移至帮助入口。
- 为什么：降低后续维护者的认知成本，避免双轨配置再次腐化。
- 改法：router/index.ts:19-25、AppHeader.vue:25,64-75、App.vue:8-9。
