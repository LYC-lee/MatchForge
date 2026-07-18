# 核心寻源工作流（前半程：发起与确认）UI 分析报告

> 审查范围：`web/src/views/ProcureView.vue`、`web/src/components/procure/QueryInput.vue`、`SpecConfirm.vue`、`AgentTimeline.vue`、`SessionHistoryPanel.vue`
> 对照阅读：`web/src/styles/tokens.css`、`web/src/stores/procure.ts`、`web/src/types/procure.ts`、`web/src/components/layout/StepNav.vue`、`web/src/composables/useHistory.ts`

## 1. 现状概述

寻源工作流页 `/procure/:id` 采用「吸顶条 + 双栏」结构：顶栏左侧为「← 新寻源」按钮与需求原文，右侧为 StepNav 六阶段步骤条；主体左栏为纵向堆叠的卡片流（寻源进度 AgentTimeline → 规格确认 SpecConfirm → 替代料 → 供应商 → RFQ → 线索分级），右栏为 300px 吸顶侧栏（Thread 标识、结果摘要指标、扩展预留卡）。视觉沿用深色令牌体系（--bg-* 层级、靛蓝 --accent、风险色 success/warning/danger）。交互上，发起页 QueryInput 为「textarea + ⌘/Ctrl+Enter + 示例 Chip」；规格确认为门控表单（缺失/低置信标黄 + 置信度列 + 状态徽章）；AgentTimeline 为轨道式时间线，含 200ms 实时计时、spinner、进度摘要条；SessionHistoryPanel 为「新建对话 + 相对时间会话列表」的侧滑面板，hover 显示删除钮。整体状态覆盖到「加载会话中 / 会话不存在 / 需求模糊空态 / 完成态」，但传输层错误与部分中间态存在盲区（详见下文）。

## 2. 问题清单

### 🔴 严重（影响可用性/明显缺陷/体验断裂）

**S1. 传输层错误（断流/网络异常）在寻源页完全无反馈，运行中的 Agent 永远「正在执行中…」**
store 定义并暴露了传输层错误与非致命警告两个状态：
- `streamError`（`web/src/stores/procure.ts:79`，赋值于 :270、:351、:438、:488）
- `streamNotice`（`web/src/stores/procure.ts:81`，赋值于 :275、:361）

但 `ProcureView.vue` 的 `storeToRefs` 解构（`ProcureView.vue:21-39`）**根本没有引入这两个状态**，模板中也没有任何渲染出口。后果链：SSE 断流时 `onError` 不带 agent 名（`procure.ts:270`），只有 `errors.value.push(message)`；若此时已有 `parsedSpec`，`isVague`（`procure.ts:121-123`）为 false，「无法完成寻源」卡不出现；时间线上 running 状态的 Agent 不会被置为 error，spinner 常转（`AgentTimeline.vue:138`）、「正在执行中…」常显（`AgentTimeline.vue:159-162`）、计时器持续上涨——用户在断流后看到的是一个**永远忙碌且无任何报错的界面**。同理，`streamNotice`（部分 SSE 帧解析失败）也被静默吞掉。

**S2. 规格确认门控：缺失字段可零拦截直接确认，与 banner 文案自相矛盾**
`SpecConfirm.vue:47-53` 的警告条明确写着「请核对补充后再继续」，但确认按钮（`SpecConfirm.vue:99-102`）无条件可用，`confirm()`（`SpecConfirm.vue:40-42`）直接 emit 当前编辑副本——用户可以在 N 个字段仍为空/缺失的情况下一键进入替代料匹配。门控（gating）本是前半程唯一的人工质量闸口，此设计使「缺失与低置信字段会影响替代料匹配准确性」的警告沦为纯文案。同时整个 gating 状态没有「返回修改需求」的出口：`ProcureView.vue` 中 gating 时顶部只有「← 新寻源」（`ProcureView.vue:129`），点击即 `store.reset()` 丢弃整轮解析结果（`ProcureView.vue:119-122`）。

