# 采购方业务数据页面 UI 分析报告

> 范围：`web/src/views/HomeView.vue`（经营驾驶舱）、`ProductsBomView.vue`（产品与 BOM）、`ShortageProcurementView.vue`（缺件与采购）、`HistoryView.vue`（历史记录），参考 `web/src/composables/useDashboard.ts`、`web/src/mock/dashboardAdapter.ts`。

## 1. 现状概述

四个页面均为自研深色卡片式布局，语言统一（bg-1 面板 + border-subtle 分隔 + 靛蓝主色），无第三方组件库。驾驶舱以「上下文条 + 4 指标卡 + 2×2 面板（订单/产品/缺件/推荐动作）+ 上下游条」构成，数据全部以文本表格与徽章呈现，无任何图表；BOM 页为「3 汇总卡 + 产品手风琴 + 七列 BOM 表」；缺件采购页为「左缺件清单 + 右详情/推荐动作/RFQ 表单/RFQ 列表/报价对比」的主从结构，是四页中交互闭环最完整的；历史记录页为简单卡片流，仅提供查看/删除。整体视觉一致性好，但数据可视化几乎为零、排序逻辑存在优先级错排缺陷、检索与批量操作能力缺失，数据过多/为空场景的处理不系统。

## 2. 问题清单

### 🔴 严重（影响可用性/明显缺陷/体验断裂）

1. **优先级排序逻辑错排：`urgent` 被排到最后**
   `severityRank()` 只映射 `{critical:4, high:3, medium:2, low:1}`，而订单/动作的 priority 取值为 `urgent/high/medium/low`（见 dashboardAdapter.ts:22 `priorityMap` 高→urgent、dashboardAdapter.ts:50 紧急→urgent）。`urgent` 命中 fallback 返回 0，比 `low(1)` 还低。
   - 证据：`useDashboard.ts:20-22`（映射表无 urgent）、`useDashboard.ts:239-242`（sortedActions 按 priority 排序）、`ShortageProcurementView.vue:53-56`（actions 同样按 `severityRank(b.priority)` 排序）。
   - 后果：驾驶舱「推荐动作」与缺件采购页「推荐动作」中，最紧急的动作沉底展示，与「优先级表达」目标完全相悖。

2. **驾驶舱数据源标签误导：mock 兜底数据显示为「暂无数据」**
   HomeView 用的是 `useEnterpriseContext` 的 dataSource（取值仅 `api/empty/loading`，见 useEnterpriseContext.ts:15），而驾驶舱数据本身走 `useDashboard` 的 api→mock 降级（useDashboard.ts:203-215）。后端挂掉时页面照常渲染 mock 数据，标签却显示「暂无数据」；`source-tag--mock` 样式（HomeView.vue:314）永远不会命中。
   - 证据：`HomeView.vue:9`（解构的是 enterprise context 的 dataSource）、`HomeView.vue:89-91`（非 api/loading 一律显示「暂无数据」）。与 ShortageProcurementView.vue:231 的「本地兜底经营数据」提示口径也不一致。

3. **缺件清单不按严重度排序，左侧列表优先级失序**
   `shortages` 直接取接口顺序（ShortageProcurementView.vue:52），而驾驶舱的 `topShortages` 做了 severity 排序（useDashboard.ts:230-233）。缺件页作为「优先级表达」的核心场景，清单顺序却是随机的，紧急缺件可能排在列表底部。

4. **RFQ 表单要求手填供应商数字 ID**
   「候选供应商ID」用文本输入框、placeholder 提示「逗号分隔， 如 9002,9006」，暴露内部主键、极易输错、无校验提示、无供应商名称联想。
   - 证据：`ShortageProcurementView.vue:334`。

5. **RFQ 状态未本地化，直接渲染英文枚举**
   状态列显示 `draft/sent/quoted/closed` 原文（ShortageProcurementView.vue:370 `{{ rfq.status }}`），在中文 B 端界面中突兀；对照同页 severity 已做中文映射（:64-66）。

6. **历史记录删除无二次确认，且不可恢复**
   `doRemove` 直接调 API + 清 localStorage（HistoryView.vue:18-21、useHistory.ts:151-158），单击「删除」即永久清除会话，危险按钮与「查看」等距并列，误触概率高。

7. **历史记录无检索/筛选/排序能力**
   整页无任何搜索框、状态筛选或排序切换（HistoryView.vue:48-103），标题即原始查询语句，记录一多（localStorage 上限 100 条，useHistory.ts:179）只能肉眼翻找，「检索与复用」目标未达成。也没有「复制查询/重新发起」的复用入口，只有「查看/删除」。

### 🟡 中等（不一致、效率低、可感知粗糙）

8. **驾驶舱订单/预测静默截断且无排序**
   `orders.slice(0, 8)`（HomeView.vue:148）、`forecasts.slice(0, 4)`（:159）截断后无「查看全部/更多」入口，用户不知道总数；且订单按接口原序展示，未按交期或优先级排序，与面板标题「需要关注的交付」不符。预测行与订单行混排，仅靠 0.85 透明度（:393）和「预测」绿徽章区分，扫描成本高。

