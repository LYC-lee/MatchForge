# 落地页与认证体验 UI 分析报告

> 审查范围：`web/src/views/LandingView.vue`、`LoginView.vue`、`RegisterView.vue`、`views/demos/LoginWithHolo.vue`、`views/demos/LoginHoloPro.vue`
> 对照文件：`web/src/styles/tokens.css`、`web/src/stores/auth.ts`、`web/src/router/index.ts`、`web/src/components/ui/AppButton.vue`、`web/tsconfig.app.json`

## 1. 现状概述

落地页为单屏滚动式介绍页：吸顶导航（品牌 + 锚点链接 + 登录/注册 CTA）→ Hero（价值主张 h1 + 双 CTA + 3 项指标 + 产品示意图）→ 使用场景 → 产品流程 → 核心功能 → 信任边界 → 底部 CTA。视觉沿用全局深色令牌（`--bg-0`、靛蓝 `--accent`），栅格底纹 + 径向光晕，层级清晰。登录/注册页为左右分屏：左侧品牌故事面板内嵌 Canvas 全息投影动画（中国版图经纬投影 + 扫描光束 + 引导线，约 190 行），右侧 380-400px 表单卡片；登录页内置「演示企业」快捷登录（6 家企业下拉）与真实账号表单，注册页含企业类型下拉 + 5 字段。`views/demos/` 下两个演示登录页与正式登录页结构几乎相同，但未挂载路由、未被任何文件引用，且被 `tsconfig.app.json:18` 排除在类型检查之外。移动端通过 820px（落地页）/ 960px（认证页）断点折叠为单列。

## 2. 问题清单

### 🔴 严重（影响可用性/明显缺陷/体验断裂）

**R1. 两个 demos 登录页是「僵尸代码」：未路由、逻辑已损坏、含乱码，却与正式页并存**

- 未被引用：`router/index.ts:5-31` 无任何 demos 路由；全仓 grep 无 import。同时 `web/tsconfig.app.json:18` 将 `src/views/demos/**` 排除出类型检查——意味着下面的损坏永远不会被 `vue-tsc` 发现。
- 登录逻辑必败：`auth.login` 已是 async 返回 Promise（`stores/auth.ts:44-47`），但两个 demos 仍在 `setTimeout` 里同步取值且**没有 await**——`LoginWithHolo.vue:19-28`、`LoginHoloPro.vue:19-28` 中 `const r = auth.login(...)`，`r.ok` 为 `undefined`，永远走失败分支。这两个页一旦被发现并挂载，登录功能 100% 报错。
- 乱码已固化进文件：`LoginHoloPro.vue:26` `error.value = r.msg || '��¼ʧ��'`，原始字节为 `ef bf bd ef bf bd c2 bc ca a7 ef bf bd ef bf bd`（U+FFFD + '¼§'），即"登录失败"经 GBK 误解码后回存 UTF-8，用户可见的报错文案是乱码。
- 资源泄漏：`LoginWithHolo.vue` 只有 `onMounted`（第 45 行 import 无 `onUnmounted`），`window.addEventListener('resize', resize)`（第 62 行）与 rAF 循环（第 140、230 行）永不清理。
- 同目录还有 6 个未引用的静态 `demo-*.html`（demo-china-grid.html 等），混在 `src/views/` 源码树内。

**R2. 登录页 `overflow: hidden` 导致矮视口/移动端表单被裁剪且无法滚动**

- 证据：`LoginView.vue:314-320` `.auth-page { min-height: 100vh; display: grid; ...; overflow: hidden; }`。
- 登录卡片内容（返回链接 + 品牌 + 标题 + 演示企业区块 + 分隔线 + 2 个字段 + 错误条 + 提交按钮 + 提示 + 免责声明）实测约 700px+；960px 断点下页面折叠为单列（`LoginView.vue:428`），卡片居中但页面根节点 `overflow: hidden` 禁止滚动——iPhone SE（667px 高）、手机横屏、桌面矮窗口下，底部提交按钮与注册入口被裁掉且无法触及。
- 对照：`RegisterView.vue:318-328` 的 `.register-page` 没有 `overflow: hidden`（正确做法），说明这是登录页独有的缺陷。两个 demos（`LoginWithHolo.vue:299-305`、`LoginHoloPro.vue:276-282`）同样带此缺陷。

**R3. 落地页面向采购用户的文案混入开发者内部黑话，首触达信任断裂**