**S3. 历史会话删除：单次点击即不可逆删除，无任何确认与失败提示**
`SessionHistoryPanel.vue:103-107`：hover 出现的 × 按钮点击后直接 `doRemove`，无 confirm 弹层、无二次确认、无撤销。底层 `useHistory.remove`（`web/src/composables/useHistory.ts:151-158`）会同步删除 API 与 localStorage 数据，且 `catch { /* ignore API error */ }`——删除失败时用户同样得不到任何反馈，列表项却已乐观移除（`SessionHistoryPanel.vue:34`）。寻源会话包含 RFQ 成果与多轮上下文，误删代价高，一键即删对 B 端工具过于激进。

### 🟡 中等（不一致、效率低、可感知粗糙）

**M1. AgentTimeline 的阶段产出计数是死 props，完成态没有任何结果反馈**
组件声明了 `alternativesCount` / `suppliersCount`（`AgentTimeline.vue:7-8`），ProcureView 也如实传入（`ProcureView.vue:175-176`），但组件脚本与模板**从未使用**这两个 props。各阶段完成后只显示静态描述文案（`AgentTimeline.vue:23-31` 的 DESC），用户无法从时间线获知「解析出 8 个字段 / 找到 3 个替代料 / 匹配到 12 家供应商」这类关键产出信息——信息设计停留在「状态可见」，没做到「结果可见」。

**M2. QueryInput 大面积硬编码色值，脱离设计令牌体系**
`QueryInput.vue` 中 6 处颜色绕过 tokens.css：
- `#151924`（:65，vs 令牌 `--bg-2: #151823`，`tokens.css:5`）
- `#343a4d`（:66，vs `--border-default: #384052`，`tokens.css:11`）
- `#f4f7ff`（:82，vs `--text-primary: #e7e9ee`，`tokens.css:15`）
- `#7f8799`（:85）、`#8d95aa`（:93）、`#9aa3b7`（:101，vs `--text-tertiary: #a3adbf`，`tokens.css:17`）

同一界面出现两套「看似相同实则不同」的深色，是肉眼可辨的色偏来源，也令后续主题调整漏改。

**M3. QueryInput 提交无 loading 态、无防重复提交**
提交按钮仅在内容为空时禁用（`QueryInput.vue:41`），`submit()`（:21-25）emit 后组件不进入任何 busy 状态。父级跳转/建流存在网络延迟窗口，用户连点或连按 ⌘+Enter 会重复触发寻源请求。

**M4. 历史面板把「加载失败」渲染成「暂无对话记录」空态**
`useHistory.load()` 在 API 异常且本地无数据时设置 `error.value = '暂无寻源记录'`（`useHistory.ts:105-111`），但 `SessionHistoryPanel.vue:15` 只解构了 `{ loading, load, remove }`，从未接收/渲染 `error`。于是后端故障被呈现为正常的空状态（`SessionHistoryPanel.vue:84-88`），用户无法区分「真的没有记录」与「服务不可用」。

**M5. 前半程全局进度文案在 ProcureView 无渲染出口**
store 在 spec 阶段维护了有信息量的进度串：「正在解析需求…」「正在标准化规格…」（`procure.ts:219, 256, 259`），但 `ProcureView.vue` 只把 `streamProgress` 传给 SuppliersMatch（:220），parse/normalize 阶段该字符串没有任何展示位置。此阶段主体只有时间线卡片，规格卡区域连 skeleton/占位都没有——页面在最关键的等待期显得「空」。

**M6. 历史面板删除按钮 hover-only + 会话项为不可聚焦 div**
- 删除钮 `opacity: 0`，仅 `:hover` 时显现（`SessionHistoryPanel.vue:247, 251-253`）：触屏设备上不可达，新用户也不易发现。
- 会话项是 `<div @click>`（`SessionHistoryPanel.vue:92-98`），非 button/无 tabindex/无 focus 样式，键盘与读屏用户无法操作。

**M7. 历史列表未利用 phase/status 字段，无法区分会话结局**
`SessionSummary` 类型含 `phase` 与 `status`（`web/src/types/procure.ts:170-171`），但列表项只渲染标题 + 相对时间（`SessionHistoryPanel.vue:99-102`）。已完成寻源、中途断流、仅聊了天的会话在列表里长得一模一样。

