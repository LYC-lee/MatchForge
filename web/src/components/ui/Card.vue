<script setup lang="ts">
withDefaults(defineProps<{
  title?: string
  subtitle?: string
  /** 浮起阴影（下拉卡片、强调卡片）；默认仅靠 1px 描边分层 */
  elevated?: boolean
  /** 紧凑模式：缩小内边距（密集列表/工作台） */
  dense?: boolean
}>(), {
  elevated: false,
  dense: false,
})
</script>

<template>
  <section class="card" :class="{ 'card--elevated': elevated, 'card--dense': dense }">
    <header v-if="title || $slots.header || $slots.actions" class="card__head">
      <slot name="header">
        <div class="card__titles">
          <h3 class="card__title">{{ title }}</h3>
          <p v-if="subtitle" class="card__subtitle">{{ subtitle }}</p>
        </div>
      </slot>
      <div v-if="$slots.actions" class="card__actions"><slot name="actions" /></div>
    </header>
    <div class="card__body"><slot /></div>
  </section>
</template>

<style scoped>
.card {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.card--elevated {
  background: var(--bg-elevated);
  box-shadow: var(--shadow-md);
}
.card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-subtle);
}
.card--dense .card__head {
  padding: var(--space-3) var(--space-4);
}
.card__title {
  font-size: var(--font-size-md);
  line-height: var(--leading-md);
  font-weight: 600;
  color: var(--text-primary);
}
.card__subtitle {
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  color: var(--text-tertiary);
  margin-top: 2px;
}
.card__actions {
  display: flex;
  gap: var(--space-2);
  flex-shrink: 0;
}
.card__body {
  padding: var(--space-5);
}
.card--dense .card__body {
  padding: var(--space-4);
}
.card__body:empty {
  display: none;
}
</style>
