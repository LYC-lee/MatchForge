# MatchForge 前端 UI 审查总报告与优化路线图

> 审查时间：2026-07-17 ｜ 范围：`web/src` 全部 39 个 .vue 文件 + 4 个样式文件（约 1.3 万行）
> 本报告为 11 份专项报告的汇总，细节与证据（文件:行号）见各分报告。

| # | 专项 | 报告 |
|---|------|------|
| 01 | 设计系统与基础组件 | [01-design-system.md](01-design-system.md) |
| 02 | 布局与导航 | [02-layout-nav.md](02-layout-nav.md) |
| 03 | 落地页与认证 | [03-landing-auth.md](03-landing-auth.md) |
| 04 | 寻源工作流（发起与确认） | [04-workflow-a.md](04-workflow-a.md) |
| 05 | 寻源工作流（匹配与报价） | [05-workflow-b.md](05-workflow-b.md) |
| 06 | 对话体验 | [06-chat.md](06-chat.md) |
| 07 | 采购方业务页 | [07-buyer-pages.md](07-buyer-pages.md) |
| 08 | 供应商端 | [08-supplier.md](08-supplier.md) |
| 09 | 管理端 | [09-admin.md](09-admin.md) |
| 10 | 可访问性与响应式 | [10-a11y-responsive.md](10-a11y-responsive.md) |
| 11 | 一致性与 CSS 工程质量 | [11-consistency.md](11-consistency.md) |

---

## 一、现状总评

项目已有不错的基础：深色令牌体系（tokens.css）设计完整、自研组件雏形（AppButton/Card/Chip/Tag）、寻源工作流的信息架构清晰。但作为 MVP 快速迭代的结果，当前 UI 存在 **三个系统性问题**：

1. **两套视觉语言并存**：遗留浅色 `global.css` 后加载覆盖深色令牌，全局类与深色组件撞车，部分页面（AdminKnowledge、SupplierProducts）仍是浅色风格。
2. **正确性缺陷多于美观问题**：多处"UI 导致功能错误"——RFQ 手改内容被静默抹掉、urgent 优先级沉底、中文 IME 回车误发送、断流零反馈、L5 风险标红误导判断。
3. **组件复用率低、重复实现多**：GradeCard 死代码 + 内联复制、空态/Skeleton/状态标签各 4–7 份实现、三个对话页三套输入区、硬编码色值大量绕过令牌。

---

## 二、跨专项关键发现（按主题）

### 🔴 主题 A：UI 导致的功能/数据正确性缺陷（最高优先级）

| 问题 | 证据 | 来源 |
|------|------|------|
| RFQ 编辑器单向全量重建同步，手改正文被任意字段编辑静默抹掉 | RfqEditor.vue:150-157 | 05 |
| RFQ 模板品名硬编码 MLCC，非 MLCC 品类生成错误询价单 | RfqEditor.vue:121-122 | 05 |
| 优先级 `severityRank` 无 `urgent` 映射，紧急项排序沉底 | useDashboard.ts:20-22 | 07 |
| SSE 断流零反馈：streamError/streamNotice 无渲染出口，Agent 永远转圈 | ProcureView.vue:21-39 | 04 |
| 三个对话页均未处理 IME 合成态，中文选词回车即误发送 | ChatView.vue:212 等 3 处 | 06 |
| Tag 将 L5「仅参考」映射为 danger 红色，误导采购判断 | Tag.vue:24 | 01 |
| demo 模式下审核队列整体消失（条件链 bug + 死代码） | P7AdminAudit.vue:177-181 | 09 |
| 供应商工作台快速入口错链到采购方 /products-bom | SupplierDashboard.vue:188 | 08 |
| 替代料只读，RFQ 自动硬取前 3 个非 L5 料，用户无法选择 | RfqEditor slice(0,3) | 05 |
| 登录页 `overflow:hidden` 裁剪表单，矮视口按钮不可达 | LoginView.vue:318 | 03 |

### 🔴 主题 B：高危操作零防护

- 历史会话 × 单击即不可逆删除（SessionHistoryPanel.vue:103-107）
- 历史记录页同样单击永久删除、无搜索（HistoryView.vue:48-103）
- 审核通过/驳回单击生效、无确认无撤销、失败静默、驳回不强制备注（P7AdminAudit.vue:142-160）
- 知识库"留空=全部公司+强制重生成"一键触发无确认（AdminKnowledge.vue:147-149）
- 供应商线索用原生 `prompt()` 拒绝、catch 静默（08）

### 🔴 主题 C：双视觉语言与令牌体系冲突

- `global.css`（浅色）在 main.ts 中后于 tokens.css 导入：body 浅底深字、`--radius-lg` 被改、深色阴影失效、`.btn/.card/.tag` 全局类与深色组件撞车（01、11）
- AdminKnowledge 用浅蓝全局类、SupplierProducts 用浅色 pastel、DemoConsole 全硬编码 25 处色值混入生产外壳（11）
- 硬编码热点：登录/注册 61 色值+73 rgba 为最大硬编码源；QueryInput 6 处硬编码（11、04）

