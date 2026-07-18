# 管理端（数据与知识库 / 审核管理）UI 分析报告

审查范围：`web/src/views/AdminKnowledge.vue`（/admin/knowledge）、`web/src/views/P7AdminAudit.vue`（/admin/audit）。对照基准：`web/src/styles/tokens.css`、`web/src/components/ui/`（AppButton / Card / Tag）、业务端页面（ChatView、HistoryView、供应商端等）。

## 1. 现状概述

两个管理端页面均为自研深色卡片式布局，直接使用 tokens.css 设计令牌。AdminKnowledge 以「运行时能力 + 聚合统计 + 生成操作 + 任务日志」四张卡片纵向堆叠，本质是一个任务触发与监控面板：知识库的手册/切片只以聚合数字呈现，无条目级浏览与管理；操作区支持全量/增量生成与索引重建，运行任务以 3s 轮询刷新进度。P7AdminAudit 是审核队列工作台：统计芯片 + 状态 Tab + 搜索 + 卡片列表，待审核项内联备注输入与通过/驳回按钮，支持 demo 沙盘只读模式，有骨架屏与错误提示条。两页视觉语言分裂明显：AdminKnowledge 用 bg-1 卡片、渐变自研按钮、英文状态原文；P7AdminAudit 用 bg-2 卡片、共享 AppButton、中文标签，更接近业务端。

## 2. 问题清单

### 🔴 严重（影响可用性/明显缺陷/体验断裂）

1. **demo 模式下审核队列整体不渲染，只读队列代码成死代码**。`P7AdminAudit.vue:177-181`：`<div v-if="isDemo" class="notice-bar--demo">` 与 `<template v-else>`（统计/Tab/列表全部内容）构成 if/else 链，demo 模式只显示一条横幅，主内容永远缺席。而 269-271 行的 `audit-card__readonly` 只读提示块、23-42 行的 demo 数据映射，显然都是为「demo 下展示只读队列」而写——实际不可达。演示路径体验断裂。
2. **审核通过/驳回零防误：单击即生效、无确认、无撤销、失败静默**。`P7AdminAudit.vue:265-266` 按钮直接触发 `handleApprove/handleReject`；`142-160` 行两个 handler 均 `catch { /* 静默失败 */ }`——接口失败时用户得不到任何反馈，会以为已生效。驳回操作也不强制填写备注（263 行 placeholder 写明"可选"），事后 `review_note` 为空无从追溯驳回原因。
3. **知识库高危操作缺乏确认与防护**。`AdminKnowledge.vue:147-149`：公司 ID 留空即"全部公司" + "强制重生成"勾选后，点一次「启动生成」直接触发全量 LLM 重建，无 confirm、无影响说明、无提交中状态（按钮不 disable，可重复点击重复发任务，51-59 行无 try/catch 与 submitting 态）。整页只有重建索引用了原生 `confirm`（68 行），取消任务（181 行）也是一键生效。确认策略在同页内自相矛盾。
4. **审核项的 detail（判定依据）被映射却从不渲染**。`P7AdminAudit.vue:31` 把 `detail` 映射进统一对象，但模板 226-273 行没有任何位置输出 `item.detail`——审核员只能看到标题和一截 payload 摘要，看不到"为什么被标记"，对报价异常/匹配类审核项的决策质量影响直接。

### 🟡 中等（不一致、效率低、可感知粗糙）

