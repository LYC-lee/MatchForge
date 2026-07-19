# 对话体验 UI 分析报告

> 审查范围：`web/src/views/ChatView.vue`（对话寻源）、`CompanyChat.vue`（上下游协同问答）、`CompanyAssistant.vue`（企业内部 AI 助手）、`web/src/components/chat/`（ChatMessage / MarkdownContent / CitationList）、`web/src/composables/useProgressiveReveal.ts`、`web/src/api/sse.ts`。

## 1. 现状概述

项目存在三个对话页，呈"一主两辅"格局：`/chat`（ChatView）是旗舰页，采用共享组件 `ChatMessage.vue`（头像 + 气泡 + 时间戳 + 悬浮操作），真 SSE 流式（`api/sse.ts` 手解 `text/event-stream`），内嵌结构化卡片（规格确认/替代料/供应商/询价单/线索分级），并有 localStorage 持久化与历史侧边栏。两个企业页（CompanyChat / CompanyAssistant）未复用 ChatMessage，而是各自在视图内联实现了一套简化消息列表，共用 `MarkdownContent`（markdown-it + DOMPurify + highlight.js，流式 120ms 防抖、围栏补全）与 `CitationList`（[n] 角标 + 展开详情卡）；因 kb 问答无流式后端，二者用 `useProgressiveReveal` 在答案到达后按 25 字/40ms 伪流式逐帧展示。整体深色基调统一，但三页在气泡语义、输入区、消息操作、错误呈现上分歧明显。

## 2. 问题清单

### 🔴 严重（影响可用性/明显缺陷/体验断裂）

**R1. 中文输入法（IME）Enter 确认候选词会直接发送消息 —— 三个页面全部命中**
- 证据：`ChatView.vue:212-217` `handleKeydown` 只判断 `e.key === 'Enter' && !e.shiftKey`，未判断 `e.isComposing`；`CompanyChat.vue:223`、`CompanyAssistant.vue:158` 使用 `@keydown.enter="send()"` 同样无合成态判断。
- 全仓 grep `isComposing|compositionstart` 零匹配。中文用户在拼音候选上按 Enter 选词时，keydown 会先触发 send，把未上屏的拼音/半句直接发出去。对中文 B 端工具这是主路径级缺陷。

**R2. ChatView 输入框承诺多行却永远单行可视**
- 证据：`ChatView.vue:820-827` textarea `rows="1"`，样式 `max-height: 120px; resize: none`（`ChatView.vue:988-989`），全文件无任何自动增高逻辑（无 `style.height` / `scrollHeight` 赋值）；而提示行写着 "Enter 发送 · Shift+Enter 换行"（`ChatView.vue:834`）。
- Shift+Enter 换行后文本在 1 行高的框内滚动，用户无法回看已输入内容。`max-height: 120px` 说明设计意图是自适应增高，但实现缺失。

**R3. 企业/伙伴切换时会话串扰，答案与引用可能挂错企业**
- 证据 a（CompanyChat 竞态）：`CompanyChat.vue:61-65` `selectPartner` 无 `busy` 守卫，发送途中可切换伙伴；`send()` 在 `await partnerChat(...)`（:76）之后才读取 `selectedPartner.value?.company_id`（:85）映射引用，随后把消息 push 进（已被清空的）新伙伴会话 —— A 伙伴的答案带着 B 伙伴归属进入 B 的对话。
- 证据 b（CompanyAssistant 无清理）：`CompanyAssistant.vue:11` 取出 `currentEnterpriseId` 后**没有任何 watch**；对照 `CompanyChat.vue:45-50` 切换企业会 `messages.value = []`。CompanyAssistant 切换企业后上一企业的问答记录原样保留，边界声明（"只回答当前企业内部范围"，:111）在 UI 层被打破。

### 🟡 中等（不一致、效率低、可感知粗糙）