9. **指标卡无量纲、无趋势、无对比**
   「预测需求」大数字无单位（HomeView.vue:111）；四张卡均无环比/趋势/sparkline，「待交付订单 12 / 3 个紧急」之外无法判断好坏。整页零图表，经营驾驶舱的「可视化」名不副实。

10. **critical 与 high 视觉无区分**
    `.sev--critical` 与 `.sev--high` 同为 danger 红色（HomeView.vue:481-483），紧急与高优在徽章上不可分辨，削弱分级意义。缺件页 risk-dot 同理且纯靠颜色（ShortageProcurementView.vue:496-499），红绿色盲用户无法区分 danger/success。

11. **BOM 手风琴单选互斥、且不能收起**
    `toggleProduct` 点击已展开项直接 return（ProductsBomView.vue:69-73），无法收起当前产品、也无法同时对照两个产品的 BOM；产品多时只能逐个点头。

12. **BOM 表无排序/筛选/搜索，行数无上限渲染**
    七列表格全量渲染（ProductsBomView.vue:156-164），无「只看关键件」过滤、无列排序、表头不 sticky（行多后表头滚走）、无分页或虚拟滚动。BOM 行数达到几十条时浏览与定位效率低。

13. **BOM「关键」列语义错位**
    非关键件显示绿色「否」徽章（ProductsBomView.vue:89-91、163），绿色在全局语义中是「正常/健康」，把「否」渲染成成功色会误导；且列头「关键」+值「是/否」信息冗余，可改为仅关键件打标。

14. **BOM 降级路径状态矛盾**
    接口失败时 products 降级自 dashboard 摘要（ProductsBomView.vue:43-53），但 `bomSummary` 为 null → 汇总条整体消失；此后展开任何产品，`getProductBom` 同样失败被 catch 成 `[]`（:64-66），显示「该产品暂无 BOM 数据」——把「接口失败」误导为「无数据」。

15. **useDashboard 无共享缓存，跨页重复拉取**
    `useDashboard()` 每次调用新建 refs 并立即 fetch（useDashboard.ts:154、221-223），HomeView/ShortageProcurementView/ProductsBomView 各自调用一次，页面切换重复 3 个并发请求且伴随 loading 闪烁。

16. **历史页跳转目标错误/复用弱**
    「开始寻源」跳 `/`（落地页，HistoryView.vue:27-29），而对话寻源在 `/chat`（router/index.ts:17）；用户从历史页发起新寻源被带到营销落地页，动线断裂。

17. **历史页状态与空态重复、状态判断粗糙**
    API 失败且本地无记录时，既显示「⚠ 暂无寻源记录」notice 又显示空状态卡（HistoryView.vue:62-72、useHistory.ts:108-110），信息重复；状态仅二分「异常/完成」（:86-88），进行中会话被误标「完成」。

18. **日期与时间格式问题**
    驾驶舱 `formatDate` 只输出 月/日（HomeView.vue:52-59），跨年订单交期无法区分；缺件详情「可用 0」来自 mock 硬编码 `available_qty: 0`（dashboardAdapter.ts:84），mock 场景下详情数字失真。

19. **关键操作静默失败、无反馈**
    重算缺件失败静默（ShortageProcurementView.vue:199-201）、RFQ 发送失败静默（:161-163）；发送成功后成功条直接消失（:160-161），无任何 toast/提示，用户无法确认动作结果。

20. **RFQ 列表截断无分页、报价对比格式粗糙**
    `rfqList.slice(0, 10)` 无分页入口（ShortageProcurementView.vue:365）；报价单价 `¥{{ q.unit_price }}` 不做千分位/小数位格式化（:397），最优行仅靠浅绿底区分、无「推荐」文字标识（:394、565）。

### 🔵 建议（锦上添花）

21. **驾驶舱加趋势与占比可视化**：指标卡加 sparkline 或环比箭头；订单面板可加按优先级分布的迷你条；缺件面板可加缺口数量横向条形，减少纯文本密度（HomeView.vue:103-124、139-170）。
22. **空状态分级**：当前各页空态只有一行灰字（如 HomeView.vue:219、ShortageProcurementView.vue:355），建议区分「确实无数据」与「接口失败」两种空态，并给出重试按钮；HistoryView 的空态（:67-72）是全站最完整的，可作模板推广。
23. **BOM 编码列加一键复制**：part_number 是采购检索的高频复制对象（ProductsBomView.vue:158），加点击复制按钮可减少手选操作。
24. **推荐动作卡片一致性**：HomeView 的 action-type 与 ShortageProcurementView 的 action-tag 是两套近似样式（HomeView.vue:458-461 / ShortageProcurementView.vue:525-528），可抽公共组件统一。
25. **mock 数据标记增强**：demo-badge 已有（HomeView.vue:396-416），但 mock 兜底数据（非 demo）无任何标识，建议在 source-tag 修正后同步标注「演示数据」水印。

## 3. 优化方案

### P0 — 立即修复

