<script setup lang="ts">
import type { LeadGrade } from '@/types/procure'
import Tag from '@/components/ui/Tag.vue'

defineProps<{
  grade: LeadGrade
}>()
</script>

<template>
  <div class="grade-card">
    <div class="grade-card__head">
      <span class="grade-card__label">线索分级</span>
    </div>
    <div class="grade-card__body">
      <div class="grade-card__main">
        <span class="grade-letter" :class="`grade-${grade.grade}`">
          {{ grade.grade }}
        </span>
        <span class="grade-score">{{ grade.score }} 分</span>
        <Tag
          :type="grade.grade === 'A' || grade.grade === 'B' ? 'success' : grade.grade === 'C' ? 'warning' : 'danger'"
          :value="`${grade.grade} 级线索`"
        />
      </div>
      <ul class="grade-card__reasons">
        <li v-for="(r, i) in grade.reasons" :key="i">{{ r }}</li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.grade-card {
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: var(--bg-2);
}
.grade-card__head {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-subtle);
  font-size: var(--font-size-sm);
  font-weight: 600;
}
.grade-card__body { padding: var(--space-4); }
.grade-card__main {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.grade-letter {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--font-size-xl);
  font-weight: 700;
  border-radius: var(--radius-md);
  font-family: var(--font-mono);
}
.grade-A, .grade-B { color: var(--success); background: var(--success-soft); }
.grade-C { color: var(--warning); background: var(--warning-soft); }
.grade-D { color: var(--danger); background: var(--danger-soft); }
.grade-score {
  font-size: var(--font-size-md);
  color: var(--text-secondary);
  font-family: var(--font-mono);
}
.grade-card__reasons { display: flex; flex-direction: column; gap: var(--space-2); }
.grade-card__reasons li {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  padding-left: var(--space-4);
  position: relative;
}
.grade-card__reasons li::before {
  content: '·';
  position: absolute;
  left: var(--space-2);
  color: var(--text-tertiary);
}
</style>
