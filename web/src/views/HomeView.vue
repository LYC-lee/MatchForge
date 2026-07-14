<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useProcureStore } from '@/stores/procure'
import { useHistory } from '@/composables/useHistory'
import QueryInput from '@/components/procure/QueryInput.vue'

const router = useRouter()
const route = useRoute()
const store = useProcureStore()
const { list } = useHistory()

const initial = computed(() => (route.query.q as string) || '')
const recent = computed(() => list().slice(0, 3))

const features = [
  { title: '自然语言寻源', desc: '输入型号或一句话需求,AI 自动解析规格参数,缺失字段标黄提示。' },
  { title: '替代料推荐', desc: '知识图谱 + 规格交叉比对,L1-L5 分级、置信度与人工核验状态透明。' },
  { title: '供应商匹配', desc: '向量检索匹配供应能力,多选供应商,按匹配度排序。' },
  { title: '询价单生成', desc: 'LLM 流式生成可编辑 RFQ,固定模板兜底,线索分级评估。' },
]

const steps = [
  { n: '01', title: '描述需求', desc: '输入缺货型号或自然语言采购需求' },
  { n: '02', title: 'AI 解析匹配', desc: '6 智能体解析规格、推荐替代料、匹配供应商' },
  { n: '03', title: '生成询价单', desc: '编辑 RFQ、标记发送、获取线索分级' },
]

function onSubmit(query: string) {
  const id = `p-${Date.now()}`
  store.startProcure(query)
  router.push(`/procure/${id}`)
}

function reuse(q: string) {
  router.push(`/?q=${encodeURIComponent(q)}`)
}
</script>

<template>
  <div class="home">
    <section class="home__hero">
      <div class="home__badge">AI 元器件替代料寻源 · Spike</div>
      <h1 class="home__title">缺货了?让 AI 帮你找<b>可靠替代料</b></h1>
      <p class="home__sub">
        输入型号或自然语言采购需求,AI 解析规格、推荐替代料、匹配供应商能力、生成可编辑询价单。
      </p>
      <QueryInput :initial="initial" @submit="onSubmit" />
    </section>

    <section class="home__section">
      <h2 class="home__section-title">核心能力</h2>
      <div class="home__features">
        <div v-for="f in features" :key="f.title" class="feature-card">
          <span class="feature-card__dot" />
          <h3 class="feature-card__title">{{ f.title }}</h3>
          <p class="feature-card__desc">{{ f.desc }}</p>
        </div>
      </div>
    </section>

    <section class="home__section">
      <h2 class="home__section-title">三步完成寻源</h2>
      <div class="home__steps">
        <div v-for="(s, i) in steps" :key="s.n" class="step-card">
          <span class="step-card__n">{{ s.n }}</span>
          <h3 class="step-card__title">{{ s.title }}</h3>
          <p class="step-card__desc">{{ s.desc }}</p>
          <span v-if="i < steps.length - 1" class="step-card__arrow">→</span>
        </div>
      </div>
    </section>

    <section v-if="recent.length" class="home__recent">
      <h3 class="home__recent-title">最近寻源</h3>
      <div class="home__recent-list">
        <button
          v-for="r in recent"
          :key="r.id"
          class="home__recent-item"
          @click="reuse(r.raw_query)"
        >
          <span class="home__recent-query">{{ r.raw_query }}</span>
          <span class="home__recent-meta">
            {{ r.created_at.slice(0, 10) }} · {{ r.state.alternatives?.length || 0 }} 个替代料
          </span>
        </button>
      </div>
    </section>

    <section class="home__disclaimer">
      <p>
        <b>声明:</b>本平台为寻源辅助工具,替代料推荐仅供参考,最终可替代性须由工程师确认;
        供应商匹配为供应能力匹配,非实时库存/报价/交期承诺。首期不提供交易、支付与物流。
      </p>
    </section>
  </div>
</template>

<style scoped>
.home {
  max-width: 1200px;
  margin: 0 auto;
  padding: var(--space-8) var(--space-5) var(--space-6);
}
.home__hero { text-align: center; margin-bottom: var(--space-8); }
.home__badge {
  display: inline-block;
  font-size: var(--font-size-xs);
  color: var(--accent-hover);
  background: var(--accent-soft);
  border: 1px solid var(--accent-border);
  padding: 4px 12px;
  border-radius: var(--radius-full);
  margin-bottom: var(--space-4);
}
.home__title {
  font-size: var(--font-size-3xl);
  font-weight: 700;
  line-height: 1.2;
  margin-bottom: var(--space-3);
  letter-spacing: -0.02em;
}
.home__title b {
  background: var(--gradient-accent);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.home__sub {
  font-size: var(--font-size-md);
  color: var(--text-secondary);
  max-width: 560px;
  margin: 0 auto var(--space-6);
}

.home__section { margin-bottom: var(--space-8); }
.home__section-title {
  font-size: var(--font-size-lg);
  font-weight: 600;
  margin-bottom: var(--space-4);
  color: var(--text-primary);
}

.home__features {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: var(--space-3);
}
.feature-card {
  background: var(--bg-2);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  transition: border-color var(--transition-base);
}
.feature-card:hover { border-color: var(--accent-border); }
.feature-card__dot {
  display: block;
  width: 28px;
  height: 4px;
  border-radius: var(--radius-full);
  background: var(--gradient-accent);
  margin-bottom: var(--space-3);
}
.feature-card__title { font-size: var(--font-size-md); font-weight: 600; margin-bottom: var(--space-2); }
.feature-card__desc { font-size: var(--font-size-sm); color: var(--text-tertiary); line-height: 1.6; }

.home__steps {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-3);
}
.step-card {
  position: relative;
  background: var(--bg-2);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
}
.step-card__n {
  font-size: var(--font-size-xl);
  font-weight: 700;
  font-family: var(--font-mono);
  color: var(--accent);
  background: var(--gradient-accent);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.step-card__title { font-size: var(--font-size-md); font-weight: 600; margin: var(--space-2) 0; }
.step-card__desc { font-size: var(--font-size-sm); color: var(--text-tertiary); line-height: 1.6; }
.step-card__arrow {
  position: absolute;
  right: -10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-tertiary);
  font-size: 18px;
  z-index: 1;
}

.home__recent { margin-bottom: var(--space-6); }
.home__recent-title { font-size: var(--font-size-sm); color: var(--text-tertiary); margin-bottom: var(--space-3); text-transform: uppercase; letter-spacing: 0.04em; }
.home__recent-list { display: flex; flex-direction: column; gap: var(--space-2); max-width: 720px; margin: 0 auto; }
.home__recent-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--bg-2);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
  text-align: left;
}
.home__recent-item:hover { border-color: var(--accent-border); background: var(--bg-3); }
.home__recent-query { font-size: var(--font-size-sm); color: var(--text-primary); }
.home__recent-meta { font-size: var(--font-size-xs); color: var(--text-tertiary); flex-shrink: 0; }

.home__disclaimer {
  max-width: 720px;
  margin: 0 auto;
  padding: var(--space-4);
  background: var(--bg-2);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
}
.home__disclaimer p { font-size: var(--font-size-xs); color: var(--text-tertiary); line-height: 1.7; }
.home__disclaimer b { color: var(--text-secondary); }

@media (max-width: 768px) {
  .home__steps { grid-template-columns: 1fr; }
  .step-card__arrow { display: none; }
}
@media (max-width: 640px) {
  .home__title { font-size: var(--font-size-2xl); }
  .home__recent-item { flex-direction: column; align-items: flex-start; }
}
</style>