**M1. 两套消息体系并存，气泡语义相反**
- ChatView 用共享 `ChatMessage.vue`：头像 32px、字母 "U"/"M"（`ChatMessage.vue:157-161`）、**AI 头像用渐变**（:279-282）、用户头像灰底（:283-287）、字号 `--font-size-md` 15px（:334）、圆角 `--radius-lg` 不对称（:307/:312）、气泡限宽 640px（:296）。
- 企业页各自内联：头像 30px、文字 "我"/"AI"（`CompanyChat.vue:193`）、**渐变给了"我"**（`CompanyChat.vue:333`）、AI 灰底（:328）、字号 `--font-size-sm` 13px（:341）、圆角硬编码 8px（:338）、气泡不限宽（`.msg__body{flex:1}` :318）。CompanyAssistant 同样 13px/8px（:241/:237）但限宽 640px（:233）。
- 同一产品里"渐变头像 = AI"与"渐变头像 = 我"两种相反语义并存，用户跨页认知断裂。

**M2. 用户消息对齐方式三页不一致**
- ChatView 右对齐（`ChatMessage.vue:255-257` row-reverse）；CompanyAssistant 右对齐（`CompanyAssistant.vue:213-214`）；**CompanyChat 没有 `.msg--user` 方向规则**（:317 起仅有通用 `.msg`），用户消息与 AI 一样靠左，仅靠头像颜色区分，对话感最弱。

**M3. 输入区能力/样式三页分裂**
- ChatView：多行 textarea + 快捷键提示 + 主色实心按钮 `background: var(--accent)`（`ChatView.vue:997`）；企业页：单行 `<input>`（无法输入多行需求/条款， CompanyChat.vue:218 / CompanyAssistant.vue:158）+ 无快捷键提示 + 渐变按钮 `var(--gradient-accent)`（CompanyChat.vue:384 / CompanyAssistant.vue:297）。同一产品发送按钮两套配色。

**M4. 企业页错误消息无视觉分级、无重试入口**
- 证据：`CompanyChat.vue:104` 错误仅 push 普通气泡 + 10px "未生成" 徽章（:201，样式 :350-362）；气泡本身无 danger 配色。对照 ChatView 错误气泡有 `--danger-soft` 底色 + 重试按钮（`ChatMessage.vue:321-325`、:228-239）。企业页接口失败（RAG/认证异常是常见态）后用户只能重打字。

**M5. 伪流式 reveal 增加阅读延迟，且真正的等待阶段无法取消**
- 证据：`useProgressiveReveal.ts:16-18` 25 字/40ms（≈625 字/秒），答案完整到达后还要再"打字"一遍，1500 字答案额外约 2.4s；停止键仅在 `revealing` 时出现（`CompanyChat.vue:225`、`CompanyAssistant.vue:159`），而真正耗时的 `sending` 网络等待阶段（`CompanyChat.vue:72-97`）没有任何取消手段（无 AbortController）。等待时不能停、能停时其实已不用等，停止键时机倒挂。

**M6. 流式期间滚动强制贴底 + smooth 叠加抖动，长对话无法回看**
- 证据：`ChatView.vue:38-44` 每个 token/进度都 `scrollTop = scrollHeight`（调用点 :59、:301、:313、:324），无"用户上滚则暂停跟随"判断，也无"回到底部"按钮；同时 `.chat__msgs` 设了 `scroll-behavior: smooth`（:901），高频程序化赋值与平滑动画叠加造成滚动滞后/回弹。生成中想翻上面的规格卡会被反复拽回底部。

**M7. 大量硬编码颜色/圆角绕过设计令牌**
- 证据：`CompanyChat.vue:246` `#10131b`、:271 `#171b26`、:250 `#aab3c4`、:255/:266 `#c7cfdd`、:275 `#aeb7c8`、:305 `#d2d8e4`、:310/:329 `#d8deea`、:379 `#9fa8ba`；圆角 8px/6px/4px 硬编码（:245/:338，令牌只有 4/6/10，无 8px）；面板边框用 `--border-strong`（:244）而 ChatView 同级容器用 `--border-default`（`ChatView.vue:962`）。CompanyAssistant.vue:177-178、:186-193、:237、:248-251 同病。这些色值与令牌近而不等，面板色调与主站有可见偏差。

**M8. 引用角标与正文论述无锚点映射，可信度链条断裂**
- 证据：`CitationList.vue:44` 角标只渲染 `[1][2][3]`，正文（MarkdownContent）中没有对应的行内 [n] 标记，用户无法知道哪句话由哪条引用支撑；`kb.ts:118` score 缺省补 0，展开详情即显示"相关度 0%"（`CitationList.vue:26-29`），像坏数据；:59 裸露 `chunk_uid`（内部主键对采购用户无意义）；详情卡无文档标题/章节/跳转，无法溯源验证。