5. **进入页面时已有运行中任务不会自动轮询**。`AdminKnowledge.vue:79-89` `startPolling` 只在本页发起任务后调用，`onMounted` 仅执行一次 `refresh`（98 行）——刷新页面或他人发起的任务，进度条永远停留在进入时的快照，需手动点刷新。
6. **知识库页面无错误反馈 + 路由无权限守卫**。`AdminKnowledge.vue:37-38` 接口失败仅 `console.error`，页面无任何提示（P7AdminAudit 有 notice-bar 错误条，178 行）；`router/index.ts:15,26` 两条 admin 路由均只有 `requiresAuth`，无角色 meta，普通用户进入 /admin/knowledge 会看到一整页空白卡片。
7. **「知识库管理」无条目组织维度**。页面标题为知识库管理，但全文没有任何手册/切片/文件列表：129-136 行只有聚合数字（中/英手册数、切片数），无法回答"哪些公司未就绪""某公司的手册内容是什么""哪份手册需要更新"，也没有上传/替换/删除入口。管理动作只有"重新生成"一种。
8. **全量生成的公司选择方式与单公司不一致且易错**。`AdminKnowledge.vue:147` 用裸文本框手填逗号分隔 ID，而 155-158 行单公司增量用下拉选择（companies 数据已加载）；54 行 `parseInt` 解析把非法输入静默丢弃，用户填 "1,abc,2" 不会得到任何校验提示。
9. **审核工作流效率短板**：无批量选择/批量通过（待审核量大时只能逐条两次点击）；无分页/虚拟列表，`filteredItems` 全量渲染（225 行）；无手动刷新按钮与自动刷新，队列会陈旧；待审核列表不按类型风险排序，`quotation_anomaly`（红色高危）与普通项混排（82-91 行有颜色映射但未用于排序）。
10. **任务日志信息粗糙**。`AdminKnowledge.vue:178-194`：任务类型、状态直接显示英文原文（`partially_completed`），无创建时间/耗时/task_id；`result_summary` 用 `JSON.stringify(...).slice(0,200)` 裸 JSON 截断展示；失败记录只显示前 5 条且无展开入口（188 行）。
11. **两个管理页视觉语言分裂**。卡片底色：AdminKnowledge 用 `--bg-1`（209-214 行）vs P7AdminAudit 与共享 `Card.vue:24` 用 `--bg-2`；按钮：AdminKnowledge 自研渐变 `.btn-primary`（238-242 行）vs 全项目 14 个文件统一用 AppButton 扁平 `--accent`；标题：26px（206 行）vs 20px（292 行）；布局：全宽 vs `max-width: 1100px` 居中（281 行）；状态：英文 pill `radius-full`（259 行）vs 中文 tag `radius-sm`。

### 🔵 建议（锦上添花）

12. `P7AdminAudit.vue:337-342` 本地重复实现 `.tag-yellow/.tag-green/...`，与共享 `Tag.vue`（success/warning/danger 语义齐全）功能重叠，可复用。
13. 待审核统计芯片无视觉强调（184-187 行与"已通过/已驳回"同灰度），可操作项应最醒目；空态 emoji "✅"（219 行）与 B 端工具调性不符。
14. `AdminKnowledge.vue:32-36` 每个任务串行 `await loadFailures`，3s 轮询下形成 N+1 串行请求，可 `Promise.all` 并行；终态任务的 failures 不必每次重拉。
15. payload 摘要中的 RFQ 号、供应商 ID（104-110 行）是纯文本，审核时需手动复制查询，可做成跳转链接。
16. 文件命名 `P7AdminAudit.vue` 带迭代前缀，与 `AdminKnowledge.vue` 命名规范不一；165 行存在一个空 watcher（`watch(..., () => {}, {deep:true})`）死代码。

## 3. 优化方案

**P0-1 修复 demo 分支渲染断裂（P7AdminAudit.vue:177-181）**
把 demo 提示条移出条件链：`<div v-if="isDemo">` 独立成句（不与主内容构成 if/else），主内容区的 `v-else` 改为挂在 loading/error 链上或改用 `v-show`。让 269-271 行的只读队列按计划可达。改动仅模板条件结构，半天可验证。

