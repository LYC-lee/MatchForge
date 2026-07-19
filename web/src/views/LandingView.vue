<script setup lang="ts">
import { RouterLink, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AppButton from '@/components/ui/AppButton.vue'

const auth = useAuthStore()
const router = useRouter()

const heroImage = '/assets/matchforge-hero.png'

// AI 寻源四步：对话提需求 → 规格确认 → 替代料推荐与供应商匹配 → RFQ 询价
const flowSteps = [
  {
    label: '01',
    title: '对话提需求',
    desc: '用自然语言描述缺货型号、关键参数或品牌偏好，AI 先把需求结构化，不急于给出未经校验的结论。',
    image: '/assets/landing-flow-input.png',
  },
  {
    label: '02',
    title: '规格确认',
    desc: '解析封装、容值、电压等关键规格；缺失字段先与你确认后再继续，把误配挡在流程之外。',
    image: '/assets/landing-flow-verify.png',
  },
  {
    label: '03',
    title: '替代料推荐与供应商匹配',
    desc: '替代建议按 L1–L5 分级展示风险，并基于经营品类与品牌覆盖匹配供应商能力。',
    image: '/assets/landing-usecase-params.png',
  },
  {
    label: '04',
    title: 'RFQ 询价',
    desc: '一键生成可编辑询价单，明确「能力匹配不等于现货承诺」，发出前每个字段都可修改。',
    image: '/assets/landing-flow-rfq.png',
  },
]

// 面向采购方的价值语言：交付周期、缺料风险、合规可溯源
const values = [
  {
    title: '缩短交付周期',
    desc: '目标 10 分钟完成一次替代寻源：从提需求到发出 RFQ 全程在线，每个环节状态可追踪。',
  },
  {
    title: '控制缺料风险',
    desc: '替代建议按 L1–L5 分级，参数一致项、差异项、风险项分开展示，误用风险在下单前暴露。',
  },
  {
    title: '合规可溯源',
    desc: '每条替代建议带来源、更新时间、置信度与人工核验状态，方便采购与工程协同复核。',
  },
  {
    title: '边界清晰不误导',
    desc: '供应商结果只表达经营品类与品牌覆盖能力，不声称已确认库存、报价或交期。',
  },
]

const metrics = [
  { value: '10 min', label: '完成一次替代寻源' },
  { value: 'Top 3', label: '可核验替代建议' },
  { value: 'L1–L5', label: '替代风险分级' },
]

function go(path: string) {
  router.push(path)
}
</script>

<template>
  <div class="landing">
    <header class="landing-nav">
      <RouterLink to="/" class="brand">
        <span class="brand__mark" />
        <span class="brand__text">MatchForge · 智配</span>
      </RouterLink>
      <nav class="landing-nav__links" aria-label="落地页导航">
        <a href="#flow">产品流程</a>
        <a href="#values">价值</a>
        <template v-if="auth.isAuthenticated">
          <span class="landing-nav__user">{{ auth.user?.name }}</span>
          <AppButton variant="secondary" size="sm" @click="go('/app')">进入工作台</AppButton>
        </template>
        <template v-else>
          <RouterLink to="/login">登录</RouterLink>
          <AppButton variant="secondary" size="sm" @click="go('/register')">免费注册</AppButton>
        </template>
      </nav>
    </header>

    <main>
      <section class="hero">
        <div class="hero__content">
          <p class="hero__eyebrow">AI 替代料寻源</p>
          <h1>缺料不停产，找到可核验的替代料</h1>
          <p class="hero__sub">
            MatchForge 面向采购团队：对话式提需求，AI 解析规格、分级推荐替代料、匹配供应商能力，并生成可编辑的
            RFQ 询价单——缩短交付周期，降低缺料风险，全程合规可溯源。
          </p>
          <div class="hero__actions">
            <AppButton v-if="auth.isAuthenticated" @click="go('/app')">进入工作台</AppButton>
            <AppButton v-else @click="go('/register')">免费注册</AppButton>
            <AppButton v-if="!auth.isAuthenticated" variant="secondary" @click="go('/login')">登录演示</AppButton>
          </div>
          <div class="hero__metrics">
            <div v-for="m in metrics" :key="m.label">
              <b class="num">{{ m.value }}</b>
              <span>{{ m.label }}</span>
            </div>
          </div>
        </div>

        <figure class="hero-visual">
          <img :src="heroImage" alt="MatchForge AI 替代料寻源工作台界面示意" class="hero-visual__image">
          <figcaption class="hero-visual__caption">
            <b>AI 寻源工作台</b>
            <span>规格解析 · 替代分级 · 供应商匹配 · RFQ</span>
          </figcaption>
        </figure>
      </section>

      <section id="flow" class="section">
        <div class="section__head">
          <span>产品流程</span>
          <h2>四步完成一次替代料寻源</h2>
          <p>从一句缺料描述到发出询价单，每一步都有明确产出，可以随时停下、修改、重来。</p>
        </div>
        <div class="flow-grid">
          <article v-for="item in flowSteps" :key="item.label" class="flow-card">
            <img :src="item.image" :alt="item.title" loading="lazy">
            <div class="flow-card__body">
              <span class="flow-card__label num">{{ item.label }}</span>
              <h3>{{ item.title }}</h3>
              <p>{{ item.desc }}</p>
            </div>
          </article>
        </div>
      </section>

      <section id="values" class="section">
        <div class="section__head">
          <span>价值</span>
          <h2>为采购团队而建，而不是又一个聊天机器人</h2>
        </div>
        <div class="value-grid">
          <article v-for="v in values" :key="v.title" class="value-card">
            <span class="value-card__mark" aria-hidden="true" />
            <h3>{{ v.title }}</h3>
            <p>{{ v.desc }}</p>
          </article>
        </div>
      </section>

      <section class="final-cta">
        <div class="final-cta__copy">
          <span>开始使用</span>
          <h2>现在就开始第一次替代料寻源</h2>
          <p>免费注册，或用演示账号登录，体验从提需求到发出 RFQ 的完整链路。</p>
        </div>
        <div class="final-cta__actions">
          <AppButton v-if="auth.isAuthenticated" @click="go('/app')">进入工作台</AppButton>
          <AppButton v-else @click="go('/register')">免费注册</AppButton>
          <AppButton v-if="!auth.isAuthenticated" variant="secondary" @click="go('/login')">登录演示</AppButton>
        </div>
      </section>
    </main>

    <footer class="landing-footer">
      <span>MatchForge · 智配</span>
      <span>AI 替代料寻源工作台</span>
    </footer>
  </div>
</template>

<style scoped>
.landing {
  min-height: 100vh;
  color: var(--text-primary);
  background: var(--bg-canvas);
}

/* ---------- 顶部导航 ---------- */
.landing-nav {
  position: sticky;
  top: 0;
  z-index: var(--z-sticky);
  height: var(--header-h);
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: var(--container-md);
  margin: 0 auto;
  padding: 0 var(--space-5);
  background: var(--bg-canvas);
  border-bottom: 1px solid var(--border-subtle);
}
.brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-primary);
}
.brand__mark {
  width: var(--space-5);
  height: var(--space-5);
  border-radius: var(--radius-md);
  background: var(--gradient-accent);
}
.brand__text {
  font-size: var(--font-size-base);
  line-height: var(--leading-base);
  font-weight: 700;
}
.landing-nav__links {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.landing-nav__links a {
  padding: var(--space-1) var(--space-2);
  color: var(--text-secondary);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
}
.landing-nav__links a:hover {
  color: var(--text-primary);
  background: var(--bg-subtle);
}
.landing-nav__user {
  max-width: 140px;
  overflow: hidden;
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ---------- Hero ---------- */
.hero,
.section {
  max-width: var(--container-md);
  margin: 0 auto;
  padding: var(--space-8) var(--space-5);
}
.hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(420px, 0.85fr);
  gap: var(--space-6);
  align-items: center;
}
.hero__eyebrow,
.section__head span,
.final-cta__copy span {
  color: var(--accent-text);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}
.hero h1 {
  max-width: 640px;
  margin-top: var(--space-3);
  font-size: clamp(var(--font-size-2xl), 4vw, var(--font-size-3xl));
  line-height: var(--leading-3xl);
  letter-spacing: -0.02em;
}
.hero__sub {
  max-width: 560px;
  margin-top: var(--space-4);
  color: var(--text-secondary);
  font-size: var(--font-size-md);
  line-height: var(--leading-md);
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
  max-width: 560px;
}
.hero__metrics div {
  padding: var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  background: var(--bg-subtle);
}
.hero__metrics b {
  display: block;
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: var(--font-size-lg);
  line-height: var(--leading-lg);
}
.hero__metrics span {
  display: block;
  margin-top: var(--space-1);
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
}
.hero-visual {
  position: relative;
}
.hero-visual__image {
  width: 100%;
  display: block;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  background: var(--bg-subtle);
  box-shadow: var(--shadow-lg);
}
.hero-visual__caption {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-top: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
}
.hero-visual__caption b {
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
}
.hero-visual__caption span {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  text-align: right;
}

/* ---------- 区块通用 ---------- */
.section {
  border-top: 1px solid var(--border-subtle);
}
.section__head h2 {
  max-width: 640px;
  margin-top: var(--space-2);
  font-size: clamp(var(--font-size-xl), 3vw, var(--font-size-2xl));
  line-height: var(--leading-2xl);
  letter-spacing: -0.02em;
}
.section__head p {
  max-width: 560px;
  margin-top: var(--space-3);
  color: var(--text-secondary);
  font-size: var(--font-size-base);
  line-height: var(--leading-base);
}

/* ---------- 四步流程 ---------- */
.flow-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-3);
  margin-top: var(--space-6);
}
.flow-card {
  overflow: hidden;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  background: var(--bg-surface);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.flow-card:hover {
  border-color: var(--border-strong);
  box-shadow: var(--shadow-md);
}
.flow-card img {
  width: 100%;
  aspect-ratio: 4 / 3;
  display: block;
  object-fit: cover;
  border-bottom: 1px solid var(--border-subtle);
}
.flow-card__body {
  padding: var(--space-4);
}
.flow-card__label {
  color: var(--accent-text);
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
}
.flow-card h3 {
  margin-top: var(--space-2);
  font-size: var(--font-size-md);
  line-height: var(--leading-md);
}
.flow-card p {
  margin-top: var(--space-2);
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
}

/* ---------- 价值点 ---------- */
.value-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-3);
  margin-top: var(--space-6);
}
.value-card {
  padding: var(--space-5);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  background: var(--bg-surface);
}
.value-card__mark {
  display: block;
  width: var(--space-5);
  height: var(--space-1);
  margin-bottom: var(--space-4);
  border-radius: var(--radius-full);
  background: var(--accent);
}
.value-card h3 {
  font-size: var(--font-size-md);
  line-height: var(--leading-md);
}
.value-card p {
  margin-top: var(--space-2);
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
}