**M8. 侧栏「扩展预留」卡片把内部路线图文案暴露给终端用户**
`ProcureView.vue:304-309`：「运营审核、供应商入驻、报价对比和真实库存确认可在这里继续扩展。」——这是写给开发/产品看的占位文字，出现在客户可用的界面上，显著拉低 B 端产品的完成度观感。

**M9. 「← 新寻源」按钮语义混乱且中途点击无确认**
`ProcureView.vue:129`：返回箭头 + 「新寻源」文案混淆了「返回」与「新建」两种心智；点击即 `store.reset()` + 跳转（:119-122），寻源进行中（流式中、已选供应商、已编辑 RFQ）不弹任何确认即全部丢弃。

**M10. AgentTimeline 错误色语义不一致**
进度条的错误态用 `var(--warning)` 黄（`AgentTimeline.vue:200`），而错误徽章、错误消息用 `var(--danger)` 红（:308, :337-344）。同一条时间线上「错误」呈现两种颜色，摘要条在出错时反而不如不出错（success 绿）醒目。

**M11. AgentTimeline 使用 emoji 作阶段图标 + chat 映射为死代码**
- 🔍📋🔄🏭📝⭐（`AgentTimeline.vue:33-41`）在 Windows/macOS/不同字体下渲染差异大，与全站自研线性图标风格（StepNav 的 ✓/!/pulse）不一致。
- LABELS/DESC/ICONS 中的 `chat` 项（:20, :30, :40）永远不会出现——`AGENT_ORDER` 只有 6 个寻源 Agent（`procure.ts:46`），属死代码。

### 🔵 建议（锦上添花）

**L1. AgentTimeline 计时器粒度过细**：live 时每 200ms 重算整棵 `items` computed 并重渲染（`AgentTimeline.vue:44-51`），只为刷新 `formatDuration` 的 0.1s 文本（:59-62）；且无 `aria-live`，读屏无法感知阶段推进。建议 1s 节流 + 仅存在 running agent 时启动 + `aria-live="polite"`。

**L2. SpecConfirm 键盘流缺失**：裸 `<input>` 无 `<form>` 包裹（`SpecConfirm.vue:69-75`），Enter 不能提交确认；无字段级「恢复原始解析值」；`onInput` 里 `Math.max(confidence, 0.8)` 的 0.8 是魔数（:37）；置信度列对无 confidence 的字段渲染空单元格而非 `—`（:78-90）；`?` 标记仅靠原生 title tooltip（:82-86），信息层级弱。

**L3. SpecConfirm 的编辑副本不同步外部更新**：`edited` 在 setup 时一次性深拷贝（`SpecConfirm.vue:15-17`），若 gating 期间后端 result 事件更新了 `normalizedSpec`，表单不会刷新（当前流程下概率低，但属隐患）。

**L4. ProcureView 细节毛边**：加载态复用跨组件类名 `.history__spinner`（`ProcureView.vue:143`，虽在本组件 scoped 重定义 :537-543，命名误导）；会话不存在态用内联样式 `padding-top: 60px`（:148）；线索分级 `grade-${leadGrade.grade}`（:258）对 A–D 之外的等级无样式兜底。

**L5. 历史面板能力缺口**：无搜索/筛选（localStorage 上限 100 条，`useHistory.ts:179-181`）；删除当前正在查看的会话后无任何后续处理；空态图标 💬 同为 emoji（`SessionHistoryPanel.vue:85`）。

**L6. QueryInput 体验细节**：textarea `resize: none` 且固定 3 行（:34, :83），长需求不可展开；点击示例 Chip 后不自动 focus 输入框；无字数提示。

## 3. 优化方案

