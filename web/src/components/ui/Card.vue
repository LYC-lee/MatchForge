<script setup lang="ts">
withDefaults(defineProps<{ title?: string; subtitle?: string; elevated?: boolean }>(), {
  elevated: false,
})
</script>

<template>
  <section class="card" :class="{ 'card--elevated': elevated }">
    <header v-if="title || $slots.header" class="card__head">
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
  background: var(--bg-2);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.card--elevated { box-shadow: var(--shadow-md); }
.card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-subtle);
}
.card__title { font-size: var(--font-size-md); font-weight: 600; }
.card__subtitle { font-size: var(--font-size-sm); color: var(--text-tertiary); margin-top: 2px; }
.card__actions { display: flex; gap: var(--space-2); flex-shrink: 0; }
.card__body { padding: var(--space-5); }
.card__body:empty { display: none; }
</style>
