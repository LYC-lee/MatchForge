# 核心寻源工作流（后半程：匹配与报价）UI 分析报告

审查范围：`web/src/components/procure/` 下 SuppliersMatch.vue、RfqEditor.vue、AlternativesList.vue、GradeCard.vue、ParamDiffTable.vue、SourceBadge.vue。对照文件：`web/src/styles/tokens.css`、`web/src/components/ui/Tag.vue`。

## 1. 现状概述

该段工作流由「供应商匹配 → 替代料推荐 → RFQ 编辑」三类视图组成。SuppliersMatch 以卡片列表呈现供应商，含搜索/地区/资质筛选、三键排序、选中对比表与底部 sticky 操作栏；匹配度用「进度条 + 百分比 + 文字等级」三段式表达。AlternativesList 将替代料分为「推荐区」与折叠的「低置信风险区」，卡片内嵌置信度/核验状态统计与可展开的 ParamDiffTable 参数对比表；SourceBadge 以绿/黄/红三色徽章传达图谱核验、LLM 推测、查询失败三种来源。RfqEditor 采用「左侧结构化字段面板 + 右侧文本编辑器」双栏布局，字段与文本之间存在自动同步逻辑。整体遵循深色令牌体系（--bg-*、--accent、--success/warning/danger），Scoped CSS 规范较好，但组件间阈值硬编码重复、编辑同步存在数据丢失风险，数据可视化表达偏弱。

## 2. 问题清单

### 🔴 严重（影响可用性/明显缺陷/体验断裂）

1. **RFQ 字段与正文双向同步冲突，手改正文会被静默覆盖**
   任何结构化字段变更都会触发 `buildRfqFromFields()` 整体重建模板并 `emit('update')` [RfqEditor.vue:150-157 `watch(fieldValues, ...)`]，而用户在右侧 textarea 的手改内容通过 `onTextInput` 直接上抛 [RfqEditor.vue:198-202]。一旦用户先改了正文、再改任一字段，正文手改部分被模板重建全部抹掉，且无任何确认或提示。`syncFromFields` 用 100ms setTimeout 防抖 [RfqEditor.vue:160-170] 属于脆弱的竞态补丁，流式推送期间仍可能误覆盖。

2. **RFQ 模板硬编码「多层陶瓷贴片电容 (MLCC)」，品名字段被收集却未进入询价单**
   `buildRfqFromFields()` 中「一、品名」固定写死 `多层陶瓷贴片电容 (MLCC)` [RfqEditor.vue:121-122]，而字段表定义了 `part_name` 必填项 [RfqEditor.vue:32 `{ key: 'part_name', ... }`] 却从未在模板中引用（全文无 `f('part_name')`）。对非 MLCC 品类（电阻、电感、IC 等），生成的询价单品名恒为错误值，且用户在左侧面板填写的品名不生效——这是会产生错误商务文档的功能性缺陷。

3. **替代料「推荐→纳入询价」链路断裂，用户无法选择哪些替代料进入 RFQ**
   AlternativesList 纯只读，无「采用/加入询价单」任何操作入口 [AlternativesList.vue:74-121]；而 RfqEditor 自动取「非 L5 的前 3 个」写入询价单 [RfqEditor.vue:100-107 `.filter(...).slice(0, 3)`]。推荐列表若有 5 个 L1/L2 候选，用户无法决定取舍，也无法剔除不认可项——替代料推荐的决策支持止步于「看」，不能「选」，后半程效率断点。

### 🟡 中等（不一致、效率低、可感知粗糙）

4. **必填校验口径不一致：6 个必填字段只检查 2 个**
   字段表将品名/封装/容值/额定电压/月用量/期望交期标记 `required: true` [RfqEditor.vue:31-41]，输入框也有 `is-missing` 红框态 [RfqEditor.vue:261]；但顶部警告 `missingFields` 仅检查月用量、期望交期、目标供应商三项 [RfqEditor.vue:177-183]。用户可在品名/封装/容值/电压全空的情况下生成询价单而无任何警告，正文中直接出现 `__(待补充)__` 占位符 [RfqEditor.vue:98]，并可一键「复制/导出」外发。

5. **匹配度阈值在组件间重复硬编码且口径不一**
   SuppliersMatch 用 `scoreClass` 定义 0.8/0.65 两档阈值 [SuppliersMatch.vue:100-104]，RfqEditor 的目标供应商摘要又以内联三元重新写了一遍 `>= 0.8 ? 'high' : >= 0.65 ? 'mid' : 'low'` [RfqEditor.vue:289]。阈值若调整需多处同步修改，已出现漂移风险。

