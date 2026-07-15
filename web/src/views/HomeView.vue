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
  router.push(`/app?q=${encodeURIComponent(q)}`)
}
</script>

<template>
  <div class="home">
    <section class="workspace-hero">
      <div class="workspace-hero__main">
        <div class="home__badge">AI 元器件替代料寻源 · Spike</div>
        <h1 class="home__title">缺货、停产、降本，都从一个采购请求开始</h1>
        <p class="home__sub">
          按 Linear 的工作区结构拆分寻源流程：输入需求、确认规格、查看替代、匹配供应商、生成 RFQ。
        </p>
        <QueryInput :initial="initial" @submit="onSubmit" />
      </div>

      <aside class="workspace-hero__side">
        <div class="side-card side-card--active">
          <span class="side-card__k">当前模式</span>
          <b>Spike Demo</b>
          <p>Mock SSE 已开启，可独立演示完整流程。</p>
        </div>
        <div class="side-card">
          <span class="side-card__k">事实边界</span>
          <b>能力匹配</b>
          <p>不展示“确认有货”，所有供应商结果最终以询价回复为准。</p>
        </div>
        <div class="side-card">
          <span class="side-card__k">首期留白</span>
          <b>运营审核 / 供应商入驻</b>
          <p>结构已预留，MVP 阶段接入真实后台。</p>
        </div>
      </aside>
    </section>

    <section class="home__grid">
      <div class="home__panel home__panel--wide">
        <div class="panel-head">
          <span>Workflow</span>
          <h2>三步完成寻源</h2>
        </div>
        <div class="home__steps">
          <div v-for="s in steps" :key="s.n" class="step-card">
            <span class="step-card__n">{{ s.n }}</span>
            <div>
              <h3 class="step-card__title">{{ s.title }}</h3>
              <p class="step-card__desc">{{ s.desc }}</p>
            </div>
          </div>
        </div>
      </div>

      <div class="home__panel">
        <div class="panel-head">
          <span>Modules</span>
          <h2>核心能力</h2>
        </div>
        <div class="home__features">
          <div v-for="f in features" :key="f.title" class="feature-card">
            <span class="feature-card__dot" />
            <h3 class="feature-card__title">{{ f.title }}</h3>
            <p class="feature-card__desc">{{ f.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <section class="home__recent">
      <div class="panel-head">
        <span>Recents</span>
        <h2>最近寻源</h2>
      </div>
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
        <div v-if="!recent.length" class="home__recent-empty">
          还没有寻源记录，提交一个型号后这里会显示最近工作流。
        </div>
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
  max-width: 1180px;
  margin: 0 auto;
  padding: var(--space-6) var(--space-5) var(--space-6);
}
.workspace-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) 320px;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}
.workspace-hero__main,
.workspace-hero__side,
.home__panel,
.home__recent,
.home__disclaimer {
  border: 1px solid var(--border-default);
  border-radius: 14px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.045), rgba(255, 255, 255, 0.015)),
    #10131b;
}
.workspace-hero__main {
  padding: clamp(28px, 5vw, 56px);
  box-shadow: 0 18px 60px rgba(0, 0, 0, 0.24);
}
.workspace-hero__side {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
}
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
  max-width: 720px;
  color: #f4f7ff;
  font-size: clamp(34px, 4.8vw, 54px);
  font-weight: 700;
  line-height: 1.08;
  margin-bottom: var(--space-4);
  letter-spacing: -0.05em;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.04);
}
.home__sub {
  font-size: var(--font-size-md);
  color: #c2c7d4;
  max-width: 660px;
  margin-bottom: var(--space-6);
}

.side-card {
  padding: var(--space-4);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.035);
}
.side-card--active {
  border-color: var(--accent-border);
  background:
    linear-gradient(180deg, rgba(99, 102, 241, 0.18), rgba(99, 102, 241, 0.06)),
    rgba(255, 255, 255, 0.04);
}
.side-card__k,
.panel-head span {
  display: block;
  color: #8d95aa;
  font-size: var(--font-size-xs);
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.side-card b {
  display: block;
  margin-top: var(--space-1);
  color: #f0f3fa;
  font-size: var(--font-size-sm);
}
.side-card p {
  margin-top: var(--space-2);
  color: #aeb5c4;
  font-size: var(--font-size-xs);
  line-height: 1.6;
}
.home__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(380px, 0.72fr);
  gap: var(--space-4);
  margin-bottom: var(--space-5);
  align-items: start;
}
.home__panel {
  padding: var(--space-5);
}
.panel-head {
  margin-bottom: var(--space-4);
}
.panel-head h2 {
  margin-top: var(--space-1);
  color: #f1f4fb;
  font-size: var(--font-size-lg);
}

.home__features {
  display: grid;
  gap: var(--space-2);
}
.feature-card {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
  gap: var(--space-3);
  padding: var(--space-4);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.032);
  transition: border-color var(--transition-base), background var(--transition-base);
}
.feature-card:hover {
  border-color: var(--accent-border);
  background: rgba(255, 255, 255, 0.05);
}
.feature-card__dot {
  display: block;
  width: 18px;
  height: 18px;
  border-radius: var(--radius-full);
  background: var(--gradient-accent);
  margin-top: 2px;
  grid-row: 1 / span 2;
}
.feature-card__title {
  grid-column: 2;
  color: #edf1f8;
  font-size: var(--font-size-md);
  font-weight: 600;
  margin-bottom: 0;
}
.feature-card__desc {
  grid-column: 2;
  min-width: 0;
  font-size: var(--font-size-sm);
  color: #aeb5c4;
  line-height: 1.6;
  word-break: normal;
  overflow-wrap: break-word;
}

.home__steps {
  display: grid;
  gap: var(--space-2);
}
.step-card {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr);
  gap: var(--space-3);
  align-items: start;
  padding: var(--space-4);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.032);
}
.step-card__n {
  font-size: var(--font-size-lg);
  font-weight: 700;
  font-family: var(--font-mono);
  color: var(--accent);
  background: var(--gradient-accent);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.step-card__title {
  color: #edf1f8;
  font-size: var(--font-size-md);
  font-weight: 600;
  margin: var(--space-2) 0;
}
.step-card__desc {
  font-size: var(--font-size-sm);
  color: #aeb5c4;
  line-height: 1.6;
}

.home__recent {
  margin-bottom: var(--space-4);
  padding: var(--space-5);
}
.home__recent-list { display: flex; flex-direction: column; gap: var(--space-2); }
.home__recent-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
  text-align: left;
}
.home__recent-item:hover { border-color: var(--accent-border); background: var(--bg-3); }
.home__recent-query { font-size: var(--font-size-sm); color: var(--text-primary); }
.home__recent-meta { font-size: var(--font-size-xs); color: var(--text-tertiary); flex-shrink: 0; }
.home__recent-empty {
  padding: var(--space-4);
  color: #aeb5c4;
  border: 1px dashed var(--border-default);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
}

.home__disclaimer {
  padding: var(--space-4);
}
.home__disclaimer p { font-size: var(--font-size-xs); color: #aeb5c4; line-height: 1.7; }
.home__disclaimer b { color: #f0f3fa; }

@media (max-width: 768px) {
  .workspace-hero,
  .home__grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 640px) {
  .home__title { font-size: var(--font-size-2xl); }
  .home__recent-item { flex-direction: column; align-items: flex-start; }
}
</style>
