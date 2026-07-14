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

@media (max-width: 640px) {
  .home__title { font-size: var(--font-size-2xl); }
  .home__recent-item { flex-direction: column; align-items: flex-start; }
}
</style>