- `LandingView.vue:143` 产品流程区标题：`<h2>介绍页只讲产品，不承载业务操作</h2>`——这是设计约束备忘，不是用户价值。
- `LandingView.vue:178-179` 信任边界正文："页面设计会保留 Linear 式的清晰分隔：公开介绍、注册登录、产品功能页各自独立，功能区只在登录后出现。"——在跟访客谈论页面信息架构本身。
- `LandingView.vue:198-199` 底部转化 CTA（全页最关键的转化点）： eyebrow 为 `"Ready for Spike"`，标题为"先演示完整寻源链路，再接真实数据和后端鉴权"——Spike、后端鉴权是研发团队内部计划语言，出现在促单位置直接削弱 B2B 可信度。

### 🟡 中等（不一致、效率低、可感知粗糙）

**M1. 同一段全息投影动画代码复制了 4 份，中国版图坐标数组（约 400 点）复制 4 份**

- `LoginView.vue:50-241`、`RegisterView.vue:51-233`、`LoginWithHolo.vue:44-231`、`LoginHoloPro.vue:34-224`。LoginWithHolo 版本还分叉出城市粒子特效（第 86-137 行）。任何视觉调整需同步 4 处，已经产生实际分叉（见 M2）。另：三处通过 `(window as any)._holoArrows` 共享箭头状态（`LoginView.vue:175-176` 等），跨页面残留全局可变状态。

**M2. 登录页故事面板指标卡使用色板外琥珀色，与 demos 的靛蓝版本风格分裂**

- `LoginView.vue:338`：`border: 1px solid rgba(241,180,15,0.3)` + 金色径向光（#f1b40f 不在 `tokens.css` 任何令牌中；令牌仅有 `--warning: #eab308`）。而 `LoginWithHolo.vue:366-372` 同款卡片用 `rgba(129,140,248,0.34)`（靛蓝）。同一组件两种配色并存，是 M1 复制式维护的直接后果。Canvas 内引导线也硬编码 `rgba(241,180,15,...)`、`rgba(255,220,80,...)`（`LoginView.vue:211` 等）。

**M3. 中文大标题使用过大的负字距，字形互相挤压**

- `LandingView.vue:312` hero h1 `letter-spacing: -0.06em`（76px 时约 -4.6px/字）；`LandingView.vue:524、729` h2 `-0.04em`；`LoginView.vue:335` `-0.04em`；`RegisterView.vue:377` `-0.05em`；`LoginWithHolo.vue:345` `-0.05em`。负字距是为拉丁字母设计的排版手法，CJK 全宽字形在 -0.04em 以上会出现可见的笔画重叠/拥挤，大字号标题反而显得廉价。

**M4. 认证相关文案与真实后端行为脱节**

- `RegisterView.vue:261` "创建本地演示账号，后续可替换为真实后端鉴权"——但 `stores/auth.ts:131` 注册已 POST 到真实 `/api/v1/auth/register`，文案与行为互相矛盾。
- `RegisterView.vue:305` "本地演示会话有效期 8 小时。生产环境建议使用后端密码哈希、CSRF 防护和 HttpOnly Cookie。"——给终端用户看的表单里写开发建议。
- `LoginView.vue:307` "演示账号：demo@matchforge.ai / demo12345"——真实登录走后端 `/api/v1/auth/login`（`stores/auth.ts:54`），该账号是否存在于后端不可知；且页面顶部已是 6 家企业演示入口，这行旧文案造成两个"演示"概念混淆。
- demos 中 "本地 mock 认证仅用于 Spike 演示"（`LoginWithHolo.vue:292`、`LoginHoloPro.vue:269`）同样已是错误描述。

**M5. 移动端隐藏故事面板后，Canvas 动画仍在空转**

- 断点 960px 下 `.auth-story { display: none }`（`LoginView.vue:428`、`RegisterView.vue:565-572`），但 rAF 循环不停止：每帧对约 400 个多边形点做三角投影计算后画到 0×0 画布上，移动端白耗 CPU/电量。且全站动画均未响应 `prefers-reduced-motion`。

**M6. 价值主张术语在三页面间漂移**

- 落地页："电子元器件缺货时…替代料寻源"（`LandingView.vue:98`）；登录页："AI 元器件替代料寻源工作台"（`LoginView.vue:269`）；注册页却变成"创建你的产业链协同工作区"（`RegisterView.vue:244`）、"AI 装配寻源"（`RegisterView.vue:246、249`）、"多角色协同审核"（`RegisterView.vue:251`）。"装配寻源"与"替代料寻源"是不同卖点，首触达转化路径上用户收到三种定位。

**M7. 落地页残留约 100 行死 CSS**

