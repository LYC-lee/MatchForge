# AI 原生工具阵营 风格对标调研

> 标杆：Linear、Vercel、Cursor、Raycast
> 调研人：AI 原生工具研究员 ｜ 调研日期：2026-07-17
> 定位：只关注「风格层」——色彩策略、字体排版、密度与留白、动效、品牌表达、信任感，提炼可迁移到 MatchForge 智配（B2B AI 采购寻源平台）的模式。

**阵营一句话总结**：四家的共同信条是「**色彩配给制 + 字重克制 + 发丝边框代替投影 + 产品截图即品牌**」。它们把深色界面当作"精密仪器"而非"炫酷舞台"：99% 的界面是无彩色灰阶，唯一的品牌色像手术刀一样只落在主动作上；字重压死在 400–600 区间，从不用 700；层级靠 0.5–1px 发丝边框与内阴影，几乎不用外投影。这与当前 AI 生成界面泛滥的「纯黑底 + 霓虹渐变按钮 + 玻璃模糊卡片」模板形成鲜明对立——后者已被设计社区公开批评为廉价感来源（[DEV Community, 2026-04-10](https://dev.to/raxxostudios/dark-mode-design-that-doesnt-look-ai-2cn3)）。

---

## 各标杆风格画像

### Linear —— 午夜精密仪器（Dark, Midnight Precision）

**视觉语言要点**

- **色彩**：四层表面递进 + 单点高饱和强调。
  - 表面阶梯：画布 `#08090a`（Void）→ 卡片 `#0f1011`（Carbon）→ 抬升面板 `#161718`（Obsidian）→ 边框/幽灵按钮底 `#23252a`（Graphite）（[Refero Styles, 2026-07-03](https://styles.refero.design/style/90ce5883-bb24-4466-93f7-801cd617b0d1)）。
  - 文本灰阶：`#ffffff`（标题）/ `#d0d6e0`（正文）/ `#8a8f98`（次要）/ `#62666d`（弱化），正文从不使用彩色（同上）。
  - 强调色配给：营销站当前用酸橙绿 `#e4f222`，**每个视图只允许出现一个**彩色主按钮，其余按钮全部中性；产品 App 内的品牌交互色为靛蓝 `#5e6ad2`（[ColorPickerCode, 2024-06](https://colorpickercode.com/color-palette/ui-ux-palettes/linear-dark/)）。辅助色（绿 `#27a644`、红 `#eb5757`、紫 `#6366f1`）只用于标签/状态小色块，"as a supporting accent, not as a status color"。
- **字体**：Inter Variable，字重只用 300/400/510/590，**明确禁止 700+**（"Linear's type scale caps at weight 590"）；48px 以上标题字距 -0.022em；OpenType `cv01/ss03/zero` 特性定义品牌字形气质。等宽字体 Berkeley Mono（可替代 JetBrains Mono）专用于 issue ID、快捷键、技术元数据，12–14px（[Refero Styles, 2026-07-03](https://styles.refero.design/style/90ce5883-bb24-4466-93f7-801cd617b0d1)）。
- **密度**：compact。间距阶梯 8/12/24/96px；卡片圆角 12px、按钮/输入 6px、徽章 4px，**全部圆角词汇只有三种**。
- **层级手法**：**0.5–1px 发丝边框 + 内阴影取代外投影**。卡片边缘用 `inset 0 0 0 1px #23252a`，"Linear's elevation comes from borders and subtle inner shadows"；唯一使用真实投影的是酸绿 CTA 的内阴影堆叠。
- **品牌表达**：产品截图即全部视觉内容——无插画、无摄影、无装饰渐变；渐变只允许出现在 hero 截图下方的一层"大气底光"。官方改版博客自述目标是"reduce visual noise, maintain visual alignment, increase the hierarchy and **density** of navigation elements"（[Linear 官方博客, 2024-03-28](https://linear.app/blog/how-we-redesigned-the-linear-ui)）。
- **动效**：无夸张叙事；交互反馈以颜色过渡为主，保持"仪器感"的即时与安静。

**值得 MatchForge 借鉴的模式**

1. **"单点主色"纪律**：每个视图只保留一个彩色主按钮（MatchForge 的靛蓝 `#6366f1` 恰好也在 Linear 的辅助色板上，色系亲和），其余操作全部中性幽灵按钮。对采购工具的价值：报价确认、发送 RFQ 这类关键动作在数据密集的界面里必须一眼可辨——主色越稀有，动作越醒目。
2. **发丝边框 + 内阴影的层级体系**：与 MatchForge 现有 `#2b3140` 边框系完全同构，改造成本极低。把五档背景的层级职责改为"3 档表面 + 1 档边框"（画布/卡片/抬升 + 发丝边），比堆外投影更适合密集表格与面板嵌套。
3. **等宽字体承担"单号感"**：RFQ 编号、物料编码、供应商编码用 ui-monospace/JetBrains Mono 12–13px 渲染——这是"专业工具信任感"最便宜的来源，且中英文混排下无字体版权风险。

---

### Vercel —— 工程化极简（Achromatic Engineering）

**视觉语言要点**

- **色彩**：**彻底无彩色**。界面运行于 4 档灰阶 `#FAFAFA → #F2F2F2 → #EBEBEB → #171717`（浅色站），蓝色 `#0072F5` 是唯一交互色，只出现在链接、焦点环、跳转指示上；其余全部状态色（绿/橙/红/紫等 12 色）**只允许以约 10px 的指示圆点出现**，"never as backgrounds or large fills"（[design-bites Vercel DESIGN.md, 2026-07-17 访问](https://github.com/educlopez/design-bites/blob/main/design-mds/vercel.com/DESIGN.md)）。
- **字体**：自研 **Geist**（Sans + Mono，OFL 开源协议，2023 年发布，官方定位"为开发者与设计师设计、受瑞士设计运动启发"——[Vercel 官方, 2026-07-17 访问](https://vercel.com/font)）。**三字重规则：只用 400/500/600，全系统不存在 700**；"Emphasis is communicated through size and spacing, not weight"（design-bites，同上）。
- **字距签名**：标题激进负字距——48px 标题 -2.28px（约 -4.75%），32px -1.28px（约 -4%），16px 以下恢复正常（同上）。
- **层级手法**：**shadow-as-border**——用 `box-shadow: 0 0 0 1px rgba(0,0,0,0.08)` 完全取代 CSS border（不影响盒模型、可多层堆叠、过渡更顺滑）； elevation 是"边框层 + 深度层 + 背景环"三层复合阴影（同上）。
- **焦点系统（对 MatchForge 最关键）**：**双层焦点环** `--ds-focus-ring: 0 0 0 2px 背景色, 0 0 0 4px 焦点蓝`——内圈 2px 背景色制造间隙，保证焦点环在任何底色上（包括蓝色按钮自身）都可见（同上）。
- **动效**：唯一缓动 `cubic-bezier(.175, .885, .32, 1.1)`（带轻微过冲的 "swift"）；浮层 0.3s、popover 0.2s、入场 scale 0.96→1；**按钮/链接 hover 只变颜色，明确禁止 transform/opacity 动画**（"No scale, translate, or fade effects"）（同上）。
- **布局**：4px 间距基元，页面宽 1200/1400px；用留白代替分隔线（"Don't add divider lines between sections"）。

**值得 MatchForge 借鉴的模式**

1. **双层焦点环**——直接命中 MatchForge 已知短板"焦点可见性弱"。深色版实现：`0 0 0 2px var(--bg-canvas), 0 0 0 4px #6366f1`，内圈用画布色做切割，键盘导航在表格、按钮、输入框上全程可读。这是 B2B 工具的合规与效率双重要求（采购用户大量键盘操作）。
2. **状态色圆点化**：供应商状态、报价状态、审批状态统一为 8–10px 彩色圆点 + 中性文本，禁止大面积彩色填充徽章。数据密集界面里彩色填充会互相打架，圆点既保留扫描性又维持灰阶秩序。
3. **hover 只变色的动效纪律**：颜色过渡 150ms、浮层 200–300ms 带过冲缓动，按钮禁缩放/位移——工具型产品"快而稳"的体感正来自这种克制，也天然规避了动效眩晕问题。

---

### Cursor —— 温暖印刷感 × AI 工作流可视化（Warm Print × AI Timeline）

**视觉语言要点**

- **色彩**：独树一帜的**暖色系**——米白画布 `#f2f1ed`（非纯白）、暖近黑文本 `#26251e`（带黄棕底色，"evokes old paper, ink, and craft"）、品牌橙 `#f54e00`；连错误色都是暖绯红 `#cf2d56` 而非冷红。边框用 **oklab 色彩空间**的暖棕透明度（10%/20%/55%），保证跨背景感知一致（[Open Design, 2026-07-17 访问](https://open-design.ai/plugins/design-system-cursor/)）。注：Cursor 编辑器本体为深色 IDE 界面（深蓝黑底 `#0b0d0f` 系，[第三方移植记录, 2026-03-13](https://github.com/kevnord/Cursor-Dark-Midnight)），营销站曾用暖米白、2025 年后转向深色午夜 + 单点强调色，此处以可查证令牌为准。
- **字体**：**三声部排版**——CursorGothic 展示体（几乎只用 400 字重，72px 处字距 -2.16px，靠尺寸与字距而非字重做层级）+ jjannon 衬线正文（带 `cswh` 花笔特性，提供"文学温度"）+ Berkeley Mono 代码体。"Three fonts, three voices"（Open Design，同上）。
- **AI 工作流语义色（最值得注意）**：AI 操作时间线中，每类操作配一个**柔和蜡笔色**——思考 蜜桃 `#dfa88f`、搜索 鼠尾草绿 `#9fc9a2`、读取 雾蓝 `#9fbbe0`、编辑 薰衣草紫 `#c0a8dd`，步骤间用细连接线串联，构成"AI 正在为你工作"的核心视觉隐喻（同上）。
- **层级手法**：大模糊半径扩散投影（28px/70px blur、0.10–0.14 透明度）营造"大气托举"而非硬边浮起；oklab 边框环做边缘定义。
- **动效**：颜色过渡 150ms ease、阴影过渡 200ms ease；签名交互是 hover 时文本转向暖绯红 `#cf2d56`。
- **密度**：营销站宽松（section 间距 80/48/32px 三档响应式），编辑器本体高密度。

**值得 MatchForge 借鉴的模式**

1. **AI 工作流步骤语义色 + 连接线**——直接映射 MatchForge 的寻源工作流：规格确认/替代料推荐/供应商匹配/RFQ 报价各分配一个低饱和语义色（建议在现有靛蓝-紫家族内取 4 个 20–30% 明度差的色阶），步骤节点用"彩色小圆点/图标 + 中性标题 + 竖向连接线"。这让 AI 多步推理过程可见、可信，是"AI 原生感"的正确表达——比给整个面板加渐变高级得多。
2. **中性色的"色温"意识**：Cursor 证明中性色不必是冷灰蓝。MatchForge 现有灰阶偏冷蓝（`#2b3140` 系），可以考虑整体轻微暖移或至少统一色温，减少"AI 模板感"，更贴近中文 B2B 用户的"稳重可靠"预期。
3. **字重极简化**：展示体只用 400，层级全靠尺寸/字距/留白——再次印证"不用 700"是头部工具共识。

---

### Raycast —— 深色驾驶舱 + 珊瑚点睛（Dark Cockpit, Coral Neon）

**视觉语言要点**

- **色彩**：近纯黑画布 `#040506` → 卡片 `#07080a` → 凹陷/输入井 `#111214` → 徽章 `#1b1c1e`，外加品牌色晕染面 `#452324`（Ember）。**页面 98% 无彩色**，珊瑚红 `#ff6363` 只出现在 logo、hero 艺术、AI 徽章三处（[Refero Styles, 2026-07-03](https://styles.refero.design/style/3b6a17f0-3bdf-418c-a95e-0b89e5a8b2f8)）。
- **CTA 反常识**：**主按钮是中性的**——浅灰 `#e6e6e6` 底 + 深灰 `#454647` 字，全系统没有彩色 CTA，"letting the dark page do the contrasting"（同上）。
- **字体**：Inter 400/500/600；**56px 大标题用 400 字重 + 微正字距（+0.22px）**——"most brands shout with 700, Raycast whispers with regular weight and lets the size do the work"；11px 全大写 eyebrow 标签（+0.073em）；Geist Mono 12px 专用于版本号/安装命令等技术元数据，竖线分隔（同上）。
- **层级手法（签名式）**：**"键盘键帽"内阴影堆叠**——`rgba(255,255,255,0.05) 0 1px 0 inset`（顶部高光）+ `rgba(255,255,255,0.25) 0 0 0 1px`（外环）+ `rgba(0,0,0,0.2) 0 -1px 0 inset`（底部内影），让卡片呈现"被按下的键帽"触感而非浮起；明确禁止给卡片加外投影（同上）。
- **导航**：悬浮玻璃药丸——`backdrop-blur(48px)` + 1px `#363739` 边框，浮于内容之上。
- **品牌表达**：**"一次破戒"策略**——hero 区用红蓝渐变几何体（40px+ 大模糊）制造电影感瞬间，页面其余部分立刻回到禁欲深色，"contrast through atmosphere, not decoration"。光效是预算，只花在第一眼（同上）。语义色细节：错误状态用橙 `#FF8C00` 而非红，因为"红色是品牌色"（[DesignMD, 2026-03-23](https://designmd.me/discover/raycast)）。

**值得 MatchForge 借鉴的模式**

1. **品牌色配给 + AI 徽章**：靛蓝-紫渐变只留给三处：产品 logo、AI 相关标识（AI 寻源入口、AI 生成中的状态）、登录/营销页的氛围光。工作界面内 98% 无彩色——这与 MatchForge 现状（渐变按钮、渐变标题分散各处）差距最大，也是收益最大的一刀。
2. **键帽内阴影堆叠**：三行 box-shadow 即可让深色卡片拥有"精密仪器"触感，且比外投影在密集布局中更不脏。适合供应商卡片、驾驶舱指标卡。
3. **中性主按钮**：在深色底上用 `#e7e9ee` 系浅色实心按钮做主 CTA（MatchForge 已有此文本色），对比度天然最高，且把靛蓝彻底解放出来专管"交互指示"（选中、聚焦、链接、AI）。
4. **错误色与品牌色解耦**：若保留靛蓝品牌，错误红可照常使用；重点是原则——功能色永远给品牌色让路。

---

## 对 MatchForge 的迁移建议汇总

按优先级排列（P0 = 立即做，P1 = 近期迭代，P2 = 规划期）。每条格式：现状差距 → 改成什么。

### P0 —— 信任与安全底线

1. **焦点可见性（Vercel 双层环）**
   现状差距：已知短板"焦点可见性弱"，采购重度键盘用户无法定位焦点。
   改成：全局 `--focus-ring: 0 0 0 2px var(--bg-canvas), 0 0 0 4px #6366f1`，内圈画布色切割保证任何底色可见；`:focus-visible` 触发，鼠标点击不显环。参考 [design-bites Vercel DESIGN.md](https://github.com/educlopez/design-bites/blob/main/design-mds/vercel.com/DESIGN.md)（2026-07-17 访问）。

2. **主色配给制（Linear 单点主色 + Raycast 98% 无彩色）**
   现状差距：靛蓝 `#6366f1` 与渐变 `#6366f1→#8b5cf6` 散布在按钮、标题、徽章、装饰上，主动作被淹没。
   改成：每个视图只允许一个彩色主按钮；渐变退出工作界面，仅保留在 logo、AI 徽章、AI 生成中状态、登录页氛围四处；其余按钮中性幽灵样式（1px `#2b3140` 边框 + `#d0d6e0` 系文本）。参考 [Refero Linear](https://styles.refero.design/style/90ce5883-bb24-4466-93f7-801cd617b0d1)（2026-07-03）、[Refero Raycast](https://styles.refero.design/style/3b6a17f0-3bdf-418c-a95e-0b89e5a8b2f8)（2026-07-03）。

3. **状态色圆点化（Vercel 10px 规则）**
   现状差距：状态徽章若为彩色填充，在供应商列表/报价表格中会互相打架。
   改成：状态统一为 8–10px 彩色圆点 + 中性文本；语义色板收敛为 绿（成功/已合作）/ 橙（待处理）/ 红（失败/风险，**仅当品牌色非红时**）/ 靛蓝（AI/信息）。

### P1 —— 精密仪器感

4. **层级改用发丝边框 + 内阴影，弃外投影（Linear + Raycast）**
   现状差距：五档背景 `#0a0b0f~#1e2230` 职责模糊，硬编码色值多。
   改成：收敛为 4 档语义表面（canvas / card / elevated / recessed）+ 1 档发丝边框 `#2b3140`；卡片边缘用 `inset 0 0 0 1px` 内描边，关键卡叠加 Raycast 键帽三件套（顶部 1px 5% 白高光 + 外环 + 底部内影）；全部色值进设计令牌，浅色遗留样式清零。

5. **字重纪律：砍掉 700（四家共识）**
   现状差距：若存在 700 标题，视觉上"喊叫"且与工具气质不符。
   改成：字重收敛为 400/500/600 三档；24px+ 标题用 600 并施加 -0.02em 负字距（**仅作用于拉丁/数字，中文不施加字距压缩**）；正文 13–14px/400。参考 Vercel 三字重规则与 Linear 590 上限（同上来源）。

6. **等宽字体 + 表格数字对齐（Linear Berkeley Mono 模式）**
   改成：RFQ 号、物料编码、供应商编码、快捷键用 ui-monospace 栈；报价金额、数量列加 `font-variant-numeric: tabular-nums` 防止数字跳动错位。

### P2 —— AI 原生品牌感

7. **AI 工作流语义色时间线（Cursor）**
   现状差距：寻源工作流（规格确认→替代料→匹配→RFQ）若为纯文本步骤条，AI 价值不可见。
   改成：四步各配低饱和语义色小圆点/图标 + 竖向连接线 + 进行态呼吸微光（此处可用一次靛紫渐变流光，作为工作界面内唯一的动效例外，时长 ≤2s 循环）。参考 [Open Design Cursor](https://open-design.ai/plugins/design-system-cursor/)（2026-07-17 访问）。

8. **动效规范与降级（Vercel）**
   现状差距：已知短板"动效无降级"。
   改成：令牌化三档时长（150ms 颜色 / 200ms 浮层 / 300ms 模态）+ 统一过冲缓动 `cubic-bezier(.175,.885,.32,1.1)`；按钮 hover 只变色不位移；全局 `prefers-reduced-motion` 媒体查询关闭位移动画、仅保留透明度淡入。

9. **中性色温统一（Cursor 暖色系启示）**
   现状差距：灰阶偏冷蓝，易显"AI 模板感"。
   改成：不必改色相，但需把全部灰阶统一到同一色温（建议保持冷蓝系并把偏暖的遗留值清掉），消除令牌与硬编码并存的"脏灰"。

### 一个反面清单（明确不抄）

- **不抄 Cursor 的衬线正文与 hover 变绯红**：衬线字体不适合中文数据密集工具；hover 转向错误色在 B2B 场景会引发"出错了？"的误读。
- **不抄营销站的大留白低密度与超大标题**：Linear/Raycast 官网的 56–72px 标题、96–120px section 间距是营销语言；MatchForge 工作界面应保持 compact 密度（间距 8/12/24 阶梯），32px 已是界面标题上限。
- **不做"AI 模板三件套"**：纯黑 `#000` 底 + 霓虹渐变按钮 + 玻璃模糊卡片全屏铺——这正是四标杆共同反对的（[DEV Community, 2026-04-10](https://dev.to/raxxostudios/dark-mode-design-that-doesnt-look-ai-2cn3)）。MatchForge 现有 `#0a0b0f` 非纯黑底子是对的，渐变必须配给化而非铺满。