6. **置信度阈值自相矛盾：0.5 与 0.6 两套标准**
   「低置信折叠入风险区」判定为 `confidence < 0.5` [AlternativesList.vue:22-24]，而卡片上「置信度低」标黄的判定是 `confidence < 0.6` [AlternativesList.vue:94 ` :class="{ low: a.confidence < 0.6 }"`]。0.55 置信度的条目留在推荐区却被标黄警告，规则对不上，损害信任。

7. **对比表 MOQ 空值处理与卡片不一致**
   卡片中 MOQ 为 0 时显示「供应商自报」[SuppliersMatch.vue:315 `s.moq ? ... : '供应商自报'`]，对比表却直接 `{{ s.moq.toLocaleString() }} pcs` 显示「0 pcs」[SuppliersMatch.vue:226]。同一数据在同一页面两种解读，且「0 pcs」在采购语义中等同「不起订」，误导性强。

8. **对比表格无冻结首列且顺序与列表脱节**
   对比表 `white-space: nowrap` + 横向滚动 [SuppliersMatch.vue:506-520]，选中 4 家以上时「维度」列随滚动消失，无法对照行含义；且列顺序取原始 `suppliers` 数组顺序 [SuppliersMatch.vue:191 `suppliers.filter(...)`]，与列表区当前排序结果不一致。另：对比按钮在 0 选中时仍可点亮 active 态，但对比视图因 `compareIds.size > 0` 判断直接消失 [SuppliersMatch.vue:182]，用户点击后无反馈。

9. **风险区替代料卡片信息结构缩水，无参数对比入口**
   trusted 卡片支持「查看参数对比」展开 ParamDiffTable [AlternativesList.vue:115-120]，risky 卡片即使带 `diffs` 数据也完全不渲染对比表 [AlternativesList.vue:134-157]，同时缺少 key_params 参数 chips 与置信度/核验统计行——恰恰是最需要细看参数差异的高风险条目，决策信息反而最少。

10. **全选语义与筛选状态矛盾**
    「全选」勾选框的选中态基于 `filteredSuppliers`（筛选后集合）[SuppliersMatch.vue:85-88]，但 `selectAll` 事件上抛后由父组件决定集合，从命名与计数 `({{ selectedIds.size }}/{{ suppliers.length }})` [SuppliersMatch.vue:259] 看作用于全集。筛选状态下点「全选」，用户预期与实际选中范围不一致。

11. **来源徽章对未知来源原样透出内部枚举字符串**
    `kind === 'unknown'` 时 label 直接返回原始 `source` 字符串 [SourceBadge.vue:49-50 `default: return s`]，类似 `rule_fallback:xxx`、`Neo4j:yyy+RAG` 的内部 snake_case 标识会直接暴露给用户，损害专业感与信任传达。同时主徽章无任何 tooltip/图标解释，「图谱核验·传递」「LLM 推测·知识库」等术语对采购用户不可理解，且绿/黄/红纯色彩区分对色弱用户不可达。

12. **「未核验」状态表达歧义**
    SourceBadge 仅在 `verified === false` 时显示「未核验」徽章 [SourceBadge.vue:54, 60]，而 `verified` 字段缺失（undefined）时不显示任何标识——「未核验」与「状态未知」两种信任等级被混为一谈。fallback 态还存在徽章 label「查询失败·须人工核验」[SourceBadge.vue:47-48] 与尾随小字「未经数据库核验,须人工确认」[SourceBadge.vue:61] 的重复警告。

13. **参数对比表状态区分度过低**
    行底色透明度仅 3%–5% [ParamDiffTable.vue:54-56 `rgba(..., 0.03/0.04/0.05)`]，在 --bg-2/#151823 深底上几乎不可见，状态识别完全依赖小小的 Tag；risk 行仅字段名与 mono 值变红 [ParamDiffTable.vue:57-58]。差异/风险行是工程师评估的核心关注点，视觉权重却最弱。说明列对 diff/risk 空 note 显示「—」[ParamDiffTable.vue:28]，无引导补全。

14. **GradeCard 信息三重冗余且分数无标尺**
    字母徽章「A」、分数「90 分」、Tag「A 级线索」三者表达同一结论 [GradeCard.vue:16-24]；分数无满分基准（90/100？）也无任何进度/刻度可视化，卡片头部「线索分级」与 Tag 文案再次重复 [GradeCard.vue:13]。数据可视化质量停留在纯文本堆叠。