**M9. 发送期间输入框 disabled 导致焦点丢失**
- 证据：`ChatView.vue:825`、CompanyChat.vue:222、CompanyAssistant.vue:158 均在处理中禁用输入框；禁用会使焦点元素 blur，回复完成后三页都没有 `focus()` 恢复逻辑，用户每轮都要鼠标点回输入框。高频对话工具中这是持续摩擦。

**M10. 企业页会话零持久化 + 切换即清**
- 证据：CompanyChat/CompanyAssistant 全文无 localStorage（grep 仅 ChatView/ProcureView 命中）；`CompanyChat.vue:61-65` 切换伙伴直接 `messages.value = []` 无确认、无暂存。刷新页面或误点伙伴即丢失整段问答，与 ChatView 的多轮持久化（`ChatView.vue:352-376`）体验落差大。

### 🔵 建议（锦上添花）

**S1. 代码块无复制按钮与语言标签**：`MarkdownContent.vue:212-234` 仅有样式，SQL/bash 答案需手动拖选。
**S2. 流式光标位置不佳**：`ChatMessage.vue:171-172` 光标 `<span>` 跟在块级 `.markdown-body` div 之后，渲染时落在正文下一行而非文本末尾（纯文本分支 :175 则是行内正确的）。
**S3. 表格单元格 `white-space: nowrap`（`MarkdownContent.vue:197`）长文本会把表格撑得很宽，全靠横向滚动。
**S4. 消息操作 hover 才显形（`ChatMessage.vue:386-392` opacity 0），触屏不可达，键盘 Tab 会聚焦到不可见按钮。
**S5. 空态行为不一致：ChatView 示例填入输入框可编辑（`ChatView.vue:701`），企业页点击直接发送（`CompanyChat.vue:189`、`CompanyAssistant.vue:127`）。
**S6. "RAG" 徽章是技术术语（`CompanyChat.vue:200`），B 端用户读不懂；"未生成" 表意也含糊，建议面向用户改写。
**S7. CompanyChat 移动端断点下 `.chat-page{height:auto}`（:413-415）后 `.chat-body` 失去有界高度，面板退化为整页滚动。
**S8. blink 光标、stop-icon、msg__cursor 样式在 ChatMessage.vue:346-352、CompanyChat.vue:393-412、CompanyAssistant.vue:304-323 重复三份，应随共享组件收敛。
**S9. `CitationList` 详情卡本身结构良好（doc 标签/相关度/摘录），可补文档标题、摘录关键词高亮与"查看知识库原文"入口，把可信度做成卖点。

## 3. 优化方案

**P0-1. 修复 IME 误发送（三页一次性根治）**
做什么：所有发送入口增加 `e.isComposing`（或 compositionstart/end 置位）判断，合成中 Enter 不发送。
为什么：中文用户主路径缺陷，影响每一次输入。
改法：新建共享组件 `components/chat/ChatInput.vue`（见 P1-2），在 keydown 内 `if (e.isComposing || e.keyCode === 229) return`；三页统一替换。涉及 `ChatView.vue:212-217`、`CompanyChat.vue:223`、`CompanyAssistant.vue:158`。

**P0-2. 修复企业/伙伴切换串扰**
做什么：① CompanyChat `selectPartner` 增加 `if (busy.value) return` 或切换时中止在途请求；② `send()` 开始时快照 `partnerId`/`enterpriseId`，响应与引用映射一律用快照值而非事后读 `selectedPartner`；③ CompanyAssistant 补 `watch(currentEnterpriseId)`，切换时 `stopRevealing()` 并清空 messages。
为什么：跨企业数据归属错误是 B 端信任红线。
改法：`CompanyChat.vue:61-109`、`CompanyAssistant.vue:11-30`。

**P0-3. ChatView 输入框自适应增高**
做什么：textarea 输入时按 `scrollHeight` 重设高度（上限 120px），发送后复位。
为什么：兑现已承诺的 Shift+Enter 换行，长需求描述可回看。
改法：并入 P1-2 的 ChatInput 组件；`ChatView.vue:820-827`、样式 :980-991 已有 max-height 预期，无需改设计。

