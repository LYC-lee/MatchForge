<script setup lang="ts">
withDefaults(defineProps<{
  label: string
  /** 选中态（筛选 chip 场景） */
  active?: boolean
  disabled?: boolean
}>(), {
  active: false,
  disabled: false,
})
const emit = defineEmits<{ (e: 'click'): void }>()
</script>

<template>
  <button
    type="button"
    class="chip"
    :class="{ 'chip--active': active }"
    :disabled="disabled"
    @click="emit('click')"
  >
    {{ label }}
  </button>
</template>

<style scoped>
.chip {
  display: inline-flex;
  align-items: center;
  height: 30px;
  padding: 0 var(--space-3);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  color: var(--text-secondary);
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-full);
  transition: background-color var(--transition-fast), border-color var(--transition-fast),
    color var(--transition-fast);
}
.chip:hover:not(:disabled) {
  color: var(--text-primary);
  border-color: var(--border-strong);
  background: var(--bg-subtle);
}
.chip--active,
.chip--active:hover:not(:disabled) {
  color: var(--accent-text);
  border-color: var(--accent-border);
  background: var(--accent-soft);
}
.chip:disabled {
  opacity: 0.45;
}
</style>
