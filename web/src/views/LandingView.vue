<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const heroImage = '/assets/matchforge-hero.png'
const trustFlowImage = '/assets/matchforge-trust-flow.png'

const sections = [
  {
    label: '01',
    title: '采购输入需求',
    desc: '输入缺货型号、参数描述或品牌偏好，系统先结构化需求，不直接给出未经校验的结论。',
    image: '/assets/landing-flow-input.png',
  },
  {
    label: '02',
    title: 'AI 拆解与核验',
    desc: '解析规格、补全缺失字段、查替代关系，并用 L1-L5 分级展示替代风险。',
    image: '/assets/landing-flow-verify.png',
  },
  {
    label: '03',
    title: '生成 RFQ',
    desc: '选择能力匹配供应商后生成可编辑询价单，明确“能力匹配非现货承诺”。',
    image: '/assets/landing-flow-rfq.png',
  },
]

const principles = [
  {
    title: '事实隔离，降低幻觉风险',
    desc: '型号、参数、供应商、库存等事实字段来自规则、字典和数据库，不交给 LLM 自由编造。',
    value: '采购决策更可信',
  },
  {
    title: '来源可追溯，便于工程复核',
    desc: '替代料展示来源、更新时间、置信度和人工核验状态，方便采购与工程协同确认。',
    value: '替代建议有依据',
  },
  {
    title: '能力匹配，不误导现货承诺',
    desc: '供应商结果只表达经营品类和品牌覆盖能力，不声称确认库存、报价或交期。',
    value: '避免错误预期',
  },
]

const scenarios = [
  { title: '指定型号缺货', desc: '研发指定料停产或缺货时，快速找到 2-3 个可核验替代建议。', image: '/assets/landing-usecase-shortage.png' },
  { title: '按参数找候选料', desc: '只有封装、容值、电压等参数时，收敛到具体可询价型号。', image: '/assets/landing-usecase-params.png' },
  { title: '生成询价单', desc: '把规格、替代料、用量、交期和供应商对象合并成可编辑 RFQ。', image: '/assets/landing-usecase-rfq.png' },
]

const capabilities = [
  { title: '需求解析', desc: '识别型号、封装、容值、电压、品牌偏好、用量和交期。' },
  { title: '替代分级', desc: '用 L1-L5 表达完全等效、向上兼容、需工程确认和仅供参考。' },
  { title: '参数差异', desc: '把一致项、差异项、风险项分开展示，降低误用风险。' },
  { title: '供应商匹配', desc: '基于经营品类、品牌覆盖、资质和地区展示能力匹配。' },
  { title: 'RFQ 生成', desc: '自动整理询价字段，生成可复制、可编辑、可保存的询价单。' },
  { title: '历史复用', desc: '沉淀寻源记录和 RFQ 草稿，方便复用同类采购需求。' },
]

const metrics = [
  { value: '10 min', label: '目标完成一次替代寻源' },
  { value: 'Top 3', label: '优先输出可核验替代建议' },
  { value: '0', label: '不展示未确认现货承诺' },
]
</script>

