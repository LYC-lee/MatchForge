<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useHistory, type HistoryRecord } from '@/composables/useHistory'
import Card from '@/components/ui/Card.vue'
import AppButton from '@/components/ui/AppButton.vue'
import Tag from '@/components/ui/Tag.vue'

const router = useRouter()
const { list, remove } = useHistory()
const records = ref<HistoryRecord[]>(list())
const expanded = ref<Set<string>>(new Set())

function toggle(id: string) {
  const s = new Set(expanded.value)
  if (s.has(id)) {
    s.delete(id)
  } else {
    s.add(id)
  }
  expanded.value = s
}

function reuse(q: string) {
  router.push(`/?q=${encodeURIComponent(q)}`)
}

function del(id: string) {
  remove(id)
  records.value = list()
}

function gradeType(g: string): 'success' | 'warning' | 'danger' {
  if (g === 'A' || g === 'B') return 'success'
  if (g === 'C') return 'warning'
  return 'danger'
}
</script>

<template>
  <div class="history">
    <div class="history__head">
      <h1>历史记录</h1>
      <p class="history__sub">寻源与询价单记录(本地存储于浏览器)</p>
    </div>

    <div v-if="!records.length" class="history__empty">
      <div class="history__empty-icon">⊘</div>
      <p class="history__empty-title">还没有寻源记录</p>
      <p class="history__empty-desc">去首页试试</p>
      <AppButton @click="router.push('/')">开始寻源</AppButton>
    </div>

    <div v-else class="history__list">
      <Card v-for="r in records" :key="r.id">
        <template #header>
          <div class="rec__head" @click="toggle(r.id)">
            <span class="rec__query">{{ r.raw_query }}</span>
            <div class="rec__meta">
              <Tag
                v-if="r.state.lead_grade"
                :type="gradeType(r.state.lead_grade.grade)"
                :value="`${r.state.lead_grade.grade} 级`"
              />
              <span v-if="r.rfq_sent" class="rec__sent">RFQ 已发送</span>
              <span class="rec__date">{{ r.created_at.slice(0, 10) }}</span>
              <span class="rec__arrow">{{ expanded.has(r.id) ? '收起' : '展开' }}</span>
            </div>
          </div>
        </template>

        <div v-if="expanded.has(r.id)" class="rec__detail">
          <div class="rec__row">
            <span>替代料</span>
            <b>{{ r.state.alternatives?.length || 0 }} 个</b>
          </div>
          <div class="rec__row">
            <span>供应商</span>
            <b>{{ r.state.matched_suppliers?.length || 0 }} 个</b>
          </div>
          <div v-if="r.state.alternatives?.length" class="rec__alts">
            <span class="rec__alts-label">替代型号:</span>
            <div class="rec__alts-tags">
              <Tag
                v-for="a in r.state.alternatives"
                :key="a.part_name"
                type="level"
                :level="a.level"
                :value="a.part_name"
              />
            </div>
          </div>
          <div v-if="r.state.rfq_doc" class="rec__rfq">
            <span class="rec__rfq-label">RFQ 摘要:</span>
            <pre class="rec__rfq-text">{{ r.state.rfq_doc.slice(0, 200) }}…</pre>
          </div>
          <div class="rec__actions">
            <AppButton variant="secondary" size="sm" @click="reuse(r.raw_query)">复用需求</AppButton>
            <AppButton variant="danger" size="sm" @click="del(r.id)">删除</AppButton>
          </div>
        </div>
      </Card>
    </div>
  </div>
</template>

<style scoped>
.history {
  max-width: 960px;
  margin: 0 auto;
  padding: var(--space-6) var(--space-5);
}
.history__head { margin-bottom: var(--space-5); }
.history__head h1 { font-size: var(--font-size-2xl); font-weight: 700; }
.history__sub { font-size: var(--font-size-sm); color: var(--text-tertiary); margin-top: var(--space-1); }

.history__empty {
  text-align: center;
  padding: var(--space-8) var(--space-4);
}
.history__empty-icon { font-size: 40px; color: var(--text-tertiary); margin-bottom: var(--space-3); }
.history__empty-title { font-size: var(--font-size-lg); font-weight: 600; color: var(--text-secondary); margin-bottom: var(--space-2); }
.history__empty-desc { font-size: var(--font-size-sm); color: var(--text-tertiary); margin-bottom: var(--space-4); }

.history__list { display: flex; flex-direction: column; gap: var(--space-3); }

.rec__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  cursor: pointer;
  width: 100%;
}
.rec__query { font-size: var(--font-size-sm); color: var(--text-primary); font-weight: 500; }
.rec__meta { display: flex; align-items: center; gap: var(--space-3); flex-shrink: 0; }
.rec__sent { font-size: var(--font-size-xs); color: var(--success); }
.rec__date { font-size: var(--font-size-xs); color: var(--text-tertiary); font-family: var(--font-mono); }
.rec__arrow { font-size: var(--font-size-xs); color: var(--accent-hover); }

.rec__detail { display: flex; flex-direction: column; gap: var(--space-3); }
.rec__row { display: flex; justify-content: space-between; font-size: var(--font-size-sm); }
.rec__row span { color: var(--text-tertiary); }
.rec__row b { color: var(--text-primary); }
.rec__alts { display: flex; flex-direction: column; gap: var(--space-2); }
.rec__alts-label { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.rec__alts-tags { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.rec__rfq { display: flex; flex-direction: column; gap: var(--space-2); }
.rec__rfq-label { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.rec__rfq-text {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  background: var(--bg-3);
  padding: var(--space-3);
  border-radius: var(--radius-sm);
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 120px;
  overflow: hidden;
}
.rec__actions { display: flex; gap: var(--space-2); padding-top: var(--space-2); border-top: 1px solid var(--border-subtle); }

@media (max-width: 640px) {
  .rec__head { flex-direction: column; align-items: flex-start; }
  .rec__meta { flex-wrap: wrap; }
}
</style>