- `LandingView.vue:395-496` 的 `.visual-window`、`.visual-grid`、`.visual-card`、`.visual-tags`、`.alt-row`、`.doc-lines` 在模板中无任何对应元素（模板已改用 `<img>` 卡片）。增加阅读和维护成本，也误导后续修改。

**M8. 表单校验全部滞后到提交后，且无字段级错误定位**

- 登录：`LoginView.vue:299-303` 账号/密码无必填、格式即时提示，空表单提交后由 store 返回"请输入账号和密码"（`stores/auth.ts:49-51`）显示在唯一错误条里。
- 注册：`RegisterView.vue:32-35` 仅在前端校验两次密码一致；邮箱格式、密码强度均由 store 校验（`stores/auth.ts:119-127`），错误全部汇入单个 `register-error`（`RegisterView.vue:300`），用户无法定位出错字段；确认密码失配无输入态即时反馈。

### 🔵 建议（锦上添花）

- **S1. 落地页无页脚**：`LandingView.vue` 在 final-cta 后结束，无版权、联系方式、备案号等 B2B 信任元素。
- **S2. 落地页按钮体系分裂**：`LandingView.vue:497-515` 自定义 `.button`（42px 高），未复用 `AppButton.vue`（其 lg 也是 42px，含 spinner/disabled 态）；`LandingView.vue:269` 用 `!important` 覆盖 CTA 颜色。
- **S3. 图片性能**：场景/流程卡片 6 张图无 `loading="lazy"`（`LandingView.vue:131、147`），hero 图无 `width/height` 属性（`LandingView.vue:116`），有 CLS 风险。
- **S4. 移动端 hero 指标折叠为单列**（`LandingView.vue:751-753`），三个小卡纵向堆叠占用大量首屏；保持 3 列或改横向滚动更紧凑。
- **S5. 演示登录按钮无 spinner**：`LoginView.vue:293-295` 用原生 button，仅靠文案"进入中..."；`AppButton` 自带 `.spinner`（`AppButton.vue:24、69-76`），两处加载态观感不一致。
- **S6. 无「忘记密码」、无密码可见性切换**：`LoginView.vue:301-302`、`RegisterView.vue:291-298`。
- **S7. 注册成功跳转丢失 redirect**：`RegisterView.vue:46` 硬跳 `/app`，而登录会带回 `route.query.redirect`（`LoginView.vue:28`）；从受保护页 → 登录 → 注册的链路丢失原目标。
- **S8. 吸顶导航只有 `backdrop-filter: blur(16px)` 无半透明底色**（`LandingView.vue:222-235`），在不支持 backdrop-filter 的环境下导航文字与滚动内容直接叠印。
- **S9. 桌面端品牌标识重复出现**：登录/注册页左侧故事面板与右侧卡片各渲染一次品牌（`LoginView.vue:248-251、265-267`），同屏双 logo。
- **S10. `document.getElementById('holoCanvas')`**（四文件共 4 处）代替模板 ref，依赖"同屏只有一个实例"的隐性约定，脆弱。
- **S11. 锚点导航无平滑滚动**（`LandingView.vue:78-81`），点击硬跳；缺 `scroll-margin-top`，目标标题会被 64px 吸顶导航遮住首行。

## 3. 优化方案

**P0-1｜清除僵尸 demos，动画收敛为单一组件（解决 R1 + M1 + M2）**
- 做什么：删除 `web/src/views/demos/` 下 2 个 .vue + 6 个 .html（或整体移出 `src` 到 `playground/` 并在 vite 中排除），同步删掉 `tsconfig.app.json:18` 的 exclude 条目。
- 为什么：它们不路由、不类型检查、逻辑已坏（无 await 必败 + 乱码 + rAF 泄漏），保留只会被误挂载或继续腐坏；6 个静态 html 同理。
- 改法：新建 `web/src/components/HoloCanvas.vue`（props：`variant?: 'grid' | 'particles'`），把 `LoginView.vue:50-241` 的动画逻辑与坐标数据迁入（数据可放 `src/data/chinaOutline.ts`），`LoginView.vue`、`RegisterView.vue` 改为 `<HoloCanvas />`，删除各自约 180 行重复代码；指标卡配色统一回令牌靛蓝（删掉 `LoginView.vue:338` 的 `rgba(241,180,15,...)`，改用 `--accent-border` / `--accent-soft`）。

**P0-2｜修复登录页矮视口裁剪（解决 R2）**
- 做什么：移除 `.auth-page` 的 `overflow: hidden`（`LoginView.vue:318`），改为 `.auth-story { overflow: hidden }` 只裁故事面板；页面允许纵向滚动，卡片改为 `margin: auto 0` 居中。
- 为什么：`overflow: hidden` 加在 100vh 根网格上，等于禁止页面滚动，内容超高即永久不可达——移动端表单提交按钮会被裁掉。
- 改法：仅 `LoginView.vue:314-320` 一处；顺手验证 667px 高视口下可滚动到底。