<template>
  <div class="landing">
    <header class="landing-nav">
      <RouterLink to="/" class="brand">
        <span class="brand__mark" />
        <span class="brand__text">MatchForge · 智配</span>
      </RouterLink>
      <nav class="landing-nav__links">
        <a href="#scenarios">使用场景</a>
        <a href="#flow">产品流程</a>
        <a href="#capabilities">核心功能</a>
        <a href="#principles">安全边界</a>
        <template v-if="auth.isAuthenticated">
          <span class="landing-nav__user">{{ auth.user?.name }}</span>
          <RouterLink to="/app" class="landing-nav__cta">进入工作台</RouterLink>
          <button class="landing-nav__button" @click="auth.logout()">退出</button>
        </template>
        <template v-else>
          <RouterLink to="/login">登录</RouterLink>
          <RouterLink to="/register" class="landing-nav__cta">注册</RouterLink>
        </template>
      </nav>
    </header>

    <main>
      <section class="hero">
        <div class="hero__content">
          <p class="hero__eyebrow">AI Component Sourcing</p>
          <h1>电子元器件缺货时，把替代料寻源变成可追踪流程</h1>
          <p class="hero__sub">
            MatchForge 面向采购人员，帮助识别规格、推荐有依据的替代料、匹配供应商能力，并生成可编辑 RFQ。
          </p>
          <div class="hero__actions">
            <RouterLink v-if="auth.isAuthenticated" to="/app" class="button button--primary">进入工作台</RouterLink>
            <RouterLink v-else to="/register" class="button button--primary">开始使用</RouterLink>
            <RouterLink v-if="!auth.isAuthenticated" to="/login" class="button button--secondary">登录工作台</RouterLink>
          </div>
          <div class="hero__metrics">
            <div v-for="m in metrics" :key="m.value">
              <b>{{ m.value }}</b>
              <span>{{ m.label }}</span>
            </div>
          </div>
        </div>

        <div class="hero-visual" aria-label="MatchForge 产品示意图">
          <img :src="heroImage" alt="AI 元器件寻源工作台视觉示意" class="hero-visual__image">
          <div class="hero-visual__caption">
            <b>AI sourcing workspace</b>
            <span>规格解析 · 替代料分级 · 供应商能力匹配 · RFQ</span>
          </div>
        </div>
      </section>

      <section id="scenarios" class="section">
        <div class="section__head">
          <span>Use Cases</span>
          <h2>先从采购最痛的三个场景切入</h2>
        </div>
        <div class="scenario-grid">
          <article v-for="s in scenarios" :key="s.title" class="scenario-card">
            <img :src="s.image" :alt="s.title">
            <div class="scenario-card__body">
              <h3>{{ s.title }}</h3>
              <p>{{ s.desc }}</p>
            </div>
          </article>
        </div>
      </section>

      <section id="flow" class="section">
        <div class="section__head">
          <span>Product Flow</span>
          <h2>介绍页只讲产品，不承载业务操作</h2>
        </div>
        <div class="flow-grid">
          <article v-for="item in sections" :key="item.label" class="flow-card">
            <img :src="item.image" :alt="item.title">
            <div class="flow-card__body">
              <span class="flow-card__label">{{ item.label }}</span>
              <h3>{{ item.title }}</h3>
              <p>{{ item.desc }}</p>
            </div>
          </article>
        </div>
      </section>

      <section id="capabilities" class="section">
        <div class="section__head">
          <span>Capabilities</span>
          <h2>不是聊天机器人，而是采购寻源工作台</h2>
        </div>
        <div class="capability-grid">
          <article v-for="c in capabilities" :key="c.title" class="capability-card">
            <span class="capability-card__icon" />
            <h3>{{ c.title }}</h3>
            <p>{{ c.desc }}</p>
          </article>
        </div>
      </section>

      <section id="principles" class="section section--split">
        <div>
          <div class="section__head">
            <span>Trust Boundary</span>
            <h2>工业采购场景里，可信比炫技更重要</h2>
          </div>
          <p class="section__copy">
            页面设计会保留 Linear 式的清晰分隔：公开介绍、注册登录、产品功能页各自独立，功能区只在登录后出现。
          </p>
          <div class="trust-visual">
            <img :src="trustFlowImage" alt="AI 寻源可信流程示意">
          </div>
        </div>
        <div class="principle-list">
          <div v-for="p in principles" :key="p.title" class="principle-item">
            <span class="principle-item__mark" />
            <div class="principle-item__content">
              <h3>{{ p.title }}</h3>
              <p>{{ p.desc }}</p>
              <b>{{ p.value }}</b>
            </div>
          </div>
        </div>
      </section>

      <section class="final-cta">
        <div>
          <span>Ready for Spike</span>
          <h2>先演示完整寻源链路，再接真实数据和后端鉴权</h2>
        </div>
        <div class="final-cta__actions">
          <RouterLink v-if="auth.isAuthenticated" to="/app" class="button button--primary">进入工作台</RouterLink>
          <RouterLink v-else to="/register" class="button button--primary">创建账号</RouterLink>
          <RouterLink v-if="!auth.isAuthenticated" to="/login" class="button button--secondary">登录</RouterLink>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.landing {
  min-height: 100vh;
  color: var(--text-primary);
  background:
    radial-gradient(circle at 18% 10%, rgba(99, 102, 241, 0.22), transparent 30%),
    linear-gradient(90deg, rgba(255, 255, 255, 0.035) 1px, transparent 1px),
    linear-gradient(180deg, rgba(255, 255, 255, 0.035) 1px, transparent 1px),
    var(--bg-0);
  background-size: auto, 56px 56px, 56px 56px, auto;
}
.landing-nav {
  position: sticky;
  top: 0;
  z-index: 10;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: 1180px;
  margin: 0 auto;
  padding: 0 var(--space-5);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(16px);
}
.brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-primary);
}
.brand__mark {
  width: 26px;
  height: 26px;
  border-radius: var(--radius-md);
  background: var(--gradient-accent);
  box-shadow: 0 0 28px rgba(99, 102, 241, 0.25);
}
.brand__text {
  font-weight: 700;
}
.landing-nav__links {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.landing-nav__links a {
  padding: 7px 10px;
  color: var(--text-secondary);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
}
.landing-nav__links a:hover,
.landing-nav__button:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.04);
}
.landing-nav__cta {
  color: #fff !important;
  background: var(--accent);
}
.landing-nav__user {
  max-width: 140px;
  overflow: hidden;
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.landing-nav__button {
  padding: 7px 10px;
  color: var(--text-secondary);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
}
.hero,
.section {
  max-width: 1180px;
  margin: 0 auto;
  padding: var(--space-8) var(--space-5);
}
.hero {
  min-height: 560px;
  display: grid;
  grid-template-columns: minmax(0, 0.95fr) minmax(420px, 0.75fr);
  gap: var(--space-6);
  align-items: center;
}
.hero__eyebrow,
.section__head span {
  color: var(--accent-hover);
  font-size: var(--font-size-xs);
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}
.hero h1 {
  max-width: 880px;
  margin-top: var(--space-4);
  font-size: clamp(42px, 7vw, 76px);
  line-height: 1.02;
  letter-spacing: -0.06em;
}
.hero__sub {
  max-width: 680px;
  margin-top: var(--space-5);
  color: var(--text-secondary);
  font-size: var(--font-size-lg);
}
.hero__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-top: var(--space-6);
}
.hero__metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
  margin-top: var(--space-6);
  max-width: 680px;
}
.hero__metrics div {
  padding: var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.025);
}
.hero__metrics b {
  display: block;
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: var(--font-size-lg);
}
.hero__metrics span {
  display: block;
  margin-top: 2px;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: 1.5;
}
.hero-visual {
  position: relative;
}
.hero-visual::before {
  content: '';
  position: absolute;
  inset: -24px;
  background: radial-gradient(circle, rgba(99, 102, 241, 0.28), transparent 62%);
  filter: blur(12px);
}
.hero-visual__image {
  position: relative;
  width: 100%;
  display: block;
  border: 1px solid var(--border-default);
  border-radius: 22px;
  background: var(--bg-1);
  box-shadow: 0 28px 90px rgba(0, 0, 0, 0.5);
}
.hero-visual__caption {
  position: absolute;
  left: var(--space-4);
  right: var(--space-4);
  bottom: var(--space-4);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-lg);
  background: rgba(10, 11, 15, 0.72);
  backdrop-filter: blur(14px);
}
.hero-visual__caption b {
  color: var(--text-primary);
  font-size: var(--font-size-sm);
}
.hero-visual__caption span {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  text-align: right;
}
.visual-window {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--border-default);
  border-radius: 18px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0.015)),
    #10131c;
  box-shadow: 0 28px 90px rgba(0, 0, 0, 0.48);
}
.visual-window__bar {
  height: 44px;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 0 var(--space-4);
  border-bottom: 1px solid var(--border-subtle);
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}
.visual-window__bar span {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--border-strong);
}
.visual-window__bar b {
  margin-left: var(--space-2);
  color: var(--text-secondary);
  font-weight: 600;
}
.visual-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
  padding: var(--space-4);
}
.visual-card {
  min-height: 118px;
  padding: var(--space-4);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.03);
}
.visual-card--wide {
  grid-column: span 2;
}
.visual-card small {
  display: block;
  margin-bottom: var(--space-3);
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
}
.visual-card p {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  line-height: 1.6;
}
.visual-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.visual-tags span {
  padding: 5px 8px;
  border-radius: var(--radius-full);
  color: var(--accent-hover);
  background: var(--accent-soft);
  border: 1px solid var(--accent-border);
  font-size: var(--font-size-xs);
}
.alt-row {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) 42px;
  gap: var(--space-2);
  align-items: center;
  padding: 7px 0;
  border-top: 1px solid var(--border-subtle);
  font-size: var(--font-size-xs);
}
.alt-row:first-of-type {
  border-top: none;
}
.alt-row b {
  color: var(--success);
  font-family: var(--font-mono);
}
.alt-row span {
  color: var(--text-secondary);
}
.alt-row em {
  color: var(--text-tertiary);
  font-style: normal;
  text-align: right;
}
.alt-row--warn b {
  color: var(--warning);
}
.doc-lines {
  color: var(--text-tertiary) !important;
}
.button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 42px;
  padding: 0 18px;
  border-radius: var(--radius-md);
  font-weight: 600;
  font-size: var(--font-size-sm);
}
.button--primary {
  color: #fff;
  background: var(--accent);
}
.button--secondary {
  color: var(--text-primary);
  background: var(--bg-2);
  border: 1px solid var(--border-default);
}
.section {
  border-top: 1px solid var(--border-subtle);
}
.section__head h2 {
  max-width: 680px;
  margin-top: var(--space-2);
  font-size: clamp(26px, 4vw, 42px);
  line-height: 1.12;
  letter-spacing: -0.04em;
}
.flow-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-3);
  margin-top: var(--space-6);
}
.scenario-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-3);
  margin-top: var(--space-6);
}
.scenario-card {
  overflow: hidden;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  background:
    linear-gradient(180deg, rgba(99, 102, 241, 0.08), rgba(255, 255, 255, 0.015)),
    var(--bg-1);
}
.scenario-card img,
.flow-card img {
  width: 100%;
  aspect-ratio: 4 / 3;
  display: block;
  object-fit: cover;
  border-bottom: 1px solid var(--border-subtle);
}
.scenario-card__body {
  padding: var(--space-5);
}
.scenario-card h3 {
  font-size: var(--font-size-lg);
}
.scenario-card p {
  margin-top: var(--space-3);
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  line-height: 1.7;
}
.capability-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-3);
  margin-top: var(--space-6);
}
.capability-card {
  padding: var(--space-5);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.025);
}
.capability-card__icon {
  display: block;
  width: 28px;
  height: 4px;
  margin-bottom: var(--space-4);
  border-radius: var(--radius-full);
  background: var(--gradient-accent);
}
.capability-card h3 {
  font-size: var(--font-size-md);
}
.capability-card p {
  margin-top: var(--space-2);
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  line-height: 1.7;
}
.flow-card {
  overflow: hidden;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.01)),
    var(--bg-1);
}
.flow-card__body {
  padding: var(--space-5);
}
.flow-card__label {
  color: var(--accent-hover);
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
}
.flow-card h3 {
  margin-top: var(--space-4);
  font-size: var(--font-size-lg);
}
.flow-card p {
  margin-top: var(--space-2);
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  line-height: 1.7;
}
.section--split {
  display: grid;
  grid-template-columns: minmax(0, 0.9fr) minmax(320px, 0.5fr);
  gap: var(--space-6);
  align-items: start;
}
.section__copy {
  max-width: 640px;
  margin-top: var(--space-4);
  color: var(--text-secondary);
}
.trust-visual {
  margin-top: var(--space-5);
  overflow: hidden;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  background: var(--bg-1);
  box-shadow: var(--shadow-lg);
}
.trust-visual img {
  width: 100%;
  display: block;
}
.principle-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.principle-item {
  position: relative;
  overflow: hidden;
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: var(--space-3);
  padding: var(--space-4);
  border: 1px solid rgba(34, 197, 94, 0.28);
  border-radius: var(--radius-lg);
  background:
    radial-gradient(circle at 12% 10%, rgba(34, 197, 94, 0.16), transparent 32%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.055), rgba(255, 255, 255, 0.018)),
    var(--bg-1);
  box-shadow: 0 16px 44px rgba(0, 0, 0, 0.24);
}
.principle-item::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  background: linear-gradient(180deg, var(--success), #60a5fa);
}
.principle-item__mark {
  width: 24px;
  height: 24px;
  margin-top: 2px;
  border-radius: 50%;
  background:
    radial-gradient(circle, #86efac 0 24%, rgba(34, 197, 94, 0.22) 25% 100%);
  box-shadow: 0 0 28px rgba(34, 197, 94, 0.32);
}
.principle-item__content h3 {
  color: #f4f7ff;
  font-size: var(--font-size-md);
  line-height: 1.35;
}
.principle-item__content p {
  margin-top: var(--space-2);
  color: #b8bfce;
  font-size: var(--font-size-sm);
  line-height: 1.65;
}
.principle-item__content b {
  display: inline-flex;
  margin-top: var(--space-3);
  padding: 5px 9px;
  color: #bbf7d0;
  background: rgba(34, 197, 94, 0.12);
  border: 1px solid rgba(34, 197, 94, 0.24);
  border-radius: var(--radius-full);
  font-size: var(--font-size-xs);
  font-weight: 700;
}
.final-cta {
  max-width: 1180px;
  margin: 0 auto var(--space-8);
  padding: var(--space-6) var(--space-5);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-5);
  border: 1px solid var(--accent-border);
  border-radius: 20px;
  background:
    radial-gradient(circle at 18% 20%, rgba(99, 102, 241, 0.22), transparent 36%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0.02)),
    var(--bg-1);
}
.final-cta span {
  color: var(--accent-hover);
  font-size: var(--font-size-xs);
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}
.final-cta h2 {
  max-width: 720px;
  margin-top: var(--space-2);
  font-size: clamp(24px, 4vw, 38px);
  line-height: 1.15;
  letter-spacing: -0.04em;
}
.final-cta__actions {
  display: flex;
  gap: var(--space-3);
  flex-shrink: 0;
}

@media (max-width: 820px) {
  .landing-nav__links a[href^='#'] {
    display: none;
  }
  .hero,
  .flow-grid,
  .scenario-grid,
  .capability-grid,
  .section--split {
    grid-template-columns: 1fr;
  }
  .hero {
    min-height: auto;
  }
  .hero__metrics {
    grid-template-columns: 1fr;
  }
  .visual-grid {
    grid-template-columns: 1fr;
  }
  .visual-card--wide {
    grid-column: span 1;
  }
  .final-cta {
    flex-direction: column;
    align-items: flex-start;
  }
  .final-cta__actions {
    flex-wrap: wrap;
  }
}
</style>
