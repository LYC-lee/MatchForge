<script setup lang="ts">
import { ref } from 'vue'
import type { Citation } from '@/types/procure'

/**
 * 引用回显 (issue #27, 契约 C2)
 * 角标 chips [1][2][3]…,点击展开/收起详情卡;同时只展开一个。
 */
defineProps<{
  citations: Citation[]
}>()

const expandedIndex = ref<number | null>(null)

function toggle(i: number) {
  expandedIndex.value = expandedIndex.value === i ? null : i
}

/** doc 手册类型映射中文,未知值原样展示 */
function docLabel(doc: string): string {
  if (doc === 'product') return '产品手册'
  if (doc === 'business') return '业务知识'
  return doc
}

function scoreLabel(score: number): string {
  if (typeof score !== 'number' || Number.isNaN(score)) return '—'
  return `${Math.round(score * 100)}%`
}
</script>

<template>
  <div v-if="citations.length" class="citations">
    <div class="citations__chips" role="list" aria-label="引用来源">
      <button
        v-for="(c, i) in citations"
        :key="c.chunk_uid || i"
        type="button"
        class="citations__chip"
        :class="{ 'citations__chip--active': expandedIndex === i }"
        :title="docLabel(c.doc)"
        @click="toggle(i)"
      >
        [{{ i + 1 }}]
      </button>
    </div>

    <div v-if="expandedIndex !== null && citations[expandedIndex]" class="citations__detail">
      <div class="citations__meta">
        <span class="citations__doc">{{ docLabel(citations[expandedIndex].doc) }}</span>
        <span class="citations__score">相关度 {{ scoreLabel(citations[expandedIndex].score) }}</span>
        <span v-if="citations[expandedIndex].language" class="citations__lang">
          {{ citations[expandedIndex].language }}
        </span>
      </div>
      <p v-if="citations[expandedIndex].excerpt" class="citations__excerpt">
        {{ citations[expandedIndex].excerpt }}
      </p>
      <div class="citations__uid mono">{{ citations[expandedIndex].chunk_uid }}</div>
    </div>
  </div>
</template>

<style scoped>
.citations {
  margin-top: var(--space-2);
}

.citations__chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.citations__chip {
  padding: 1px 6px;
  font-size: var(--font-size-xs);
  font-family: var(--font-mono);
  line-height: 1.6;
  color: var(--text-tertiary);
  background: transparent;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.citations__chip:hover {
  color: var(--accent-hover);
  border-color: var(--accent-border);
  background: var(--accent-soft);
}
.citations__chip--active {
  color: var(--accent-hover);
  border-color: var(--accent-border);
  background: var(--accent-soft);
}

.citations__detail {
  margin-top: var(--space-2);
  padding: var(--space-3);
  background: var(--bg-1);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  animation: citeFadeIn 0.15s ease;
}
@keyframes citeFadeIn {
  from { opacity: 0; transform: translateY(2px); }
  to { opacity: 1; transform: translateY(0); }
}

.citations__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
  font-size: var(--font-size-xs);
}
.citations__doc {
  padding: 1px 6px;
  color: var(--text-secondary);
  background: var(--bg-3);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
}
.citations__score {
  color: var(--text-tertiary);
  font-family: var(--font-mono);
}
.citations__lang {
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  text-transform: uppercase;
}

.citations__excerpt {
  font-size: var(--font-size-sm);
  line-height: 1.7;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  margin-bottom: var(--space-2);
}

.citations__uid {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  opacity: 0.8;
  word-break: break-all;
}
.mono {
  font-family: var(--font-mono);
}
</style>