**方案 1：修复优先级排序，统一 rank 映射**
- 做什么：在 `useDashboard.ts:20-22` 的 `severityRank` 中补全订单/动作优先级取值：`{ critical:4, urgent:4, high:3, medium:2, low:1 }`，或新增 `priorityRank()` 专用函数供 sortedActions / ShortageProcurementView 使用。
- 为什么：urgent 当前 rank=0 被排到最后，直接影响驾驶舱与缺件页的优先级表达，是纯逻辑 bug，改动一行映射即可。
- 涉及文件：`web/src/composables/useDashboard.ts`（排序函数与 sortedActions）、`ShortageProcurementView.vue:53-56`。

**方案 2：修正驾驶舱数据源标签口径**
- 做什么：HomeView 改用 `useDashboard()` 返回的 `dataSource`（api/mock/loading），mock 时显示「本地数据」黄色标签；删除 enterprise context 版本的误用；`source-tag--mock` 样式（HomeView.vue:314）随之生效。
- 为什么：当前「暂无数据」与页面实际展示的兜底数据互相矛盾，破坏信任。
- 涉及文件：`HomeView.vue:9、89-91`。

**方案 3：缺件清单按严重度排序 + 优先级去颜色依赖**
- 做什么：`ShortageProcurementView.vue:52` 的 shortages 改为 `[...items].sort((a,b) => severityRank(b.severity)-severityRank(a.severity))`；risk-dot 旁保留中文等级文字，并将 critical 与 high 用不同色阶区分（critical 用 --danger、high 用 --notice #f97316，令牌已存在于 tokens.css:31-32）。
- 为什么：缺件页的核心价值是优先级表达，排序与色阶双通道缺一不可。
- 涉及文件：`ShortageProcurementView.vue`（shortages computed、severityTone、risk-dot 样式）、可同步修 `HomeView.vue:481-483` 的 sev--high 配色。

### P1 — 体验补齐

**方案 4：历史记录页加检索/筛选/复用 + 删除确认**
- 做什么：头部加搜索框（按 title 模糊过滤的 computed）、状态筛选 chips（全部/完成/异常）；每条记录加「重新寻源」按钮（跳 `/chat` 并带 `?q=title` 预填）；删除前弹确认（可用原生 confirm 或轻量 modal）；「开始寻源」目标从 `/` 改为 `/chat`。
- 为什么：检索与复用是该页的核心任务，当前完全缺失；误删不可恢复。
- 涉及文件：`HistoryView.vue`（模板头部、doRemove、newProcure）。

**方案 5：RFQ 表单供应商选择器 + 状态本地化**
- 做什么：将「候选供应商ID」文本框换成多选下拉/搜索选择器，数据源用 `dashboard.upstream_summary.items`（已有 company_id+company_name）；RFQ 状态列加 `{draft:'草稿',sent:'已发送',quoted:'已报价',closed:'已关闭'}` 映射。
- 为什么：消除内部 ID 暴露与英文状态，是 B 端表单的基本可用性。
- 涉及文件：`ShortageProcurementView.vue:334、370`，可复用 useDashboard 数据。

**方案 6：BOM 表效率增强**
- 做什么：表头吸顶（position: sticky）；加「只看关键件」开关与按品类筛选；「关键」列改为仅关键件显示红色「关键」徽章、非关键留空；手风琴允许再次点击收起（toggleProduct 改为同 id 时置 null）；接口失败时 BOM 区显示「加载失败，重试」而非「暂无数据」。
- 为什么：BOM 行数多、对照需求强，当前密度与操作成本失衡。
- 涉及文件：`ProductsBomView.vue:69-73、143-166、260-291`。

### P2 — 可视化与一致性提升

**方案 7：驾驶舱可视化升级**
- 做什么：指标卡加单位与环比/趋势箭头；订单面板按 due_date+priority 排序，截断处加「查看全部 N 条」入口；订单/预测分行或加类型列；缺件面板加缺口量横向条形；critical/high 色阶拆分（复用 --notice）。
- 为什么：让「经营驾驶舱」具备基本的趋势感知与优先级导航能力。
- 涉及文件：`HomeView.vue:103-170`，可选引入轻量 SVG sparkline 组件。

**方案 8：操作反馈与空态体系化**
- 做什么：引入全局轻量 toast（或复用现有 notice-bar 模式）覆盖重算缺件、RFQ 发送/创建的结果反馈；统一各页空态为「图标+标题+引导按钮」结构（以 HistoryView 空态为模板）；区分「无数据」与「加载失败」。
- 为什么：当前静默失败与单行灰字空态让用户无法判断系统状态。
- 涉及文件：`ShortageProcurementView.vue:156-163、191-203`，各页 `.empty-line`。

**方案 9：useDashboard 共享化**
- 做什么：将 useDashboard 的状态提升为模块级单例或 Pinia store，跨页共享缓存，企业切换时统一失效。
- 为什么：消除三个页面重复拉取与 loading 闪烁，也为方案 5 的供应商选择器提供统一数据源。
- 涉及文件：`web/src/composables/useDashboard.ts`（或迁移 `stores/`）。