**P0-3｜重写落地页开发者黑话文案（解决 R3 + M6）**
- 做什么：三处替换为面向采购方的价值语言：
  - `LandingView.vue:143` "介绍页只讲产品，不承载业务操作" → 类似 "三步完成一次可核验的替代寻源"；
  - `LandingView.vue:178-179` Linear 式分隔说明 → 面向用户的可信承诺（如"未经核验的信息不进入你的询价单"）；
  - `LandingView.vue:198-199` "Ready for Spike / 先演示…再接后端鉴权" → "现在开始 / 10 分钟完成第一次替代料寻源"，CTA 保持"创建账号"。
- 同步统一注册页定位话术：`RegisterView.vue:244-251` 的"产业链协同工作区 / AI 装配寻源"改回与落地页一致的"替代料寻源工作台"主线。
- 为什么：落地页唯一任务是建立信任并转化，内部迭代计划语言出现在首触达页面等同于向访客展示施工脚手架。
- 改法：仅 `LandingView.vue` script 数据区与模板三处、`RegisterView.vue` story 区文案，无样式改动。

**P1-4｜修复中文标题负字距（解决 M3）**
- 做什么：CJK 标题 `letter-spacing` 收敛到 `-0.02em` 以内或直接归 0；如需紧排效果只针对含拉丁/数字的 eyebrow（已是大写拉丁，可保留 0.14em 正字距）。
- 改法：`LandingView.vue:312（-0.06em）、524（-0.04em）、729（-0.04em）`、`LoginView.vue:335`、`RegisterView.vue:377`。

**P1-5｜认证文案对齐真实后端行为（解决 M4）**
- 做什么：`RegisterView.vue:261` 改为"创建企业账号，注册即进入工作台"；`RegisterView.vue:305` 开发建议改为一句用户向安全承诺（或删除）；`LoginView.vue:307` 免责声明与顶部演示企业入口合并为一处说明，未确认后端 seeded 账号前删除硬编码账密。
- 改法：三个文件的模板文案区，无逻辑改动。

**P1-6｜Canvas 动画增加可见性与减动效守卫（解决 M5）**
- 做什么：`HoloCanvas.vue` 内监听 `document.visibilitychange` 与 `matchMedia('(prefers-reduced-motion: reduce)')`，面板 `display: none`（配合 ResizeObserver 尺寸为 0）时 `cancelAnimationFrame` 停帧；`window._holoArrows` 改为组件内局部数组。
- 改法：随 P0-1 的组件抽取一并完成。

**P1-7｜删除落地页死 CSS（解决 M7）**
- 做什么：删除 `LandingView.vue:395-496` 的 `.visual-window`/`.visual-grid`/`.visual-card`/`.visual-tags`/`.alt-row`/`.doc-lines` 规则块。
- 改法：纯删除；删后全局搜索类名确认无引用。

**P2-8｜表单体验增强（解决 M8 + S5/S6/S7）**
- 字段级校验：账号失焦校验邮箱格式、注册页确认密码输入中实时提示失配（红边 + 字段下文案），错误条保留给服务端错误；涉及 `LoginView.vue`、`RegisterView.vue` 模板与少量 state。
- 演示登录按钮换用 `AppButton` 并传 `:loading="demoLoading"`，获得 spinner。
- 登录卡片加"忘记密码"占位链接（即使先指向 `mailto:` 或提示页）；密码框加可见性切换。
- `RegisterView.vue:46` 改为读取 `route.query.redirect` 回跳，与登录对齐。

**P2-9｜落地页收尾项（解决 S1/S3/S4/S8/S11）**
- 补页脚（版权 + 联系 + 占位备案行）；6 张卡片图加 `loading="lazy"`，hero 图加宽高属性；`hero__metrics` 在移动端保持 3 列（小字号）或横向滚动；吸顶导航补 `background: rgba(10, 11, 15, 0.72)`；`html { scroll-behavior: smooth }` + section 加 `scroll-margin-top: 64px`。

**P2-10｜统一按钮与品牌渲染（解决 S2/S9/S10）**
- 落地页 `.button` 替换为 `AppButton`（variant/size 映射：primary lg / secondary lg），去掉 `!important`；认证页故事面板与卡片只保留一处品牌标识；`HoloCanvas` 用模板 ref 替代 `getElementById`。