**P1-1. 三页统一消息渲染：全面复用 ChatMessage.vue**
做什么：企业页删除内联消息模板，改用 ChatMessage；为其增加可选 props（`sourceBadge`、`compact`）承载企业页的 RAG/未生成徽章与 640px 限宽；统一头像语义（渐变=AI）、用户右对齐、字号 15px、时间戳显示。
为什么：消除 M1/M2/M4 的语义相反与错误无分级；后续只维护一套。
改法：`CompanyChat.vue:192-215`、`CompanyAssistant.vue:130-154` 替换为 `<ChatMessage>`；`ChatMessage.vue` 增 props 与 source 徽章 slot；错误消息沿用现有 `resultType:'error'` + 重试 emit，企业页补重发逻辑。

**P1-2. 三页统一输入区：新建 ChatInput.vue 共享组件**
做什么：封装 textarea（自动增高、IME 安全、Enter/Shift+Enter）、发送/停止双态按钮（统一主色实心样式）、快捷键提示行；sending 阶段支持 AbortController 取消请求，停止键在 sending 与 revealing 两阶段都可用。
为什么：消除 M3/M5/M9 + R1/R2 同源问题；取消能力覆盖真实等待阶段。
改法：新组件 `components/chat/ChatInput.vue`；`api/enterprise.ts` 的 chatAsk/partnerChat 增加 signal 参数；替换三页输入栏（`ChatView.vue:807-835`、CompanyChat.vue:217-227、CompanyAssistant.vue:157-161）；完成后 `focus()` 回输入框。

**P2-1. 滚动跟随策略 + 回到底部按钮**
做什么：记录用户是否贴底（阈值约 80px），仅贴底时 token 更新才跟随滚动；上滚后停止跟随并浮出"↓ 新消息"按钮，点击回底；`.chat__msgs` 去掉全局 `scroll-behavior: smooth`，仅回底按钮点击时用平滑滚动。
为什么：消除 M6 的拽回与抖动，长对话可边看边生成。
改法：`ChatView.vue:38-44`、:897-902；同样逻辑并入企业页 scrollBottom（CompanyChat.vue:130-133、CompanyAssistant.vue:88-91）。

**P2-2. 引用可信度升级**
做什么：① 后端/前端约定在答案正文插入行内 `[n]`，点击高亮定位到对应角标/详情；② score 缺失或为 0 时隐藏"相关度"而非显示 0%；③ `chunk_uid` 移入 title 或详情折叠区；④ 详情卡补文档标题（现有 docLabel 只有类型）与摘录截断（如 200 字 + 展开）。
为什么：M8——引用是 RAG 答案唯一的信任来源，当前角标与论述脱节。
改法：`CitationList.vue:26-59`、`api/kb.ts:114-122` 映射层补 title 字段；行内锚点需 kb 答案契约配合，可先做②③④前端独立项。

**P2-3. 设计令牌收敛**
做什么：企业页硬编码色值全部替换令牌（`#10131b`→`--bg-1`、`#171b26`→`--bg-3`、`#c7cfdd/#d8deea/#d2d8e4`→`--text-secondary`、`#aab3c4/#aeb7c8/#9fa8ba`→`--text-tertiary`）；8px 圆角→`--radius-lg` 或与 ChatMessage 对齐；面板边框统一 `--border-default`。
为什么：M7，近而不等的色值造成"说不出的粗糙感"。
改法：`CompanyChat.vue:233-419`、`CompanyAssistant.vue:166-327` 样式段整体过一遍。

**P3-1. 企业页会话持久化与切换保护**
做什么：会话按 `enterpriseId + partnerId + mode` 键存 sessionStorage/localStorage（仅文本与引用，轻量）；切换伙伴/企业时若有未保存内容给出确认或自动暂存可回切恢复。
为什么：M10，刷新/误点即丢在企业场景代价高。
改法：新增 `composables/useChatSession.ts`，CompanyChat/CompanyAssistant 接入。

**P3-2. 细节批次**
代码块加语言标签 + 复制按钮（`MarkdownContent.vue:212-234`，highlight 回调已知 lang）；流式光标改为行内尾随（`ChatMessage.vue:171-176`）；消息操作在 `:focus-within` 与触屏（`@media (hover: none)`）下常显（`ChatMessage.vue:386-392`）；空态点击行为统一为"填入输入框"（对齐 ChatView）；"RAG"→"知识库答案"、"未生成"→"未能生成答案"（CompanyChat.vue:200-201、CompanyAssistant.vue:138-139）。