### 🟡 主题 D：导航与信息架构

- 多角色无分流：采购/供应商/管理端 8 入口平铺混排，守卫只验登录不验角色（AppHeader.vue:14-23）
- 孤儿路由：/history、/admin/audit 无导航入口；无 404 兜底（02）
- 移动端步骤条被顶栏遮挡：sticky top 写死 56px vs 移动端头部 104px（ProcureView.vue:324）
- 宽度/断点失控：9 种 max-width、5–8 套断点（02、10）

### 🟡 主题 E：可访问性

- 焦点可见性失效：输入框 `outline:none` 焦点指示对比度仅 1.53:1（需 3:1）；按钮/标签页无 `:focus-visible`（10）
- 零 `prefers-reduced-motion`：28 文件 80 处动画无降级，登录页 Canvas 无限 rAF（违反 WCAG 2.2.2）
- 对话流无 live region，读屏不可见；弹层无 `role="dialog"` 无焦点管理（10）
- 主按钮白字/靛蓝 4.47:1、accent 文字 4.22:1，不达 AA 4.5:1（10）

### 🟡 主题 F：文案与信任

- 落地页混入开发者黑话："Ready for Spike / 再接真实数据"（LandingView.vue:198-199）
- 状态英文枚举直出、供应商两页 `declined` 翻译不一致（07、08）
- 驾驶舱降级 mock 时数据源标签显示"暂无数据"，与实际展示矛盾（HomeView.vue:89-91）
- demos/ 两登录页是未挂路由的腐坏僵尸代码（乱码文案、async 未 await），另有 6 个未引用 demo-*.html（03）

---

## 三、优化路线图

### P0 — 修正确性缺陷与高危操作（1–2 天，纯修复、不改视觉）

1. **RFQ 编辑器**：确立字段/正文单一数据源，手改加脏标记 + 覆盖确认；模板品名改 `f('part_name')` 删 MLCC 硬编码；替代料改用户勾选「纳入询价单」替代 slice(0,3)。
2. **补全 urgent 优先级映射**（urgent=4），修驾驶舱与缺件页排序。
3. **断流反馈**：ProcureView 渲染 streamError/streamNotice 横幅，AgentTimeline 断流降级为错误态。
4. **IME 安全**：三个对话页 Enter 处理加 `isComposing` 判断（顺手抽共享 ChatInput）。
5. **高危操作确认**：新建共享 ConfirmDialog，接入历史删除、审核通过/驳回、知识库全量重建；驳回强制备注；操作按钮加 submitting 态。
6. **修 demo 条件链**（审核队列可达）、**修供应商错链**、**移除登录页 overflow:hidden**、**Tag L5 改 neutral**。
7. **删除/隔离 demos 目录**与 6 个 demo-*.html 僵尸文件。

### P1 — 统一视觉系统与导航骨架（2–4 天）

1. **拆除 global.css**：main.ts 移除导入，存量全局类（skeleton/empty-state/btn/tag-*）用深色令牌重写或迁入组件；tokens.css 归一为唯一令牌源。
2. **令牌补齐**：`--focus-ring`、z-index 分层、`--header-h`/`--header-h-mobile`/`--sidebar-w`、三档容器宽（760/1200/1360）、统一断点（640/920/1280）、overlay/blur；替换全部硬编码耦合。
3. **角色化导航**：路由加 `meta.roles`，导航按角色过滤分组，补 /history、/admin/audit 入口，加 404 页。
4. **组件收敛**：ChatView 改用 GradeCard 删内联复制；抽 AuthLayout（登录/注册）、EmptyState、Skeleton、StatusTag、ChatInput/ChatMessage 共享化；供应商三页接入 Card/Tag。
5. **a11y 地基**：全局 `:focus-visible` 规则、`prefers-reduced-motion` 降级、ChatView live region + 错误 `role="alert"`、弹层 dialog 语义与焦点圈禁；主色文字对比度调到达 AA。

### P2 — 体验打磨（持续）

1. 对话体验统一：三页共用消息组件与输入区，修企业/伙伴切换竞态，补复制/重试/自动增高。
2. 数据页增强：历史记录搜索/筛选、BOM 与缺件页空态/过载策略、驾驶舱数据源口径修正、缺件 severity 色阶。
3. 供应商端闭环：产品页接真实 API（未就绪前标注演示数据）、状态字典抽共享模块、线索状态流转可视化。
4. 落地页文案重写为采购方价值语言，消除定位漂移（替代料寻源 vs 装配寻源）。
5. 工作流打磨：SpecConfirm 支持 Enter 提交与「返回修改需求」、步骤条 sticky 偏移令牌化、死代码清理（AgentTimeline 产出计数 props 等）。

---

## 四、度量建议

- 硬编码色值计数（当前：登录/注册 61+73 rgba，DemoConsole 25）→ 目标趋近 0
- 重复模式计数（空态 7、Skeleton 4、状态标签 4）→ 目标各 1 个共享组件
- 断点数（当前 5–8 套）→ 目标 3 档
- WCAG：焦点指示 ≥3:1、正文对比度 ≥4.5:1、reduced-motion 全覆盖
