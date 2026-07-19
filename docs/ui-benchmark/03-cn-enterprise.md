# 国产 B 端设计体系风格对标调研

> 调研日期：2026-07-17｜标杆：Ant Design（蚂蚁）、TDesign（腾讯）、Arco Design（字节/火山引擎）、飞书
> 聚焦「风格层」：中文排版、密度档位、深色模式、表单表格实践、B 端效率感，提炼可迁移到 MatchForge 智配（B2B AI 采购寻源）的模式。

---

## 各标杆风格画像

### Ant Design（蚂蚁集团）——企业级「确定性」范式

**视觉语言要点**

- **色彩**：三层 Design Token 派生结构 —— Seed Token（种子）→ Map Token（梯度）→ Alias Token（别名）。改 `colorPrimary` 一个种子值，算法自动生成全套色板与语义梯度。默认种子值：`colorPrimary #1677ff`、`colorError #ff4d4f`、`colorWarning #faad14`、`colorSuccess #52c41a`、`borderRadius 6`、`controlHeight 32`。文本色为 4 级透明度：`rgba(0,0,0,0.88 / 0.65 / 0.45 / 0.25)`（标题/正文/辅助/禁用）。（来源：[ant.design 定制主题](https://ant.design/docs/react/customize-theme-cn/)，2026-07 访问）
- **中文排版**：基准字号 14px、行高 22px（官方基于 50cm 屏幕阅读距离与 0.3° 阅读角，将基准字号从 12 升级为 14）；字阶由「五声音阶 + 自然对数律」生成 10 级，建议一个系统内字阶控制在 3–5 档；字重常规仅用 400/500；正文字号对比度遵循 WCAG AAA（7:1）。（来源：[ant.design 字体规范](https://ant.design/docs/spec/font)，2026-07 访问）
- **中西文混排**：字体走系统栈（`-apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans'`…）；数字强制 `font-variant-numeric: tabular-nums` 保证表格数字纵向对齐；**按钮内仅两个汉字时自动插入空格**（如「确 定」），属官方设计原则，可用 `autoInsertSpaceInButton` 关闭。（来源：[ant.design 字体规范](https://ant.design/docs/spec/font)、[Button FAQ](https://ant.design/components/button-cn/)，2026-07 访问）
- **密度档位**：Table 提供 default / middle / small 三档（small 官方建议只用于对话框内）；全局另有 `compactAlgorithm` 紧凑算法，且**可与 `darkAlgorithm` 叠加**，一行配置得到「暗色 + 紧凑」组合主题；ProTable 工具栏内置密度切换器（`options.density`）。（来源：[ant.design 定制主题](https://ant.design/docs/react/customize-theme-cn/)、[antd 4.x Table](https://4x-ant-design.antgroup.com/components/table-cn/)、[ProTable #749](https://github.com/ant-design/pro-table/issues/749)，2026-07 访问）
- **深色模式**：`darkAlgorithm` 以主色 + 页面背景色为输入，由算法生成暗色全套色板（官方提供暗色色板生成器，基于 12 组基础色板）。两条设计原则：① **内容舒适性**——避免高对比强刺激配色，长期使用不疲劳；② **信息一致性**——暗色下不打破浅色模式的信息层级。社区验证的典型落地值：`colorBgBase #141414`、`colorBgContainer #1f1f1f`、`colorBorder #424242`、暗色主色可略微调亮。（来源：[ant.design 暗色规范](https://ant.design/docs/spec/dark)、[OSChina 实战指南](https://my.oschina.net/emacs_7985923/blog/19475715)，2026-04 / 2026-07 访问）
- **动效**：时长三档 `motionDurationFast 0.1s / Mid 0.2s / Slow 0.3s`；极端性能场景可通过 token `motion: false` 一键全局关闭动画。（来源：[ant.design 定制主题](https://ant.design/docs/react/customize-theme-cn/)，2026-07 访问）
- **品牌/趋势**：定位「企业级设计系统」，2025 年已演进为「AI 友好的设计系统」（antd 6 + React 19 + Ant Design X AI 组件）。（来源：[ant.design 首页](https://ant.design/index-cn/)，2025-11 抓取）

**值得 MatchForge 借鉴的模式**

1. **三层 Token 派生（Seed→Map→Alias）**：只维护种子值（主色、背景基色、圆角、控件高），梯度色、hover 态、边框、语义浅底色全部由算法派生。对 MatchForge 的价值：自研组件 + 硬编码色值多的现状下，这是根治「浅色遗留样式与深色令牌并存」的最直接架构——一处改色、全局一致，且天然支持未来加浅色主题。
2. **数字等宽（tabular-nums）**：RFQ 报价单、经营驾驶舱里价格/数量/交期密集排列，等宽数字让纵向扫描、比价对齐效率倍增，是 B 端采购工具「效率感」的低成本高回报细节。
3. **「暗色 × 紧凑」双算法叠加**：密度不是一套独立样式，而是与主题正交的算法层。MatchForge 供应商工作台（数据极密集）与 AI 对话页（宽松阅读）可用同一套 token 体系按页面密度切换，无需维护两套组件样式。

---

### TDesign（腾讯）——体系化色彩工程与「品牌灰」

**视觉语言要点**

- **价值观**：包容、多元、进化、连接。（来源：[TDesign 设计价值观](https://tdesign.tencent.com/design/values)，2026-07 访问）
- **色彩**：主题色 Tencent Blue `#0052d9`（Blue7，对比度 6.54:1）；色阶用 **HCT 色彩空间** + 插值拟合曲线生成，保证多色间亮度均等、过渡均匀；功能色：错误 Red6 `#d54941`、告警 Orange5 `#e37318`、成功 Green5 `#2ba471`，每色 10 级。（来源：[TDesign 色彩](https://tdesign.tencent.com/design/color)，2026-07 访问）
- **中性色与「品牌灰」**：中性灰按 CIELab 亮度扩展到 **14 级**（Gray1 L96 `#f3f3f3` → Gray14 L8 `#181818`），扩展理由明确写了——**深色模式下需要靠中性色区分界面层级**。页面模板场景用 **RGB 混色把品牌色以 8%–12% 比例混入各级灰色**（BlueGray 系列，如 BlueGray13 `#20232b`、BlueGray14 `#15181d`），让界面带品牌倾向而不抢内容。（来源：[TDesign 色彩](https://tdesign.tencent.com/design/color)，2026-07 访问）
- **文字色透明度制（亮暗两套独立校准）**：浅色 `#000000` 90/60/40/26% 四档；深色 `#ffffff` 100/55/35/22% 四档。官方特别说明：黑底白字与白底黑字的 AIM 对比度曲线不同，**暗色模式有意略微降低透明度**以保持一致的阅读舒适性——即暗色文字不是浅色文字的反色。（来源：[TDesign 字体](https://tdesign.tencent.com/design/fonts)，2026-07 访问）
- **中文排版**：桌面端正文 14px、最小 12px（移动端 10px）；大字标题用第二字阶按 +4/+8/+12/+16 步进（20/24/28/36/48/64）；**行高公式 `line-height = font-size + 8`**——官方验证固定 1.5 倍行高在大字号混排时会产生割裂，「字号+n」让所有字号行距呼吸一致；字重只给 400/600 两档（兼顾 Windows 下 500 无法渲染的问题）；数字使用腾讯云等宽数字字体 TCloud Number。（来源：[TDesign 字体](https://tdesign.tencent.com/design/fonts)，2026-07 访问）
- **Token 分层**：色板 → 全局语义 Token（`brand-color-hover:@blue-color-6`）→ 组件 Token（`button-bg:@brand-color`），理解全局语义即可推导全部组件用色规则；主题提供明亮/暗色一键切换。（来源：[TDesign 色彩](https://tdesign.tencent.com/design/color)、[TDesign 官方介绍](http://tdesign.tencent.com/about/introduce)，2026-07 访问）

**值得 MatchForge 借鉴的模式**

1. **品牌灰（8–12% 品牌色混中性灰）**：MatchForge 深色背景 `#0a0b0f~#1e2230` 本身就是蓝灰系——把这一直觉工程化：以靛蓝 `#6366f1` 按 8–12% 混入 14 级灰阶，生成全套「带品牌倾向的深色背景/边框/填充」，深色界面立刻有品牌氛围而非纯黑灰。这是成本最低的品牌感升级。
2. **行高 = 字号 + 8**：MatchForge 现有 11–32px 八档字号若各配行高容易失控，一条公式统一所有文本行高，大小字混排（如驾驶舱大数字 + 小标签）呼吸感一致。
3. **暗色文字透明度独立校准**：MatchForge 现有文本 `#e7e9ee` 系接近纯白，可参考 TDesign 四档 `rgba(255,255,255, 1.0/0.55/0.35/0.22)` 并整体略降透明度，长表格阅读不刺眼。
4. **14 级亮度灰阶**：深色模式的层级（页面底→卡片→弹层→下拉）靠灰阶明度差表达，配合 MatchForge 现有五档背景正好对齐。

---

### Arco Design（字节跳动 / 火山引擎）——算法化深色与「填充透明度」阶梯

**视觉语言要点**

- **深色令牌（官方源码验证，最有参考价值）**：CSS 变量构建，暗色色板由亮色色板**算法自动生成反转**（`@arco-design/color` 包，14 组预设色板；改 `@arcoblue-6` 一个主色即重新生成亮暗两套 1–10 级）。暗色具体值：5 级背景 `#17171a → #232324 → #2a2a2b → #313132 → #373739`（整体底→一级容器→二级→三级→下拉/Tooltip）；文字 `fade(#fff, 90/70/50/30%)`；**填充 `fade(#fff, 4/8/12/16%)` 四级**；边框 `#333335`；菜单深色 hover 用 `fade(#fff,4%)`。（来源：[Arco Dark Mode 文档](https://arco.design/react/en-US/docs/dark)、[arco-design/theme/global.less 源码](https://raw.githubusercontent.com/arco-design/arco-design/main/components/style/theme/global.less)，2026-07 访问）
- **深色下语义浅底色 = 同色透明度派生**：暗色模式中 tag/badge/选中底色不引入新颜色，而是 `rgba(primary-6, 0.2 / 0.35 / 0.5 / 0.65)`——同一个色相、四档透明度。danger/success/warning/link 同规则。（来源：[global.less 源码](https://raw.githubusercontent.com/arco-design/arco-design/main/components/style/theme/global.less)，2026-07 访问）
- **中西文混排字体栈**：**西文字体 Inter 置于栈首**，中文回落 PingFang SC / Hiragino Sans GB / Microsoft YaHei——英文与数字用几何感更强的 Inter 渲染，中文用系统黑体，混排时基线与灰度更统一。（来源：[theme/default.less 源码](https://raw.githubusercontent.com/arco-design/arco-design/main/components/style/theme/default.less)，2026-07 访问）
- **排版**：正文 14px、`line-height: 1.5715`（14×1.5715≈22，与 AntD 殊途同归）；字阶 10 级：caption/body-1 12、body-2 **13**、body-3 14、title 16/20/24、display 36/48/56——官方明确使用 13px 这一奇数字号做次级正文。（来源：同上 default.less）
- **密度档位**：组件尺寸四档 **mini 24 / small 28 / default 32 / large 36**；间距刻度 2–120px 共 22 档（4 的倍数为主）；Space 组件 mini4/small8/medium16/large24。（来源：[Arco DesignLab 指南](https://arco.design/docs/designlab/guideline)、[Arco Space 组件](https://arco.design/react/en-US/components/space)，2026-07 访问）
- **表单风格**：默认 Input 为**灰底无边框的「面性」设计**（背景 `color-fill`、无边框），密集表单中视觉噪音显著低于描边输入框。（来源：[Arco DesignLab 指南](https://arco.design/docs/designlab/guideline)，2026-07 访问）
- **圆角/阴影/动效**：圆角 2/4/8px 三档（偏小，克制）；阴影统一 `rgba(0,0,0,0.1)`、三级×八方向；动效时长 0.1–0.5s 五档 + 5 条标准贝塞尔曲线（含 overshoot 过冲曲线 `cubic-bezier(0.3,1.3,0.3,1)`）。（来源：default.less / global.less 源码，2026-07 访问）
- **平台化**：DesignLab 支持一键创建/复制设计系统、实时预览 token 配置——「设计系统本身被产品化」。（来源：[Arco DesignLab 指南](https://arco.design/docs/designlab/guideline)，2026-07 访问）

**值得 MatchForge 借鉴的模式**

1. **深色填充透明度阶梯（白 4/8/12/16%）**：MatchForge 深色主题下 hover/选中/次级背景目前散落在 `#2b3140` 边框系里硬编码；改用白色透明度阶梯后，hover 态在任何背景层级上都自动适配，且层级逻辑（4% hover→8% 选中→12% 强调→16% 最高）一眼可读。这是对深色 B 端工具迁移价值最高的一条。
2. **语义色透明度派生**：AI 对话寻源中的「推荐」「风险提示」等标签，深色下用主色/功能色的 0.2 alpha 底色 + 实色文字，比浅色模式的浅底色实块更融合、更高级，且不需要新增色值。
3. **灰底无边框输入框**：规格确认、RFQ 表单字段密集，面性输入（深灰底、聚焦时主色描边/光晕）比一圈描边更安静，顺带解决「焦点可见性弱」——聚焦态从边框色变化升级为背景→光晕的强对比变化。
4. **Inter 优先字体栈**：MatchForge 现为系统字体栈，英文/数字（型号、料号、MOQ）与中文混排时视觉跳跃；引入一个开源西文字体（Inter）置于栈首即可明显改善，代价极小。

---

### 飞书（字节跳动）——效率品牌的「亲和力」表达

**视觉语言要点**

- **品牌色克制使用**：开放平台设计规范定义品牌蓝 `#1456F0`，官方定性为「高效、智能化、简洁、冷静」，应用场景**仅**为链接文字、按钮文字、部分菜单选中态——主色不做大面积铺色。（来源：[飞书开放平台《色彩》设计规范](https://open.feishu.cn/document/design-specification/design-language/color?lang=zh-CN)，页面更新于 2025-02，2026-07 访问）
- **大圆角 + 卡片化**：V5.0（2020-12）界面焕新，官方表述「采用更多大圆角和卡片化设计，提高产品的亲和力，表达高效、愉悦、领先、未来的品牌主张，与最新操作系统设计语言保持一致」。（来源：[飞书 V5.0 视觉升级官方公告](https://www.feishu.cn/hc/zh-CN/articles/793993008432)，2020-12-24 发布）
- **深色模式一等公民**：V5.0 同版本上线深色模式（弱光环境优化）+ 桌面端三套主题色可切换，深色与个性化主题作为大版本核心卖点发布。（来源：[飞书 V5.0 官方公告](https://www.feishu.cn/hc/zh-CN/articles/426070523032-v5.0-%E9%A3%9E%E4%B9%A6%E5%85%A8%E6%96%B0%E5%8D%87%E7%BA%A7-%E6%B7%B1%E8%89%B2%E6%A8%A1%E5%BC%8F%E6%83%8A%E5%96%9C%E4%B8%8A%E7%BA%BF)，2020-12-24 发布）
- **效率感的信息架构**：导航可拖拽排序、隐藏低频应用、展开/收起切换视图；状态（勿扰/会议）自动同步——高频操作前置、界面可由用户裁剪。（来源：[飞书 V5.0 官方公告](https://www.feishu.cn/hc/zh-CN/articles/793993008432)，2020-12-24）
- **行业佐证（B 端工作台通用手法）**：工作台设计通行的效率手法——24 栅格承载密集模块、待办/审批前置、核心数据一眼透传（色彩聚焦+字号对比）、辅助信息降噪。（来源：[人人都是产品经理·B 端工作台案例拆解](https://www.woshipm.com/pd/5558735.html)，2022-08 发布，2026-07 访问）

**值得 MatchForge 借鉴的模式**

1. **主色只做「路标」不做「油漆」**：`#6366f1` 限定在链接、主按钮、选中态、关键数据高亮；渐变 `#6366f1→#8b5cf6` 收敛为品牌装饰（登录页、空状态插画、加载态、AI 身份标识），不进表格/表单等效率区。深色界面上大面积高饱和渐变既刺眼也削弱信任感。
2. **圆角与卡片传递亲和力**：MatchForge 圆角 4/6/10px 偏硬朗，可在卡片/弹窗层用 10px 甚至更大圆角 + 柔和阴影，控件层保持 4–6px——「内容区亲和、操作区利落」的双层圆角策略，与 AI 对话寻源的对话卡片天然契合。
3. **深色模式按正式产品规格打磨**：飞书把深色当大版本卖点而非反色补丁。MatchForge 深色优先的策略是对的，但需补齐「信息层级与浅色语义一致」的验收标准（哪一级文字、哪一级背景、hover 几档，逐一对齐规范）。
4. **可裁剪的工作台**：经营驾驶舱允许采购方按角色配置模块（待办 RFQ、报价提醒前置；低频图表可收起）——效率感很大程度来自「界面是我裁剪过的」。

---

## 对 MatchForge 的迁移建议汇总

按优先级排列（现状差距 → 改成什么）：

| 优先级 | 建议 | 现状差距 → 目标 | 来源标杆 |
|---|---|---|---|
| P0 | **Token 三层架构** | 硬编码色值多、浅色遗留样式与深色令牌并存 → 收敛为种子值（主色/背景基/文字基/圆角/控件高）+ 算法派生梯度 + 语义别名，全部走 CSS 变量 | Ant Design / TDesign |
| P0 | **深色填充透明度阶梯** | 边框 `#2b3140` 系硬撑层级、hover 态不统一 → `rgba(255,255,255,4/8/12/16%)` 四级填充 + 5 级背景（现有五档背景正好对齐），hover=4%、选中=8% | Arco |
| P0 | **排版收敛** | 字号 11–32px 八档散乱 → 收敛至 4–5 档（12/13/14/16/20/24 取用）；行高统一 `字号+8`；数字 `tabular-nums`；字体栈引入 Inter 置首 | TDesign / Arco / AntD |
| P1 | **密度双档正交化** | 全产品一种密度 → 默认控件高 32 + 紧凑 28（表格 default/middle/small 三档）；密度与主题为正交维度，供应商工作台默认紧凑、AI 对话默认宽松 | AntD / Arco |
| P1 | **语义色透明度派生** | 深色下 tag/badge 用实色块刺眼 → 功能色 `alpha 0.2/0.35/0.5/0.65` 派生浅底，同色相不新增色值 | Arco |
| P1 | **表单降噪三件套** | 输入框描边重、焦点弱 → 灰底无边框输入 + 聚焦主色光晕；操作区「1 主 + n 次，3 个以上收 Dropdown」；两字按钮自动空格 | Arco / AntD |
| P2 | **品牌灰工程化** | 深色背景偏纯灰、品牌感弱 → 靛蓝按 8–12% 混入 14 级灰阶，生成品牌倾向的深色中性色板 | TDesign |
| P2 | **动效规范 + 降级** | 动效无降级 → 时长三档 0.1/0.2/0.3s，标准/减速两条贝塞尔；`prefers-reduced-motion` 全局关闭非必要动效 | AntD / Arco |
| P2 | **效率感工具化** | 表格仅展示 → 表格工具栏（密度切换/列设置/刷新/全屏）；驾驶舱待办前置、可裁剪；文案去开发者痕迹（参照 AntD 文案规范另行整理） | AntD Pro / 飞书 |

**一个该避的坑**：**不要用「反色/降亮度」思路做深色模式**。Ant Design 暗色原则（内容舒适、信息一致）、TDesign 暗色文字透明度独立校准、Arco 暗色语义色透明度派生，三家一致表明：深色是一套独立校准的色板体系，不是浅色模式的负片。同理，渐变主色 `#6366f1→#8b5cf6` 不要大面积铺进效率区——四大标杆的主按钮全部是纯色，渐变只配出现在品牌装饰位。