15. **供应商卡片「库存/交期/价格确认」行可扫描性差**
    三项状态以「✓ 已确认 / ✗ 未确认库存 | ✗ 未确认交期 | ✗ 未确认价格」长文本平铺 [SuppliersMatch.vue:327-341]，未确认用 text-tertiary 灰色 [SuppliersMatch.vue:681]，与绿色已确认权重接近，扫读时需逐字解析「未确认」前缀，无法一眼定位缺口项。匹配度进度条仅 80px 宽 [SuppliersMatch.vue:599]，在卡片头部视觉权重偏低。

16. **工具栏原生 select 在深色主题下观感割裂**
    地区/资质筛选用原生 `<select>`，仅设背景色未重置 `appearance` [SuppliersMatch.vue:445-453]，Windows 深色模式下拉箭头与展开面板保持系统亮色样式，与整体深色 UI 断裂。搜索框无清空按钮，筛选组合后无一键重置。

17. **杂项**
    - RFQ 日期用 `toISOString().slice(0,10)`（UTC），中国时区凌晨生成的询价单日期可能差一天 [RfqEditor.vue:119]。
    - 模板中三次重复调用 `alternatives.filter(...)` [RfqEditor.vue:270, 272, 277]，应为 computed。
    - 左侧栏 `max-height: calc(100vh - 200px)` 魔数 [RfqEditor.vue:401]。
    - 「AI 重新生成」「从文本回填字段」均为无确认的覆盖性操作 [RfqEditor.vue:297-304]。
    - `rag_insights` 用 `(s as any)` 取值 [SuppliersMatch.vue:320]，类型外数据无空态保护。
    - AlternativesList 以 `a.part_name` 作 key [AlternativesList.vue:74]，空值或重名时 key 冲突。
    - 供应商空状态「系统将继续扩充供应商库」无任何引导动作（调整规格/重试/联系运营）[SuppliersMatch.vue:242-246]。

### 🔵 建议（锦上添花）

18. 匹配度/置信度等阈值应抽取为共享常量（如 `web/src/constants/thresholds.ts` 或 types/procure 内），配合统一的颜色映射函数，替代散落的三元表达式。
19. SourceBadge 为主徽章增加图标（✓/AI/⚠）与 title 解释文案，fallback 的重复小字合并为一条；`verified === undefined` 时显示「核验状态未知」中性徽章。
20. ParamDiffTable 增加行状态左侧 3px 色条 + 提高行底色透明度至 8%–10%，说明列空值引导「待工程师补充」；考虑首列参数名 sticky。
21. GradeCard 用「字母大徽章 + 环形/条形分数刻度」合并三重冗余表达，reasons 支持正/负向图标区分加分项与扣分项。
22. RFQ 编辑器增加正文字数/字符统计与「正文已被手动修改」脏状态提示；月用量等数值字段加单位后缀与输入校验。
23. SuppliersMatch 确认状态行改为三个独立小徽章（库存/交期/价格各一），未确认项用 warning 色而非灰色，提升缺口可见性。
24. 对比模式限定最多 4 家并给出超限提示；首列冻结；空选择点击「对比选中」时 toast 提示「请先勾选供应商」。
25. 供应商空状态增加「调整规格重新匹配」次按钮；免责声明 notice 与 RFQ 底部 note 文案抽为共享常量，避免三处文案漂移。

## 3. 优化方案

按优先级排序：

**P0-1 修复 RFQ 双向同步冲突（问题 1）**
做什么：确立「字段 ↔ 文本」的单一数据源与显式合并策略。为什么：当前任一字段编辑都会静默抹掉用户手改正文，属于数据丢失级缺陷。改法：RfqEditor.vue 中——① 将模式显式化为「结构化模式 / 自由文本模式」二选一，正文被手改后打 `textDirty` 标记，字段变更时若 `textDirty` 则弹确认「用字段重建正文将覆盖手动修改」；② 或改为字段仅驱动正文中对应行做行级替换（按 `品名：` 等锚点局部替换），不做全量重建；③ 移除 `syncFromFields` 的 setTimeout 竞态补丁，改用「emit 来源标记」区分内部/外部更新。涉及 RfqEditor.vue 的 watch 逻辑（:150-170）与 onTextInput（:198-202）。

**P0-2 修复 RFQ 模板硬编码 MLCC、接入 part_name（问题 2）**
做什么：模板「一、品名」改为 `f('part_name')`，删除硬编码行。为什么：非 MLCC 品类会生成品名错误的正式询价单。改法：RfqEditor.vue:121-122，将固定文案替换为 `- 品名: ${f('part_name')}` 并入规格段或保留独立段；同时核对 spec 初始化 watch（:55-69）中 part_name 的 specKey 映射是否覆盖「品名/型号」双键。