**P1（对应 S1）打通传输层状态的渲染出口 —— 涉及 `ProcureView.vue`、`AgentTimeline.vue`**
- 在 `storeToRefs` 中补解构 `streamError`、`streamNotice`、`isStreaming`，在主体卡片流顶部渲染两条横幅：错误条（`--danger-soft` 底 + 错误文案 +「重试/返回」按钮，复用 `store.retryMatch` / `newProcure`）与通知条（`--notice-soft` 底，可关闭，调 `clearStreamNotice`）。
- AgentTimeline 增加「断流兜底」：当 `live` 且存在 running agent 但 store `isStreaming === false` 时，将该 agent 视觉降级为 error 样式并提示「连接中断」。理由：消灭「永远忙碌的假进行态」，这是前半程最伤信任的体验断裂。

**P2（对应 S2）强化规格确认门控 —— 涉及 `SpecConfirm.vue`、`ProcureView.vue`**
- 用 `<form @submit.prevent="confirm">` 包裹表格与按钮，Enter 即可提交；确认逻辑改为：`missingCount > 0` 时弹出确认层（「仍有 N 个缺失字段，缺失将影响匹配准确性，仍要继续？」）而非直接放行；
- 卡片 footer 增加左侧次级按钮「返回修改需求」（gating 时 emit 新事件，ProcureView 中路由回 `/chat` 并预填 `rawQuery`，避免用户只能「全部重来」）；
- 每行增加「↺ 恢复解析值」小按钮（保留 props.spec 原始副本）。理由：门控是人工质量闸口，必须「拦得住、回得去」。

**P3（对应 S3、M4、M6）历史面板安全性与状态完整性 —— 涉及 `SessionHistoryPanel.vue`、`useHistory.ts`**
- 删除改为两步态：点击 × 后该项内联变为「确认删除？✓/✕」，3 秒无操作自动还原；删除失败时恢复列表项并 toast 提示。
- 解构并渲染 `error`：加载失败时显示「记录加载失败，点击重试」而非空态文案。
- 删除按钮对触屏常显（媒体查询 `@media (hover: none)` 下 `opacity: 1`）；会话项改为 `<button type="button">` 或加 `tabindex="0"` + `:focus-visible` 样式。

**P4（对应 M1、M10、M11、L1）时间线信息设计升级 —— 涉及 `AgentTimeline.vue`**
- 把已传入的 `alternativesCount`/`suppliersCount` 用起来：对应阶段 done 时在 desc 行渲染产出徽标（如「产出 3 个替代料」）；为 parse/normalize 阶段扩展 `fields-count` prop（可从 `normalizedSpec` keys 派生，在 ProcureView 计算后传入）。
- 错误态进度条统一为 `var(--danger)`；emoji 图标替换为与 StepNav 一致的字符/线性符号（或抽公共 `AgentIcon`）；删除 `chat` 死映射；计时改为 1s 节流 + `aria-live="polite"`。

**P5（对应 M5、M8、M9）ProcureView 状态与文案收口 —— 涉及 `ProcureView.vue`**
- spec 阶段在规格卡位置渲染 skeleton 占位 + `streamProgress` 文案（复用 `--bg-2`/shimmer 即可）；
- 「扩展预留」卡下线或改为真实功能（如「导出 RFQ / 分享会话」入口）；
- 「← 新寻源」拆分为「← 返回列表」（`/history`）与「+ 新寻源」，且在 `phase` 非 idle/done 时点击弹确认。

**P6（对应 M2、M3、L6）QueryInput 令牌化与防重 —— 涉及 `QueryInput.vue`**
- 6 处硬编码色值全部替换为 `--bg-2`、`--border-default`、`--text-primary`、`--text-tertiary` 等令牌；
- 组件增加 `submitting` prop（或内部 500ms 防抖禁用），提交中按钮显示 spinner 文案「发起中…」；
- 示例 Chip 点击后 focus textarea。

**P7（对应 M7、L2–L5）长尾打磨**：历史列表项追加状态点（done 绿 / 中断黄，取自 `SessionSummary.status`）；SpecConfirm 置信度列空值统一渲染 `—`、0.8 魔数提为常量 `CONFIRMED_CONFIDENCE`、`edited` 加 `watch(() => props.spec, …, { deep: true })` 同步；`.history__spinner` 改名 `.procure__spinner`；线索分级加默认底色兜底。