/* ---------- 收尾 CTA ---------- */
.final-cta {
  max-width: var(--container-md);
  margin: 0 auto var(--space-8);
  padding: var(--space-6) var(--space-5);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-5);
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-lg);
  background: var(--accent-soft);
}
.final-cta__copy h2 {
  max-width: 640px;
  margin-top: var(--space-2);
  font-size: clamp(var(--font-size-xl), 3vw, var(--font-size-2xl));
  line-height: var(--leading-2xl);
  letter-spacing: -0.02em;
}
.final-cta__copy p {
  margin-top: var(--space-2);
  color: var(--text-secondary);
  font-size: var(--font-size-base);
  line-height: var(--leading-base);
}
.final-cta__actions {
  display: flex;
  gap: var(--space-3);
  flex-shrink: 0;
}

/* ---------- 页脚 ---------- */
.landing-footer {
  max-width: var(--container-md);
  margin: 0 auto;
  padding: var(--space-5);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  border-top: 1px solid var(--border-subtle);
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
}

/* ---------- 响应式 ---------- */
@media (max-width: 920px) {
  .hero {
    grid-template-columns: 1fr;
  }
  .flow-grid,
  .value-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .final-cta {
    flex-direction: column;
    align-items: flex-start;
  }
  .final-cta__actions {
    flex-wrap: wrap;
  }
}
@media (max-width: 640px) {
  .landing-nav__links a[href^='#'] {
    display: none;
  }
  .hero__metrics,
  .flow-grid,
  .value-grid {
    grid-template-columns: 1fr;
  }
  .hero-visual__caption {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-1);
  }
  .hero-visual__caption span {
    text-align: left;
  }
}
</style>