**P0-2 建立审核操作防误闭环（P7AdminAudit.vue:142-160, 262-268）**
- 通过/驳回增加确认弹层（项目暂无共享 ConfirmDialog，建议新建 `components/ui/ConfirmDialog.vue`，复用 tokens 的 `--danger-soft`/`--shadow-lg`，后续 DemoConsole:159 的 window.confirm 也可收敛）；
- 驳回强制填写备注：`驳回` 按钮在 `noteInputs[item.id]` 为空时 disabled 或点击时红框提示；
- 去除静默 catch，失败时用行内错误条或 toast 提示"操作失败，请重试"，成功后乐观移除卡片并给 3 秒撤销窗口（撤销即调反向接口或重新入队）。

**P0-3 知识库高危操作确认与提交态（AdminKnowledge.vue:51-77, 147-149, 181）**
- 「启动生成」在留空（=全部）或勾选强制重生成时弹确认框，文案写明影响面："将对 N 家公司重新生成知识，预计消耗 LLM 调用"，N 由已加载的 `companies.length` 或解析后的 ids 长度得出；
- 所有操作按钮加 `submitting` ref，请求期间 disable + loading 文案，杜绝重复发任务；
- 取消任务二次确认；统一收敛到 P0-2 的 ConfirmDialog，替换 68 行原生 confirm。

**P1-4 渲染审核详情并按风险排序（P7AdminAudit.vue:31, 226-273）**
在 `audit-card__meta` 之前输出 `item.detail`（次要文本色，可折叠）；`filteredItems` 在 pending Tab 下按 `typeClass` 的危险等级（red > yellow > blue > gray）排序，让报价异常类高危项置顶。

**P1-5 审核队列效率与批量能力（P7AdminAudit.vue）**
卡片左侧加 checkbox + 工具条出现"批量通过（n）"入口（批量驳回仍需逐条备注，不开放）；批量动作复用 P0-2 确认框并逐条回报失败项。列表加分页（每页 20）或"加载更多"；页头补一个刷新按钮（对齐 AdminKnowledge 的 btn-refresh 模式）。

**P1-6 知识库条目化与输入纠偏（AdminKnowledge.vue:147-158）**
- 新增"公司知识状态"表格卡片：利用已加载的 `companies` + stats 接口（或扩一句 per-company 状态字段），列出每家公司的就绪状态、中/英手册数、切片数、最近生成时间，行内挂"增量更新"按钮——把 153-160 行的下拉入口并入表格，操作目标可视化；
- 全量生成的公司选择由裸文本框改为多选（复用该表格的行选择），非法 ID 输入即时红框校验。

**P1-7 轮询健壮性（AdminKnowledge.vue:32-36, 79-99）**
`onMounted` 的 `refresh()` 完成后检查是否存在 running/pending 任务，有则立即 `startPolling`；`loadFailures` 改 `Promise.all` 并行，且仅对 running 任务每次重拉、终态任务只拉一次缓存结果。

**P2-8 统一两页视觉与组件（AdminKnowledge.vue 全文样式）**
卡片底色 `--bg-1` → `--bg-2`（或直接换用共享 `Card.vue`）；`.btn-primary/.btn-secondary/.btn-refresh/.btn-cancel` 全部替换为 `AppButton`（variant: primary/secondary/ghost/danger）；标题字号统一到 `--font-size-xl`、页面加 `max-width: 1100px` 居中对齐 P7AdminAudit；任务状态加中文映射（completed→已完成 等），复用共享 `Tag.vue` 替代 `.s--*` 自定义 pill；接口失败补 notice-bar 错误提示（对齐 P7AdminAudit:178）。

**P2-9 权限边界显式化（router/index.ts:15,26 + 两页）**
路由 meta 增加 `requiresAdmin: true`，全局守卫读用户角色，非管理员跳转 /app 并提示；AdminKnowledge 捕获 403 时展示与 P7AdminAudit 一致的错误条而非静默空白。

**P2-10 小项清理**
P7AdminAudit 换用共享 Tag.vue、删除 165 行空 watcher、空态 emoji 换为线性图标或文字插画；AdminKnowledge 失败记录加"展开全部（n）"、`result_summary` 改为键值对列表展示；文件改名 `P7AdminAudit.vue` → `AdminAudit.vue`（同步改路由 import）。
