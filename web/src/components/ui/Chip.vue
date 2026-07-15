<script setup lang="ts">
defineProps<{ label: string }>()
const emit = defineEmits<{ (e: 'click'): void }>()
</script>

<template>
  <button class="chip" @click="emit('click')">{{ label }}</button>
</template>

<style scoped>
.chip {
  display: inline-flex;
  align-items: center;
  height: 30px;
  padding: 0 12px;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  background: var(--bg-2);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-full);
  transition: all var(--transition-fast);
}
.chip:hover {
  color: var(--accent-hover);
  border-color: var(--accent-border);
  background: var(--accent-soft);
}
</style>