**P0-3 打通替代料「选择 → 纳入 RFQ」链路（问题 3、9）**
做什么：AlternativesList 增加「纳入询价单」勾选/按钮并上抛事件；RfqEditor 以用户选择替代 `slice(0, 3)` 硬编码；risky 卡片补齐参数对比入口。为什么：替代料推荐当前止步于只读展示，用户无法影响写入询价单的候选集，高风险项反而看不到参数差异。改法：① Alternative 类型或父组件状态增加 `selectedForRfq: Set<string>`，AlternativesList 卡片头部加 checkbox/「纳入」按钮（trusted 区默认勾选前 3，可改）；② RfqEditor.vue:100-107 改为按该集合生成替代料段；③ risky 卡片复用 trusted 的 `alt__toggle + ParamDiffTable` 结构（:115-120 与 :134-157）。涉及 AlternativesList.vue、RfqEditor.vue 及父级 procure 视图状态。

**P1-4 统一必填校验与占位符外发拦截（问题 4）**
做什么：`missingFields` 改为遍历 `fields` 中所有 `required: true` 项自动生成；正文含 `__(待补充)__` 时禁用「复制/导出/标记已发送」或弹二次确认。为什么：校验口径与 UI 必填标记不一致，用户会外发含占位符的询价单。改法：RfqEditor.vue:177-183 用 `fields.filter(f => f.required && !fieldValues.value[f.key])` 生成缺失列表；isFallback 已有占位符检测（:185-187），将其接入 :317-331 按钮 disabled/confirm 逻辑。

**P1-5 抽取共享阈值与颜色映射（问题 5、6）**
做什么：新建 `web/src/constants/procure.ts`（或并入 types/procure），导出 `MATCH_SCORE_HIGH = 0.8`、`MATCH_SCORE_MID = 0.65`、`CONFIDENCE_LOW = 0.6` 及 `scoreClass()`/`confidenceClass()` 函数。为什么：0.8/0.65 已两处重复、置信度 0.5/0.6 已互相矛盾，继续漂移会直接损害用户信任。改法：SuppliersMatch.vue:100-104、RfqEditor.vue:289、AlternativesList.vue:22-24 与 :94 全部改为引用常量与共享函数，并统一低置信折叠与标黄为同一阈值。

**P1-6 修复对比表一致性与可用性（问题 7、8、10）**
做什么：① MOQ 空值统一走同一格式化函数（0 →「供应商自报」）；② 对比表首列 `position: sticky; left: 0`，列顺序改用 `filteredSuppliers` 顺序，最多 4 家超限提示；③ 0 选中时禁用「对比选中」按钮或点击给 toast；④ 明确全选作用域为「当前筛选结果」并在计数文案体现。改法：SuppliersMatch.vue:226 与 :315 提取 `formatMoq()`；:186-238 表格 sticky 首列 + 数据源改 filteredSuppliers；:171-177 按钮 disabled 绑定 `!selectedIds.size`；:91-97 selectAll 语义与父组件对齐。

**P2-7 强化来源徽章信任传达（问题 11、12）**
做什么：unknown 来源显示中性文案「来源待确认」而非原始枚举串；主徽章加图标与 title 解释；`verified === undefined` 显示「核验状态未知」；合并 fallback 重复警告。为什么：内部标识外露与状态歧义直接侵蚀 B 端用户对数据可信度的判断。改法：SourceBadge.vue:49-50 default 分支改固定文案；:57-63 模板增加图标 span 与 title 属性；:54 判定改 `props.verified !== true` 分「未核验/未知」两态；删除 :61 重复小字或在父组件统一收口。

**P2-8 提升数据可视化权重（问题 13、14、15）**
做什么：ParamDiffTable 行底色透明度提至 8%–10% 并加左侧色条；GradeCard 合并三重表达并加分数刻度条；供应商确认状态改三枚独立徽章、未确认项用 warning 色；匹配度进度条加宽至 120px。为什么：这些表格/评分卡是工程师与采购的决策依据，当前风险行、缺口状态视觉权重过低，扫读效率差。改法：ParamDiffTable.vue:54-58、GradeCard.vue:16-24 与样式、SuppliersMatch.vue:327-341 与 :599、tokens.css 无需新增令牌（复用现有 --success/--warning/--danger）。

**P3-9 体验打磨（问题 16、17 及建议项）**
原生 select 重置 appearance 并自绘箭头；RFQ 覆盖性操作加确认；UTC 日期改本地时区格式化；模板内重复 filter 提取 computed；空状态加引导动作；免责声明文案抽常量收口。
